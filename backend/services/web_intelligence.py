"""
services/web_intelligence.py — Web Intelligence data layer for Iroko AI.
=========================================================================
Provides five domain-specific async signal collectors, each backed by
Bright Data's SERP API and/or Web Unlocker, that agents call in addition to
(or instead of) Azure AI Search when they need live external signals.

Design notes (inspired by Tower's competitor change-detection loop):
  - Each collector runs independently; failures are swallowed with a warning
    so one bad source never crashes the whole pipeline.
  - URL-level deduplication is applied per collector — duplicate URLs that
    surface across multiple SERP queries are collapsed to the first occurrence.
  - Each collector caps output at MAX_SIGNALS_PER_TYPE items to keep the
    agent context window manageable.
  - ``run_all_signals`` fires all five collectors concurrently via
    ``asyncio.gather`` and returns a single composite dict.

Usage::

    from services.web_intelligence import run_all_signals
    from services.brightdata import bright_data_client

    signals = await run_all_signals(bright_data_client)
    regulatory = signals["regulatory"]   # list[dict]
    competitors = signals["competitor"]  # list[dict]
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from services.brightdata import BrightDataClient, bright_data_client

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_SIGNALS_PER_TYPE = 10

_DEFAULT_COMPETITORS: list[str] = [
    "MTN Nigeria",
    "Airtel Nigeria",
    "Glo Mobile",
    "9mobile Nigeria",
]

_DEFAULT_VENDORS: list[str] = [
    "Huawei Nigeria",
    "Ericsson Nigeria",
    "Nokia Networks",
]

# Risk keyword sets used to classify vendor-risk snippets
_HIGH_RISK_KEYWORDS = {"fraud", "breach", "indicted", "arrested", "sanction", "bribery", "corruption"}
_MEDIUM_RISK_KEYWORDS = {"fine", "penalty", "investigation", "probe", "departure", "resign", "lawsuit"}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _deduplicate(signals: list[dict[str, Any]], url_key: str = "url") -> list[dict[str, Any]]:
    """
    Remove duplicate signals that share the same URL.

    Only the first occurrence of each URL is kept; subsequent entries for the
    same URL are dropped and a debug log is emitted.

    Parameters
    ----------
    signals : list[dict]
        Raw list of signal dicts (may contain duplicates).
    url_key : str
        The dict key that holds the URL (default ``"url"``).

    Returns
    -------
    list[dict]
        Deduplicated list preserving original insertion order.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in signals:
        url = item.get(url_key, "")
        if url and url in seen:
            logger.debug("[WebIntel] Deduplication: dropped repeated URL %s", url)
            continue
        if url:
            seen.add(url)
        unique.append(item)
    return unique


def _classify_risk(text: str) -> str:
    """
    Classify a snippet's risk level from its text content.

    Returns ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"`` based on keyword presence.
    """
    lower = text.lower()
    if any(kw in lower for kw in _HIGH_RISK_KEYWORDS):
        return "HIGH"
    if any(kw in lower for kw in _MEDIUM_RISK_KEYWORDS):
        return "MEDIUM"
    return "LOW"


# ── Signal collectors ─────────────────────────────────────────────────────────


