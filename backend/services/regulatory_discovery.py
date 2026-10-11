"""Opt-in search discovery. Only public regulatory vocabulary leaves Iroko.

The query is built from the regulatory words and phrases the question itself
uses ("agent banking", "cash-out limits", "data breach"), taken from a fixed
vocabulary, plus years. Anything outside that vocabulary (names, companies,
numbers, amounts, emails, links, instructions) never reaches the search engine.

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
# Public regulatory vocabulary a question may contribute to a search, longest phrases first.
# Selection, never redaction: a word reaches the search engine only if it is listed here.
PHRASES = (
    "anti money laundering", "know your customer", "customer due diligence", "enhanced due diligence",
    "politically exposed persons", "politically exposed person", "beneficial ownership", "targeted financial sanctions",
    "suspicious transaction", "currency transaction", "terrorist financing", "terrorism financing",
    "proliferation financing", "money laundering", "data protection", "data breach", "data subject", "data controller",
    "data processor", "cross border", "consumer protection", "deposit insurance", "credit bureau", "credit reporting",
    "corporate governance", "risk management", "business continuity", "whistle blowing", "regulatory sandbox",
    "open banking", "agent banking", "mobile money", "digital lending", "consumer lending", "payment service bank",
    "payment service banks", "payment service provider", "payment service providers", "payment terminal",
    "point of sale", "merchant acquiring", "switching and processing", "money transfer", "foreign exchange",
    "bureau de change", "virtual assets", "digital assets", "minimum capital", "capital adequacy",
    "liquidity ratio", "single obligor", "cash out", "cash withdrawal", "transaction limits", "transaction limit",
    "account opening", "dormant accounts", "unclaimed balances", "instant payments", "electronic payments",
    "card scheme", "financial inclusion", "audited financial statements", "financial statements",
    "annual returns", "monthly returns", "license renewal", "licence renewal", "fit and proper", "board appraisal",
    "chief compliance officer", "compliance officer", "internal audit", "external auditor", "information security",
    "cyber security", "incident reporting", "third party", "service level", "global standing instruction",
    "e money",
)
WORDS = {
    "aml", "cft", "cpf", "kyc", "cdd", "edd", "bvn", "nin", "pep", "peps", "str", "strs", "ctr", "ctrs", "ftr",
    "mfb", "mfbs", "psb", "psbs", "psp", "psps", "pssp", "ptsp", "ptsa", "mmo", "mmos", "imto", "imtos", "bdc", "bdcs",
    "ofi", "ofis", "dmb", "dmbs", "dfi", "dfis", "pmb", "pmbs", "ndpa", "gaid", "dpia", "dpo", "ifrs", "bofia",
    "cama", "mlppa", "tppa", "ussd", "pos", "atm", "nip", "nibss", "enaira", "gsi", "api", "apis", "otp", "fx", "vasp",
    "microfinance", "fintech", "fintechs", "payments", "payment", "remittance", "remittances", "wallet", "wallets",
    "lending", "loan", "loans", "credit", "deposit", "deposits", "savings", "account", "accounts", "tier", "tiers",
    "capital", "recapitalisation", "recapitalization", "liquidity", "prudential", "provisioning", "impairment",
    "licence", "license", "licensing", "licensed", "registration", "renewal", "approval", "permit",
    "penalty", "penalties", "fine", "fines", "sanction", "sanctions", "enforcement", "revocation", "suspension",
    "breach", "breaches", "contravention", "infraction", "compliance", "regulation", "regulations", "guidelines",
    "guideline", "circular", "circulars", "framework", "directive", "directives", "rules", "act", "code",
    "exposure", "draft", "amendment", "amended", "revised", "repeal", "returns", "rendition", "reporting",
    "deadline", "timeline", "disclosure", "governance", "board", "directors", "shareholding", "ownership",
    "audit", "auditor", "outsourcing", "cloud", "cybersecurity", "privacy", "consent", "retention", "records",
    "fraud", "frauds", "forgeries", "complaints", "complaint", "dispute", "disputes", "chargeback", "refund",
    "charges", "fees", "tariff", "interest", "agent", "agents", "agency", "merchant", "merchants", "terminal",
    "terminals", "card", "cards", "transfer", "transfers", "cashless", "cash", "limits", "limit", "threshold",
    "interoperability", "settlement", "clearing", "switching", "crypto", "cryptocurrency", "stablecoin",
    "sandbox", "insurance", "terrorism", "proliferation", "whistleblowing", "training", "inclusion",
}
# The search runs inside the regulator's own site; naming the regulator again only narrows it.
_REGULATOR_WORDS = {"cbn", "sec", "ndpc", "ndic", "nfiu", "fccpc", "central", "bank", "nigeria", "nigerian"}
_NOT_WORDS = re.compile(r"\S+@\S+|https?://\S+|www\.\S+|\b[\w-]+\.(?:com|ng|org|net|gov|io|example)\b\S*", re.I)
_cache = OrderedDict()  # Generic public discovery only, never prompts or answers.
CACHE_TTL = 600
FAILURE_TTL = 30


def search_terms(question, limit=6):
    """The question's public regulatory terms, in its own order: phrases, listed words and years."""
    text = " " + re.sub(r"[^a-z0-9]+", " ", _NOT_WORDS.sub(" ", question or "").lower()) + " "
    found = []
    for phrase in sorted(PHRASES, key=len, reverse=True):
        if f" {phrase} " in text:
            found.append((text.index(f" {phrase} "), phrase))
            text = text.replace(f" {phrase} ", " " + " " * len(phrase) + " ")
    for match in re.finditer(r"[a-z]+|\d+", text):
        token = match.group()
        if token in WORDS or (token.isdigit() and len(token) == 4 and 1990 <= int(token) <= 2039):
            found.append((match.start(), token))
    terms = [term for _, term in sorted(found) if term not in _REGULATOR_WORDS]
    return list(dict.fromkeys(terms))[:limit]


def public_query(regulator, question):
    """Construct from our vocabulary, not by redacting or rewriting user text."""
    terms = search_terms(question)
    if not terms:
        labels = [label for pattern, label in TOPIC_LABELS if re.search(pattern, question, re.I)]
        terms = [" ".join(labels[:2]) or DEFAULT_TOPICS[regulator]]
    # Prefer actual published instruments over homepages/news. The parallel
    # catalogue path still discovers HTML notices and other official material.
    return f"site:{DOMAINS[regulator]} {' '.join(terms)} filetype:pdf"


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
