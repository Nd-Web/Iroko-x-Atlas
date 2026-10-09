"""Bounded public-regulator research, with optional public-topic search discovery.

Public pages are discovery/evidence, not proof that a rule is in force or that a
customer is compliant. Downloaded page text is untrusted, never instructions.
No customer documents are shared, ingested, or made public by this path.
"""
import asyncio
import hashlib
import logging
import re
import tempfile
import time
from collections import OrderedDict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from ingestion.sources import OfficialClient, official_url, parse_cbn
from services.regulatory_discovery import discover

logger = logging.getLogger(__name__)

# Discovery endpoints, NOT a hardcoded set of regulations or answers.
CATALOGUES = {
    "CBN": ["https://www.cbn.gov.ng/AboutCBN/Reforms.html", "https://www.cbn.gov.ng/api/GetAllCirculars"],
    "SEC": ["https://sec.gov.ng/our-mandate/regulation/rules-and-regulations/"],
    "NDPC": ["https://ndpc.gov.ng/resources/"],
    "NDIC": ["https://ndic.gov.ng/"],
    "NFIU": ["https://nfiu.gov.ng/"],
    "FCCPC": ["https://fccpc.gov.ng/"],
}
TOPICS = {
    "microfinance": ("microfinance", "mfb", "ofis", "ofi"),
    "fintech": ("fintech", "payment", "digital", "mobile money"),
    "capital": ("capital", "prudential", "liquidity"),
    "aml": ("aml", "cft", "kyc", "bvn", "money laundering", "suspicious"),
    "privacy": ("privacy", "data protection", "ndpa", "ndpc", "data breach"),
    "penalty": ("penalt", "fine", "sanction", "enforcement", "revoke", "revocation", "non-compliance"),
}
_cache = OrderedDict()  # Only public fetched text; no query/customer-specific answers.
CACHE_TTL = 600


def mentioned_date(text):
    """Ranking hint only: a mentioned past date is NOT a verified publication date."""
    dates = []
    months = "January February March April May June July August September October November December".split()
    month_names = "|".join(months)
    patterns = [rf"\b(\d{{1,2}})\s+({month_names})\s+(\d{{4}})\b",
                rf"\b({month_names})\s+(\d{{1,2}}),?\s+(\d{{4}})\b"]
    for i, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, re.I):
            a, b, year = match.groups()
            day, month = (a, b) if i == 0 else (b, a)
            try:
                value = datetime(int(year), months.index(month.capitalize()) + 1, int(day), tzinfo=timezone.utc)
                if value <= datetime.now(timezone.utc):
                    dates.append(value.date().isoformat())
            except ValueError:
                continue
    return max(dates, default="")


def eligible(question):
    q = question.lower()
    # A precise source-reading question must remain within that source's boundary.
    if re.search(r"\b(uploaded|attached|letter|spreadsheet|template|circular dated|from the document|in the document)\b", q):
        return False
    return bool(re.search(r"\b(cbn|sec|ndpc|ndpa|nfiu|ndic|fccpc|compliance|regulat\w*|aml|kyc)\b", q))


def freshness_requested(question):
    return bool(re.search(r"\b(latest|recent|newest|current|today|new regulation|new rule)\b", question.lower()))


def needs_internal_records(question):
    q = question.lower()
    return bool(re.search(r"\b(our|my|organisation|organization|this institution|this company|customer|client)\b", q)
                and re.search(r"\b(status|filings?|records?|returns?|ratios?|submitted|compliant|due|audit|exposure|risk)\b", q))


def regulators(question):
    q = question.lower()
    explicit = [reg for reg in CATALOGUES if re.search(r"\b" + reg.lower() + r"\b", q)]
    if explicit:
        return explicit[:3]
    if any(term in q for term in TOPICS["privacy"]):
        return ["NDPC"]
    if any(term in q for term in TOPICS["aml"]):
        return ["CBN", "NFIU"]
    return ["CBN", "NDPC", "SEC"]


def terms(question):
    q = question.lower()
    chosen = set()
    for topic, words in TOPICS.items():
        if any(word in q for word in words):
            chosen.update(words)
    # Broad risk questions should discover obligations and sanctions, not just "latest".
    if not chosen or "risk" in q or "compliance" in q:
        chosen.update(TOPICS["penalty"])
        chosen.update(TOPICS["microfinance"])
        chosen.update(TOPICS["fintech"])
        chosen.update(TOPICS["privacy"])
    return chosen


