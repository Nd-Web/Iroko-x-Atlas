"""Opt-in discovery from official regulator domains, with conservative HTTP policy."""

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import tempfile
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urldefrag, urljoin, urlsplit, urlunsplit

import httpx

from ingestion.models import CrawlRun, Revision, Source
from ingestion.pipeline import accept
from ingestion.storage import preserve

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
    def __init__(self, regulator):
        self.regulator, self.robots, self.last_request = regulator, {}, 0.0
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60, connect=10),
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
        for attempt in range(4):
            await asyncio.sleep(max(0, 2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                async with self.client.stream("GET", url) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt == 3:
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
                if attempt == 3:
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
            code, headers, body = await self._request(url, 512_000 if robots else MAX_BYTES)
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
    result = []
    for item in data:
        result.append(
            {
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
        )
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
                    "title": label or Path(urlsplit(url).path).name,
                    "listing_url": listing_url,
                }
            )
            seen.add(url)
    return result


async def collect(db, source_id):
    source = db.get(Source, source_id)
    if not source or not source.enabled:
        return
    client = OfficialClient(source.regulator)
    result = {"found": 0, "accepted": 0, "errors": [], "status": "running"}
    run = CrawlRun(source_id=source_id, result=dict(result))
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
            attempted = 0
            for item in listings:
                source_key = f"regulator:{source.regulator}:{item['source_url']}"
                previous = (
                    db.query(Revision)
                    .filter_by(source_key=source_key)
                    .order_by(Revision.created_at.desc())
                    .first()
                )
                checked = previous.provenance.get("last_verified_at") if previous else None
                if checked and (datetime.utcnow() - datetime.fromisoformat(checked)).days < 30:
                    continue
                if attempted >= source.max_documents:
                    break
                attempted += 1
                try:
                    _, headers, data = await client.fetch(item["source_url"])
                    ext = Path(urlsplit(item["source_url"]).path).suffix.lower()
                    if ext == ".pdf" and not data.startswith(b"%PDF-"):
                        raise ValueError("Expected PDF bytes; server returned another format")
                    if ext in {".xlsx", ".docx"} and not data.startswith(b"PK"):
                        raise ValueError("Expected Office file bytes")
                    if ext not in {".pdf", ".docx", ".xlsx"}:
                        raise ValueError(
                            "Unsupported regulatory attachment; original needs manual import"
                        )
                    path = Path(directory) / ("download" + ext)
                    path.write_bytes(data)
                    doc = await accept(
                        db,
                        str(path),
                        Path(urlsplit(item["source_url"]).path).name,
                        item["title"],
                        source.owner_id,
                        {
                            **item,
                            "classification": "public",
                            "doc_type": "regulatory",
                            "last_verified_at": datetime.utcnow().isoformat(),
                        },
                        source_key,
                    )
                    revision = db.get(Revision, doc.id)
                    revision.provenance = {
                        **revision.provenance,
                        "last_verified_at": datetime.utcnow().isoformat(),
                    }
                    db.commit()
                    result["accepted"] += 1
                except Exception as exc:
                    db.rollback()
                    result["errors"].append(
                        {
                            "url": item["source_url"],
                            "error": type(exc).__name__,
                            "detail": str(exc)[:250],
                        }
                    )
            result["status"] = (
                "suspect"
                if not listings or len(result["errors"]) > max(1, attempted) * 0.2
                else "succeeded"
            )
    except Exception as exc:
        db.rollback()
        result["status"] = "failed"
        result["errors"].append({"error": type(exc).__name__, "detail": str(exc)[:250]})
    finally:
        await client.close()
        source = db.get(Source, source_id)
        source.last_run, source.result = datetime.utcnow(), result
        run.finished_at, run.result = datetime.utcnow(), dict(result)
        db.commit()
