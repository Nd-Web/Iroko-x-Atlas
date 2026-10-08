"""Regulator collection: challenges, re-verification, broken links and manual import."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from ingestion import batch, worker
from ingestion.models import Job, Revision, Source
from ingestion.pipeline import accept, process
from ingestion.queue import claim
from ingestion.sources import AccessChallenge, collect, parse_cbn
from models.database import Document, User, get_db
from services.auth_utils import create_access_token

LISTING = "https://www.cbn.gov.ng/api/GetAllCirculars"


def catalog(count, size=None):
    return json.dumps(
        [
            {
                "title": f"Circular {i}",
                "link": f"/Out/{i}.pdf",
                "refNo": f"CBN/TEST/{i:03d}",
                # Newest first after sorting: item 0 is the most recent.
                "documentDate": (datetime(2026, 9, 1) - timedelta(days=i)).strftime("%d/%m/%Y"),
                **({"filesize": str(size)} if size else {}),
            }
            for i in range(count)
        ]
    ).encode()


def fake_client(listing, respond):
    calls = []

    class Client:
        def __init__(self, regulator):
            pass

        async def fetch(self, url):
            calls.append(url)
            return (200, {}, listing) if "/api/" in url else respond(url)

        async def close(self):
            pass

    return Client, calls


@pytest.fixture
def source(db, monkeypatch):
    monkeypatch.setattr(
        "ingestion.sources.preserve", AsyncMock(return_value="https://storage.invalid/snapshot")
    )
    row = Source(
        id="cbn", regulator="CBN", url=LISTING, parser="cbn_json", enabled=True, owner_id="owner"
    )
    db.add(row)
    db.commit()
    return row


async def test_access_challenge_stops_run_and_lists_missing_items(
    db, adapters, monkeypatch, source
):
    def respond(url):
        raise AccessChallenge("browser check")

    client, calls = fake_client(catalog(5, size=1234), respond)
    monkeypatch.setattr("ingestion.sources.OfficialClient", client)
    await collect(db, "cbn")
    db.expire_all()
    result = db.get(Source, "cbn").result
    assert result["status"] == "blocked" and result["blocked"]
    # One refused file ends the run: the host is not asked for the other four.
    assert len(calls) == 2 and result["attempted"] == 1
    assert [i["reference_number"] for i in result["missing"]] == [
        f"CBN/TEST/{i:03d}" for i in range(5)
    ]
    assert result["missing"][0]["catalogue_size"] == 1234
    assert result["missing"][0]["importable"]
    assert result["failures"] == {}  # Challenges are retried next run, newest first.
    assert db.query(Document).count() == 0


async def test_imported_files_are_not_redownloaded_and_new_items_go_first(
    db, adapters, monkeypatch, source, pdf_bytes, tmp_path
):
    # Item 0 was imported by hand under the crawler's source key, without a crawl.
    path = tmp_path / "imported.pdf"
    path.write_bytes(pdf_bytes)
    await accept(
        db,
        str(path),
        "0.pdf",
        "Circular 0",
        "owner",
        {"source_url": "https://www.cbn.gov.ng/Out/0.pdf", "regulator": "CBN"},
        "regulator:CBN:https://www.cbn.gov.ng/Out/0.pdf",
    )
    source.max_documents = 2
    db.commit()
    client, calls = fake_client(catalog(4), lambda url: (200, {}, pdf_bytes))
    monkeypatch.setattr("ingestion.sources.OfficialClient", client)
    await collect(db, "cbn")
    downloads = [c for c in calls if "/api/" not in c]
    assert downloads == ["https://www.cbn.gov.ng/Out/1.pdf", "https://www.cbn.gov.ng/Out/2.pdf"]
    db.expire_all()
    result = db.get(Source, "cbn").result
    assert result["status"] == "succeeded"
    assert [i["source_url"] for i in result["missing"]] == ["https://www.cbn.gov.ng/Out/3.pdf"]
    # Filenames are readable, not percent-encoded URL fragments.
    assert {d.filename for d in db.query(Document)} == {"0.pdf", "1.pdf", "2.pdf"}


async def test_broken_link_backs_off_instead_of_consuming_every_run(
    db, adapters, monkeypatch, source, pdf_bytes
):
    def respond(url):
        if url.endswith("/0.pdf"):
            raise ValueError("Source document not found (404)")
        return 200, {}, pdf_bytes

    source.max_documents = 1
    db.commit()
    client, calls = fake_client(catalog(3), respond)
    monkeypatch.setattr("ingestion.sources.OfficialClient", client)
    await collect(db, "cbn")
    db.expire_all()
    first = db.get(Source, "cbn").result
    assert first["status"] == "partial" and first["accepted"] == 0
    assert first["failures"]["https://www.cbn.gov.ng/Out/0.pdf"]["count"] == 1
    calls.clear()
    await collect(db, "cbn")
    db.expire_all()
    second = db.get(Source, "cbn").result
    assert [c for c in calls if "/api/" not in c] == ["https://www.cbn.gov.ng/Out/1.pdf"]
    assert second["skipped_recent_failures"] == 1 and second["accepted"] == 1
    assert "https://www.cbn.gov.ng/Out/0.pdf" in second["failures"]


def test_cbn_parser_skips_malformed_rows_and_keeps_catalogue_size():
    rows = json.loads(catalog(2, size=99))
    rows.append({"title": "No date", "link": "/Out/x.pdf"})
    rows.append({"title": "Bad date", "link": "/Out/y.pdf", "documentDate": "31/13/2020"})
    parsed = parse_cbn(json.dumps(rows).encode(), LISTING)
    assert [p["title"] for p in parsed] == ["Circular 0", "Circular 1"]
    assert parsed[0]["catalogue_size"] == 99
    with pytest.raises(ValueError, match="no parseable"):
        parse_cbn(json.dumps(rows[2:]).encode(), LISTING)


@pytest.mark.parametrize(
    ("label", "url", "title"),
    [
        ("Download the Full SEC Guideline Document on Sec 60-63 of ISA 2007",
         "https://sec.gov.ng/documents/1/x.pdf", "SEC Guideline Document on Sec 60-63 of ISA 2007"),
        ("Explore the Full NCCG 2018 Guidelines Here \n      ",
         "https://sec.gov.ng/documents/2/x.pdf", "NCCG 2018 Guidelines"),
        ("Download the Full RI Guidelines of FinTechs Here\n pdf · 415.6 KB",
         "https://sec.gov.ng/documents/3/x.pdf", "RI Guidelines of FinTechs"),
        ("Download the reporting template (FORM 01) here", "https://sec.gov.ng/documents/4/x.pdf",
         "Reporting template (FORM 01)"),
        ("SEC Guideline on Sec 60 – 63 of ISA 2007 PDF (774.2 KB)",
         "https://sec.gov.ng/documents/5/x.pdf", "SEC Guideline on Sec 60 – 63 of ISA 2007"),
        ("Download", "https://sec.gov.ng/documents/1319/Investments_and_Securities_Act_2025_x9rSXtI.pdf",
         "Investments and Securities Act 2025"),
        ("Read more",
         "https://ndic.gov.ng/storage/cms/media/2023-preliminaries-0df1a38b-903c-4e0f-a821-4cbabd634fc6.pdf",
         "2023 preliminaries"),
        ("", "https://fccpc.gov.ng/wp-content/uploads/2022/07/FCCPA-2018.pdf", "FCCPA 2018"),
        ("Guidelines on Data Protection Impact Assessment", "https://ndpc.gov.ng/Files/x.pdf",
         "Guidelines on Data Protection Impact Assessment"),
        ("Document", "https://sec.gov.ng/documents/8/Rules-on-Issuance-Offering-and-Custody-of-Digital-Assets.pdf",
         "Rules on Issuance Offering and Custody of Digital Assets"),
        ("Preview Document",
         "https://ndic.gov.ng/storage/cms/media/ndic-act-2023-latest-14ab1a0a-82c7-4e05-9419-4b6e0afbfbc8.pdf",
         "Ndic act 2023 latest"),
        ("To delve deeper into these guidelines for Shareholders Associations and ensure your full "
         "compliance, we invite you to download the full document",
         "https://sec.gov.ng/documents/29/20090408210018Code-of-Conduct-for-Shareholders-Associations-in-Nigeria.pdf",
         "Code of Conduct for Shareholders Associations in Nigeria"),
    ],
)
def test_listing_titles_drop_link_boilerplate(label, url, title):
    from ingestion.sources import listing_title

    assert listing_title(label, url) == title


async def test_oversized_robots_file_is_read_up_to_its_limit(monkeypatch):
    """An HTML page served as robots.txt must not stop collection (RFC 9309 size limit)."""
    import httpx

    from ingestion.sources import OfficialClient

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, content=b"User-agent: *\nDisallow: /private/\n" + b"x" * 700_000)
        return httpx.Response(200, content=b"<html>listing</html>")

    monkeypatch.setattr(
        "ingestion.sources.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("41.58.0.10", 443))],
    )
    monkeypatch.setattr("ingestion.sources.asyncio.sleep", AsyncMock())
    client = OfficialClient("NFIU", attempts=1)
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        code, _, body = await client.fetch("https://nfiu.gov.ng/")
        assert code == 200 and body == b"<html>listing</html>"
        with pytest.raises(ValueError, match="robots"):
            await client.fetch("https://nfiu.gov.ng/private/report.pdf")
    finally:
        await client.close()


async def test_scheduled_drain_queues_only_due_recurring_sources(db, monkeypatch):
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(batch, "Session", factory)
    monkeypatch.setattr(worker, "Session", factory)
    db.add_all(
        [
            Source(id="manual", regulator="SEC", url="https://sec.gov.ng/a/", parser="html_links",
                   enabled=True, owner_id="owner"),
            Source(id="daily", regulator="SEC", url="https://sec.gov.ng/b/", parser="html_links",
                   enabled=True, interval_hours=24, owner_id="owner",
                   last_run=datetime.utcnow() - timedelta(hours=25)),
            Source(id="recent", regulator="SEC", url="https://sec.gov.ng/c/", parser="html_links",
                   enabled=True, interval_hours=24, owner_id="owner",
                   last_run=datetime.utcnow() - timedelta(hours=1)),
        ]
    )
    db.commit()
    collected = []

    async def fake_collect(session, source_id):
        collected.append(source_id)

    monkeypatch.setattr(worker, "collect", fake_collect)
    await batch.drain(max_seconds=5, poll_seconds=0.01, allow_idle=True)
    assert collected == ["daily"]
    assert db.query(Job).filter_by(kind="source").count() == 1


async def test_parser_rejection_fails_immediately_with_reason(db, adapters, monkeypatch, content):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")

    def reject(path, file_type):
        raise ValueError("Document parser rejected the file or exceeded its resource limit")

    monkeypatch.setattr("ingestion.extraction.bounded_native_pages", reject)
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(worker, "Session", factory)
    assert await worker.run_once(include_scheduled=False)
    db.expire_all()
    job = db.get(Job, f"document:{doc.id}")
    assert job.state == "failed" and job.attempts == 1
    stored = db.get(Document, doc.id)
    assert stored.status == "failed"
    assert "parser rejected" in stored.error_message


async def test_short_text_document_is_indexed_without_review(db, adapters, tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("Board meets on Friday.", encoding="utf-8")
    doc = await accept(db, note, "note.txt", "Note", "owner")
    await process(db, *claim(db))
    db.expire_all()
    assert db.get(Document, doc.id).status == "indexed"
    assert db.get(Revision, doc.id).issues == []


async def test_reviewer_supplied_publication_date_reaches_provenance_and_index(
    db, adapters, content
):
    from datetime import date

    from ingestion.pipeline import review

    doc = await accept(
        db, content, "guideline.txt", "Guideline", "owner",
        {"regulator": "SEC", "source_url": "https://sec.gov.ng/documents/1/guideline.pdf"},
        "regulator:SEC:https://sec.gov.ng/documents/1/guideline.pdf",
    )
    await process(db, *claim(db))
    db.expire_all()
    assert db.get(Document, doc.id).status == "review_required"
    assert db.get(Revision, doc.id).issues == [{"reasons": ["publication_date_missing"]}]
    review(db, doc.id, "owner", "approve", "Date read from page 1", date(2024, 3, 5))
    await process(db, *claim(db))
    db.expire_all()
    assert db.get(Document, doc.id).status == "indexed"
    provenance = db.get(Revision, doc.id).provenance
    assert provenance["published_date"] == "2024-03-05"
    assert provenance["date_basis"] == "reviewer_confirmed"
    assert adapters[1].await_args.args[3]["published_date"] == "2024-03-05"


# ── Manual import of a listed file the crawler could not download ──────────────


@pytest.fixture
def api(db, monkeypatch):
    from ingestion.api import router

    monkeypatch.setenv("DOCUMENT_PIPELINE_ENABLED", "true")
    db.add(User(id="root", email="root@example.invalid", hashed_password="x", role="superadmin"))
    db.commit()
    app = FastAPI()
    app.include_router(router)

    def dependency():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as client:
        yield client


def auth(user_id, role):
    return {"Authorization": "Bearer " + create_access_token(user_id, role)}


def listed_source(db, size):
    url = "https://www.cbn.gov.ng/Out/2026/OFISD/Circular%20A.pdf"
    item = {
        "title": "Circular A",
        "source_url": url,
        "regulator": "CBN",
        "reference_number": "OFI/DIR/001",
        "published_date": "2026-08-01",
        "listing_url": LISTING,
        "catalogue_size": size,
        "importable": True,
    }
    db.add(
        Source(id="cbn", regulator="CBN", url=LISTING, parser="cbn_json", enabled=True,
               owner_id="root", result={"status": "blocked", "missing": [item], "missing_total": 1})
    )
    db.commit()
    return url


async def test_import_accepts_catalogue_matching_file_with_official_provenance(
    api, db, adapters, pdf_bytes
):
    url = listed_source(db, len(pdf_bytes))
    response = api.post(
        "/api/ingestion/sources/cbn/import",
        headers=auth("root", "superadmin"),
        data={"source_url": url},
        files={"file": ("download.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    doc = db.get(Document, response.json()["document_id"])
    assert doc.filename == "Circular A.pdf" and doc.title == "Circular A"
    revision = db.get(Revision, doc.id)
    assert revision.source_key == f"regulator:CBN:{url}"
    assert revision.provenance["reference_number"] == "OFI/DIR/001"
    assert revision.provenance["acquisition"] == "browser_download_import"
    db.expire_all()
    assert db.get(Source, "cbn").result["missing"] == []


async def test_import_rejects_wrong_size_unlisted_link_and_non_platform_admin(
    api, db, adapters, pdf_bytes
):
    url = listed_source(db, len(pdf_bytes) + 1)
    post = lambda headers, link=url: api.post(  # noqa: E731
        "/api/ingestion/sources/cbn/import",
        headers=headers,
        data={"source_url": link},
        files={"file": ("download.pdf", pdf_bytes, "application/pdf")},
    )
    wrong_size = post(auth("root", "superadmin"))
    assert wrong_size.status_code == 422 and "catalogue lists" in wrong_size.json()["detail"]
    unlisted = post(auth("root", "superadmin"), "https://www.cbn.gov.ng/Out/other.pdf")
    assert unlisted.status_code == 409
    assert post(auth("owner", "admin")).status_code == 403
    assert db.query(Document).count() == 0
