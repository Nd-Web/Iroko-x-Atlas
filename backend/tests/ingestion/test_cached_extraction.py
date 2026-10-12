"""Saved evidence imports are atomic, source-bound and fail closed on quality."""
import hashlib
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from ingestion.cached_extraction import validate_cached
from ingestion.extraction import normalize, page
from ingestion.models import Chunk, Job, Page, Revision
from ingestion.pipeline import accept, process
from ingestion.queue import claim
from ingestion.sources import official_url
from models.database import Document


def bundle_for(path, pages):
    return {"extractor_version": "test-v1", "source": {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, "pages": pages}


@pytest.fixture
def cached_pdf(tmp_path):
    from reportlab.pdfgen.canvas import Canvas

    path = tmp_path / "reference.pdf"
    canvas = Canvas(str(path))
    canvas.drawString(20, 700, "Verified regulatory reference")
    canvas.save()
    saved = page("SOURCE\n" + "Institutions must retain complete records for compliance review. " * 12, 1, method="pdf_text")
    return path, bundle_for(path, [saved])


async def test_cached_accept_saves_checkpoint_before_job_is_committed(db, cached_pdf, adapters, monkeypatch):
    path, bundle = cached_pdf
    original = deepcopy(bundle)
    doc = await accept(db, path, path.name, "Reference", "owner", cached_extraction=bundle)
    assert db.query(Page).filter_by(document_id=doc.id).count() == 1
    assert db.query(Chunk).filter_by(document_id=doc.id).count() > 0
    assert db.get(Job, f"document:{doc.id}").state == "queued"
    artifact = db.get(Revision, doc.id).provenance["cached_extraction"]
    assert artifact["artifact_sha256"] and artifact["artifact_url"].endswith("extracted-evidence-v1.json")
    assert bundle == original
    monkeypatch.setattr("ingestion.extraction.bounded_native_pages", lambda *args: pytest.fail("Repeated extraction"))
    monkeypatch.setattr("ingestion.extraction.ocr_pages", lambda *args: pytest.fail("Repeated paid OCR"))
    await process(db, *claim(db))
    assert doc.status == "indexed"
    assert adapters[1].await_count == 1


async def test_cached_duplicate_never_overwrites_existing_evidence(db, cached_pdf, adapters):
    path, bundle = cached_pdf
    first = await accept(db, path, path.name, "Reference", "owner", cached_extraction=bundle)
    second = await accept(db, path, path.name, "Other title", "owner", cached_extraction=bundle)
    assert first.id == second.id
    assert db.query(Document).count() == db.query(Revision).count() == db.query(Job).count() == 1
    assert db.query(Page).count() == 1


async def test_mismatched_cached_checksum_never_uploads_or_accepts(db, cached_pdf, monkeypatch):
    path, bundle = cached_pdf
    bundle["source"]["sha256"] = "0" * 64
    preserve = AsyncMock()
    monkeypatch.setattr("ingestion.pipeline.preserve", preserve)
    with pytest.raises(ValueError, match="checksum"):
        await accept(db, path, path.name, "Reference", "owner", cached_extraction=bundle)
    assert preserve.await_count == 0 and db.query(Document).count() == 0


@pytest.mark.parametrize("numbers", [[], [2], [1, 1]])
def test_cached_pdf_cannot_skip_or_duplicate_physical_pages(cached_pdf, numbers):
    path, bundle = cached_pdf
    bundle["pages"] = [page("text", number, method="pdf_text") for number in numbers]
    with pytest.raises(ValueError, match="records|physical PDF"):
        validate_cached(bundle, bundle["source"]["sha256"], "pdf", path)


def test_cached_text_cannot_be_rewritten_or_misreport_quality(cached_pdf):
    path, bundle = cached_pdf
    bundle["pages"][0]["text"] = "invented text"
    with pytest.raises(ValueError, match="normalization"):
        validate_cached(bundle, bundle["source"]["sha256"], "pdf", path)
    bundle["pages"][0]["text"] = normalize(bundle["pages"][0]["raw_text"])
    bundle["pages"][0]["quality"]["characters"] = 123456
    with pytest.raises(ValueError, match="quality counts"):
        validate_cached(bundle, bundle["source"]["sha256"], "pdf", path)


@pytest.mark.parametrize("flag", ["low_confidence_numeric_tokens", "layout_review_required", "local_ocr_manual_review_required"])
async def test_uncertain_saved_evidence_is_held_without_search_or_ocr(db, cached_pdf, adapters, flag):
    path, bundle = cached_pdf
    bundle["pages"][0]["quality"][flag] = [{"text": "5000", "confidence": 0.5}] if flag == "low_confidence_numeric_tokens" else True
    doc = await accept(db, path, path.name, "Reference", "owner", cached_extraction=bundle)
    assert doc.status == db.get(Job, f"document:{doc.id}").state == "review_required"
    assert db.get(Revision, doc.id).review_status == "required"
    assert adapters[1].await_count == 0 and claim(db) is None


async def test_known_draft_cannot_become_binding_evidence(db, cached_pdf, adapters):
    path, bundle = cached_pdf
    doc = await accept(db, path, path.name, "Draft", "owner", {"legal_status": "draft - not binding"}, cached_extraction=bundle)
    assert doc.status == "review_required" and not db.get(Revision, doc.id).is_current
    assert adapters[1].await_count == 0


async def test_artifact_upload_failure_accepts_no_partial_database_evidence(db, cached_pdf, monkeypatch):
    path, bundle = cached_pdf
    calls = []
    async def preserve(path, doc_id, filename):
        calls.append(filename)
        if filename.endswith(".json"):
            raise RuntimeError("artifact upload unavailable")
        return "https://storage.invalid/original.pdf"
    monkeypatch.setattr("ingestion.pipeline.preserve", preserve)
    with pytest.raises(RuntimeError, match="artifact upload"):
        await accept(db, path, path.name, "Reference", "owner", cached_extraction=bundle)
    db.rollback()
    assert db.query(Document).count() == db.query(Revision).count() == db.query(Page).count() == db.query(Job).count() == 0


def test_frc_official_urls_use_exact_domains_not_lookalikes():
    assert official_url("https://frcnigeria.gov.ng/wp-content/uploads/reference.pdf", "FRC")
    with pytest.raises(ValueError):
        official_url("https://frcnigeria.gov.ng.attacker.invalid/reference.pdf", "FRC")
