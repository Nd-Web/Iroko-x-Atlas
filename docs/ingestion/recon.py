"""Phase 0 snapshot helper; no application imports, database writes, or services.

From the repository root, after setting INGESTION_CONTACT_EMAIL:
    python docs/ingestion/recon.py https://www.cbn.gov.ng/documents/ \
        --save backend/tests/ingestion/fixtures/cbn/documents.html

Use only URLs supplied in the brief or discovered in saved official pages.
This one-process, sequential helper is not the production ingestion HTTP client.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

ALLOWED_HOSTS = frozenset(
    {"cbn.gov.ng", "www.cbn.gov.ng", "sec.gov.ng", "www.sec.gov.ng", "home.sec.gov.ng"}
)
MAX_BYTES = 100 * 1024 * 1024


class ReconStopped(RuntimeError):
    """Stop reconnaissance without bypassing a restriction or guessing content."""


class PageSummary(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.in_title = False
        self.title: list[str] = []
        self.links: list[dict[str, str]] = []
        self.feeds: list[str] = []
        self.tables = 0
        self.anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "table":
            self.tables += 1
        href = attributes.get("href")
        if href and tag in {"a", "link"}:
            resolved = urljoin(self.page_url, href)
            if tag == "a":
                self.anchor = {"url": resolved, "label": ""}
                self.links.append(self.anchor)
            if attributes.get("type") in {"application/rss+xml", "application/atom+xml"}:
                self.feeds.append(resolved)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "a":
            self.anchor = None

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        if self.anchor is not None:
            self.anchor["label"] += data


class SnapshotClient:
    def __init__(self, contact_email: str) -> None:
        self.user_agent = f"IrokoAI-RegulatoryIngest/1.0 (+mailto:{contact_email})"
        self.client = httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "identity"},
            timeout=httpx.Timeout(60, connect=10),
            follow_redirects=False,
            http2=False,
            verify=True,
        )
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, RobotFileParser] = {}
        self.robots_evidence: list[dict[str, object]] = []

    @staticmethod
    def validate_url(url: str) -> str:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ReconStopped(f"URL outside the HTTPS regulator allow-list: {url}")
        return f"https://{parsed.hostname}"

    def request(self, url: str, delay: float = 2.0) -> tuple[httpx.Response, bytes]:
        origin = self.validate_url(url)
        remaining = delay - (time.monotonic() - self.last_request.get(origin, 0))
        if remaining > 0:
            time.sleep(remaining)
        self.last_request[origin] = time.monotonic()
        # A failed attempt deliberately stops Phase 0. Retry later with approval
        # or after the indicated delay; never loop around a block or challenge.
        with self.client.stream("GET", url) as response:
            encoding = response.headers.get("content-encoding", "identity").strip().lower()
            if encoding not in {"", "identity"}:
                raise ReconStopped(
                    f"Unexpected Content-Encoding={encoding}; inspect before saving exact bytes: {url}"
                )
            body = bytearray()
            for part in response.iter_raw():
                body.extend(part)
                if len(body) > MAX_BYTES:
                    raise ReconStopped(f"Response exceeded {MAX_BYTES} bytes: {url}")
            return response, bytes(body)

    def robot_rules(self, origin: str) -> RobotFileParser:
        if origin in self.robots:
            return self.robots[origin]
        robots_url = f"{origin}/robots.txt"
        for _ in range(6):
            response, body = self.request(robots_url)
            self.robots_evidence.append(
                {
                    "url": robots_url,
                    "status": response.status_code,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "body": body.decode("utf-8", errors="replace"),
                }
            )
            if response.is_redirect:
                target = urljoin(robots_url, response.headers.get("location", ""))
                if self.validate_url(target) != origin:
                    raise ReconStopped("robots.txt redirected across origins; inspect before continuing")
                robots_url = target
                continue
            rules = RobotFileParser(robots_url)
            if response.status_code == 404:
                rules.parse(["User-agent: *", "Disallow:"])
            elif response.status_code == 200 and "html" not in response.headers.get("content-type", "").lower():
                robots_text = body.decode("utf-8-sig")
                if robots_text.lstrip().startswith("<"):
                    raise ReconStopped("robots.txt contains markup; inspect for a block or challenge")
                rules.parse(robots_text.splitlines())
            else:
                retry_after = response.headers.get("retry-after", "unspecified")
                raise ReconStopped(
                    f"robots.txt unavailable ({response.status_code}); Retry-After={retry_after}. "
                    "No publication request was made."
                )
            self.robots[origin] = rules
            return rules
        raise ReconStopped("robots.txt exceeded five redirects")

    def fetch(self, url: str) -> tuple[httpx.Response, bytes]:
        initial_origin = self.validate_url(url)
        regulator_domain = "cbn.gov.ng" if initial_origin.endswith("cbn.gov.ng") else "sec.gov.ng"
        for _ in range(6):
            origin = self.validate_url(url)
            if not origin.endswith(regulator_domain):
                raise ReconStopped("Publication redirected outside its regulator's domain family")
            rules = self.robot_rules(origin)
            if not rules.can_fetch(self.user_agent, url):
                raise ReconStopped(f"robots.txt disallows: {url}")
            delay = max(2.0, float(rules.crawl_delay(self.user_agent) or 0))
            rate = rules.request_rate(self.user_agent)
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            response, body = self.request(url, delay)
            if response.is_redirect:
                url = urljoin(url, response.headers.get("location", ""))
                continue
            if response.status_code != 200:
                raise ReconStopped(
                    f"HTTP {response.status_code}: {url}; "
                    f"Retry-After={response.headers.get('retry-after', 'unspecified')}"
                )
            return response, body
        raise ReconStopped("Publication exceeded five redirects")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--save", required=True, type=Path)
    args = parser.parse_args()
    contact = os.environ.get("INGESTION_CONTACT_EMAIL", "").strip()
    if "@" not in contact or any(c.isspace() for c in contact) or any(c in contact for c in "()<>"):
        parser.error("Set the user-provided INGESTION_CONTACT_EMAIL before fetching")
    destination = args.save.resolve()
    manifest = destination.with_suffix(destination.suffix + ".source.json")
    if destination.exists() or manifest.exists():
        parser.error("Choose new snapshot paths; existing fixtures are never overwritten")
    snapshot = SnapshotClient(contact)
    try:
        response, body = snapshot.fetch(args.url)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        evidence: dict[str, object] = {
            "requested_url": args.url,
            "final_url": str(response.url),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_type": content_type,
            "content_type_header": response.headers.get("content-type", ""),
            "content_encoding": response.headers.get("content-encoding", "identity"),
            "etag": response.headers.get("etag"),
            "last_modified": response.headers.get("last-modified"),
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "robots": snapshot.robots_evidence,
        }
        if content_type == "text/html":
            page = PageSummary(str(response.url))
            summary_encoding = response.encoding or "utf-8"
            try:
                summary_text = body.decode(summary_encoding)
            except (UnicodeError, LookupError):
                summary_encoding = "utf-8"
                summary_text = body.decode(summary_encoding, errors="replace")
                evidence["summary_warning"] = "Lossy preview only; inspect the source charset before deriving a parser"
            page.feed(summary_text)
            evidence["summary_encoding"] = summary_encoding
            evidence["title"] = "".join(page.title)
            evidence["links"] = page.links
            evidence["tables"] = page.tables
            evidence["feeds"] = page.feeds
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(body)
        with manifest.open("x", encoding="utf-8") as handle:
            json.dump(evidence, handle, indent=2, ensure_ascii=False)
        print(json.dumps({k: v for k, v in evidence.items() if k != "robots"}, indent=2))
        return 0
    except (ReconStopped, httpx.HTTPError, UnicodeError, ValueError, OSError) as exc:
        print(json.dumps({
            "status": "stopped",
            "error": str(exc),
            "url": args.url,
            "fixture_saved": destination.exists(),
            "metadata_saved": manifest.exists(),
        }))
        return 1
    finally:
        snapshot.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
