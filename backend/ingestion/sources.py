"""Opt-in discovery from official regulator domains, with conservative HTTP policy."""

import asyncio
import hashlib
import ipaddress
import json
import logging
import re
import socket
import tempfile
import time
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit, urlunsplit

import httpx

from ingestion.models import CrawlRun, Revision, Source
from ingestion.pipeline import accept
from ingestion.storage import preserve

logger = logging.getLogger(__name__)

DOMAINS = {
    "CBN": {"cbn.gov.ng", "www.cbn.gov.ng"},
    "SEC": {"sec.gov.ng", "www.sec.gov.ng", "home.sec.gov.ng"},
    "NDIC": {"ndic.gov.ng", "www.ndic.gov.ng"},
    "NFIU": {"nfiu.gov.ng", "www.nfiu.gov.ng"},
    "NDPC": {"ndpc.gov.ng", "www.ndpc.gov.ng"},
    "FCCPC": {"fccpc.gov.ng", "www.fccpc.gov.ng"},
}
USER_AGENT = "IrokoAI-RegulatoryIngest/1.0 (+mailto:ingest@irokoai.site)"
MAX_BYTES = 50 * 1024 * 1024
ATTACHMENT_TYPES = {".pdf", ".docx", ".xlsx"}
RECHECK_DAYS = 30  # Known versions are re-downloaded to detect changed files.
MISSING_LIMIT = 50  # Newest listed-but-not-collected items kept for manual import.
FAILURE_LIMIT = 500


class AccessChallenge(ValueError):
    """The host answered with a bot challenge. Iroko never attempts to bypass one."""


def attachment_filename(url):
    return unquote(Path(urlsplit(url).path).name)


def source_key(regulator, url):
    return f"regulator:{regulator}:{url}"


def official_url(url, regulator, base=""):
    p = urlsplit(urldefrag(urljoin(base, url.strip()))[0])
    if (
        p.scheme != "https"
        or p.hostname not in DOMAINS.get(regulator, set())
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise ValueError("Source URL must use an approved regulator HTTPS domain")
    return urlunsplit(("https", p.hostname, quote(p.path, safe="/%:@-._~!$&'()*+,;="), p.query, ""))


def robots_allowed(text, url):
    """Longest matching path wins, including * and $; Allow wins a tie."""
    groups, agents, rules = [], [], []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif key in {"allow", "disallow"} and agents and value:
            rules.append((key == "allow", value))
    groups.append((agents, rules))
    matched = [
        (max((len(a) for a in aa if a != "*" and a in USER_AGENT.lower()), default=0), rr)
        for aa, rr in groups
        if "*" in aa or any(a in USER_AGENT.lower() for a in aa)
    ]
    best_agent = max((n for n, _ in matched), default=-1)
    target = urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else "")
    hits = []
    for score, rr in matched:
        if score != best_agent:
            continue
        for allowed, pattern in rr:
            end = pattern.endswith("$")
            body = pattern[:-1] if end else pattern
            regex = "^" + re.escape(body).replace(r"\*", ".*") + ("$" if end else "")
            if re.search(regex, target):
                hits.append((len(body.replace("*", "")), allowed))
    return max(hits)[1] if hits else True