def relevance(text, words):
    q = text.lower()
    return sum(1 for word in words if word in q)


class PageText(HTMLParser):
    """Preserve visible wording and links; exclude executable/navigation material."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.hidden, self.anchor = [], [], [], None
        self.title, self.in_title = [], False
        self.primary, self.primary_depth = [], 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.hidden:
            if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
                self.hidden.append(tag)
            return
        noise = " ".join([attrs.get("class", ""), attrs.get("id", ""), attrs.get("role", "")])
        if tag in {"script", "style", "svg", "nav", "footer", "header", "aside"} or re.search(
            r"(nav-menu|menu-container|location-header|location-footer|cookie|cky-|modal-check|recent-post|related-post|social-icons|breadcrumb|navigation)", noise, re.I
        ):
            self.hidden.append(tag)
            return
        if tag in {"main", "article"}:
            self.primary_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "a":
            self.anchor = [attrs.get("href", ""), []]
        if tag in {"p", "div", "h1", "h2", "h3", "li", "tr", "br"}:
            self.parts.append("\n")
            if self.primary_depth:
                self.primary.append("\n")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag == "title":
            self.in_title = False
        if tag in {"main", "article"}:
            self.primary_depth = max(0, self.primary_depth - 1)
        if tag == "a" and self.anchor:
            self.links.append((self.anchor[0], " ".join(self.anchor[1])))
            self.anchor = None
        if tag in {"p", "div", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")
            if self.primary_depth:
                self.primary.append("\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title.append(data)
            return
        self.parts.append(data)
        if self.primary_depth:
            self.primary.append(data)
        if self.anchor:
            self.anchor[1].append(data.strip())

    def parsed(self):
        paragraphs = [" ".join(line.split()) for line in "".join(self.primary or self.parts).splitlines()]
        return "\n".join(line for line in paragraphs if line), " ".join(self.title).strip()


async def fetched(client, url):
    url = official_url(url, client.regulator)
    cached = _cache.get(url)
    if cached and time.monotonic() - cached[0] < CACHE_TTL:
        _cache.move_to_end(url)
        return cached[1]
    status, headers, body = await client.fetch(url)
    if status != 200:
        raise ValueError("Official source did not return a successful page")
    checked = datetime.now(timezone.utc).isoformat()
    kind = headers.get("content-type", "").lower()
    if "json" in kind or body.lstrip().startswith(b"["):
        entries = parse_cbn(body, url) if client.regulator == "CBN" else []
        value = {"url": url, "title": "Official circular catalogue", "pages": [],
                 "links": [(item["source_url"], item["title"]) for item in entries],
                 "catalogue_dates": {item["source_url"]: item["published_date"] for item in entries},
                 "checked_at": checked, "sha256": hashlib.sha256(body).hexdigest()}
    elif "pdf" in kind or body.startswith(b"%PDF-"):
        from ingestion.extraction import bounded_native_pages
        with tempfile.TemporaryDirectory(prefix="iroko-public-research-") as directory:
            file = Path(directory) / "source.pdf"
            file.write_bytes(body)
            pages = await asyncio.to_thread(bounded_native_pages, file, "pdf", timeout_seconds=8, max_pages=50)
        # Scanned or garbled pages are not evidence; OCR belongs to the ingestion worker.
        pages = [(p["page_number"], p["text"]) for p in pages
                 if p.get("quality", {}).get("characters", 0) >= 80
                 and p.get("quality", {}).get("bad_character_ratio", 1) <= 0.05]
        value = {"url": url, "title": Path(urlsplit(url).path).name,
                 "pages": pages, "links": [], "checked_at": checked,
                 "sha256": hashlib.sha256(body).hexdigest()}
    elif "html" in kind:
        parser = PageText()
        parser.feed(body.decode("utf-8", errors="replace"))
        text, title = parser.parsed()
        if re.search(r"(just a moment|verify you are human|access denied|captcha)", title, re.I):
            raise ValueError("Official page is blocked")
        value = {"url": url, "title": title or client.regulator,
                 "pages": [(None, text[:80_000])], "links": parser.links[:5000],
                 "checked_at": checked, "sha256": hashlib.sha256(body).hexdigest()}
    else:
        raise ValueError("Unsupported public-source format")
    _cache[url] = (time.monotonic(), value)
    while len(_cache) > 24:
        _cache.popitem(last=False)
    return value


def evidence(page, regulator, words):
    result = []
    for number, text in page["pages"]:
        # Contiguous windows with stable source coordinates. Never combine disjoint quotes.
        for offset in range(0, len(text), 1500):
            block = text[offset:offset + 1800]
            score = relevance(block, words)
            if score < 1 or len(block) < 80:
                continue
            key = hashlib.sha256(f"{page['url']}|{page['sha256']}|{number}|{offset}".encode()).hexdigest()
            result.append({
                "document_id": "public:" + hashlib.sha256(page["url"].encode()).hexdigest()[:24],
                "chunk_id": "public:" + key[:24],
                "title": page["title"], "content": block, "full_document": False,
                "provenance": {"source_url": page["url"], "source_kind": "official_live",
                    "regulator": regulator, "fetched_at": page["checked_at"],
                    "sha256": page["sha256"], "physical_page": number,
                    "text_offset": offset, "legal_applicability_status": "not_assessed"},
                "_relevance": score,
                "_mentioned_date": mentioned_date(block),
            })
    return result


def regulatory_candidate(url, title):
    """Exclude website housekeeping from regulatory discovery, not regulatory acts.

    A regulator's policy for its own website visitors is not a regulated firm's
    obligation. Domain authenticity alone does not make a page a regulatory source.
    """
    path = urlsplit(url).path.lower().rstrip("/")
    label = re.sub(r"[\s_-]+", " ", title.lower()).strip()
    return not (
        path in {"", "/about", "/about-us", "/contact", "/contact-us", "/careers", "/sitemap"}
        or re.search(r"/(?:our[-_])?(?:data[-_])?privacy[-_]policy(?:\.html?)?$|/(?:cookie[-_]policy|terms[-_]of[-_](?:use|service))(?:\.html?)?$", path)
        or label in {"privacy policy", "our privacy policy", "our data privacy policy", "cookie policy", "terms of use", "terms of service"}
    )


async def research(question):
    """At most three regulators, two documents each, and 28 seconds of network/parser work."""
    if not eligible(question):
        return {"sources": [], "checks": [], "discovery_checks": [], "regulators": [],
                "checked_at": datetime.now(timezone.utc).isoformat(), "exhaustive": False}
    selected, words = regulators(question), terms(question)
    sources, checks, discovery_checks = [], [], []
    async def one(regulator):
        client = OfficialClient(regulator, timeout=6, attempts=1, max_bytes=3_000_000)
        candidates = []

        async def catalogues():
            for url in CATALOGUES[regulator]:
                check = {"regulator": regulator, "url": url, "status": "unavailable"}
                checks.append(check)
                try:
                    page = await fetched(client, url)
                    check.update(status="checked", fetched_at=page["checked_at"])
                    sources.extend(evidence(page, regulator, words))
                    for href, title in page["links"]:
                        try:
                            link = official_url(urljoin(url, href), regulator)
                        except (ValueError, TypeError):
                            continue
                        if not regulatory_candidate(link, title):
                            continue
                        score = relevance(title + " " + urlsplit(link).path, words)
                        if score and link != url and not re.search(r"\.(png|jpg|jpeg|css|js|zip)$", urlsplit(link).path, re.I):
                            if re.search(r"\b(act|rule|directive|guidelines|circular|notice)\b", title, re.I):
                                score += 2
                            candidates.append((score, link, page.get("catalogue_dates", {}).get(link, "")))
                except Exception as error:
                    check["failure_type"] = type(error).__name__

        async def bounded_catalogues():
            try:
                await asyncio.wait_for(catalogues(), timeout=10)
            except TimeoutError:
                logger.info("Official catalogue discovery reached its deadline (%s)", regulator)

        try:
            discovery, _ = await asyncio.gather(discover(regulator, question), bounded_catalogues())
            discovery_checks.append(discovery["check"])
            for item in discovery["candidates"]:
                # Recheck the boundary here, even if a discovery adapter is replaced.
                try:
                    link = official_url(item["url"], regulator)
                except (ValueError, TypeError, KeyError):
                    continue
                title = item.get("title", "")
                if not regulatory_candidate(link, title):
                    continue
                if re.search(r"\.(png|jpg|jpeg|css|js|zip)$", urlsplit(link).path, re.I):
                    continue
                if link in CATALOGUES[regulator]:
                    continue
                # Search may match PDF contents while its filename/title is an
                # opaque reference number. Fetch it before judging its evidence.
                score = max(1, relevance(title + " " + urlsplit(link).path, words))
                if score:
                    # Search ranking is discovery, never a publication/effective date.
                    if re.search(r"\b(acts?|rules?|regulations?|directives?|guidelines?|circulars?|notices?)\b", title, re.I):
                        score += 4
                    if urlsplit(link).path.lower().endswith(".pdf"):
                        score += 2
                    candidates.append((score + 2, link, ""))
            seen = set()
            # Reserve one document slot for search discovery when available. An old
            # dated catalogue entry must not exclude all undated search candidates.
            search_urls = {item["url"] for item in discovery["candidates"]}
            search_candidates = sorted((item for item in candidates if item[1] in search_urls),
                                       key=lambda item: item[0], reverse=True)
            ordered = sorted(candidates, key=lambda item: (item[2], item[0]) if freshness_requested(question) else (item[0], item[2]), reverse=True)
            if search_candidates:
                ordered = [search_candidates[0], *ordered]
            # Preserve catalogue order for equal relevance.
            for _, url, _ in ordered:
                if url in seen:
                    continue
                seen.add(url)
                if len(seen) > 2:
                    break
                check = {"regulator": regulator, "url": url, "status": "unavailable"}
                checks.append(check)
                try:
                    page = await fetched(client, url)
                    check.update(status="checked", fetched_at=page["checked_at"])
                    sources.extend(evidence(page, regulator, words))
                except Exception as error:
                    check["failure_type"] = type(error).__name__
        finally:
            await client.close()

    try:
        await asyncio.wait_for(asyncio.gather(*(one(reg) for reg in selected)), timeout=28)
    except TimeoutError:
        logger.info("Official research reached its bounded deadline")
    # Diversify so one long PDF cannot monopolize the answer evidence.
    ranked, counts, unique = [], {}, set()
    for source in sorted(sources, key=lambda s: (s["_mentioned_date"], s["_relevance"]) if freshness_requested(question) else (s["_relevance"], s["_mentioned_date"]), reverse=True):
        doc = source["document_id"]
        if counts.get(doc, 0) >= 3 or source["chunk_id"] in unique:
            continue
        counts[doc] = counts.get(doc, 0) + 1
        unique.add(source["chunk_id"])
        source.pop("_relevance", None)
        source.pop("_mentioned_date", None)
        ranked.append(source)
        if len(ranked) == 9:
            break
    return {"sources": ranked, "checks": checks, "discovery_checks": discovery_checks, "regulators": selected,
            "checked_at": datetime.now(timezone.utc).isoformat(), "exhaustive": False}


def _finish_helpful(result, report, question):
    """Add research coverage without replacing findings or precise failure causes."""
    from services.grounded_answers import helpful_result

    missing = list(result.get("missing_information", []))
    if freshness_requested(question):
        missing.append("latest_coverage")
    if result.get("knowledge_gap"):
        if re.search(r"\b(cost|fine|penalt\w*|sanction\w*)\b", question, re.I) or "cod=st" in question.lower():
            missing.append("penalty")
        if report["sources"]:
            # These links establish discovery, not approval of any proposed claim.
            citations, seen = [], set()
            for source in report["sources"]:
                if source["document_id"] in seen:
                    continue
                seen.add(source["document_id"])
                citations.append({"document_id": source["document_id"], "document_title": source["title"],
                    "chunk_id": source["chunk_id"], "excerpt": source["content"][:500],
                    "provenance": source["provenance"], "source_url": source["provenance"]["source_url"]})
                if len(citations) == 3:
                    break
            result["citations"] = citations
            base = result.get("_finding_answer", result["answer"])
            result["_finding_answer"] = base + "\n\nOfficial source links are available below for review; they are not approved answer findings."
    result.update(missing_information=list(dict.fromkeys(missing)), source_checks=report["checks"],
                  research_checked_at=report["checked_at"], _grounded=True, verdict="MONITOR")
    result = helpful_result(result, question)
    if any(check["status"] != "checked" for check in report["checks"]):
        result["answer"] += "\n\nSome official sources were unavailable during this check, so coverage is incomplete."
    return result


def finish(result, report, question, *, helpful=False):
    """Server-owned limitations, never model-generated claims of legal completeness."""
    if helpful:
        return _finish_helpful(result, report, question)
    missing = list(result.get("missing_information", []))
    if freshness_requested(question):
        missing.append("latest_coverage")
    if result.get("knowledge_gap"):
        if report["sources"]:
            reason = "The reasoning service could not complete validation" if result.get("_gap_reason") == "unavailable" else "The automated evidence checks could not approve a reliable summary"
            result["answer"] = reason + ". I did find official source material; the source links below are available for review. No compliance conclusion or penalty estimate has been made."
            # Discovery must not disappear when model validation fails. These are
            # source excerpts for review, NOT model-approved compliance findings.
            citations, seen = [], set()
            for source in report["sources"]:
                if source["document_id"] in seen:
                    continue
                seen.add(source["document_id"])
                citations.append({"document_id": source["document_id"], "document_title": source["title"],
                    "chunk_id": source["chunk_id"], "excerpt": source["content"][:500],
                    "provenance": source["provenance"], "source_url": source["provenance"]["source_url"]})
                if len(citations) == 3:
                    break
            result["citations"] = citations
        else:
            result["answer"] = (
                "The official-source check did not return usable passages, and the accessible "
                "document evidence could not establish this answer. That does not mean there is no regulatory risk or fine."
            )
        missing.append("scope")
        if re.search(r"\b(cost|fine|penalt\w*|sanction\w*)\b", question, re.I) or "cod=st" in question.lower():
            missing.append("penalty")
    else:
        result["answer"] = "Verified source findings:\n\n" + result["answer"]
    missing = list(dict.fromkeys(missing))
    labels = {
        "latest_coverage": "These are relevant sources checked, not an exhaustive latest-regulation search or a ranking of your company's risks.",
        "current_applicability": "Current applicability and whether later rules supersede these sources remain unverified.",
        "institution_status": "Your institution's compliance or exposure requires its licence details and internal records.",
        "penalty": "An applicable monetary penalty has not been verified; no amount is being assumed.",
        "scope": "The relevant institution/licence category and specific breach need to be identified.",
        "other_requested_fact": "Another requested detail could not be established from the checked evidence.",
    }
    if missing:
        # Preserve all gap metadata, without making the user read six overlapping
        # caveats in place of an answer. Put the requested cost gap first.
        visible = [item for item in ("penalty", "scope", "institution_status", "other_requested_fact") if item in missing]
        if "scope" in visible and "institution_status" in visible:
            visible.remove("institution_status")
        if len(visible) > 1 and "other_requested_fact" in visible:
            visible.remove("other_requested_fact")
        if visible:
            result["answer"] += "\n\nStill needed:\n\n" + "\n".join("- " + labels[item] for item in visible)
        if "latest_coverage" in missing:
            result["answer"] += "\n\nThis was a bounded official-source check, not exhaustive latest-regulation coverage or a ranking of your institution's risks."
        elif "current_applicability" in missing:
            result["answer"] += "\n\nCurrent applicability and supersession remain unverified."
    if any(check["status"] != "checked" for check in report["checks"]):
        result["answer"] += "\n\nSome official sources were unavailable during this check, so coverage is incomplete."
    if "scope" in missing:
        result["answer"] += "\n\nIs this for a microfinance bank or a fintech, and which licence type?"
    result.update(partial_answer=bool(missing) and not result.get("knowledge_gap"),
                  missing_information=missing, source_checks=report["checks"],
                  research_checked_at=report["checked_at"],
                  suggested_followups=["Focus on a microfinance bank or fintech licence, and specify the compliance area to verify its requirements and penalties."],
                  _grounded=True, verdict="MONITOR")
    return result