async def fetch_regulatory_signals(client: BrightDataClient) -> list[dict[str, Any]]:
    """
    Collect live NCC regulatory signals via **Bright Data SERP API** and
    **Web Unlocker**.

    Sources queried:
      - SERP: ``"NCC Nigeria new regulations 2026"`` (country=ng)
      - SERP: ``"NCC Nigeria regulatory update site:ncc.gov.ng"`` (country=ng)
      - Web Unlocker fetch of ``https://www.ncc.gov.ng/media-centre/news-headlines``
        with JS rendering enabled.

    Returns
    -------
    list[dict]
        Each item::

            {
                "source": str,       # e.g. "ncc.gov.ng"
                "title": str,
                "summary": str,      # snippet or first 300 chars of body
                "url": str,
                "fetched_at": str,   # ISO-8601 UTC
                "signal_type": "regulatory",
            }
    """
    signals: list[dict[str, Any]] = []
    fetched_at = _now_iso()

    # ── SERP pass 1 ──────────────────────────────────────────────────────────
    try:
        results = await client.serp_search(
            query="NCC Nigeria new regulations 2026",
            country="ng",
            num_results=MAX_SIGNALS_PER_TYPE,
        )
        for r in results:
            signals.append({
                "source": _extract_domain(r.get("url", "")),
                "title": r.get("title", ""),
                "summary": r.get("snippet", ""),
                "url": r.get("url", ""),
                "fetched_at": fetched_at,
                "signal_type": "regulatory",
            })
        logger.info("[WebIntel] Regulatory SERP-1: %d results", len(results))
    except Exception as exc:
        logger.warning("[WebIntel] fetch_regulatory_signals SERP-1 failed: %s", exc)

    # ── SERP pass 2 ──────────────────────────────────────────────────────────
    try:
        results2 = await client.serp_search(
            query="NCC Nigeria regulatory update site:ncc.gov.ng",
            country="ng",
            num_results=MAX_SIGNALS_PER_TYPE,
        )
        for r in results2:
            signals.append({
                "source": _extract_domain(r.get("url", "")),
                "title": r.get("title", ""),
                "summary": r.get("snippet", ""),
                "url": r.get("url", ""),
                "fetched_at": fetched_at,
                "signal_type": "regulatory",
            })
        logger.info("[WebIntel] Regulatory SERP-2: %d results", len(results2))
    except Exception as exc:
        logger.warning("[WebIntel] fetch_regulatory_signals SERP-2 failed: %s", exc)

    # ── Web Unlocker: NCC news headlines page ─────────────────────────────────
    try:
        page = await client.fetch_url(
            "https://www.ncc.gov.ng/media-centre/news-headlines",
            render_js=True,
        )
        # Emit the page as a single signal; downstream agents parse the HTML
        if page.get("status") == 200 and page.get("content"):
            signals.append({
                "source": "ncc.gov.ng",
                "title": "NCC News Headlines (live page)",
                "summary": page["content"][:300].strip(),
                "url": "https://www.ncc.gov.ng/media-centre/news-headlines",
                "fetched_at": page.get("fetched_at", fetched_at),
                "signal_type": "regulatory",
            })
            logger.info("[WebIntel] Regulatory Web Unlocker: NCC headlines page fetched")
    except Exception as exc:
        logger.warning("[WebIntel] fetch_regulatory_signals Web Unlocker failed: %s", exc)

    unique = _deduplicate(signals)[:MAX_SIGNALS_PER_TYPE]
    logger.info("[WebIntel] fetch_regulatory_signals → %d unique signals", len(unique))
    return unique


# ─────────────────────────────────────────────────────────────────────────────


