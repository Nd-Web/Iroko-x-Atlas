"""
services/ncc_live_rules.py — Live NCC Enforcement Rules Engine for Iroko AI.
=============================================================================
Extends the static NCC regulatory corpus (``regulatory_service.NCC_REGULATIONS``)
with live-scraped enforcement notices and directives from ncc.gov.ng.

Architecture (inspired by RegulaForge's compiler.py + Polaris auditor.py):
  1. ``fetch_latest_ncc_updates``   — Bright Data SERP + Web Unlocker scrape
  2. ``match_update_to_regulation`` — LLM-powered mapping to NCC_REGULATIONS IDs
  3. ``compile_live_enforcement_rules`` — Orchestrator: merge static + live corpus
  4. ``check_decision_against_rules``  — Agent decision compliance gate (GO/NO-GO/MONITOR)

Graceful degradation:
  - If Bright Data API is unavailable → returns static corpus only.
  - If LLM (Azure OpenAI) is unavailable → mock match with keyword fallback.
  - All exceptions are caught per-call and logged; no call crashes the pipeline.

Usage::

    from services.ncc_live_rules import ncc_rules_service

    rules = await ncc_rules_service.compile_live_enforcement_rules()
    check = await ncc_rules_service.check_decision_against_rules(
        "We will delay the quarterly QoS report submission by two weeks."
    )
    # → {"compliant": False, "violations": [...], "verdict": "NO-GO"}
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from services.brightdata import bright_data_client
from services.regulatory_service import NCC_REGULATIONS

# ── LLM import with graceful mock fallback ────────────────────────────────────
try:
    from agents.kernel import llm_complete  # type: ignore
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

    async def llm_complete(prompt: str, **kwargs: Any) -> str:  # type: ignore[misc]
        """Mock stub when Azure OpenAI / kernel is unavailable (local dev / CI)."""
        return ""


logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_NCC_REGULATIONS_PAGE = "https://www.ncc.gov.ng/regulatory/regulations"

# Keyword → regulation IDs — used as LLM fallback for matching
_KEYWORD_REGULATION_MAP: dict[str, list[str]] = {
    "qos": ["NCC-003"],
    "quality of service": ["NCC-003"],
    "dropped call": ["NCC-003"],
    "network performance": ["NCC-003"],
    "sim": ["NCC-004"],
    "sim registration": ["NCC-004"],
    "nin": ["NCC-004"],
    "spectrum": ["NCC-005"],
    "signal booster": ["NCC-005"],
    "frequency": ["NCC-005"],
    "consumer": ["NCC-002"],
    "complaint": ["NCC-002"],
    "billing": ["NCC-002"],
    "outage": ["NCC-002"],
    "governance": ["NCC-006"],
    "board": ["NCC-006"],
    "director": ["NCC-006"],
    "enforcement": ["NCC-001"],
    "fine": ["NCC-001"],
    "penalty": ["NCC-001"],
    "licence": ["NCC-001"],
    "false": ["NCC-001"],
}

# NCC_REGULATIONS indexed by ID for fast lookup
_NCC_REG_INDEX: dict[str, dict] = {r["id"]: r for r in NCC_REGULATIONS}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc or ""
        return host.lstrip("www.")
    except Exception:
        return ""


def _keyword_match_regulation(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Keyword-based fallback: scan ``text`` for NCC topic keywords and return
    ``(regulation_id, None)``. Returns ``(None, None)`` if no match found.
    """
    lower = text.lower()
    for keyword, reg_ids in _KEYWORD_REGULATION_MAP.items():
        if keyword in lower and reg_ids:
            reg_id = reg_ids[0]
            reg = _NCC_REG_INDEX.get(reg_id, {})
            # Try to find a relevant section
            for sec in reg.get("key_sections", []):
                if keyword in sec.get("summary", "").lower():
                    return reg_id, sec.get("section")
            return reg_id, None
    return None, None


