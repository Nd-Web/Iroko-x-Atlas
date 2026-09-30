from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from ingestion.models import Chunk, Job, Revision
from ingestion.pipeline import accept, process, reindex, review
from ingestion.queue import MAX_ATTEMPTS, claim
from models.database import Document


async def test_source_run_persists_results_and_queues_downloaded_original(
    db, adapters, monkeypatch
):
    import json

    from ingestion.models import CrawlRun, Source
    from ingestion.sources import collect

    catalog = json.dumps(
        [
            {
                "title": "Test circular",
                "link": "/Out/test.pdf",
                "refNo": "CBN/TEST/001",
                "documentDate": "30/09/2026",
            }
        ]
    ).encode()

    class Client:
        def __init__(self, regulator):
            pass

        async def fetch(self, url):
            return 200, {}, catalog if "/api/" in url else b"%PDF- synthetic preserved file"

        async def close(self):
            pass

    monkeypatch.setattr("ingestion.sources.OfficialClient", Client)
    monkeypatch.setattr(
        "ingestion.sources.preserve", AsyncMock(return_value="https://storage.invalid/snapshot")
    )
    source = Source(
        id="cbn",
        regulator="CBN",
        url="https://www.cbn.gov.ng/api/GetAllCirculars",
        parser="cbn_json",
        enabled=True,
        owner_id="owner",
    )
    db.add(source)
    db.commit()
    await collect(db, "cbn")
    db.expire_all()
    run = db.query(CrawlRun).one()
    assert run.result["status"] == "succeeded"
    assert run.result["accepted"] == 1
    assert run.result["snapshot_sha256"]
    assert db.query(Document).one().status == "pending"
    assert db.query(Revision).one().provenance["published_date"] == "2026-09-30"
    await collect(db, "cbn")
    assert db.query(Document).count() == 1
    assert db.query(CrawlRun).count() == 2


async def test_reindex_uses_saved_evidence_without_downloading_or_extracting(
    db, content, adapters, monkeypatch
):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    await process(db, *claim(db))
    download = AsyncMock(side_effect=AssertionError("Reindex must not fetch or OCR original"))
    monkeypatch.setattr("services.blob_storage.download_document", download)
    count = db.query(Chunk).count()
    reindex(db, doc.id)
    await process(db, *claim(db))
    assert doc.status == "indexed"
    assert db.query(Chunk).count() == count
    download.assert_not_awaited()


async def test_late_old_version_cannot_displace_newer_published_version(db, content, adapters):
    original = await accept(db, content, "policy.txt", "Policy", "owner")
    await process(db, *claim(db))
    content.write_text(content.read_text() + "\nAmendment one: revised records.")
    middle = await accept(db, content, "policy.txt", "Policy v2", "owner")
    await process(db, *claim(db))
    content.write_text(content.read_text() + "\nAmendment two: updated retention.")
    latest = await accept(db, content, "policy.txt", "Policy v3", "owner")
    await process(db, *claim(db))
    review(db, latest.id, "owner", "approve", "Verified the latest source")
    await process(db, *claim(db))
    review(db, middle.id, "owner", "approve", "Reviewed a delayed older upload")
    await process(db, *claim(db))
    assert db.get(Revision, latest.id).is_current
    assert not db.get(Revision, middle.id).is_current
    assert middle.status == "superseded"
    assert original.status == "superseded"


async def test_exhausted_crashed_job_becomes_visible_failure(db, content, adapters):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    lease = claim(db)
    job = db.get(Job, lease[0])
    job.attempts = MAX_ATTEMPTS
    job.lease_until = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert claim(db) is None
    db.expire_all()
    assert db.get(Job, lease[0]).state == "failed"
    assert db.get(Document, doc.id).status == "failed"


async def test_checksum_mismatch_prevents_extraction(db, content, adapters):
    doc = await accept(db, content, "policy.txt", "Policy", "owner")
    adapters[0][doc.id] = b"Unexpected modified original"
    with pytest.raises(ValueError, match="checksum"):
        await process(db, *claim(db))
    assert db.query(Chunk).count() == 0
    assert adapters[1].await_count == 0