class OfficialClient:
    def __init__(self, regulator, *, timeout=60, attempts=4, max_bytes=MAX_BYTES):
        self.regulator, self.robots, self.last_request = regulator, {}, 0.0
        self.attempts, self.max_bytes = attempts, max_bytes
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(10, timeout)),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            trust_env=False,
        )

    async def close(self):
        await self.client.aclose()

    async def _request(self, url, cap):
        # DNS checks supplement domain allowlisting; private source endpoints are never fetched.
        host = urlsplit(url).hostname
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Regulator host resolved to a non-public address")
        for attempt in range(self.attempts):
            await asyncio.sleep(max(0, 2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                async with self.client.stream("GET", url) as response:
                    if response.headers.get("cf-mitigated") == "challenge":
                        raise AccessChallenge(
                            "The regulator's site requires a browser check for this file. "
                            "Download it from the official link and import it."
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == self.attempts - 1:
                            response.raise_for_status()
                        retry = response.headers.get("Retry-After", "")
                        await asyncio.sleep(min(60, int(retry)) if retry.isdigit() else 2**attempt)
                        continue
                    if response.is_redirect:
                        return response.status_code, response.headers, b""
                    if response.status_code != 404:
                        response.raise_for_status()
                    body = bytearray()
                    async for part in response.aiter_bytes():
                        body.extend(part)
                        if len(body) > cap:
                            raise ValueError("Source response exceeds download limit")
                    return response.status_code, response.headers, bytes(body)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.attempts - 1:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("Source request exhausted retries")

    async def fetch(self, url, *, robots=False):
        for _ in range(6):
            url = official_url(url, self.regulator)
            origin = "https://" + urlsplit(url).hostname
            if not robots:
                if origin not in self.robots:
                    code, _, body = await self.fetch(origin + "/robots.txt", robots=True)
                    self.robots[origin] = (
                        "" if code == 404 else body.decode("utf-8", errors="replace")
                    )
                if not robots_allowed(self.robots[origin], url):
                    raise ValueError("Source path disallowed by robots.txt")
            code, headers, body = await self._request(url, 512_000 if robots else self.max_bytes)
            if 300 <= code < 400:
                url = official_url(headers["location"], self.regulator, url)
                continue
            if code == 404 and not robots:
                raise ValueError("Source document not found (404)")
            return code, headers, body
        raise ValueError("Too many source redirects")


def parse_cbn(body, listing_url):
    data = json.loads(body)
    if not isinstance(data, list):
        raise ValueError("CBN listing shape changed: expected a JSON array")
    result, skipped = [], 0
    for item in data:
        try:
            record = {
                "title": item["title"],
                "source_url": official_url(item["link"], "CBN", listing_url),
                "regulator": "CBN",
                "reference_number": item.get("refNo"),
                "reference_number_normalized": " ".join((item.get("refNo") or "").split()).upper(),
                "published_date": datetime.strptime(item["documentDate"].strip(), "%d/%m/%Y")
                .date()
                .isoformat(),
                "listing_url": listing_url,
            }
        except (KeyError, TypeError, AttributeError, ValueError):
            skipped += 1  # One malformed catalogue row must not hide the rest.
            continue
        size = str(item.get("filesize") or "").strip()
        if size.isdigit():
            record["catalogue_size"] = int(size)
        result.append(record)
    if skipped:
        logger.warning("Skipped %d malformed CBN catalogue rows in %s", skipped, listing_url)
        if not result:
            raise ValueError("CBN listing shape changed: no parseable circulars")
    return sorted(result, key=lambda item: item["published_date"], reverse=True)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.label = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href, self.label = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.label).strip()))
            self.href = None


_LINK_PREFIX = re.compile(
    r"^(?:click here to |please )?(?:download|explore|view|read|open|get|access|see)\b"
    r"(?:\s+(?:the|this|our))?(?:\s+full)?\s*",
    re.I,
)
# Trailing badges inside link text, e.g. "… Here pdf · 415.6 KB".
_LINK_TRAILERS = (
    re.compile(r"[\s·•|,\-–—(]*\d+(?:[.,]\d+)?\s*(?:[KMG]i?B|bytes)\)?[\s.]*$", re.I),
    re.compile(r"[\s·•|,\-–—(]*\b(?:pdf|docx?|xlsx?)\b\)?[\s.:!]*$", re.I),
    re.compile(r"\s*\b(?:here|now)\b[\s.:!]*$", re.I),
)