def _parse_confidence(text: str) -> float:
    """Extract the first float between 0–1 from a JSON-ish LLM response."""
    match = re.search(r'"confidence"\s*:\s*([0-9.]+)', text)
    if match:
        try:
            val = float(match.group(1))
            return max(0.0, min(1.0, val))
        except ValueError:
            pass
    return 0.5


def _extract_json(text: str) -> dict:
    """
    Robustly extract the first valid JSON object from an LLM response string.

    Three-pass strategy:
      1. Try json.loads(text.strip()) — LLM sometimes returns clean JSON.
      2. Non-greedy re.search for the first ``{...}`` block.
      3. Walk character by character: find each ``{``, try json.loads forward
         until something parses.

    Raises
    ------
    ValueError
        If no valid JSON object can be found in the text.
    """
    # Pass 1: clean response (LLM returned only JSON)
    stripped = text.strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Pass 2: non-greedy regex — grab the first {...} block
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Pass 3: walk forward from every '{', try progressively shorter slices
    for i, ch in enumerate(text):
        if ch == "{":
            for j in range(len(text), i, -1):
                candidate = text[i:j]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                    break
                except (json.JSONDecodeError, ValueError):
                    continue

    raise ValueError(
        f"No valid JSON object found in LLM response: {text[:200]!r}"
    )


def _build_ncc_corpus_text() -> str:
    """Serialise NCC_REGULATIONS into a compact text block for LLM context."""
    lines: list[str] = []
    for reg in NCC_REGULATIONS:
        lines.append(
            f"[{reg['id']}] {reg['name']} — category: {reg.get('category', '')}"
        )
        for sec in reg.get("key_sections", [])[:3]:
            lines.append(f"  • {sec['section']}: {sec['summary'][:120]}")
    return "\n".join(lines)


# ── Service class ─────────────────────────────────────────────────────────────


