"""Import a curated list of regulator documents (for example a pilot library).

Each manifest entry names a document's official URL and its listing metadata:

    {"id": "cbn-pep-2023", "regulator": "CBN", "url": "https://www.cbn.gov.ng/Out/...pdf",
     "title": "...", "published_date": "2023-06-23", "reference_number": "...",
     "catalogue_size": 123456, "listing_url": "https://www.cbn.gov.ng/api/GetAllCirculars"}

Files are fetched with the identified regulator client (robots.txt, domain
allowlist, size limits). A host's bot challenge is never bypassed. For an entry
whose catalogue states a byte size, an Internet Archive capture of the same
official URL may be used instead, but only when its bytes match that size exactly.
Files saved from a browser can be imported from a folder; they are matched to
entries by exact byte size and file name. Every route records how the file was
acquired in the document's provenance.
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from ingestion.models import Revision
from ingestion.sources import (
    ATTACHMENT_TYPES,
    USER_AGENT,
    AccessChallenge,
    OfficialClient,
    accept_listed,
    attachment_filename,
    check_attachment,
    official_url,
    source_key,
)
from ingestion.validation import UploadLimitError

logger = logging.getLogger(__name__)
ARCHIVE = "https://web.archive.org"
# Public legal archives used only for Acts no government site publishes. Copies from
# them are labelled as such, keep no regulator, and so can never be shared as official.
LEGAL_ARCHIVES = {
    "placng.org", "www.placng.org", "archive.gazettes.africa",  # PLAC, Gazettes.Africa
    "www.icnl.org", "icnl.org", "cyrilla.org",  # ICNL and Cyrilla law libraries
}
METADATA = ("title", "published_date", "reference_number", "catalogue_size", "listing_url", "date_basis")


def load_manifest(path):
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    for entry in entries:
        if entry.get("copy"):
            entry["url"] = official_url(entry["url"], "COPY", hosts=LEGAL_ARCHIVES)
        else:
            entry["url"] = official_url(entry["url"], entry["regulator"])
    return entries


def listed_item(entry):
    item = {k: entry[k] for k in METADATA if entry.get(k) not in (None, "")}
    item["source_url"] = entry["url"]
    if entry.get("copy"):
        # An archive copy names who issued the law and who published the copy, never a regulator.
        item.update({"issuer": entry.get("issuer", ""), "publisher": entry.get("publisher", ""),
                     "official_copy": False})
    else:
        item["regulator"] = entry["regulator"]
    item.setdefault("title", attachment_filename(entry["url"]))
    return item


def entry_key(entry):
    if entry.get("copy"):
        return f"copy:{urlsplit(entry['url']).hostname}:{entry['url']}"
    return source_key(entry["regulator"], entry["url"])


def existing_document(db, entry):
    revision = (
        db.query(Revision)
        .filter_by(source_key=entry_key(entry))
        .order_by(Revision.created_at.desc())
        .first()
    )
    return revision.id if revision else None


class ArchiveClient:
    """Exact captures from the Internet Archive, identified and rate-limited."""

    def __init__(self, *, delay=2.0, timeout=90):
        self.delay, self.last = delay, 0.0
        self.client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=False
        )

    async def close(self):
        await self.client.aclose()

    async def _get(self, url, params=None):
        loop = asyncio.get_running_loop()
        await asyncio.sleep(max(0, self.delay - (loop.time() - self.last)))
        self.last = loop.time()
        for _ in range(5):
            response = await self.client.get(url, params=params or None)
            location = response.headers.get("location", "")
            if response.is_redirect and urlsplit(location).hostname in (None, "web.archive.org"):
                url, params = (location if location.startswith("http") else ARCHIVE + location), {}
                continue
            return response
        raise ValueError("Too many archive redirects")

    async def capture(self, url, expected_size):
        """Return (bytes, capture_url) for a PDF capture of exactly `expected_size` bytes."""
        response = await self._get(
            f"{ARCHIVE}/cdx/search/cdx",
            {
                "url": unquote(url).split("://", 1)[1],
                "output": "json",
                "fl": "timestamp,original",
                "filter": ["statuscode:200", "mimetype:application/pdf"],
                "limit": "-5",
            },
        )
        rows = response.json()[1:] if response.status_code == 200 and response.text.strip() else []
        for timestamp, original in reversed(rows):  # Newest capture first.
            capture_url = f"{ARCHIVE}/web/{timestamp}id_/{original}"
            got = await self._get(capture_url)
            if got.status_code == 200 and len(got.content) == expected_size:
                return got.content, capture_url
        raise ValueError("No archived copy matches the catalogue byte size")


async def _accept(db, data, entry, owner_id, extra, directory):
    ext = check_attachment(data, entry["url"])
    path = Path(directory) / ("download" + ext)
    path.write_bytes(data)
    for _ in range(120):
        try:
            doc = await accept_listed(db, path, listed_item(entry), owner_id, entry.get("regulator"),
                                      extra, key=entry_key(entry), filename=entry.get("filename"))
            return doc.id
        except UploadLimitError as exc:
            db.rollback()
            if "queue is full" not in str(exc):
                raise
            await asyncio.sleep(30)  # Let workers drain the workspace queue.
    raise UploadLimitError("Workspace queue stayed full for an hour")


async def import_entries(db, entries, owner_id, *, archive=False, clients=None, archive_client=None):
    """Fetch and accept each entry. Returns one result per entry; never raises per entry."""
    clients = clients if clients is not None else {}
    own_archive = archive and archive_client is None
    archive_client = archive_client or (ArchiveClient() if archive else None)
    blocked_hosts, results = set(), []
    try:
        with tempfile.TemporaryDirectory(prefix="iroko-manifest-") as directory:
            for entry in entries:
                result = {"id": entry.get("id"), "url": entry["url"]}
                try:
                    existing = existing_document(db, entry)
                    if existing:
                        results.append({**result, "status": "exists", "document_id": existing})
                        continue
                    host = urlsplit(entry["url"]).hostname
                    data, extra = None, {"acquisition": "official_download"}
                    if entry.get("copy"):
                        extra = {"acquisition": "public_archive_copy"}
                    if host not in blocked_hosts:
                        family = "COPY" if entry.get("copy") else entry["regulator"]
                        client = clients.get(family)
                        if client is None:
                            client = clients[family] = OfficialClient(
                                family, hosts=LEGAL_ARCHIVES if entry.get("copy") else None
                            )
                        try:
                            _, _, data = await client.fetch(entry["url"])
                        except AccessChallenge:
                            blocked_hosts.add(host)  # Ask a refusing host only once per run.
                    if data is None:
                        size = entry.get("catalogue_size")
                        if not (archive_client and size):
                            results.append({**result, "status": "blocked"})
                            continue
                        data, capture = await archive_client.capture(entry["url"], int(size))
                        extra = {
                            "acquisition": "internet_archive_capture",
                            "archive_url": capture,
                            "size_verified_against": "regulator catalogue",
                        }
                    elif entry.get("catalogue_size") and len(data) != int(entry["catalogue_size"]):
                        extra["catalogue_size_mismatch"] = len(data)
                    document_id = await _accept(db, data, entry, owner_id, extra, directory)
                    results.append({**result, "status": "accepted", "document_id": document_id,
                                    "acquisition": extra["acquisition"], "bytes": len(data)})
                except Exception as exc:  # One bad entry must not stop the rest.
                    db.rollback()
                    results.append({**result, "status": "failed",
                                    "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                logger.info("%s %s", results[-1]["status"], entry.get("id") or entry["url"])
    finally:
        for client in clients.values():
            await client.close()
        if own_archive:
            await archive_client.close()
    return results


def _name_key(name):
    return re.sub(r"[^a-z0-9]", "", Path(unquote(name)).stem.lower())


async def import_folder(db, folder, entries, owner_id):
    """Accept files saved from a browser, matched by exact catalogue size and file name."""
    by_size = {}
    for entry in entries:
        if entry.get("catalogue_size"):
            by_size.setdefault(int(entry["catalogue_size"]), []).append(entry)
    results = []
    with tempfile.TemporaryDirectory(prefix="iroko-folder-") as directory:
        for path in sorted(Path(folder).iterdir()):
            if not path.is_file() or path.suffix.lower() not in ATTACHMENT_TYPES:
                continue
            candidates = by_size.get(path.stat().st_size, [])
            if len(candidates) > 1:
                named = [e for e in candidates if _name_key(attachment_filename(e["url"])) == _name_key(path.name)]
                candidates = named or candidates
            # Only a size match is checked against the regulator's catalogue.
            checks = {"size_verified_against": "regulator catalogue"} if candidates else {"matched_by": "official file name"}
            if not candidates:
                # Documents the catalogue gives no size for match on their exact official file name.
                candidates = [e for e in entries if not e.get("catalogue_size")
                              and _name_key(attachment_filename(e["url"])) == _name_key(path.name)]
            if len(candidates) != 1:
                results.append({"file": path.name, "status": "unmatched",
                                "reason": "no entry with this exact size" if not candidates else "ambiguous"})
                continue
            entry = candidates[0]
            try:
                existing = existing_document(db, entry)
                if existing:
                    results.append({"file": path.name, "id": entry.get("id"), "status": "exists", "document_id": existing})
                    continue
                document_id = await _accept(db, path.read_bytes(), entry, owner_id,
                                            {"acquisition": "browser_download_import", **checks}, directory)
                results.append({"file": path.name, "id": entry.get("id"), "status": "accepted", "document_id": document_id})
            except Exception as exc:
                db.rollback()
                results.append({"file": path.name, "id": entry.get("id"), "status": "failed",
                                "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
    return results


def summarise(results):
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def write_report(results, path):
    Path(path).write_text(
        json.dumps({"finished_at": datetime.utcnow().isoformat(), "counts": summarise(results),
                    "results": results}, indent=1),
        encoding="utf-8",
    )


def backfill_limits(uploads, queue=0):
    """An operator backfill may raise its own process's upload and queue quotas."""
    if uploads:
        os.environ["WORKSPACE_DAILY_UPLOAD_LIMIT"] = str(uploads)
    if queue:
        os.environ["WORKSPACE_PENDING_DOCUMENT_LIMIT"] = str(queue)
