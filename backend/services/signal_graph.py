"""
services/signal_graph.py — Signal Knowledge Graph for Iroko AI.
================================================================
Improvements over v1:
  1. SQLite persistence  — signals are upserted into signal_nodes table so the
     graph accumulates history across restarts.  CO_OCCURRENCE edges can now
     span days, not just the current request.
  2. Temporal decay     — recent signals score higher via exponential decay:
     decayed_score = base_score * source_authority * exp(-age_hours / HALF_LIFE)
  3. Source authority   — official regulators (cbn.gov.ng, sec.gov.ng …) get a
     1.5x multiplier; tier-2 sources get 1.0x; unknown sources 0.8x.
  4. Expanded entity matching — 40+ Nigerian fintech entities with aliases so
     "Kuda Bank", "Kuda MFB", "Kuda" all resolve to the same node.
  5. LLM narratives     — `generate_risk_narrative` calls Azure OpenAI (nano)
     to produce a specific, actionable 2-sentence analysis instead of a
     template string.  Falls back to the template when LLM is unavailable.
  6. Category cross-signal bonus — compound score gets a +20% bonus when
     signals come from 3+ distinct categories (multi-domain confirmation).

Usage::

    from services.signal_graph import signal_graph_service
    from services.web_intelligence import run_all_signals
    from services.brightdata import bright_data_client
    from models.database import SessionLocal

    all_signals = await run_all_signals(bright_data_client)
    db = SessionLocal()
    graph = await signal_graph_service.build_signal_graph(all_signals, db=db)
    risks = await signal_graph_service.get_high_risk_entities(graph, db=db)
    db.close()
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Optional networkx ─────────────────────────────────────────────────────────

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    nx = None  # type: ignore[assignment]
    _NX_AVAILABLE = False
    logger.warning("[SignalGraph] networkx not installed — compound risk detection disabled.")

# ── Constants ─────────────────────────────────────────────────────────────────

# Exponential decay half-life: a signal loses half its weight every 24 hours
_DECAY_HALF_LIFE_HOURS = 24.0

# CO_OCCURRENCE window pulled from DB history (not just current batch)
_CO_OCCURRENCE_WINDOW = timedelta(hours=72)

# Base risk scores per signal category
_CATEGORY_SCORES: dict[str, float] = {
    "fraud":       1.0,
    "regulatory":  0.8,
    "vendor_risk": 0.7,
    "competitor":  0.3,
    "market":      0.2,
}

# Source authority multipliers — higher = more trustworthy source
_AUTHORITY_TIERS: dict[str, float] = {
    # Tier 1 — Official regulators
    "cbn.gov.ng":   1.5,
    "sec.gov.ng":   1.5,
    "nfiu.gov.ng":  1.5,
    "ndpc.gov.ng":  1.5,
    "efcc.gov.ng":  1.5,
    "ncc.gov.ng":   1.5,
    # Tier 2 — Reputable Nigerian financial press
    "businessday.ng":     1.2,
    "techcabal.com":      1.2,
    "nairametrics.com":   1.2,
    "techpoint.africa":   1.2,
    "guardian.ng":        1.1,
    "thisdaylive.com":    1.1,
    "punchng.com":        1.1,
    "disrupt-africa.com": 1.0,
}
_DEFAULT_AUTHORITY = 0.8  # unknown source

# Entity aliases — all variants resolve to the canonical name
_ENTITY_ALIASES: dict[str, str] = {
    # Kuda
    "kuda bank": "Kuda", "kuda mfb": "Kuda", "kuda microfinance": "Kuda",
    # Carbon
    "carbon mfb": "Carbon", "carbon microfinance": "Carbon", "one credit": "Carbon",
    # Moniepoint
    "moniepoint mfb": "Moniepoint", "moniepoint inc": "Moniepoint",
    "teamapt": "Moniepoint",
    # OPay
    "opay nigeria": "OPay", "opera pay": "OPay",
    # PalmPay
    "palmpay nigeria": "PalmPay",
    # FairMoney
    "fairmoney mfb": "Fairmoney", "fair money": "Fairmoney",
    # Flutterwave
    "flutter wave": "Flutterwave",
    # Interswitch
    "interswitch nigeria": "Interswitch",
    # NIBSS
    "nibss plc": "NIBSS",
    # Regulators
    "central bank of nigeria": "CBN",
    "securities and exchange commission": "SEC",
    "nigerian data protection commission": "NDPC",
    "ndpa": "NDPC",
    "economic and financial crimes commission": "EFCC",
    "nigerian communications commission": "NCC",
    "nigerian financial intelligence unit": "NFIU",
}

# Canonical entity list (after alias resolution)
_KNOWN_ENTITIES: list[str] = [
    "Kuda", "Carbon", "Moniepoint", "Fairmoney", "OPay", "PalmPay",
    "Flutterwave", "Interswitch", "NIBSS", "CRC", "Paga",
    "CBN", "SEC", "NDPC", "EFCC", "NCC", "NFIU",
    "MTN", "Airtel", "Glo", "9mobile",
    "IHS", "American Tower", "Ericsson", "Huawei",
]

_REGULATION_PATTERN = re.compile(
    r"CBN[-\s]\w+[-\s]\d+|SEC[-\s]\d+|Section\s+\d+|NDPA\s+Art(?:icle)?\.?\s*\d+|"
    r"CBN Circular \d{4}/\d+",
    re.IGNORECASE,
)

_NODE_SIGNAL      = "signal"
_NODE_ENTITY      = "entity"
_ENTITY_COMPANY   = "company"
_ENTITY_REGULATION = "regulation"
_EDGE_MENTIONS      = "MENTIONS"
_EDGE_CO_OCCURRENCE = "CO_OCCURRENCE"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _signal_hash(signal: dict) -> str:
    raw = (signal.get("url", "") + signal.get("title", "")).strip() or repr(signal)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _signal_id(h: str) -> str:
    return "sig_" + h


def _entity_id(name: str) -> str:
    return "ent_" + name.lower().replace(" ", "_").replace("-", "_")


def _source_host(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lstrip("www.")
        return host or ""
    except Exception:
        return ""


def _authority(host: str) -> float:
    return _AUTHORITY_TIERS.get(host, _DEFAULT_AUTHORITY)


def _temporal_decay(last_seen: datetime) -> float:
    """Exponential decay: score * 2^(-age / half_life)."""
    now = datetime.now(timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age_hours = (now - last_seen).total_seconds() / 3600
    return math.exp(-math.log(2) * age_hours / _DECAY_HALF_LIFE_HOURS)


def _resolve_alias(text: str) -> str | None:
    """Return the canonical entity name if text matches a known alias."""
    lower = text.lower().strip()
    return _ENTITY_ALIASES.get(lower)


def _extract_entities(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    lower_text = text.lower()

    # Check aliases first (longer strings → more specific)
    for alias in sorted(_ENTITY_ALIASES, key=len, reverse=True):
        if alias in lower_text:
            canonical = _ENTITY_ALIASES[alias]
            if canonical not in seen:
                seen.add(canonical)
                found.append((canonical, _ENTITY_COMPANY))

    # Check canonical names not already found via alias
    for entity in _KNOWN_ENTITIES:
        pattern = re.compile(r"\b" + re.escape(entity) + r"\b", re.IGNORECASE)
        if pattern.search(text) and entity not in seen:
            seen.add(entity)
            found.append((entity, _ENTITY_COMPANY))

    # Regulation references
    for match in _REGULATION_PATTERN.finditer(text):
        ref = match.group(0).strip().upper()
        if ref not in seen:
            seen.add(ref)
            found.append((ref, _ENTITY_REGULATION))

    return found


def _parse_ts(signal: dict) -> Optional[datetime]:
    for key in ("timestamp", "date", "published_at", "fetched_at", "created_at"):
        raw = signal.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw[:19], fmt)
                except ValueError:
                    continue
    return None


# ── DB upsert helpers ─────────────────────────────────────────────────────────

def _upsert_signals(signals_by_category: dict, db) -> None:
    """Persist new signals and refresh last_seen on existing ones."""
    try:
        from models.signal_node import SignalNode
        now = datetime.utcnow()
        for category, signals in signals_by_category.items():
            if not isinstance(signals, list):
                continue
            base_score = _CATEGORY_SCORES.get(category, 0.2)
            for sig in signals:
                if not isinstance(sig, dict):
                    continue
                h = _signal_hash(sig)
                existing = db.query(SignalNode).filter_by(signal_hash=h).first()
                if existing:
                    existing.last_seen = now
                else:
                    host = _source_host(sig.get("url", ""))
                    db.add(SignalNode(
                        signal_hash=h,
                        category=category,
                        title=sig.get("title", "")[:500],
                        url=sig.get("url", "")[:1000],
                        snippet=(sig.get("snippet") or sig.get("summary") or "")[:1000],
                        source_host=host[:128],
                        base_score=base_score,
                        first_seen=now,
                        last_seen=now,
                    ))
        db.commit()
    except Exception as exc:
        logger.warning("[SignalGraph] upsert_signals failed: %s", exc)
        db.rollback()


def _load_history(db, window_hours: int = 72) -> list:
    """Load signals seen within the last `window_hours` from the DB."""
    try:
        from models.signal_node import SignalNode
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        return db.query(SignalNode).filter(SignalNode.last_seen >= cutoff).all()
    except Exception as exc:
        logger.warning("[SignalGraph] load_history failed: %s", exc)
        return []


# ── LLM narrative ─────────────────────────────────────────────────────────────

async def _llm_narrative(entity: str, signals: list[dict]) -> str:
    """
    Call Azure OpenAI nano to produce a specific, actionable 2-sentence
    risk narrative.  Falls back to the template on any failure.
    """
    try:
        from agents.kernel import llm_complete

        titles = "; ".join(s.get("title", "") for s in signals[:5] if s.get("title"))
        categories = list({s.get("category", "") for s in signals})
        score = round(sum(s.get("effective_score", s.get("score", 0.2)) for s in signals), 2)

        prompt = (
            f"You are a Nigerian fintech compliance analyst for Iroko AI.\n"
            f"Entity under review: {entity}\n"
            f"Signal count: {len(signals)} ({', '.join(categories)})\n"
            f"Signal titles: {titles}\n"
            f"Compound risk score: {score}\n\n"
            f"Write exactly 2 sentences:\n"
            f"1. What specific regulatory or competitive risk this entity faces RIGHT NOW "
            f"based on the signals, citing the most relevant signal.\n"
            f"2. What Kuda MFB's compliance team should do about it in the next 48 hours.\n"
            f"Be specific. No generic language. Max 60 words total."
        )
        result = await llm_complete(
            prompt,
            service_id="nano",
            max_tokens=120,
            temperature=0.2,
        )
        return result.strip() if result.strip() else _template_narrative(entity, signals)
    except Exception as exc:
        logger.debug("[SignalGraph] LLM narrative failed (%s) — using template", exc)
        return _template_narrative(entity, signals)


def _template_narrative(entity: str, signals: list[dict]) -> str:
    n = len(signals)
    categories = list({s.get("category", "unknown") for s in signals})
    types_str = " and ".join(categories) if len(categories) <= 2 else ", ".join(categories[:-1]) + f", and {categories[-1]}"
    score = round(sum(s.get("effective_score", s.get("score", 0.2)) for s in signals), 2)
    return (
        f"{entity} flagged by {n} independent signal{'s' if n != 1 else ''} "
        f"across {types_str} domains. "
        f"Compound risk score {score:.2f} — review recommended within 48h."
    )


# ── Service ───────────────────────────────────────────────────────────────────

class SignalGraphService:

    async def build_signal_graph(
        self,
        all_signals: dict,
        db=None,
    ) -> "nx.DiGraph":
        """
        Build a weighted directed signal-entity graph.

        If `db` is provided, signals are persisted and 72h history is loaded
        from the DB so CO_OCCURRENCE edges span across restarts.
        Without `db` the graph is built from the current batch only (v1 behaviour).
        """
        if not _NX_AVAILABLE:
            logger.warning("[SignalGraph] networkx unavailable — returning stub")
            return object()  # type: ignore[return-value]

        # ── Persist current batch and load history ────────────────────────────
        if db is not None:
            _upsert_signals(all_signals, db)
            db_rows = _load_history(db, window_hours=72)
        else:
            db_rows = []

        G: nx.DiGraph = nx.DiGraph()
        entity_signal_map: dict[str, list[tuple[str, Optional[datetime], float]]] = {}
        now = datetime.now(timezone.utc)

        # ── Helper to add one signal to the graph ─────────────────────────────
        def _add_signal(sig_hash: str, category: str, title: str, url: str,
                        snippet: str, source_host: str, base_score: float,
                        last_seen: datetime, raw: dict) -> None:
            sig_id = _signal_id(sig_hash)
            if G.has_node(sig_id):
                return

            auth    = _authority(source_host)
            decay   = _temporal_decay(last_seen)
            eff     = round(base_score * auth * decay, 4)

            G.add_node(
                sig_id,
                node_type=_NODE_SIGNAL,
                category=category,
                title=title,
                url=url,
                snippet=snippet,
                source_host=source_host,
                base_score=base_score,
                authority=auth,
                decay=decay,
                effective_score=eff,
                last_seen=last_seen,
                raw=raw,
            )

            text = f"{title} {snippet}"
            for entity_name, entity_type in _extract_entities(text):
                ent_id = _entity_id(entity_name)
                if not G.has_node(ent_id):
                    G.add_node(ent_id, node_type=_NODE_ENTITY,
                               entity_type=entity_type, name=entity_name)
                if not G.has_edge(sig_id, ent_id):
                    G.add_edge(sig_id, ent_id, relationship=_EDGE_MENTIONS)
                entity_signal_map.setdefault(ent_id, []).append((sig_id, last_seen, eff))

        # ── Pass 1a: signals from DB history ─────────────────────────────────
        for row in db_rows:
            h = row.signal_hash
            ls = row.last_seen if row.last_seen else now.replace(tzinfo=None)
            _add_signal(h, row.category, row.title, row.url, row.snippet,
                        row.source_host or "", row.base_score, ls, {})

        # ── Pass 1b: signals from current batch not already in DB ─────────────
        for category, signals in all_signals.items():
            if not isinstance(signals, list):
                continue
            base = _CATEGORY_SCORES.get(category, 0.2)
            for sig in signals:
                if not isinstance(sig, dict):
                    continue
                h = _signal_hash(sig)
                if G.has_node(_signal_id(h)):
                    continue  # already added from DB
                host = _source_host(sig.get("url", ""))
                ts   = _parse_ts(sig) or now.replace(tzinfo=None)
                _add_signal(h, category,
                            sig.get("title", "")[:500],
                            sig.get("url", ""),
                            (sig.get("snippet") or sig.get("summary") or "")[:500],
                            host, base, ts, sig)

        # ── Pass 2: CO_OCCURRENCE edges ───────────────────────────────────────
        window_secs = _CO_OCCURRENCE_WINDOW.total_seconds()
        for ent_id, sig_list in entity_signal_map.items():
            if len(sig_list) < 2:
                continue
            for i in range(len(sig_list)):
                for j in range(i + 1, len(sig_list)):
                    sid_a, ts_a, _ = sig_list[i]
                    sid_b, ts_b, _ = sig_list[j]
                    if sid_a == sid_b:
                        continue
                    if ts_a and ts_b:
                        ta = ts_a if ts_a.tzinfo else ts_a.replace(tzinfo=timezone.utc)
                        tb = ts_b if ts_b.tzinfo else ts_b.replace(tzinfo=timezone.utc)
                        if abs((ta - tb).total_seconds()) > window_secs:
                            continue
                    if not G.has_edge(sid_a, sid_b):
                        G.add_edge(sid_a, sid_b,
                                   relationship=_EDGE_CO_OCCURRENCE,
                                   via_entity=ent_id)

        logger.info("[SignalGraph] graph built: %d nodes, %d edges",
                    G.number_of_nodes(), G.number_of_edges())
        return G

    # ── Find compound risks ───────────────────────────────────────────────────

    async def find_compound_risks(
        self,
        graph: "nx.DiGraph",
        min_signals: int = 2,
        db=None,
    ) -> list[dict]:
        if not _NX_AVAILABLE or not isinstance(graph, nx.DiGraph):
            return []

        results: list[dict] = []

        entity_nodes = [
            (nid, data)
            for nid, data in graph.nodes(data=True)
            if data.get("node_type") == _NODE_ENTITY
        ]

        for ent_id, ent_data in entity_nodes:
            predecessors = [
                (pred, graph.nodes[pred])
                for pred in graph.predecessors(ent_id)
                if graph.nodes[pred].get("node_type") == _NODE_SIGNAL
            ]
            if len(predecessors) < min_signals:
                continue

            eff_scores = [d.get("effective_score", d.get("base_score", 0.2))
                          for _, d in predecessors]
            n          = len(eff_scores)
            avg        = sum(eff_scores) / n
            # Volume boost: more independent signals = higher confidence
            compound   = round(avg * (n ** 1.2), 4)

            # Cross-category diversity bonus (+20% if 3+ distinct categories)
            categories = {d.get("category", "") for _, d in predecessors}
            if len(categories) >= 3:
                compound = round(compound * 1.2, 4)

            signal_dicts = [
                {
                    "title":           d.get("title", ""),
                    "url":             d.get("url", ""),
                    "snippet":         d.get("snippet", ""),
                    "category":        d.get("category", ""),
                    "score":           d.get("base_score", 0.2),
                    "effective_score": d.get("effective_score", 0.2),
                    "authority":       d.get("authority", 0.8),
                    "decay":           round(d.get("decay", 1.0), 3),
                    "source_host":     d.get("source_host", ""),
                }
                for _, d in predecessors
            ]

            entity_name = ent_data.get("name", ent_id)
            narrative   = await _llm_narrative(entity_name, signal_dicts)

            results.append({
                "entity":              entity_name,
                "entity_type":         ent_data.get("entity_type", _ENTITY_COMPANY),
                "signal_count":        n,
                "categories":          sorted(categories),
                "compound_risk_score": compound,
                "signals":             signal_dicts,
                "risk_narrative":      narrative,
            })

        results.sort(key=lambda r: r["compound_risk_score"], reverse=True)
        logger.info("[SignalGraph] compound risks: %d entities (min_signals=%d)",
                    len(results), min_signals)
        return results

    async def get_high_risk_entities(
        self,
        graph: "nx.DiGraph",
        threshold: float = 0.6,
        db=None,
    ) -> list[dict]:
        all_risks = await self.find_compound_risks(graph, db=db)
        high      = [r for r in all_risks if r["compound_risk_score"] >= threshold]
        logger.info("[SignalGraph] high-risk entities: %d/%d above %.2f",
                    len(high), len(all_risks), threshold)
        return high

    # Keep sync shim for any callers that don't await
    def build_signal_graph_sync(self, all_signals: dict) -> "nx.DiGraph":
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run,
                                         self.build_signal_graph(all_signals, db=None))
                    return future.result()
            return loop.run_until_complete(
                self.build_signal_graph(all_signals, db=None))
        except Exception:
            return self._build_sync_fallback(all_signals)

    def _build_sync_fallback(self, all_signals: dict) -> "nx.DiGraph":
        """Sync-only fallback with no DB and no LLM — identical to v1 behaviour."""
        if not _NX_AVAILABLE:
            return object()  # type: ignore[return-value]
        G: nx.DiGraph = nx.DiGraph()
        entity_signal_map: dict[str, list] = {}
        now = datetime.now(timezone.utc)
        for category, signals in all_signals.items():
            if not isinstance(signals, list):
                continue
            base = _CATEGORY_SCORES.get(category, 0.2)
            for sig in signals:
                if not isinstance(sig, dict):
                    continue
                h   = _signal_hash(sig)
                sid = _signal_id(h)
                if not G.has_node(sid):
                    G.add_node(sid, node_type=_NODE_SIGNAL, category=category,
                               title=sig.get("title", ""), url=sig.get("url", ""),
                               snippet=sig.get("snippet", ""), base_score=base,
                               effective_score=base, last_seen=now, raw=sig)
                text = f"{sig.get('title','')} {sig.get('snippet','')}"
                for ename, etype in _extract_entities(text):
                    eid = _entity_id(ename)
                    if not G.has_node(eid):
                        G.add_node(eid, node_type=_NODE_ENTITY,
                                   entity_type=etype, name=ename)
                    if not G.has_edge(sid, eid):
                        G.add_edge(sid, eid, relationship=_EDGE_MENTIONS)
                    entity_signal_map.setdefault(eid, []).append((sid, now))
        for eid, slist in entity_signal_map.items():
            if len(slist) < 2:
                continue
            for i in range(len(slist)):
                for j in range(i + 1, len(slist)):
                    sa, _ = slist[i]
                    sb, _ = slist[j]
                    if sa != sb and not G.has_edge(sa, sb):
                        G.add_edge(sa, sb, relationship=_EDGE_CO_OCCURRENCE, via_entity=eid)
        return G


# ── Singleton ─────────────────────────────────────────────────────────────────

signal_graph_service = SignalGraphService()
