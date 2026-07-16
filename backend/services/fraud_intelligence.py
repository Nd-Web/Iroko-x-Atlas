"""
services/fraud_intelligence.py — Multi-Source Fraud Alert Pipeline for Iroko AI.
==================================================================================
Implements the BrandIntel pattern: collect from multiple sources → noise filter →
LLM triage → graph correlation → verdict.

Pipeline stages
---------------
1. ``collect_all_fraud_signals`` — merges static FRAUD_SIGNALS + live Bright Data hits,
   normalises both to a common schema.
2. ``filter_noise``             — removes generic signals (no named entity), deduplicates
   by URL and character-set overlap, culls entries older than 90 days, caps at 20.
3. ``run_llm_triage``           — rates each surviving signal via Azure OpenAI; adds an
   ``llm_triage`` field ({relevance, urgency, action}) to each dict.
4. ``generate_fraud_alert``     — orchestrates the full pipeline, runs graph correlation
   via ``signal_graph_service``, computes an overall verdict via ``verdict_engine``,
   and logs the result to the hash-chained audit trail.

Design constraints
------------------
- All public methods are ``async``.
- Bright Data import is deferred and wrapped in try/except — absence of the client
  only skips live signals, it does not crash the pipeline.
- LLM errors are caught per-signal; the field is set to ``None`` so the rest of the
  pipeline continues.
- Character overlap ratio for deduplication uses the Jaccard coefficient on character
  sets as specified: ``len(set(a) & set(b)) / len(set(a) | set(b)) >= 0.8``.

Usage::

    from services.fraud_intelligence import fraud_intel_service
    from models.database import SessionLocal

    db  = SessionLocal()
    try:
        alert = await fraud_intel_service.generate_fraud_alert(db)
        print(alert["overall_verdict"], alert["alert_count"])
    finally:
        db.close()
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Known entities for noise filter ──────────────────────────────────────────

_KNOWN_ENTITIES: list[str] = [
    "Kuda", "Carbon", "Moniepoint", "Fairmoney", "OPay", "PalmPay", "Flutterwave",
    "Interswitch", "NIBSS", "CRC", "CBN", "SEC", "NDPC", "EFCC",
    "Zumax", "Optimus", "Kano", "Lagos", "Abuja", "Nigeria",
]
_ENTITY_PATTERNS = [re.compile(r"\b" + re.escape(e) + r"\b", re.IGNORECASE) for e in _KNOWN_ENTITIES]
_REGULATION_PATTERN = re.compile(r"CBN-\w+-\d+|SEC-\d+|Section\s+\d+", re.IGNORECASE)

# Risk level ordering for sorting / capping
_RISK_ORDER: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

# Maximum signals to retain after noise filtering
_MAX_SIGNALS = 20

# Signals older than this are discarded
_MAX_AGE_DAYS = 90


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _stable_id(title: str, url: Optional[str]) -> str:
    """Generate a stable dedup-friendly ID from title + url."""
    raw = (title + (url or "")).strip()
    return "frd_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _has_named_entity(text: str) -> bool:
    """Return True if ``text`` contains at least one known company/regulation entity."""
    for pattern in _ENTITY_PATTERNS:
        if pattern.search(text):
            return True
    if _REGULATION_PATTERN.search(text):
        return True
    return False


def _char_overlap_ratio(a: str, b: str) -> float:
    """
    Jaccard coefficient on character sets (case-insensitive).

        ratio = |set(a) ∩ set(b)| / |set(a) ∪ set(b)|

    Returns 0.0 when both strings are empty.
    """
    sa = set(a.lower())
    sb = set(b.lower())
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601-ish date string; return None on failure."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19], fmt[:len(fmt)])
        except ValueError:
            continue
    return None


def _normalise_static(entry: dict) -> dict:
    """Normalise a FRAUD_SIGNALS entry to the common schema."""
    return {
        "id":          entry.get("id") or _stable_id(entry.get("title", ""), None),
        "title":       entry.get("title", ""),
        "description": entry.get("detail", entry.get("description", "")),
        "risk_level":  entry.get("risk", entry.get("risk_level", "LOW")).upper(),
        "source":      "static",
        "url":         entry.get("url") or entry.get("source_url") or None,
        "detected_at": entry.get("detected_at") or _now_iso(),
    }


def _normalise_web(entry: dict) -> dict:
    """Normalise a fetch_fraud_signals() entry to the common schema."""
    return {
        "id":          _stable_id(entry.get("title", ""), entry.get("url")),
        "title":       entry.get("title", ""),
        "description": entry.get("snippet", entry.get("description", "")),
        "risk_level":  entry.get("risk_level", "LOW").upper(),
        "source":      "web",
        "url":         entry.get("url") or None,
        "detected_at": entry.get("fetched_at") or entry.get("detected_at") or _now_iso(),
    }


# ── Service ───────────────────────────────────────────────────────────────────


class FraudIntelligenceService:
    """
    Multi-source fraud alert pipeline for Iroko AI.

    Collects from static corpus and live web intelligence, filters noise,
    triages with an LLM, correlates via the signal knowledge graph, and
    produces a structured fraud alert with an overall compliance verdict.
    """

    # ── 1. Collect and normalise ──────────────────────────────────────────────

    async def collect_all_fraud_signals(self) -> list[dict]:
        """
        Merge static ``FRAUD_SIGNALS`` with live Bright Data web signals.

        Both sources are normalised to a common schema::

            {
                "id":          str,            # stable hash-based ID
                "title":       str,
                "description": str,
                "risk_level":  "HIGH"|"MEDIUM"|"LOW",
                "source":      "static"|"web",
                "url":         str | None,
                "detected_at": str,            # ISO-8601 UTC
            }

        Live signals are fetched with a graceful fallback: if ``bright_data_client``
        is unavailable or the call fails, only static signals are returned.

        Returns
        -------
        list[dict]
            Combined, normalised list (static first, then web).
        """
        # ── Static signals ────────────────────────────────────────────────────
        try:
            from services.fraud_service import FRAUD_SIGNALS
            static = [_normalise_static(s) for s in FRAUD_SIGNALS]
        except Exception as exc:
            logger.warning("[FraudIntel] Could not import FRAUD_SIGNALS: %s", exc)
            static = []

        # ── Live web signals ──────────────────────────────────────────────────
        web: list[dict] = []
        try:
            from services.brightdata import bright_data_client
            from services.web_intelligence import fetch_fraud_signals
            raw_web = await fetch_fraud_signals(bright_data_client)
            web = [_normalise_web(s) for s in raw_web]
        except Exception as exc:
            logger.warning("[FraudIntel] Live fraud signals unavailable: %s", exc)

        combined = static + web
        logger.info(
            "[FraudIntel] collect_all_fraud_signals: %d static + %d web = %d total",
            len(static), len(web), len(combined),
        )
        return combined

    # ── 2. Noise filter ───────────────────────────────────────────────────────

    async def filter_noise(self, signals: list[dict]) -> list[dict]:
        """
        Apply three noise-reduction passes and cap results.

        Pass 1 — **Named-entity gate**: discard signals whose ``title`` contains
        no recognisable company name or regulation reference.  Generic headlines
        like "Fraud is on the rise" add no actionable intelligence.

        Pass 2 — **Deduplication**: two signals are considered duplicates when:
          - They share the same non-empty ``url``, OR
          - Their titles have a Jaccard character-set overlap ratio ≥ 0.8.
        The first occurrence is kept; subsequent duplicates are dropped.

        Pass 3 — **Age gate**: signals with a parseable ``detected_at`` timestamp
        older than 90 days are discarded.

        Cap — The surviving list is sorted by risk level (HIGH → MEDIUM → LOW) and
        truncated to ``_MAX_SIGNALS`` (20).

        Parameters
        ----------
        signals : list[dict]
            Normalised signal dicts from ``collect_all_fraud_signals``.

        Returns
        -------
        list[dict]
            Filtered list, at most 20 entries.
        """
        cutoff = datetime.utcnow() - timedelta(days=_MAX_AGE_DAYS)
        filtered: list[dict] = []
        seen_urls: set[str]  = set()
        seen_titles: list[str] = []

        for sig in signals:
            title = sig.get("title", "")
            url   = sig.get("url") or ""

            # Pass 1: named-entity gate
            if not _has_named_entity(title):
                logger.debug("[FraudIntel] filter_noise: dropping generic signal %r", title[:60])
                continue

            # Pass 2a: URL deduplication
            if url and url in seen_urls:
                logger.debug("[FraudIntel] filter_noise: duplicate URL %r", url[:80])
                continue

            # Pass 2b: title character-overlap deduplication
            is_dup = False
            for seen_title in seen_titles:
                if _char_overlap_ratio(title, seen_title) >= 0.8:
                    logger.debug("[FraudIntel] filter_noise: near-duplicate title %r", title[:60])
                    is_dup = True
                    break
            if is_dup:
                continue

            # Pass 3: age gate
            detected_at = _parse_date(sig.get("detected_at"))
            if detected_at is not None and detected_at < cutoff:
                logger.debug("[FraudIntel] filter_noise: stale signal %r", title[:60])
                continue

            # Signal survives — register it
            if url:
                seen_urls.add(url)
            seen_titles.append(title)
            filtered.append(sig)

        # Cap at _MAX_SIGNALS, highest risk first
        filtered.sort(key=lambda s: _RISK_ORDER.get(s.get("risk_level", "LOW"), 2))
        result = filtered[:_MAX_SIGNALS]

        logger.info(
            "[FraudIntel] filter_noise: %d → %d signals after filtering",
            len(signals), len(result),
        )
        return result

    # ── 3. LLM triage ─────────────────────────────────────────────────────────

    async def run_llm_triage(self, signals: list[dict]) -> list[dict]:
        """
        Rate each signal via Azure OpenAI and attach an ``llm_triage`` field.

        The prompt instructs the model to act as a Nigerian telecom fraud analyst
        and return a compact JSON object with three fields:

        - ``relevance`` (float 0–1) — how relevant this signal is to Nigerian telecom fraud.
        - ``urgency``   (str)       — ``"immediate"`` | ``"24h"`` | ``"weekly"``.
        - ``action``    (str)       — one-sentence recommended action.

        LLM errors are caught per-signal; on failure ``llm_triage`` is set to ``None``
        so the pipeline continues unimpeded.

        Parameters
        ----------
        signals : list[dict]
            Filtered signal dicts from ``filter_noise``.

        Returns
        -------
        list[dict]
            Same list with ``llm_triage`` added to every element.
        """
        try:
            from agents.kernel import llm_complete
        except ImportError:
            logger.warning("[FraudIntel] llm_complete unavailable — skipping LLM triage")
            for sig in signals:
                sig["llm_triage"] = None
            return signals

        for sig in signals:
            title       = sig.get("title", "")
            description = sig.get("description", "")
            prompt = (
                "You are a Nigerian telecom fraud analyst. "
                f"Rate this signal: {title} — {description}. "
                'Return JSON only: {"relevance": 0-1, "urgency": "immediate"|"24h"|"weekly", "action": str}'
            )
            try:
                raw = await llm_complete(
                    prompt,
                    max_tokens=200,
                    temperature=0.2,
                    service_id="nano",
                    system_prompt=(
                        "You are a concise fraud risk analyst. "
                        "Respond with valid JSON only — no preamble, no markdown fences."
                    ),
                )
                # Strip markdown fences if the model adds them despite instructions
                clean = re.sub(r"```(?:json)?|```", "", raw).strip()
                triage = json.loads(clean)
                # Validate expected keys are present
                sig["llm_triage"] = {
                    "relevance": float(triage.get("relevance", 0.0)),
                    "urgency":   str(triage.get("urgency", "weekly")),
                    "action":    str(triage.get("action", "")),
                }
            except Exception as exc:
                logger.warning(
                    "[FraudIntel] LLM triage failed for signal %r: %s",
                    title[:60], exc,
                )
                sig["llm_triage"] = None

        logger.info(
            "[FraudIntel] run_llm_triage: triaged %d signals (%d successful)",
            len(signals),
            sum(1 for s in signals if s.get("llm_triage") is not None),
        )
        return signals

    # ── 4. Full pipeline ──────────────────────────────────────────────────────

    async def generate_fraud_alert(self, db: Session) -> dict:
        """
        Execute the full multi-source fraud alert pipeline.

        Stages
        ------
        1. ``collect_all_fraud_signals`` — merge static + live web signals.
        2. ``filter_noise``              — remove noise, deduplicate, age-filter.
        3. ``run_llm_triage``            — LLM relevance + urgency rating.
        4. Graph correlation             — build fraud sub-graph, find compound risks.
        5. Verdict                       — compute overall GO/NO-GO/MONITOR verdict.
        6. Audit log                     — persist result to hash-chained audit trail.

        Parameters
        ----------
        db : Session
            Active SQLAlchemy session (used for the audit trail write).

        Returns
        -------
        dict
            ::

                {
                    "signals":          list[dict],   # filtered + triaged signal list
                    "compound_risks":   list[dict],   # from signal_graph_service
                    "overall_verdict":  str,           # "GO" | "NO-GO" | "MONITOR"
                    "alert_count":      int,
                    "generated_at":     str,           # ISO-8601 UTC
                }
        """
        generated_at = _now_iso()

        # ── Stage 1: collect ──────────────────────────────────────────────────
        raw_signals = await self.collect_all_fraud_signals()

        # ── Stage 2: filter ───────────────────────────────────────────────────
        filtered = await self.filter_noise(raw_signals)

        # ── Stage 3: LLM triage ───────────────────────────────────────────────
        triaged = await self.run_llm_triage(filtered)

        # ── Stage 4: graph correlation (fraud signals only) ───────────────────
        compound_risks: list[dict] = []
        try:
            from services.signal_graph import signal_graph_service
            # Wrap fraud signals in the expected run_all_signals dict shape
            fraud_only_signals = {"fraud": triaged}
            graph = await signal_graph_service.build_signal_graph(fraud_only_signals)
            compound_risks = await signal_graph_service.find_compound_risks(graph, min_signals=2)
        except Exception as exc:
            logger.warning("[FraudIntel] Signal graph correlation failed: %s", exc)

        # ── Stage 5: overall verdict ──────────────────────────────────────────
        high_count    = sum(1 for s in triaged if s.get("risk_level") == "HIGH")
        medium_count  = sum(1 for s in triaged if s.get("risk_level") == "MEDIUM")
        alert_count   = len(triaged)
        signal_strength = len(compound_risks)

        # Confidence is driven by signal volume and risk mix
        confidence: float
        if alert_count == 0:
            confidence = 0.1
        else:
            high_weight = (high_count * 1.0 + medium_count * 0.5) / alert_count
            confidence  = min(0.95, 0.4 + high_weight * 0.55)

        # Compliance result: flag NO-GO when HIGH signals or compound risks exist
        if high_count > 0 or compound_risks:
            compliance_result = {"verdict": "NO-GO", "compliant": False, "violations": [
                f"{high_count} HIGH-risk fraud signal(s) detected"
            ]}
        elif medium_count > 0:
            compliance_result = {"verdict": "MONITOR", "compliant": True, "violations": []}
        else:
            compliance_result = {"verdict": "GO", "compliant": True, "violations": []}

        try:
            from services.verdict_engine import verdict_engine
            overall_verdict = verdict_engine.compute_verdict(
                confidence=confidence,
                compliance_result=compliance_result,
                signal_strength=max(signal_strength, alert_count),
            )
        except Exception as exc:
            logger.warning("[FraudIntel] verdict_engine unavailable: %s", exc)
            overall_verdict = compliance_result["verdict"]

        # ── Stage 6: audit trail ──────────────────────────────────────────────
        try:
            from services.audit_service import AuditService
            summary = (
                f"Fraud alert pipeline: {alert_count} signal(s) after filtering "
                f"({high_count} HIGH, {medium_count} MEDIUM). "
                f"Compound risks: {len(compound_risks)}. Verdict: {overall_verdict}."
            )
            await AuditService.log_decision(
                db,
                agent_name="FraudIntelligenceService",
                action_type="fraud_flag",
                decision_summary=summary,
                confidence=round(confidence, 4),
                verdict=overall_verdict,
            )
        except Exception as exc:
            logger.warning("[FraudIntel] Audit trail write failed: %s", exc)

        logger.info(
            "[FraudIntel] generate_fraud_alert complete: %d signals, %d compound risks, verdict=%s",
            alert_count, len(compound_risks), overall_verdict,
        )

        return {
            "signals":         triaged,
            "compound_risks":  compound_risks,
            "overall_verdict": overall_verdict,
            "alert_count":     alert_count,
            "generated_at":    generated_at,
        }


# ── Module-level singleton ────────────────────────────────────────────────────

fraud_intel_service = FraudIntelligenceService()
"""
Shared ``FraudIntelligenceService`` singleton.

Usage::

    from services.fraud_intelligence import fraud_intel_service
    from models.database import SessionLocal

    db    = SessionLocal()
    alert = await fraud_intel_service.generate_fraud_alert(db)
    db.close()
"""
