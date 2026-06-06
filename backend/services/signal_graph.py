"""
services/signal_graph.py — Signal Knowledge Graph for Iroko AI.
================================================================
Implements an in-memory signal correlation graph (NexusGraph pattern) using
networkx. When multiple independent signals point at the same entity — a
telco, vendor, or NCC regulation — the graph connects them into a single
high-confidence compound risk alert that no single signal could trigger alone.

Architecture:
  - Nodes: one node per unique signal (keyed by hash of url+title) plus one
    node per extracted entity (company name or regulation ref).
  - Edges:
      MENTIONS      signal → entity  (signal references that entity)
      CO_OCCURRENCE signal → signal  (two signals share an entity within 72h)
  - ``build_signal_graph``    — constructs the DiGraph from run_all_signals() output.
  - ``find_compound_risks``   — entities with 2+ incoming signal edges.
  - ``generate_risk_narrative`` — 2-sentence human-readable summary.
  - ``get_high_risk_entities`` — filtered + sorted compound risk list.

Graceful degradation:
  - If networkx is not installed the module still imports cleanly; all methods
    return empty results and log a warning so the rest of the pipeline is
    unaffected.

Graph is in-memory only — rebuilt on every call (no persistence required).

Usage::

    from services.signal_graph import signal_graph_service
    from services.web_intelligence import run_all_signals
    from services.brightdata import bright_data_client

    all_signals = await run_all_signals(bright_data_client)
    graph       = signal_graph_service.build_signal_graph(all_signals)
    risks       = signal_graph_service.get_high_risk_entities(graph, threshold=0.6)
    for r in risks:
        print(r["entity"], r["compound_risk_score"], r["risk_narrative"])
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Optional networkx import with graceful degradation ────────────────────────

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:  # pragma: no cover
    nx = None  # type: ignore[assignment]
    _NX_AVAILABLE = False
    logger.warning(
        "[SignalGraph] networkx is not installed — compound risk detection disabled. "
        "Run: pip install networkx"
    )


# ── Constants ─────────────────────────────────────────────────────────────────

# Known telco / vendor entities to match against signal text
_KNOWN_COMPANIES: list[str] = [
    "MTN", "Airtel", "Glo", "9mobile", "Huawei", "Ericsson", "Nokia", "NCC",
]

# Regex patterns for NCC regulation references
_REGULATION_PATTERN = re.compile(r"NCC-\d+|Section\s+\d+", re.IGNORECASE)

# Time window for CO_OCCURRENCE edges (signals must share an entity within this)
_CO_OCCURRENCE_WINDOW = timedelta(hours=72)

# Base risk scores per signal category
_CATEGORY_SCORES: dict[str, float] = {
    "fraud":       1.0,
    "regulatory":  0.8,
    "vendor_risk": 0.7,
    "competitor":  0.3,
    "market":      0.2,
}

# Node type attribute values
_NODE_SIGNAL     = "signal"
_NODE_ENTITY     = "entity"
_ENTITY_COMPANY  = "company"
_ENTITY_REGULATION = "regulation"

# Edge type attribute values
_EDGE_MENTIONS      = "MENTIONS"
_EDGE_CO_OCCURRENCE = "CO_OCCURRENCE"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _signal_id(signal: dict) -> str:
    """
    Stable node ID for a signal: SHA-256 of ``url + title`` (first 16 hex chars).
    Falls back to hashing the full dict repr if both are missing.
    """
    raw = (signal.get("url", "") + signal.get("title", "")).strip()
    if not raw:
        raw = repr(signal)
    return "sig_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _entity_id(entity_name: str) -> str:
    """Stable node ID for an entity (lowercased, spaces → underscores)."""
    return "ent_" + entity_name.lower().replace(" ", "_").replace("-", "_")


def _extract_entities(text: str) -> list[tuple[str, str]]:
    """
    Extract (entity_name, entity_type) pairs from a text string.

    Company names are matched via simple substring search against
    ``_KNOWN_COMPANIES``; regulation references via ``_REGULATION_PATTERN``.

    Returns a deduplicated list of (name, type) tuples.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Company name matching — case-insensitive word-boundary search
    for company in _KNOWN_COMPANIES:
        pattern = re.compile(r"\b" + re.escape(company) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            key = company.upper()
            if key not in seen:
                seen.add(key)
                found.append((company, _ENTITY_COMPANY))

    # Regulation ref matching
    for match in _REGULATION_PATTERN.finditer(text):
        ref = match.group(0).upper().replace("SECTION", "Section")
        if ref not in seen:
            seen.add(ref)
            found.append((ref, _ENTITY_REGULATION))

    return found


def _parse_signal_timestamp(signal: dict) -> Optional[datetime]:
    """
    Parse a timestamp from a signal dict.  Tries common key names and ISO-8601
    format.  Returns ``None`` if no valid timestamp can be extracted.
    """
    for key in ("timestamp", "date", "published_at", "fetched_at", "created_at"):
        raw = signal.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            # Try ISO-8601 with/without timezone
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw[:19], fmt[:len(fmt)])
                except ValueError:
                    continue
    return None