def humanize_filename(url):
    stem = Path(attachment_filename(url)).stem
    # Drop storage suffixes: "_18521", Django's random "_x9rSXtI", or a trailing UUID.
    stem = re.sub(r"[-_][0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", "", stem, flags=re.I)
    stem = re.sub(r"_(?:\d+|(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Z])[A-Za-z0-9]{7})$", "", stem)
    return " ".join(re.split(r"[-_\s]+", stem)).strip() or attachment_filename(url)


def listing_title(label, url):
    """A document title from link text, without "Download the full … here" boilerplate."""
    text = _LINK_PREFIX.sub("", " ".join((label or "").split()))
    previous = None
    while text != previous:
        previous = text
        for pattern in _LINK_TRAILERS:
            text = pattern.sub("", text).strip(" -–—:·•|")
    if len(text) < 8:
        return humanize_filename(url)
    return text[0].upper() + text[1:]


def parse_links(body, regulator, listing_url):
    parser = Links()
    parser.feed(body.decode("utf-8", errors="replace"))
    result, seen = [], set()
    for href, label in parser.links:
        if not urlsplit(href).path.lower().endswith((".pdf", ".docx", ".xlsx")):
            continue
        try:
            url = official_url(href, regulator, listing_url)
        except ValueError:
            continue
        if url not in seen:
            result.append(
                {
                    "source_url": url,
                    "regulator": regulator,
                    "title": listing_title(label, url),
                    "listing_url": listing_url,
                }
            )
            seen.add(url)
    return result


def _retry_due(failure, now):
    """Exponential backoff for broken links: 1, 2, 4, ... days, capped at 30."""
    wait = timedelta(days=min(RECHECK_DAYS, 2 ** max(0, failure.get("count", 1) - 1)))
    return now - datetime.fromisoformat(failure["last"]) >= wait


def _latest_revisions(db, regulator):
    """Latest revision per source key, in one query rather than one per listed item."""
    latest = {}
    prefix = source_key(regulator, "")
    for revision in (
        db.query(Revision)
        .filter(Revision.source_key.startswith(prefix, autoescape=True))
        .order_by(Revision.created_at)
    ):
        latest[revision.source_key] = revision
    return latest


def check_attachment(data, url):
    ext = Path(urlsplit(url).path).suffix.lower()
    if ext not in ATTACHMENT_TYPES:
        raise ValueError("Unsupported regulatory attachment; original needs manual import")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("Expected PDF bytes; server returned another format")
    if ext in {".xlsx", ".docx"} and not data.startswith(b"PK"):
        raise ValueError("Expected Office file bytes")
    return ext


async def accept_listed(db, path, item, owner_id, regulator, extra=None):
    """Accept a regulator file under its official source key and listing metadata."""
    now = datetime.utcnow().isoformat()
    key = source_key(regulator, item["source_url"])
    doc = await accept(
        db,
        str(path),
        attachment_filename(item["source_url"]),
        item["title"],
        owner_id,
        {
            **item,
            **(extra or {}),
            "classification": "public",
            "doc_type": "regulatory",
            "last_verified_at": now,
        },
        key,
    )
    # An unchanged file returns the existing revision: record that it was re-verified.
    revision = db.get(Revision, doc.id)
    revision.provenance = {**revision.provenance, "last_verified_at": now}
    db.commit()
    return doc


