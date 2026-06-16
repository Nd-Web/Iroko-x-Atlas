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


# ── Mock fallback data (used when Bright Data is unavailable) ─────────────────

def _mock_signals() -> dict[str, Any]:
    """
    Return realistic Kuda MFB-context signals for use when Bright Data is
    unreachable (e.g. carrier IP blacklisted, no connectivity, quota exhausted).
    Marked with mock=True so the frontend can show an indicator.
    """
    ts = _now_iso()
    return {
        "mock": True,
        "regulatory": [
            {
                "source": "cbn.gov.ng",
                "title": "CBN Circular: Revised KYC/AML Requirements for Microfinance Banks (2026)",
                "summary": "The Central Bank of Nigeria has issued updated KYC and AML guidelines requiring all MFBs to implement real-time BVN verification at onboarding. Effective date: Q3 2026.",
                "url": "https://www.cbn.gov.ng/Out/2026/FPRD/CBN%20Circular%20KYC%20MFB%202026.pdf",
                "fetched_at": ts,
                "signal_type": "regulatory",
                "risk_level": "HIGH",
            },
            {
                "source": "sec.gov.ng",
                "title": "SEC Nigeria: New Capital Adequacy Rules for Digital Lenders",
                "summary": "SEC released new minimum capital requirements for digital-only lenders. MFBs with deposit liabilities above ₦5bn must maintain a 12% capital adequacy ratio.",
                "url": "https://www.sec.gov.ng/news/capital-adequacy-digital-lenders-2026",
                "fetched_at": ts,
                "signal_type": "regulatory",
                "risk_level": "HIGH",
            },
            {
                "source": "cbn.gov.ng",
                "title": "CBN PSSP Licence Renewal: Compliance Checklist Published",
                "summary": "CBN has published the 2026 Payment Service Solution Provider renewal checklist. Institutions must resubmit cybersecurity audit reports and data residency attestations by 31 August 2026.",
                "url": "https://www.cbn.gov.ng/supervisory/pssp-renewal-2026",
                "fetched_at": ts,
                "signal_type": "regulatory",
                "risk_level": "MEDIUM",
            },
            {
                "source": "nfiu.gov.ng",
                "title": "NFIU: Suspicious Transaction Reporting Threshold Lowered to ₦1m",
                "summary": "The Nigerian Financial Intelligence Unit has lowered the STR threshold for digital wallets from ₦5m to ₦1m effective immediately, citing increased smurfing activity.",
                "url": "https://www.nfiu.gov.ng/index.php/news/str-threshold-update-2026",
                "fetched_at": ts,
                "signal_type": "regulatory",
                "risk_level": "HIGH",
            },
            {
                "source": "cbn.gov.ng",
                "title": "CBN Open Banking Framework Phase 2 — API Standards Released",
                "summary": "Phase 2 of the CBN Open Banking Framework mandates that all Tier-1 and Tier-2 banks expose read APIs for account data by December 2026. MFBs must comply by March 2027.",
                "url": "https://www.cbn.gov.ng/open-banking/phase2-standards",
                "fetched_at": ts,
                "signal_type": "regulatory",
                "risk_level": "MEDIUM",
            },
        ],
        "competitor": [
            {
                "competitor": "Moniepoint MFB",
                "title": "Moniepoint Cuts POS Transaction Fees to 0.3% — Below Industry Floor",
                "snippet": "Moniepoint has slashed its POS transaction fee to 0.3%, undercutting rivals by 40%. The move follows its latest Series C raise and targets SME merchants currently on Kuda Business.",
                "url": "https://techcabal.com/2026/05/moniepoint-fee-cut",
                "fetched_at": ts,
                "signal_type": "competitor",
            },
            {
                "competitor": "Carbon MFB",
                "title": "Carbon Launches Salary Advance Product Targeting Kuda's Core Demographic",
                "snippet": "Carbon's new SalaryNow product offers same-day salary advances to salaried employees at 2% flat fee, directly competing with Kuda's overdraft feature.",
                "url": "https://techcabal.com/2026/06/carbon-salarynow-launch",
                "fetched_at": ts,
                "signal_type": "competitor",
            },
            {
                "competitor": "OPay Nigeria",
                "title": "OPay Acquires MFB Licence — Set to Launch Savings Products",
                "snippet": "OPay has received full MFB approval from CBN. The move signals direct entry into the savings and fixed-deposit space, encroaching on Kuda's primary value proposition.",
                "url": "https://businessday.ng/fintech/article/opay-mfb-licence-2026",
                "fetched_at": ts,
                "signal_type": "competitor",
            },
            {
                "competitor": "Fairmoney MFB",
                "title": "FairMoney Raises $42m Series C, Plans to Triple Loan Book",
                "snippet": "FairMoney's new raise will fund aggressive loan origination targeting employed Nigerians earning ₦100k–₦500k/month — the same segment Kuda targets with its overdraft and bill payment features.",
                "url": "https://disrupt-africa.com/2026/05/fairmoney-series-c",
                "fetched_at": ts,
                "signal_type": "competitor",
            },
        ],
        "vendor_risk": [
            {
                "vendor": "Interswitch Nigeria",
                "risk_type": "MEDIUM",
                "title": "Interswitch NIBSS Gateway Intermittent Outage — 4-Hour Disruption",
                "snippet": "Interswitch's NIBSS gateway experienced a 4-hour outage on June 10th, impacting settlement for 23 MFBs. Post-incident report cites configuration drift after a routine patch.",
                "url": "https://techpoint.africa/2026/06/interswitch-outage-mfbs",
                "fetched_at": ts,
                "signal_type": "vendor_risk",
            },
            {
                "vendor": "Flutterwave Nigeria",
                "risk_type": "HIGH",
                "title": "Flutterwave Under CBN Investigation for FX Compliance Breach",
                "snippet": "CBN has opened a formal investigation into Flutterwave's FX practices following a whistleblower complaint. Institutions using Flutterwave for FX settlement should review exposure.",
                "url": "https://businessday.ng/financial-services/article/flutterwave-cbn-probe-2026",
                "fetched_at": ts,
                "signal_type": "vendor_risk",
            },
            {
                "vendor": "CRC Credit Bureau",
                "risk_type": "MEDIUM",
                "title": "CRC Credit Bureau Data Quality Audit Finds 12% Error Rate",
                "snippet": "An independent audit commissioned by CBN found a 12% error rate in CRC Credit Bureau consumer records, predominantly affecting low-income borrowers. Institutions relying on CRC scores for loan decisioning should apply additional verification.",
                "url": "https://www.cbn.gov.ng/Out/2026/CRC-audit-findings.pdf",
                "fetched_at": ts,
                "signal_type": "vendor_risk",
            },
        ],
        "fraud": [
            {
                "title": "EFCC Arrests 47 in Coordinated Account Takeover Ring Targeting MFBs",
                "snippet": "The EFCC dismantled a syndicate that used BVN spoofing and social engineering to take over 1,200+ MFB accounts across Lagos and Abuja. Kuda was among the five MFBs named in the incident report.",
                "url": "https://efcc.gov.ng/news/account-takeover-ring-2026",
                "risk_level": "HIGH",
                "fetched_at": ts,
                "signal_type": "fraud",
            },
            {
                "title": "CBN Issues Alert: New SIM-Swap Fraud Variant Bypassing OTP",
                "snippet": "A new SIM-swap technique using insider telco access has been observed bypassing standard OTP verification. CBN recommends MFBs implement device binding and biometric step-up for high-value transfers.",
                "url": "https://www.cbn.gov.ng/Out/2026/FPRD/SIM-swap-fraud-alert.pdf",
                "risk_level": "HIGH",
                "fetched_at": ts,
                "signal_type": "fraud",
            },
            {
                "title": "Ponzi Operators Exploiting MFB Account Opening Loopholes — NDIC Warning",
                "snippet": "The NDIC has warned that unlicensed investment schemes are using anonymous MFB accounts to receive and funnel funds. Affected MFBs face regulatory sanctions if KYC gaps are not closed within 60 days.",
                "url": "https://www.ndic.org.ng/news/ponzi-mfb-warning-2026",
                "risk_level": "HIGH",
                "fetched_at": ts,
                "signal_type": "fraud",
            },
        ],
        "market": [
            {
                "title": "Nigeria Digital Banking Users to Reach 48m by End of 2026 — EFInA Report",
                "snippet": "EFInA projects Nigeria's digital banking user base will hit 48 million by December 2026, with MFBs capturing 60% of net-new accounts as traditional banks struggle with branch costs.",
                "url": "https://efina.org.ng/publication/digital-banking-report-2026",
                "fetched_at": ts,
                "signal_type": "market",
            },
            {
                "title": "CBN Open Banking API Sandbox Now Live — 14 MFBs Onboarded",
                "snippet": "CBN's Open Banking sandbox has gone live with 14 MFBs including Kuda, Moniepoint, and Carbon. Third-party developers can now test account-information and payment-initiation APIs.",
                "url": "https://www.cbn.gov.ng/open-banking/sandbox-launch-2026",
                "fetched_at": ts,
                "signal_type": "market",
            },
            {
                "title": "Interswitch NQRP QR Standard Adopted by CBN — All MFBs Must Comply by Q4",
                "snippet": "CBN has mandated adoption of the Nigeria Quick Response Payment (NQRP) standard across all licensed MFBs by Q4 2026. Non-compliant institutions face licence suspension.",
                "url": "https://techcabal.com/2026/06/nqrp-mandate-mfbs",
                "fetched_at": ts,
                "signal_type": "market",
            },
            {
                "title": "Inflation Impact: MFB Loan Default Rate Rises to 8.4% — CBN Stability Report",
                "snippet": "CBN's mid-year financial stability report shows MFB NPL ratio climbed from 6.1% to 8.4% in H1 2026, driven by consumer loan stress in the ₦50k–₦200k bracket.",
                "url": "https://www.cbn.gov.ng/Out/2026/stability-report-h1.pdf",
                "fetched_at": ts,
                "signal_type": "market",
            },
        ],
        "collected_at": ts,
    }

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_SIGNALS_PER_TYPE = 68

