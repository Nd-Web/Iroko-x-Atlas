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
_ENTITY_ALIASES: dict[str, dict[str, Any]] = {
    # ── Vendors / partners ────────────────────────────────────────────────
    "ihs":                {"name": "IHS Nigeria", "type": "vendor"},
    "ihs towers":         {"name": "IHS Nigeria", "type": "vendor"},
    "ihs nigeria":        {"name": "IHS Nigeria", "type": "vendor"},
    "ericsson":           {"name": "Ericsson", "type": "vendor"},
    "huawei":             {"name": "Huawei", "type": "vendor"},
    "nokia":              {"name": "Nokia", "type": "vendor"},
    "zte":                {"name": "ZTE", "type": "vendor"},
    "american tower":     {"name": "ATC Nigeria", "type": "vendor"},
    "atc":                {"name": "ATC Nigeria", "type": "vendor"},
    "mtn":                {"name": "MTN Nigeria", "type": "vendor"},
    "airtel":             {"name": "Airtel Nigeria", "type": "vendor"},
    "glo":                {"name": "Globacom", "type": "vendor"},
    "globacom":           {"name": "Globacom", "type": "vendor"},
    "9mobile":            {"name": "9mobile", "type": "vendor"},
    "zenith bank":        {"name": "Zenith Bank", "type": "vendor"},

    # ── Regulators ────────────────────────────────────────────────────────
    "ncc":                {"name": "NCC", "type": "regulator"},
    "nigerian communications commission": {"name": "NCC", "type": "regulator"},
    "ndpc":               {"name": "NDPC", "type": "regulator"},
    "nigeria data protection commission": {"name": "NDPC", "type": "regulator"},
    "fccpc":              {"name": "FCCPC", "type": "regulator"},
    "cbn":                {"name": "CBN", "type": "regulator"},

    # ── Regulations / frameworks ──────────────────────────────────────────
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

    # ── Locations / clusters ──────────────────────────────────────────────
    "ikeja":              {"name": "Ikeja Cluster", "type": "location"},
    "lagos":              {"name": "Lagos", "type": "location"},
    "abuja":              {"name": "Abuja", "type": "location"},
    "kano":               {"name": "Kano", "type": "location"},
    "kaduna":             {"name": "Kaduna", "type": "location"},
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
