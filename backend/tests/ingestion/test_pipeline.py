import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ingestion.chunking import chunk_pages
from ingestion.extraction import native_pages, page
from ingestion.models import Chunk, Job, Page, PipelineBase, Revision
from ingestion.pipeline import accept, process, reprocess, review
from ingestion.queue import claim, enqueue, finish, heartbeat
from ingestion.sources import official_url, parse_cbn, parse_links, robots_allowed
from models.database import Base, Document


async def test_accept_is_durable_and_duplicate_is_idempotent(db, content, adapters):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    again = await accept(db, content, "policy.txt", "Policy", "owner")
    assert doc.id == again.id
    assert doc.status == "pending"
    assert db.query(Job).count() == db.query(Revision).count() == db.query(Document).count() == 1
    assert adapters[1].await_count == 0
    assert db.get(Revision, doc.id).sha256 == hashlib.sha256(content.read_bytes()).hexdigest()


async def test_storage_failure_does_not_accept_document(db, content, monkeypatch):
    monkeypatch.setattr(
        "ingestion.pipeline.preserve", AsyncMock(side_effect=RuntimeError("offline"))
    )
    with pytest.raises(RuntimeError, match="offline"):
        await accept(db, content, "policy.txt", "Policy", "owner")
    assert db.query(Document).count() == db.query(Job).count() == 0


async def test_process_saves_exact_pages_chunks_and_publishes(db, content, adapters):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    key, token = claim(db)
    await process(db, key, token)
    assert doc.status == "indexed"
    assert db.get(Revision, doc.id).is_current
    assert db.get(Job, key).state == "done"
    extracted = db.query(Page).filter_by(document_id=doc.id).one()
    assert extracted.page_number is None
    for chunk in db.query(Chunk).filter_by(document_id=doc.id):
        assert (
            chunk.content
            == extracted.text[chunk.provenance["char_start"] : chunk.provenance["char_end"]]
        )
    assert db.get(Revision, doc.id).extraction["obligation_candidates"]


async def test_new_version_waits_for_review_and_replaces_current_only_when_indexed(
    db, content, adapters
):
    original = await accept(db, content, "policy.txt", "Policy", "owner")
    await process(db, *claim(db))
    content.write_text(
        content.read_text() + "\nAdditional procedures must be documented.", encoding="utf-8"
    )
    updated = await accept(db, content, "policy.txt", "Policy v2", "owner")
    await process(db, *claim(db))
    assert updated.status == "review_required"
    assert db.get(Revision, original.id).is_current
    assert not db.get(Revision, updated.id).is_current
    assert adapters[1].await_count == 1
    review(db, updated.id, "owner", "approve", "Checked against the signed policy")
    await process(db, *claim(db))
    assert updated.status == "indexed"
    assert db.get(Revision, updated.id).previous_id == original.id
    assert not db.get(Revision, original.id).is_current


async def test_index_failure_retains_extraction_checkpoint(db, content, adapters):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    adapters[1].return_value = False
    lease = claim(db)
    with pytest.raises(RuntimeError, match="indexing"):
        await process(db, *lease)
    assert db.query(Page).filter_by(document_id=doc.id).count() == 1
    assert not db.get(Revision, doc.id).is_current
    finish(db, *lease, error="offline")
    job = db.get(Job, lease[0])
    assert job.state == "retry"
    job.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    adapters[1].return_value = True
    await process(db, *claim(db))
    assert db.query(Page).filter_by(document_id=doc.id).count() == 1
    assert doc.status == "indexed"


async def test_scanned_page_with_missing_ocr_is_held_and_cannot_be_approved(
    db, content, adapters, monkeypatch, pdf_bytes
):
    content.write_bytes(pdf_bytes)
    doc = await accept(db, content, "scan.pdf", "Scan", "owner")
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", raising=False)
    await process(db, *claim(db))
    assert doc.status == "review_required"
    assert adapters[1].await_count == 0
    with pytest.raises(ValueError, match="Incomplete OCR"):
        review(db, doc.id, "owner", "approve", "Accept")
    reprocess(db, doc.id)
    assert db.query(Page).count() == 0
    assert db.get(Job, f"document:{doc.id}").state == "queued"


def test_worker_lease_fences_old_worker_and_recovers_crash(db):
    enqueue(db, "document", "test")
    db.commit()
    first = claim(db)
    assert claim(db) is None
    job = db.get(Job, first[0])
    job.lease_until = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    second = claim(db)
    assert second[1] != first[1]
    assert not heartbeat(db, *first)
    with pytest.raises(RuntimeError, match="lease lost"):
        finish(db, *first)
    assert heartbeat(db, *second)
    finish(db, *second)