async def collect(db, source_id):
    source = db.get(Source, source_id)
    if not source or not source.enabled:
        return
    client = OfficialClient(source.regulator)
    previous_result = dict(source.result or {})
    failures = dict(previous_result.get("failures") or {})
    result = {
        "found": 0,
        "accepted": 0,
        "attempted": 0,
        "skipped_recent_failures": 0,
        "blocked": False,
        "errors": [],
        "status": "running",
        # Carried forward so a failed listing fetch does not lose the worklist.
        "missing": previous_result.get("missing", []),
        "missing_total": previous_result.get("missing_total", 0),
        "failures": failures,
    }
    run = CrawlRun(source_id=source_id, result=_run_summary(result))
    db.add(run)
    db.commit()
    try:
        _, _, body = await client.fetch(source.url)
        with tempfile.TemporaryDirectory(prefix="iroko-source-") as directory:
            snapshot = Path(directory) / "listing.txt"
            snapshot.write_bytes(body)
            result["snapshot"] = await preserve(
                str(snapshot),
                f"source-{source.id}-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}",
                "listing.txt",
            )
            result["snapshot_sha256"] = hashlib.sha256(body).hexdigest()
            listings = (
                parse_cbn(body, source.url)
                if source.parser == "cbn_json"
                else parse_links(body, source.regulator, source.url)
            )
            result["found"] = len(listings)
            now = datetime.utcnow()
            latest = _latest_revisions(db, source.regulator)
            fresh, recheck = [], []
            for item in listings:
                previous = latest.get(source_key(source.regulator, item["source_url"]))
                if previous is None:
                    fresh.append(item)
                    continue
                # Files imported without a crawl were verified when they were accepted.
                checked = previous.provenance.get("last_verified_at")
                verified = datetime.fromisoformat(checked) if checked else previous.created_at
                if now - verified >= timedelta(days=RECHECK_DAYS):
                    recheck.append(item)
            accepted_urls = set()
            attempted = 0
            # Never-collected documents take priority over periodic re-verification.
            for item in fresh + recheck:
                if attempted >= source.max_documents or result["blocked"]:
                    break
                url = item["source_url"]
                failure = failures.get(url)
                if failure and not _retry_due(failure, now):
                    result["skipped_recent_failures"] += 1
                    continue
                attempted += 1
                try:
                    _, _, data = await client.fetch(url)
                    ext = check_attachment(data, url)
                    path = Path(directory) / ("download" + ext)
                    path.write_bytes(data)
                    await accept_listed(db, path, item, source.owner_id, source.regulator)
                    failures.pop(url, None)
                    accepted_urls.add(url)
                    result["accepted"] += 1
                except Exception as exc:
                    db.rollback()
                    result["errors"].append(
                        {"url": url, "error": type(exc).__name__, "detail": str(exc)[:250]}
                    )
                    if isinstance(exc, AccessChallenge):
                        # The host is challenging automated clients: stop for this run
                        # instead of repeating requests it has already refused.
                        result["blocked"] = True
                    else:
                        failures[url] = {
                            "count": failures.get(url, {}).get("count", 0) + 1,
                            "last": now.isoformat(),
                            "error": type(exc).__name__,
                        }
            result["attempted"] = attempted
            missing = [
                {
                    **item,
                    "importable": Path(urlsplit(item["source_url"]).path).suffix.lower()
                    in ATTACHMENT_TYPES,
                }
                for item in fresh
                if item["source_url"] not in accepted_urls
            ]
            result["missing"], result["missing_total"] = missing[:MISSING_LIMIT], len(missing)
            if not listings:
                result["status"] = "suspect"  # A layout change can look like "no documents".
            elif result["blocked"]:
                result["status"] = "blocked"
            elif result["errors"]:
                result["status"] = "partial"
            else:
                result["status"] = "succeeded"
    except Exception as exc:
        db.rollback()
        result["status"] = "blocked" if isinstance(exc, AccessChallenge) else "failed"
        result["blocked"] = isinstance(exc, AccessChallenge)
        result["errors"].append({"error": type(exc).__name__, "detail": str(exc)[:250]})
    finally:
        await client.close()
        if len(failures) > FAILURE_LIMIT:
            newest = sorted(failures.items(), key=lambda kv: kv[1]["last"], reverse=True)
            result["failures"] = dict(newest[:FAILURE_LIMIT])
        source = db.get(Source, source_id)
        source.last_run, source.result = datetime.utcnow(), result
        run.finished_at, run.result = datetime.utcnow(), _run_summary(result)
        db.commit()


def _run_summary(result):
    """Crawl history keeps per-run outcomes, not the source's carried worklists."""
    return {k: v for k, v in result.items() if k not in {"missing", "failures"}}
