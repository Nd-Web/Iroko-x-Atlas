"""Opt-in search discovery. Only fixed public topic labels leave Iroko.

Search results are pointers, never legal evidence. The research service must
fetch their approved official URLs before any text reaches the answer pipeline.
"""
import asyncio
import re
import time
from collections import OrderedDict

from ingestion.sources import official_url
from services.brightdata import bright_data_client

DOMAINS = {
    "CBN": "cbn.gov.ng", "SEC": "sec.gov.ng", "NDPC": "ndpc.gov.ng",
    "NDIC": "ndic.gov.ng", "NFIU": "nfiu.gov.ng", "FCCPC": "fccpc.gov.ng",
}
DEFAULT_TOPICS = {
    "CBN": "financial institutions", "SEC": "capital market",
    "NDPC": "data protection", "NDIC": "deposit insurance",
    "NFIU": "anti money laundering", "FCCPC": "consumer protection",
}
# Match known concepts locally; never pass through arbitrary words, names,
# account numbers, copied document text, dates, URLs or user instructions.
TOPIC_LABELS = (
    (r"\b(mfb|microfinance)\b", "microfinance banks"),
    (r"\b(fintech|payments?|psp|mobile money)\b", "fintech"),
    (r"\b(aml|cft|kyc|bvn|money laundering|suspicious)\b", "AML CFT KYC"),
    (r"\b(privacy|ndpa|data protection|data breach)\b", "data protection"),
    (r"\b(capital|prudential|liquidity)\b", "capital prudential requirements"),
    (r"\b(penalt\w*|fines?|sanctions?|enforcement)\b", "penalties sanctions"),
    (r"\b(cyber\w*|security)\b", "cybersecurity"),
    (r"\b(licen[cs]\w*|registration)\b", "licensing registration"),
)
_cache = OrderedDict()  # Generic public discovery only, never prompts or answers.
CACHE_TTL = 600
FAILURE_TTL = 30


def public_query(regulator, question):
    """Construct from our vocabulary, not by redacting or rewriting user text."""
    labels = [label for pattern, label in TOPIC_LABELS if re.search(pattern, question, re.I)]
    topic = " ".join(labels[:2]) or DEFAULT_TOPICS[regulator]
    # Prefer actual published instruments over homepages/news. The parallel
    # catalogue path still discovers HTML notices and other official material.
    return f"site:{DOMAINS[regulator]} {topic} filetype:pdf"


async def discover(regulator, question):
    """One bounded API call per regulator; callers select at most three regulators."""
    check = {"provider": "brightdata", "regulator": regulator, "status": "disabled"}
    client = bright_data_client
    try:
        if not client.config.BRIGHTDATA_REGULATORY_SEARCH_ENABLED:
            return {"candidates": [], "check": check}
        if not client.serp_configured:
            return {"candidates": [], "check": {**check, "status": "unconfigured"}}
    except Exception as error:
        return {"candidates": [], "check": {**check, "status": "unavailable", "failure_type": type(error).__name__}}
    query = public_query(regulator, question)
    cached = _cache.get(query)
    if cached:
        created, ttl, result = cached
        if time.monotonic() - created < ttl:
            _cache.move_to_end(query)
            return {"candidates": list(result["candidates"]), "check": {**result["check"], "cached": True}}
        del _cache[query]
    try:
        # No nested retries: provider timeouts must not consume the entire chat budget.
        results = await asyncio.wait_for(client.serp_search(
            # Regulator domains establish jurisdiction; don't require a Nigerian
            # search-engine location/proxy for public Nigerian documents.
            query, country="", num_results=10, timeout_seconds=12, max_attempts=1,
        ), timeout=13)
        candidates, seen = [], set()
        for item in results[:10]:
            try:
                url = official_url(item.get("url", ""), regulator)
            except (ValueError, TypeError, AttributeError):
                continue
            if url in seen:
                continue
            seen.add(url)
            title = item.get("title", "")
            candidates.append({"url": url, "title": title[:500] if isinstance(title, str) else ""})
        # Snippets, knowledge panels and provider-generated answers are discarded.
        result = {"candidates": candidates, "check": {
            **check, "status": "checked", "result_count": len(candidates),
            "provider_result_count": len(results), "cached": False,
        }}
        ttl = CACHE_TTL
        if results and not candidates:
            result["check"].update(status="unavailable", failure_type="NoOfficialResults")
            ttl = FAILURE_TTL
    except Exception as error:
        # Never copy provider response bodies (or credentials) into chat or logs.
        result = {"candidates": [], "check": {
            **check, "status": "unavailable", "failure_type": type(error).__name__,
        }}
        status = getattr(error, "status_code", None)
        if isinstance(status, int):
            result["check"]["http_status"] = status
        ttl = FAILURE_TTL
    _cache[query] = (time.monotonic(), ttl, result)
    while len(_cache) > 128:
        _cache.popitem(last=False)
    return result