class NCCLiveRulesService:
    """
    Live NCC enforcement rules engine for Iroko AI.

    Combines the static ``NCC_REGULATIONS`` corpus with live-scraped NCC
    updates from Bright Data, then uses Azure OpenAI to match each update
    to the closest regulation ID and evaluate agent decisions for compliance.
    """

    # ── 1. Fetch latest NCC updates via Bright Data ───────────────────────────

    async def fetch_latest_ncc_updates(self) -> list[dict[str, Any]]:
        """
        Scrape live NCC enforcement notices and new directives.

        Three source sweeps (all failures swallowed individually):
          1. SERP: ``"NCC Nigeria new regulation directive 2025 2026 site:ncc.gov.ng"``
          2. SERP: ``"NCC Nigeria enforcement notice fine 2025 2026"``
          3. Web Unlocker fetch of ``https://www.ncc.gov.ng/regulatory/regulations``

        Returns
        -------
        list[dict]
            Each item::

                {
                    "title":    str,
                    "url":      str,
                    "summary":  str,
                    "date_str": str,   # extracted date string or ""
                    "source":   "ncc_serp" | "ncc_direct",
                }
        """
        updates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        # ── SERP sweep 1: site-scoped regulation search ───────────────────────
        try:
            results = await bright_data_client.serp_search(
                query="NCC Nigeria new regulation directive 2025 2026 site:ncc.gov.ng",
                country="ng",
                num_results=10,
            )
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    date_match = re.search(
                        r'\b(20\d{2}[-/]\d{2}[-/]\d{2}|[A-Z][a-z]+ \d{1,2},?\s*20\d{2})\b',
                        r.get("snippet", "")
                    )
                    date_str = date_match.group(1) if date_match else ""
                    updates.append({
                        "title":    r.get("title", ""),
                        "url":      url,
                        "summary":  r.get("snippet", ""),
                        "date_str": date_str,
                        "source":   "ncc_serp",
                    })
            logger.info(
                "[NCCLiveRules] SERP sweep 1 (site:ncc.gov.ng) → %d results", len(results)
            )
        except Exception as exc:
            logger.warning("[NCCLiveRules] SERP sweep 1 failed: %s", exc)

        # ── SERP sweep 2: general enforcement + fine search ───────────────────
        try:
            results2 = await bright_data_client.serp_search(
                query="NCC Nigeria enforcement notice fine 2025 2026",
                country="ng",
                num_results=10,
            )
            for r in results2:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    date_match = re.search(
                        r'\b(20\d{2}[-/]\d{2}[-/]\d{2}|[A-Z][a-z]+ \d{1,2},?\s*20\d{2})\b',
                        r.get("snippet", "")
                    )
                    date_str = date_match.group(1) if date_match else ""
                    updates.append({
                        "title":    r.get("title", ""),
                        "url":      url,
                        "summary":  r.get("snippet", ""),
                        "date_str": date_str,
                        "source":   "ncc_serp",
                    })
            logger.info(
                "[NCCLiveRules] SERP sweep 2 (enforcement+fine) → %d results", len(results2)
            )
        except Exception as exc:
            logger.warning("[NCCLiveRules] SERP sweep 2 failed: %s", exc)

        # ── Scraping Browser with Web Unlocker Fallback: NCC regulations index page ──────
        try:
            logger.info("[NCCLiveRules] Escalating to Scraping Browser for interactive extraction of NCC regulations index")
            actions = [
                {"type": "scroll"},
                {"type": "wait", "timeout": 1500},
                {"type": "scroll"},
                {"type": "wait", "timeout": 1000}
            ]
            page = await bright_data_client.scraping_browser_interact(
                _NCC_REGULATIONS_PAGE, actions=actions
            )
            if page.get("status") == 200 and page.get("content"):
                content = page["content"]
                url = _NCC_REGULATIONS_PAGE
                if url not in seen_urls:
                    seen_urls.add(url)
                    updates.append({
                        "title":    "NCC Regulations Index (interactive page)",
                        "url":      url,
                        "summary":  content[:400].strip(),
                        "date_str": page.get("fetched_at", ""),
                        "source":   "ncc_scraping_browser" if page.get("source") == "scraping_browser" else "ncc_direct",
                    })
                    logger.info("[NCCLiveRules] Scraping Browser: NCC regulations page fetched")
        except Exception as exc:
            logger.warning("[NCCLiveRules] Scraping Browser fetch failed: %s", exc)

        logger.info(
            "[NCCLiveRules] fetch_latest_ncc_updates → %d unique updates", len(updates)
        )
        return updates

    # ── 2. Match a live update to the static NCC corpus via LLM ──────────────

    async def match_update_to_regulation(self, update: dict[str, Any]) -> dict[str, Any]:
        """
        Use Azure OpenAI to match a live NCC update to the closest regulation
        in ``NCC_REGULATIONS``.

        Falls back to keyword-based matching if the LLM is unavailable or
        returns an unparseable response.

        Parameters
        ----------
        update : dict
            A single update dict from ``fetch_latest_ncc_updates``.

        Returns
        -------
        dict
            ::

                {
                    "update":                 dict,   # original update
                    "matched_regulation_id":  str | None,
                    "matched_section":        str | None,
                    "confidence":             float,  # 0.0–1.0
                    "action_required":        bool,
                }
        """
        title = update.get("title", "")
        summary = update.get("summary", "")
        combined_text = f"{title} {summary}"

        if not _LLM_AVAILABLE:
            logger.warning(
                "[NCCLiveRules] LLM unavailable — using keyword fallback for update: %s",
                title[:80],
            )
            reg_id, section = _keyword_match_regulation(combined_text)
            return {
                "update": update,
                "matched_regulation_id": reg_id,
                "matched_section": section,
                "confidence": 0.45,
                "action_required": reg_id is not None,
            }

        corpus_text = _build_ncc_corpus_text()

        prompt = f"""You are an NCC Nigeria regulatory compliance expert.

Given this live NCC enforcement update:
TITLE: {title}
SUMMARY: {summary}

And the following NCC regulation corpus:
{corpus_text}

Task:
1. Identify the MOST relevant regulation ID from the corpus (e.g. "NCC-001", "NCC-003").
2. Identify the most relevant section within that regulation (e.g. "Section 70").
3. Rate your confidence from 0.0 to 1.0.
4. State whether immediate action is required (true/false).

Respond ONLY with valid JSON in this exact format:
{{
  "matched_regulation_id": "<ID or null>",
  "matched_section": "<section name or null>",
  "confidence": <float 0.0-1.0>,
  "action_required": <true|false>
}}"""

        logger.info(
            "[NCCLiveRules] LLM call: match_update_to_regulation for '%s'", title[:80]
        )

        try:
            response = await llm_complete(
                prompt,
                max_tokens=200,
                temperature=0.1,
                system_prompt=(
                    "You are a Nigerian telecommunications regulatory analyst. "
                    "Return only valid JSON. No commentary."
                ),
            )

            # Extract JSON block from response using robust parser
            parsed = _extract_json(response)
            reg_id = parsed.get("matched_regulation_id") or None
            section = parsed.get("matched_section") or None
            confidence = float(parsed.get("confidence", 0.5))
            action_required = bool(parsed.get("action_required", False))

        except Exception as exc:
            logger.warning(
                "[NCCLiveRules] LLM match failed (%s) — using keyword fallback", exc
            )
            reg_id, section = _keyword_match_regulation(combined_text)
            confidence = 0.4
            action_required = reg_id is not None

        return {
            "update": update,
            "matched_regulation_id": reg_id,
            "matched_section": section,
            "confidence": confidence,
            "action_required": action_required,
        }

    # ── 3. Compile full live enforcement rules corpus ─────────────────────────

    async def compile_live_enforcement_rules(self) -> dict[str, Any]:
        """
        Orchestrate a full live enforcement rules compilation.

        Steps:
          1. Fetch live NCC updates via ``fetch_latest_ncc_updates``.
          2. For each update, call ``match_update_to_regulation``.
          3. Merge matched updates into the static corpus.
          4. Derive new obligations and high-priority alerts.

        Returns
        -------
        dict
            ::

                {
                    "base_regulations":    list[dict],  # NCC_REGULATIONS
                    "live_updates":        list[dict],  # matched updates
                    "new_obligations":     list[str],
                    "high_priority_alerts": list[str],
                    "compiled_at":         str,         # ISO-8601 UTC
                }

        Notes
        -----
        If live fetching fails completely, the method still returns the static
        corpus with an empty ``live_updates`` list — agents can continue
        operating on the hardcoded corpus.
        """
        compiled_at = _now_iso()
        live_updates: list[dict[str, Any]] = []
        new_obligations: list[str] = []
        high_priority_alerts: list[str] = []

        # ── Step 1: fetch live updates ────────────────────────────────────────
        try:
            raw_updates = await self.fetch_latest_ncc_updates()
        except Exception as exc:
            logger.error(
                "[NCCLiveRules] fetch_latest_ncc_updates raised unexpectedly: %s. "
                "Returning static corpus only.",
                exc,
            )
            return {
                "base_regulations": NCC_REGULATIONS,
                "live_updates": [],
                "new_obligations": [],
                "high_priority_alerts": [],
                "compiled_at": compiled_at,
            }

        # ── Step 2: LLM-match each update to a regulation ────────────────────
        import asyncio

        async def _safe_match(update: dict) -> dict:
            try:
                return await self.match_update_to_regulation(update)
            except Exception as exc:
                logger.warning("[NCCLiveRules] match_update_to_regulation failed: %s", exc)
                return {
                    "update": update,
                    "matched_regulation_id": None,
                    "matched_section": None,
                    "confidence": 0.0,
                    "action_required": False,
                }

        # Process in batches of 5 to avoid Azure OpenAI 429 rate-limiting
        _BATCH_SIZE = 5
        matched_results: list[dict] = []
        for batch_start in range(0, len(raw_updates), _BATCH_SIZE):
            batch = raw_updates[batch_start: batch_start + _BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[_safe_match(u) for u in batch],
                return_exceptions=False,
            )
            matched_results.extend(batch_results)
            if batch_start + _BATCH_SIZE < len(raw_updates):
                await asyncio.sleep(0.5)
        live_updates = matched_results

        # ── Step 3: derive new obligations and high-priority alerts ───────────
        for matched in live_updates:
            update = matched.get("update", {})
            reg_id = matched.get("matched_regulation_id")
            confidence = matched.get("confidence", 0.0)
            action_required = matched.get("action_required", False)
            title = update.get("title", "Untitled update")
            url = update.get("url", "")
            source_hint = f" (source: {url})" if url else ""

            # New obligation: any matched, action-required update
            if action_required and reg_id:
                obligation = (
                    f"[{reg_id}] Review and respond to: \"{title}\"{source_hint}"
                )
                new_obligations.append(obligation)

            # High-priority alert: high-confidence action-required updates
            if action_required and confidence >= 0.70:
                alert = (
                    f"🔴 HIGH PRIORITY [{reg_id or 'UNCLASSIFIED'}] "
                    f"confidence={confidence:.0%}: {title}{source_hint}"
                )
                high_priority_alerts.append(alert)

        logger.info(
            "[NCCLiveRules] compile_live_enforcement_rules: %d live updates, "
            "%d new obligations, %d high-priority alerts",
            len(live_updates),
            len(new_obligations),
            len(high_priority_alerts),
        )

        return {
            "base_regulations": NCC_REGULATIONS,
            "live_updates": live_updates,
            "new_obligations": new_obligations,
            "high_priority_alerts": high_priority_alerts,
            "compiled_at": compiled_at,
        }

    # ── 4. Check an agent decision against compiled NCC rules ─────────────────

    async def check_decision_against_rules(
        self, decision_text: str
    ) -> dict[str, Any]:
        """
        Evaluate whether an agent decision or proposed action may violate any
        NCC regulation in the compiled corpus.

        Uses Azure OpenAI with the full ``NCC_REGULATIONS`` corpus as context.
        Falls back to keyword-based heuristics if the LLM is unavailable.

        Parameters
        ----------
        decision_text : str
            Free-text description of the agent's decision or planned action.

        Returns
        -------
        dict
            ::

                {
                    "compliant": bool,
                    "violations": [
                        {
                            "regulation_id": str,
                            "section":       str,
                            "reason":        str,
                        },
                        ...
                    ],
                    "verdict": "GO" | "NO-GO" | "MONITOR",
                }
        """
        if not _LLM_AVAILABLE:
            logger.warning(
                "[NCCLiveRules] LLM unavailable — using keyword heuristic for decision check."
            )
            return self._keyword_decision_check(decision_text)

        corpus_text = _build_ncc_corpus_text()

        prompt = f"""You are an NCC Nigeria regulatory compliance expert reviewing an agent decision.

Agent decision / planned action:
\"\"\"{decision_text}\"\"\"

NCC Regulatory Corpus:
{corpus_text}

Task:
Determine if this decision may violate any NCC regulation.
For each potential violation, cite the exact regulation ID and section.
Assign an overall verdict:
  "GO"      — no violations detected, decision is compliant.
  "NO-GO"   — one or more definite violations; do not proceed.
  "MONITOR" — possible concerns; flag for human review.

Respond ONLY with valid JSON in this exact format:
{{
  "compliant": <true|false>,
  "violations": [
    {{
      "regulation_id": "<e.g. NCC-003>",
      "section": "<e.g. Section 70>",
      "reason": "<brief explanation>"
    }}
  ],
  "verdict": "<GO|NO-GO|MONITOR>"
}}"""

        logger.info(
            "[NCCLiveRules] LLM call: check_decision_against_rules (decision length=%d chars)",
            len(decision_text),
        )

        try:
            response = await llm_complete(
                prompt,
                max_tokens=600,
                temperature=0.05,
                system_prompt=(
                    "You are a Nigerian telecommunications regulatory compliance analyst. "
                    "Be precise and conservative. Return only valid JSON. No commentary."
                ),
            )

            parsed = _extract_json(response)
            compliant = bool(parsed.get("compliant", True))
            violations = parsed.get("violations", [])
            verdict = parsed.get("verdict", "MONITOR")

            # Normalise verdict to allowed values
            if verdict not in ("GO", "NO-GO", "MONITOR"):
                verdict = "MONITOR"

            logger.info(
                "[NCCLiveRules] Decision check complete: verdict=%s violations=%d",
                verdict,
                len(violations),
            )

            return {
                "compliant": compliant,
                "violations": violations,
                "verdict": verdict,
            }

        except Exception as exc:
            logger.warning(
                "[NCCLiveRules] LLM compliance check failed (%s) — using keyword fallback",
                exc,
            )
            return self._keyword_decision_check(decision_text)

    # ── Keyword fallback for decision checking ────────────────────────────────

    def _keyword_decision_check(self, decision_text: str) -> dict[str, Any]:
        """
        Heuristic-only compliance check used when LLM is unavailable.

        Scans ``decision_text`` for regulatory keywords and flags potential
        violations. Always returns ``"MONITOR"`` so a human reviews the
        decision before it proceeds.
        """
        lower = decision_text.lower()
        violations: list[dict[str, str]] = []

        # High-risk keyword patterns
        risk_patterns: list[tuple[str, str, str, str]] = [
            ("delay", "NCC-003", "Section — Reporting", "Delayed QoS report submission may breach quarterly reporting obligation."),
            ("skip", "NCC-003", "Section — Reporting", "Skipping network performance reporting violates QoS Business Rules 2024."),
            ("unregistered sim", "NCC-004", "NIN Requirement", "Unregistered SIM activation violates SIM Registration Business Rules 2025."),
            ("block emergency", "NCC-002", "Emergency Services", "Blocking emergency calls violates Consumer Code of Practice Regulations 2024."),
            ("no complaint", "NCC-002", "Complaint Management", "Failing to log complaints violates Consumer Code of Practice Regulations 2024."),
            ("unlicensed spectrum", "NCC-005", "Spectrum Licensing", "Using unlicensed spectrum is a criminal offence under NCA 2003."),
            ("false report", "NCC-001", "Section 73", "Submitting false information to NCC is an offence under NCA 2003 Section 73."),
            ("misrepresent", "NCC-001", "Section 73", "Misrepresentation to NCC is an offence under NCA 2003 Section 73."),
        ]

        for keyword, reg_id, section, reason in risk_patterns:
            if keyword in lower:
                violations.append({
                    "regulation_id": reg_id,
                    "section": section,
                    "reason": reason,
                })

        if violations:
            verdict = "NO-GO" if len(violations) >= 2 else "MONITOR"
            compliant = False
        else:
            verdict = "MONITOR"  # Conservative: always monitor when LLM is absent
            compliant = True

        return {
            "compliant": compliant,
            "violations": violations,
            "verdict": verdict,
        }


# ── Module-level singleton ────────────────────────────────────────────────────

ncc_rules_service = NCCLiveRulesService()
"""
Shared singleton ``NCCLiveRulesService`` instance.
Import and use this directly in agents and routes::

    from services.ncc_live_rules import ncc_rules_service

    rules = await ncc_rules_service.compile_live_enforcement_rules()
    check = await ncc_rules_service.check_decision_against_rules(decision_text)
"""
