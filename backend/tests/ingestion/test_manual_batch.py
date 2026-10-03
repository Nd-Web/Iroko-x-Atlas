"""An Azure manual job must finish finite work without starting other sources."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from ingestion import batch, worker
from ingestion.models import CrawlRun, Job, Source
from ingestion.queue import enqueue, finish


def _sessions(db, monkeypatch):
    factory = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(batch, "Session", factory)
    monkeypatch.setattr(worker, "Session", factory)


async def test_manual_batch_drains_source_and_documents_without_scheduling(db, monkeypatch):
    _sessions(db, monkeypatch)
    db.add(
        Source(
            id="cbn",
            regulator="CBN",
            url="https://www.cbn.gov.ng/test",
            parser="cbn_json",
            enabled=True,
            interval_hours=6,
            owner_id="owner",
        )
    )
    enqueue(db, "source", "cbn")
    db.commit()

    def unexpected_schedule(_):
        raise AssertionError("Manual drain must not schedule recurring sources")

    async def collect(session, source_id):
        session.add(
            CrawlRun(
                source_id=source_id,
                result={"status": "succeeded", "found": 1, "accepted": 1, "errors": []},
            )
        )
        enqueue(session, "document", "doc-1")
        session.commit()

    async def process(session, key, token):
        finish(session, key, token)

    monkeypatch.setattr(worker, "schedule", unexpected_schedule)
    monkeypatch.setattr(worker, "collect", collect)
    monkeypatch.setattr(worker, "process", process)

    result = await batch.drain(max_seconds=5, poll_seconds=0.01)
    assert result["processed_jobs"] == 2
    db.expire_all()
    assert db.get(Job, "source:cbn").state == "done"
    assert db.get(Job, "document:doc-1").state == "done"


async def test_manual_batch_reports_partial_source_failure(db, monkeypatch):
    _sessions(db, monkeypatch)
    enqueue(db, "source", "cbn")
    db.commit()

    async def collect(session, source_id):
        session.add(
            CrawlRun(
                source_id=source_id,
                result={
                    "status": "succeeded",
                    "found": 1,
                    "accepted": 0,
                    "errors": [{"url": "https://www.cbn.gov.ng/bad.pdf", "error": "HTTPError"}],
                },
            )
        )
        session.commit()

    monkeypatch.setattr(worker, "collect", collect)
    with pytest.raises(batch.BatchIncomplete, match="sources with errors"):
        await batch.drain(max_seconds=5, poll_seconds=0.01)
    assert db.get(Job, "source:cbn").state == "done"


async def test_manual_batch_reports_exhausted_document_job(db, monkeypatch):
    _sessions(db, monkeypatch)
    db.add(
        Job(
            id="document:bad",
            kind="document",
            target_id="bad",
            state="queued",
            attempts=4,
            available_at=datetime.utcnow(),
        )
    )
    db.commit()

    async def process(session, key, token):
        finish(session, key, token, error="extraction failed")

    monkeypatch.setattr(worker, "process", process)
    with pytest.raises(batch.BatchIncomplete, match="failed jobs"):
        await batch.drain(max_seconds=5, poll_seconds=0.01)
    db.expire_all()
    assert db.get(Job, "document:bad").state == "failed"


async def test_manual_batch_waits_for_retry_then_times_out(db, monkeypatch):
    _sessions(db, monkeypatch)
    db.add(
        Job(
            id="document:later",
            kind="document",
            target_id="later",
            state="retry",
            attempts=1,
            available_at=datetime.utcnow() + timedelta(hours=1),
        )
    )
    db.commit()
    with pytest.raises(batch.BatchIncomplete, match="timed out with 1 unfinished"):
        await batch.drain(max_seconds=0.03, poll_seconds=0.005)


async def test_manual_batch_requires_queued_work(db, monkeypatch):
    _sessions(db, monkeypatch)
    with pytest.raises(batch.BatchIncomplete, match="No queued work"):
        await batch.drain(max_seconds=5, poll_seconds=0.01)