async def fetch_competitor_signals(
    client: BrightDataClient,
    competitors: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Collect live competitor pricing and product signals via **Bright Data SERP API**.

    Inspired by Tower's ``dailyCompetitorScan`` loop that sweeps pricing,
    careers, blog, and changelog pages for each tracked competitor. Here we
    focus on SERP-based detection of pricing announcements and product launches.

    For each competitor two queries are fired:
      1. ``"{competitor} pricing announcement 2026"`` (country=ng)
      2. ``"{competitor} new product launch 2026"`` (country=ng)

    Parameters
    ----------
    client : BrightDataClient
        The shared Bright Data client instance.
    competitors : list[str] | None
        Override the default list of Nigerian telecom competitors.

    Returns
    -------
    list[dict]
        Each item::

            {
                "competitor": str,
                "title": str,
                "snippet": str,
                "url": str,
                "signal_type": "competitor",
            }
    """
    targets = competitors or _DEFAULT_COMPETITORS
    signals: list[dict[str, Any]] = []

    async def _scan_competitor(name: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for query_template in [
            "{name} pricing announcement 2026",
            "{name} new product launch 2026",
        ]:
            query = query_template.format(name=name)
            try:
                hits = await client.serp_search(query=query, country="ng", num_results=5)
                for h in hits:
                    results.append({
                        "competitor": name,
                        "title": h.get("title", ""),
                        "snippet": h.get("snippet", ""),
                        "url": h.get("url", ""),
                        "fetched_at": _now_iso(),
                        "signal_type": "competitor",
                    })
                logger.info("[WebIntel] Competitor '%s' query '%s' → %d hits", name, query[:60], len(hits))
            except Exception as exc:
                logger.warning(
                    "[WebIntel] fetch_competitor_signals '%s' query '%s' failed: %s",
                    name, query[:60], exc,
                )
        return results

    # Run all competitor scans concurrently (Tower pattern: gather per-domain scans)
    per_competitor = await asyncio.gather(*[_scan_competitor(c) for c in targets])
    for batch in per_competitor:
        signals.extend(batch)

    unique = _deduplicate(signals)[:MAX_SIGNALS_PER_TYPE]
    logger.info("[WebIntel] fetch_competitor_signals → %d unique signals", len(unique))
    return unique


# ─────────────────────────────────────────────────────────────────────────────


async def fetch_vendor_risk_signals(
    client: BrightDataClient,
    vendor_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Detect vendor risk events via **Bright Data SERP API**.

    Queries for fraud allegations, security breaches, and executive departures
    for each tracked equipment/services vendor. Risk level is auto-classified
    from snippet keywords (HIGH / MEDIUM / LOW).

    Parameters
    ----------
    client : BrightDataClient
        The shared Bright Data client instance.
    vendor_names : list[str] | None
        Override the default vendor watchlist.

    Returns
    -------
    list[dict]
        Each item::

            {
                "vendor": str,
                "risk_type": str,    # derived from snippet keywords
                "title": str,
                "snippet": str,
                "url": str,
                "signal_type": "vendor_risk",
            }
    """
    targets = vendor_names or _DEFAULT_VENDORS
    signals: list[dict[str, Any]] = []

    async def _scan_vendor(name: str) -> list[dict[str, Any]]:
        query = f"{name} fraud allegations OR breach OR executive departure 2026"
        results: list[dict[str, Any]] = []
        try:
            hits = await client.serp_search(query=query, country="ng", num_results=5)
            for h in hits:
                combined_text = f"{h.get('title', '')} {h.get('snippet', '')}"
                results.append({
                    "vendor": name,
                    "risk_type": _classify_risk(combined_text),
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", ""),
                    "url": h.get("url", ""),
                    "fetched_at": _now_iso(),
                    "signal_type": "vendor_risk",
                })
            logger.info("[WebIntel] Vendor '%s' → %d risk signals", name, len(hits))
        except Exception as exc:
            logger.warning("[WebIntel] fetch_vendor_risk_signals '%s' failed: %s", name, exc)
        return results

    per_vendor = await asyncio.gather(*[_scan_vendor(v) for v in targets])
    for batch in per_vendor:
        signals.extend(batch)

    unique = _deduplicate(signals)[:MAX_SIGNALS_PER_TYPE]
    logger.info("[WebIntel] fetch_vendor_risk_signals → %d unique signals", len(unique))
    return unique


# ─────────────────────────────────────────────────────────────────────────────


async def fetch_fraud_signals(client: BrightDataClient) -> list[dict[str, Any]]:
    """
    Detect active telecom fraud and enforcement events via **Bright Data SERP API**.

    Three query perspectives are used to maximise coverage:
      1. SIM-swap / subscriber fraud trends
      2. Operator-level breach / security incidents
      3. NCC enforcement actions and fines

    Risk level is auto-classified from snippet text.

    Returns
    -------
    list[dict]
        Each item::

            {
                "title": str,
                "snippet": str,
                "url": str,
                "risk_level": "HIGH" | "MEDIUM" | "LOW",
                "signal_type": "fraud",
            }
    """
    queries = [
        "Nigeria telecom fraud SIM swap 2026",
        "MTN Nigeria Airtel fraud breach security 2026",
        "NCC enforcement action fine 2026 telecom",
    ]
    signals: list[dict[str, Any]] = []

    async def _run_query(query: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            hits = await client.serp_search(query=query, country="ng", num_results=5)
            for h in hits:
                combined = f"{h.get('title', '')} {h.get('snippet', '')}"
                results.append({
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", ""),
                    "url": h.get("url", ""),
                    "risk_level": _classify_risk(combined),
                    "fetched_at": _now_iso(),
                    "signal_type": "fraud",
                })
            logger.info("[WebIntel] Fraud query '%s' → %d hits", query[:60], len(hits))
        except Exception as exc:
            logger.warning("[WebIntel] fetch_fraud_signals query '%s' failed: %s", query[:60], exc)
        return results

    batches = await asyncio.gather(*[_run_query(q) for q in queries])
    for batch in batches:
        signals.extend(batch)

    unique = _deduplicate(signals)[:MAX_SIGNALS_PER_TYPE]
    logger.info("[WebIntel] fetch_fraud_signals → %d unique signals", len(unique))
    return unique


# ─────────────────────────────────────────────────────────────────────────────


async def fetch_market_intelligence(client: BrightDataClient) -> list[dict[str, Any]]:
    """
    Gather macro market intelligence via **Bright Data SERP API**.

    Three strategic lenses:
      1. 5G / spectrum policy developments
      2. NCC tenders, RFPs, and procurement notices
      3. Job-posting signals (a leading indicator of vendor expansion in Nigeria)

    Returns
    -------
    list[dict]
        Each item::

            {
                "title": str,
                "snippet": str,
                "url": str,
                "signal_type": "market",
            }
    """
    queries = [
        "Nigeria telecom market 2026 5G spectrum",
        "Nigerian Communications Commission tender RFP 2026",
        "Africa telecom job postings Huawei Ericsson 2026",
    ]
    signals: list[dict[str, Any]] = []
    async def _run_query(query: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            # Check if MCP server URL is configured and we should call the MCP tool!
            if client.config.BRIGHTDATA_MCP_SERVER_URL and not client.mock_mode:
                logger.info("[WebIntel] MCP Server URL is configured. Routing live query to Bright Data MCP Server...")
                mcp_res = await client.call_mcp_tool("search_serp", {"query": query, "country": "ng", "num_results": 5})
                # Handle standard MCP return content vs fallback structure
                if isinstance(mcp_res, list):
                    hits = mcp_res
                elif isinstance(mcp_res, dict):
                    hits = mcp_res.get("results", mcp_res.get("content", []))
                    if isinstance(hits, str): # if content was returned as string, parse it
                        try:
                            import json
                            hits = json.loads(hits)
                        except Exception:
                            hits = [{"title": "MCP Result", "snippet": hits, "url": "https://mcp.brightdata.com"}]
                else:
                    hits = []
            else:
                hits = await client.serp_search(query=query, country="ng", num_results=5)
                
            for h in hits:
                results.append({
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", ""),
                    "url": h.get("url", ""),
                    "fetched_at": _now_iso(),
                    "signal_type": "market",
                })
            logger.info("[WebIntel] Market query '%s' → %d hits", query[:60], len(hits))
        except Exception as exc:
            logger.warning("[WebIntel] fetch_market_intelligence query '%s' failed: %s", query[:60], exc)
        return results

    batches = await asyncio.gather(*[_run_query(q) for q in queries])
    for batch in batches:
        signals.extend(batch)

    unique = _deduplicate(signals)[:MAX_SIGNALS_PER_TYPE]
    logger.info("[WebIntel] fetch_market_intelligence → %d unique signals", len(unique))
    return unique


# ── Parallel orchestrator ─────────────────────────────────────────────────────


async def run_all_signals(
    client: BrightDataClient | None = None,
) -> dict[str, Any]:
    """
    Run all five signal collectors **in parallel** and return a consolidated
    intelligence snapshot.

    Modelled on Tower's ``dailyCompetitorScan`` + ``extract-signals`` pattern:
    all domain scans fire concurrently; individual failures never abort the
    overall run — they surface as empty lists in the returned dict.

    Parameters
    ----------
    client : BrightDataClient | None
        The Bright Data client to use. Defaults to the module-level singleton
        ``bright_data_client`` if not provided.

    Returns
    -------
    dict
        ::

            {
                "regulatory":  list[dict],
                "competitor":  list[dict],
                "vendor_risk": list[dict],
                "fraud":       list[dict],
                "market":      list[dict],
                "collected_at": str,   # ISO-8601 UTC
            }

    Example::

        from services.web_intelligence import run_all_signals

        snapshot = await run_all_signals()
        print(snapshot["regulatory"])   # live NCC signals
        print(snapshot["competitor"])   # competitor moves
    """
    bd = client or bright_data_client
    collected_at = _now_iso()

    logger.info("[WebIntel] run_all_signals: launching 5 collectors in parallel")

    (
        regulatory,
        competitor,
        vendor_risk,
        fraud,
        market,
    ) = await asyncio.gather(
        fetch_regulatory_signals(bd),
        fetch_competitor_signals(bd),
        fetch_vendor_risk_signals(bd),
        fetch_fraud_signals(bd),
        fetch_market_intelligence(bd),
        return_exceptions=True,
    )

    results = [regulatory, competitor, vendor_risk, fraud, market]
    names = ["regulatory", "competitor", "vendor_risk", "fraud", "market"]
    cleaned = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.error("[WebIntel] Collector '%s' raised: %s", name, result)
            cleaned.append([])
        else:
            cleaned.append(result)
    regulatory, competitor, vendor_risk, fraud, market = cleaned

    total = len(regulatory) + len(competitor) + len(vendor_risk) + len(fraud) + len(market)
    logger.info(
        "[WebIntel] run_all_signals complete — %d total signals "
        "(regulatory=%d, competitor=%d, vendor_risk=%d, fraud=%d, market=%d)",
        total, len(regulatory), len(competitor), len(vendor_risk), len(fraud), len(market),
    )

    return {
        "regulatory":  regulatory,
        "competitor":  competitor,
        "vendor_risk": vendor_risk,
        "fraud":       fraud,
        "market":      market,
        "collected_at": collected_at,
    }


# ── Utility ───────────────────────────────────────────────────────────────────


def _extract_domain(url: str) -> str:
    """
    Extract the bare domain name from a full URL string.

    Examples::

        _extract_domain("https://www.ncc.gov.ng/media/foo") → "ncc.gov.ng"
        _extract_domain("") → ""
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.netloc or ""
        return host.lstrip("www.")
    except Exception:
        return ""