def test_chunk_substrings_have_real_page_numbers_and_bounded_unicode_tokens():
    pages = [
        page("SECTION ONE\n\n" + "MFBs must retain records. ₦100,000. " * 100, 1),
        page("SECOND SECTION\n\n" + "Fintech compliance review. " * 100, 2),
    ]
    chunks = chunk_pages(pages, target=100, maximum=120, overlap=10)
    full = "\n\n".join(p["text"] for p in pages)
    assert len(chunks) > 4
    assert chunks[0]["char_start"] == 0
    assert chunks[-1]["char_end"] == len(full)
    for chunk in chunks:
        assert chunk["content"] == full[chunk["char_start"] : chunk["char_end"]]
        assert chunk["token_count"] <= 120
        assert chunk["page_start"] in {1, 2}
    assert all(b["char_start"] <= a["char_end"] for a, b in zip(chunks, chunks[1:], strict=False))


def test_pdf_native_extraction_has_actual_pages(tmp_path):
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "pages.pdf"
    canvas = Canvas(str(path))
    canvas.drawString(20, 700, "Page one records")
    canvas.showPage()
    canvas.drawString(20, 700, "Page two obligations")
    canvas.save()
    pages = native_pages(str(path), "pdf")
    assert [p["page_number"] for p in pages] == [1, 2]
    assert "Page two obligations" in pages[1]["text"]


def test_cbn_fixture_dates_and_reference_are_preserved():
    path = Path(__file__).parent / "fixtures/cbn/api-all-sample.json"
    records = parse_cbn(path.read_bytes(), "https://www.cbn.gov.ng/api/GetAllCirculars")
    assert records
    assert any(r["published_date"] == "2012-08-01" for r in records)
    assert all(r["source_url"].startswith("https://www.cbn.gov.ng/") for r in records)


@pytest.mark.parametrize(
    "url",
    [
        "http://cbn.gov.ng/file.pdf",
        "https://evil.test/file.pdf",
        "https://cbn.gov.ng@evil.test/file.pdf",
        "https://cbn.gov.ng:8000/file.pdf",
    ],
)
def test_official_url_rejects_nonofficial_targets(url):
    with pytest.raises(ValueError):
        official_url(url, "CBN")


def test_official_url_preserves_path_case_and_escapes_spaces():
    assert (
        official_url("/Out/Policy A.pdf#page=3", "CBN", "https://www.cbn.gov.ng/documents/")
        == "https://www.cbn.gov.ng/Out/Policy%20A.pdf"
    )


def test_robots_longest_match_wildcard_and_specific_agent():
    rules = "User-agent: *\nAllow: /\nDisallow: /museum/\nDisallow: /*.asp$\nAllow: /museum/open/"
    assert not robots_allowed(rules, "https://www.cbn.gov.ng/museum/private")
    assert not robots_allowed(rules, "https://www.cbn.gov.ng/old.asp")
    assert robots_allowed(rules, "https://www.cbn.gov.ng/museum/open/index")
    assert robots_allowed(rules, "https://www.cbn.gov.ng/api/GetAllCirculars")


def test_listing_deduplicates_and_ignores_unapproved_hosts():
    result = parse_links(
        b'<a href="/Out/a.pdf">A</a><a href="/Out/a.pdf">A again</a><a href="https://evil.test/a.pdf">Evil</a>',
        "CBN",
        "https://www.cbn.gov.ng/documents/",
    )
    assert len(result) == 1


async def test_retrieval_excludes_unapproved_old_and_partial_chunks(
    db, content, adapters, monkeypatch
):
    from contextlib import contextmanager

    from services.azure_search import eligible_results

    monkeypatch.setenv("DOCUMENT_PIPELINE_ENABLED", "true")

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr("ingestion.db.Session", session)
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    await process(db, *claim(db))
    chunk = db.query(Chunk).filter_by(document_id=doc.id).first()
    hit = {"id": chunk.id, "doc_id": doc.id, "content": chunk.content}
    from ingestion.access import Principal, as_user

    with as_user(Principal("owner", "admin")):
        assert eligible_results([hit])[0]["provenance"]["sha256"]
    assert not eligible_results([{**hit, "content": "stale partial index text"}])
    db.get(Revision, doc.id).is_current = False
    db.commit()
    assert not eligible_results([hit])


async def test_missing_search_client_never_reports_success(monkeypatch):
    from services import azure_search

    monkeypatch.setattr(azure_search, "get_search_client", lambda: None)
    assert not await azure_search.index_document_chunks("id", "Title", ["text"], {})


def test_pipeline_metadata_is_isolated():
    assert len(PipelineBase.metadata.tables) == 12
    assert PipelineBase.metadata is not Base.metadata
    assert all(t.schema == "ingestion" for t in PipelineBase.metadata.tables.values())