_DEFAULT_COMPETITORS: list[str] = [
    "Carbon MFB",
    "Moniepoint MFB",
    "OPay Nigeria",
    "Fairmoney MFB",
]

_DEFAULT_VENDORS: list[str] = [
    "Interswitch Nigeria",
    "Flutterwave Nigeria",
    "CRC Credit Bureau",
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
    Collect live CBN/SEC regulatory signals via **Bright Data SERP API** and
    **Web Unlocker**.

    Sources queried:
      - SERP: ``"CBN Nigeria fintech regulations 2026"`` (country=ng)
      - SERP: ``"CBN Nigeria regulatory update site:cbn.gov.ng"`` (country=ng)
      - Web Unlocker fetch of ``https://www.cbn.gov.ng/supervisory/institution.asp``
        with JS rendering enabled.

    Returns
    -------
    list[dict]
        Each item::

            {
                "source": str,       # e.g. "cbn.gov.ng"
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
            query="CBN Nigeria fintech regulations 2026",
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
            query="CBN Nigeria regulatory update site:cbn.gov.ng",
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

    # ── Web Unlocker: CBN supervisory institutions page ────────────────────────
    try:
        page = await client.fetch_url(
            "https://www.cbn.gov.ng/supervisory/institution.asp",
            render_js=True,
        )
        # Emit the page as a single signal; downstream agents parse the HTML
        if page.get("status") == 200 and page.get("content"):
            signals.append({
                "source": "cbn.gov.ng",
                "title": "CBN Supervisory Institutions (live page)",
                "summary": page["content"][:300].strip(),
                "url": "https://www.cbn.gov.ng/supervisory/institution.asp",
                "fetched_at": page.get("fetched_at", fetched_at),
                "signal_type": "regulatory",
            })
            logger.info("[WebIntel] Regulatory Web Unlocker: CBN supervisory page fetched")
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
        Override the default list of Nigerian fintech competitors.

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
    Detect active fintech fraud and enforcement events via **Bright Data SERP API**.

    Three query perspectives are used to maximise coverage:
      1. Account takeover / BVN fraud trends
      2. Fintech-level breach / security incidents
      3. CBN enforcement actions and fines

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
        "Nigeria fintech fraud account takeover BVN 2026",
        "Kuda Carbon Moniepoint fraud breach security 2026",
        "CBN enforcement action fine 2026 fintech microfinance",
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
      1. Fintech / open banking policy developments
      2. CBN/SEC tenders, RFPs, and regulatory procurement notices
      3. Job-posting signals (a leading indicator of fintech expansion in Nigeria)

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
        "Nigeria fintech market 2026 open banking CBN",
        "CBN SEC Nigeria tender RFP regulatory framework 2026",
        "Africa fintech job postings Interswitch Flutterwave 2026",
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
        print(snapshot["regulatory"])   # live CBN/SEC signals
        print(snapshot["competitor"])   # competitor moves
    """
    bd = client or bright_data_client
    collected_at = _now_iso()

    # Quick connectivity probe — if Bright Data is unreachable (e.g. carrier IP
    # blacklisted) skip the full gather and return mock data immediately so the
    # UI always shows signals instead of an empty/error state.
    try:
        await bd.health_check()
    except Exception as probe_exc:
        logger.warning(
            "[WebIntel] Bright Data health check failed (%s). "
            "Returning mock signal data.",
            probe_exc,
        )
        return _mock_signals()

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

    # If every collector came back empty (all failed), fall back to mock data
    # rather than showing a blank dashboard.
    if total == 0:
        logger.warning("[WebIntel] All collectors returned empty. Falling back to mock data.")
        return _mock_signals()

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
