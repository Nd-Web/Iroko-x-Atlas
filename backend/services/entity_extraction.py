"""
services/entity_extraction.py — telecom-aware entity extraction for the
knowledge graph.

Lightweight, deterministic (regex/alias) extraction that runs at ingestion
time over document text. No LLM call — fast, free, and predictable — which
matters because it runs inside the upload pipeline.

Entity types: vendor | regulator | regulation | location | department
"""
from __future__ import annotations

import re
from typing import Any

# Alias map → canonical entity. Extend freely; matching is case-insensitive
# on word boundaries.
# Telecom-only universe: infrastructure vendors, network operators, telecom &
# data-protection regulators, telecom regulations, and Nigerian network sites.
# Deliberately excludes financial-sector entities (banks, CBN) so the graph
# stays purely telecom.
_ENTITY_ALIASES: dict[str, dict[str, Any]] = {
    # ── Infrastructure vendors / partners ─────────────────────────────────
    "ihs":                {"name": "IHS Nigeria", "type": "vendor"},
    "ihs towers":         {"name": "IHS Nigeria", "type": "vendor"},
    "ihs nigeria":        {"name": "IHS Nigeria", "type": "vendor"},
    "ericsson":           {"name": "Ericsson", "type": "vendor"},
    "huawei":             {"name": "Huawei", "type": "vendor"},
    "nokia":              {"name": "Nokia", "type": "vendor"},
    "zte":                {"name": "ZTE", "type": "vendor"},
    "american tower":     {"name": "ATC Nigeria", "type": "vendor"},
    "atc":                {"name": "ATC Nigeria", "type": "vendor"},
    "julius berger":      {"name": "Julius Berger", "type": "vendor"},
    "ikeja electric":     {"name": "Ikeja Electric", "type": "vendor"},
    "ikedc":              {"name": "Ikeja Electric", "type": "vendor"},

    # ── Network operators (MTN + competitors) ─────────────────────────────
    "mtn":                {"name": "MTN Nigeria", "type": "operator"},
    "airtel":             {"name": "Airtel Nigeria", "type": "operator"},
    "glo":                {"name": "Globacom", "type": "operator"},
    "globacom":           {"name": "Globacom", "type": "operator"},
    "9mobile":            {"name": "9mobile", "type": "operator"},

    # ── Telecom & data-protection regulators ──────────────────────────────
    "ncc":                {"name": "NCC", "type": "regulator"},
    "nigerian communications commission": {"name": "NCC", "type": "regulator"},
    "ndpc":               {"name": "NDPC", "type": "regulator"},
    "nigeria data protection commission": {"name": "NDPC", "type": "regulator"},
    "fccpc":              {"name": "FCCPC", "type": "regulator"},
    "nimc":               {"name": "NIMC", "type": "regulator"},

    # ── Telecom regulations / frameworks ──────────────────────────────────
    "ndpa":               {"name": "NDPA 2023", "type": "regulation"},
    "ndpr":               {"name": "NDPA 2023", "type": "regulation"},
    "data protection act": {"name": "NDPA 2023", "type": "regulation"},
    "nca 2003":           {"name": "NCA 2003", "type": "regulation"},
    "nigerian communications act": {"name": "NCA 2003", "type": "regulation"},
    "qos":                {"name": "NCC QoS Rules", "type": "regulation"},
    "quality of service": {"name": "NCC QoS Rules", "type": "regulation"},
    "consumer code":      {"name": "Consumer Code of Practice", "type": "regulation"},
    "sim registration":   {"name": "SIM Registration Regs", "type": "regulation"},
    "nin-sim":            {"name": "SIM Registration Regs", "type": "regulation"},
    "type approval":      {"name": "Type Approval Regs", "type": "regulation"},
    "gaid":               {"name": "GAID 2025", "type": "regulation"},
    "sla":                {"name": "SLA", "type": "regulation"},

    # ── Network locations / clusters ──────────────────────────────────────
    "ikeja":              {"name": "Ikeja Cluster", "type": "location"},
    "lagos":              {"name": "Lagos", "type": "location"},
    "abuja":              {"name": "Abuja", "type": "location"},
    "kano":               {"name": "Kano", "type": "location"},
    "kaduna":             {"name": "Kaduna", "type": "location"},
    "oregun":             {"name": "Oregun", "type": "location"},
    "port harcourt":      {"name": "Port Harcourt", "type": "location"},
}

# Pre-compile one pattern per alias (word-boundary, case-insensitive).
_PATTERNS: list[tuple[re.Pattern, dict[str, Any]]] = [
    (re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE), meta)
    for alias, meta in _ENTITY_ALIASES.items()
]


def extract_entities(text: str, max_chars: int = 12000) -> list[dict[str, Any]]:
    """
    Extract canonical telecom entities from text.

    Returns a deduped list of {"name", "type", "mentions"} sorted by mention
    count (most-mentioned first).
    """
    if not text:
        return []
    sample = text[:max_chars]

    counts: dict[str, dict[str, Any]] = {}
    for pattern, meta in _PATTERNS:
        n = len(pattern.findall(sample))
        if n:
            key = meta["name"]
            if key in counts:
                counts[key]["mentions"] += n
            else:
                counts[key] = {"name": meta["name"], "type": meta["type"], "mentions": n}

    return sorted(counts.values(), key=lambda e: -e["mentions"])


def entity_id(name: str) -> str:
    """Stable slug id for an entity node."""
    return "ent_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