# ── Service class ─────────────────────────────────────────────────────────────


class SignalGraphService:
    """
    In-memory signal correlation graph (NexusGraph pattern).

    Rebuilt fresh on every ``build_signal_graph`` call — no persistence
    required for the hackathon phase.  All methods are synchronous because
    graph construction is CPU-bound and networkx is not async-native.
    """

    # ── 1. Build the DiGraph ──────────────────────────────────────────────────

    def build_signal_graph(self, all_signals: dict) -> "nx.DiGraph":
        """
        Construct a directed signal-entity graph from ``run_all_signals()`` output.

        Parameters
        ----------
        all_signals : dict
            Dict with keys ``"regulatory"``, ``"competitor"``, ``"vendor_risk"``,
            ``"fraud"``, ``"market"`` — each a ``list[dict]`` of signal objects.

        Returns
        -------
        nx.DiGraph
            Nodes carry a ``node_type`` attribute (``"signal"`` or ``"entity"``).
            Signal nodes also carry ``category``, ``title``, ``url``,
            ``base_score``, and ``timestamp``.
            Entity nodes carry ``entity_type`` (``"company"`` or ``"regulation"``).

            Edges carry a ``relationship`` attribute
            (``"MENTIONS"`` or ``"CO_OCCURRENCE"``).

        Notes
        -----
        If networkx is not available, returns an empty ``object()`` placeholder
        and logs a warning.  Callers should treat a non-DiGraph return as an
        empty graph (``find_compound_risks`` handles this gracefully).
        """
        if not _NX_AVAILABLE:
            logger.warning("[SignalGraph] build_signal_graph: networkx unavailable — returning stub")
            return object()  # type: ignore[return-value]

        G: nx.DiGraph = nx.DiGraph()

        # ── Pass 1: Add signal nodes and MENTIONS edges ───────────────────────
        # Track {entity_id: [(signal_id, timestamp)]} for CO_OCCURRENCE pass
        entity_signal_map: dict[str, list[tuple[str, Optional[datetime]]]] = {}

        for category, signals in all_signals.items():
            if not isinstance(signals, list):
                continue
            base_score = _CATEGORY_SCORES.get(category, 0.2)

            for signal in signals:
                if not isinstance(signal, dict):
                    continue

                sig_id    = _signal_id(signal)
                sig_title = signal.get("title", "")
                sig_url   = signal.get("url", "")
                sig_text  = f"{sig_title} {signal.get('snippet', '')} {signal.get('description', '')}"
                sig_ts    = _parse_signal_timestamp(signal)

                # Add or update signal node
                if not G.has_node(sig_id):
                    G.add_node(
                        sig_id,
                        node_type=_NODE_SIGNAL,
                        category=category,
                        title=sig_title,
                        url=sig_url,
                        snippet=signal.get("snippet", signal.get("description", "")),
                        base_score=base_score,
                        timestamp=sig_ts,
                        raw=signal,
                    )

                # Extract entities and add MENTIONS edges
                entities = _extract_entities(sig_text)
                for entity_name, entity_type in entities:
                    ent_id = _entity_id(entity_name)

                    if not G.has_node(ent_id):
                        G.add_node(
                            ent_id,
                            node_type=_NODE_ENTITY,
                            entity_type=entity_type,
                            name=entity_name,
                        )

                    if not G.has_edge(sig_id, ent_id):
                        G.add_edge(sig_id, ent_id, relationship=_EDGE_MENTIONS)

                    # Track for CO_OCCURRENCE pass
                    entity_signal_map.setdefault(ent_id, []).append((sig_id, sig_ts))

        # ── Pass 2: Add CO_OCCURRENCE edges ───────────────────────────────────
        for ent_id, sig_list in entity_signal_map.items():
            if len(sig_list) < 2:
                continue

            for i in range(len(sig_list)):
                for j in range(i + 1, len(sig_list)):
                    sid_a, ts_a = sig_list[i]
                    sid_b, ts_b = sig_list[j]

                    if sid_a == sid_b:
                        continue

                    # Apply 72h window only when both timestamps are available
                    if ts_a is not None and ts_b is not None:
                        if abs((ts_a - ts_b).total_seconds()) > _CO_OCCURRENCE_WINDOW.total_seconds():
                            continue

                    if not G.has_edge(sid_a, sid_b):
                        G.add_edge(
                            sid_a, sid_b,
                            relationship=_EDGE_CO_OCCURRENCE,
                            via_entity=ent_id,
                        )

        logger.info(
            "[SignalGraph] build_signal_graph: %d nodes, %d edges",
            G.number_of_nodes(), G.number_of_edges(),
        )
        return G

    # ── 2. Find compound risks ────────────────────────────────────────────────

    def find_compound_risks(
        self,
        graph: "nx.DiGraph",
        min_signals: int = 2,
    ) -> list[dict]:
        """
        Identify entities with ``min_signals`` or more independent signals
        pointing to them and compute a compound risk score.

        Compound risk score formula::

            raw_score  = sum(base_score for each signal)
            volume_boost = len(signals) ** 1.2
            compound   = (raw_score / len(signals)) * volume_boost

        This rewards signal volume (more independent sources = higher confidence)
        while keeping the per-signal quality contribution proportional.

        Parameters
        ----------
        graph : nx.DiGraph
            Output of ``build_signal_graph``.
        min_signals : int
            Minimum number of distinct signals an entity must have to be
            included (default 2).

        Returns
        -------
        list[dict]
            Each element::

                {
                    "entity":               str,   # display name
                    "entity_type":          str,   # "company" | "regulation"
                    "signal_count":         int,
                    "compound_risk_score":  float,
                    "signals":              list[dict],  # raw signal dicts
                    "risk_narrative":       str,
                }

            Sorted by ``compound_risk_score`` descending.
        """
        if not _NX_AVAILABLE or not isinstance(graph, nx.DiGraph):
            return []

        results: list[dict] = []

        # Iterate over entity nodes only
        entity_nodes = [
            (nid, data)
            for nid, data in graph.nodes(data=True)
            if data.get("node_type") == _NODE_ENTITY
        ]

        for ent_id, ent_data in entity_nodes:
            # Predecessors of an entity node are the signals that MENTION it
            signal_predecessors = [
                (pred, graph.nodes[pred])
                for pred in graph.predecessors(ent_id)
                if graph.nodes[pred].get("node_type") == _NODE_SIGNAL
            ]

            if len(signal_predecessors) < min_signals:
                continue

            # Compute compound risk score
            base_scores = [data.get("base_score", 0.2) for _, data in signal_predecessors]
            n = len(base_scores)
            avg_score    = sum(base_scores) / n
            volume_boost = n ** 1.2
            compound_score = round(avg_score * volume_boost, 4)

            # Build signal dicts for output
            signal_dicts = [
                {
                    "title":    data.get("title", ""),
                    "url":      data.get("url", ""),
                    "snippet":  data.get("snippet", ""),
                    "category": data.get("category", ""),
                    "score":    data.get("base_score", 0.2),
                }
                for _, data in signal_predecessors
            ]

            entity_name = ent_data.get("name", ent_id)
            narrative   = self.generate_risk_narrative(entity_name, signal_dicts)

            results.append({
                "entity":              entity_name,
                "entity_type":         ent_data.get("entity_type", _ENTITY_COMPANY),
                "signal_count":        n,
                "compound_risk_score": compound_score,
                "signals":             signal_dicts,
                "risk_narrative":      narrative,
            })

        results.sort(key=lambda r: r["compound_risk_score"], reverse=True)
        logger.info(
            "[SignalGraph] find_compound_risks: %d entities qualify (min_signals=%d)",
            len(results), min_signals,
        )
        return results

    # ── 3. Generate risk narrative ────────────────────────────────────────────

    def generate_risk_narrative(self, entity: str, signals: list[dict]) -> str:
        """
        Generate a concise 2-sentence human-readable risk narrative.

        Sentence 1 — what is flagged and by how many signals of what types.
        Sentence 2 — combined confidence score and compound risk classification.

        Parameters
        ----------
        entity : str
            Display name of the entity (company or regulation ref).
        signals : list[dict]
            Signal dicts, each with at least a ``"category"`` and ``"score"`` key.

        Returns
        -------
        str
            Two-sentence narrative string.
        """
        n = len(signals)

        # Collect unique signal categories in descending score order
        categories: list[str] = []
        seen_cats: set[str] = set()
        for sig in sorted(signals, key=lambda s: s.get("score", 0.0), reverse=True):
            cat = sig.get("category", "unknown")
            if cat not in seen_cats:
                seen_cats.add(cat)
                categories.append(cat.replace("_", " "))

        # Format category list naturally
        if len(categories) == 1:
            types_str = categories[0]
        elif len(categories) == 2:
            types_str = f"{categories[0]} and {categories[1]}"
        else:
            types_str = ", ".join(categories[:-1]) + f", and {categories[-1]}"

        # Recompute score for the narrative
        base_scores = [s.get("score", 0.2) for s in signals]
        avg_score   = sum(base_scores) / n if n else 0.0
        compound    = round(avg_score * (n ** 1.2), 2)

        sentence_1 = (
            f"{entity} is flagged by {n} independent signal{'s' if n != 1 else ''}: "
            f"{types_str}."
        )
        sentence_2 = (
            f"Combined confidence score of {compound:.2f} — classified as compound risk."
        )
        return f"{sentence_1} {sentence_2}"

    # ── 4. Get high-risk entities ─────────────────────────────────────────────

    def get_high_risk_entities(
        self,
        graph: "nx.DiGraph",
        threshold: float = 0.6,
    ) -> list[dict]:
        """
        Return compound risks with ``compound_risk_score >= threshold``,
        sorted by score descending.

        Parameters
        ----------
        graph : nx.DiGraph
            Output of ``build_signal_graph``.
        threshold : float
            Minimum compound risk score to include (default 0.6).

        Returns
        -------
        list[dict]
            Filtered and sorted subset of ``find_compound_risks()`` output.
        """
        all_risks = self.find_compound_risks(graph)
        high_risk = [r for r in all_risks if r["compound_risk_score"] >= threshold]

        logger.info(
            "[SignalGraph] get_high_risk_entities: %d/%d entities above threshold=%.2f",
            len(high_risk), len(all_risks), threshold,
        )
        return high_risk


# ── Module-level singleton ────────────────────────────────────────────────────

signal_graph_service = SignalGraphService()
"""
Shared ``SignalGraphService`` singleton.

Usage in agents and routes::

    from services.signal_graph import signal_graph_service

    graph = signal_graph_service.build_signal_graph(all_signals)
    risks = signal_graph_service.get_high_risk_entities(graph, threshold=0.6)
"""
