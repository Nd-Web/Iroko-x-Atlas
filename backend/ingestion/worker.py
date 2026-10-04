"""Run in a separate process: python -m ingestion worker."""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

from ingestion.db import Session
from ingestion.models import Job, Source
from ingestion.pipeline import process
from ingestion.queue import claim, enqueue, finish, heartbeat
from ingestion.sources import collect
from models.database import Document

logger = logging.getLogger(__name__)


async def renew(key, token):
    while True:
        await asyncio.sleep(30)
        try:
            with Session() as db:
                if not heartbeat(db, key, token):
                    return
        except Exception:
            # The final checkpoint still verifies ownership after any DB outage.
            logger.exception("Could not renew ingestion lease %s", key)
            continue


def schedule(db):
    now = datetime.utcnow()
    for source in db.query(Source).filter_by(enabled=True).all():
        if source.interval_hours <= 0:
            continue  # Manual-only sources must never acquire an automatic batch.
        if not source.last_run or source.last_run + timedelta(hours=source.interval_hours) <= now:
            enqueue(db, "source", source.id)
    db.commit()


async def run_once(*, include_scheduled=True):
    with Session() as db:
        if include_scheduled:
            schedule(db)
        lease = claim(db)
        if not lease:
            return False
        key, token = lease
        pulse = asyncio.create_task(renew(key, token))
        try:
            job = db.get(Job, key)
            if job.kind == "source":
                await collect(db, job.target_id)
                finish(db, key, token)
            else:
                await process(db, key, token)
        except Exception as exc:
            db.rollback()
            logger.exception("Ingestion job %s failed", key)
            # Validation, checksum and parser errors are deterministic and raised
            # with user-facing messages; outages and lost leases are retried.
            permanent = isinstance(exc, ValueError)
            try:
                finish(
                    db,
                    key,
                    token,
                    error=f"{type(exc).__name__}: {str(exc)[:300]}",
                    permanent=permanent,
                )
                job = db.get(Job, key)
                if job.kind == "document":
                    doc = db.get(Document, job.target_id)
                    if doc:
                        doc.status = "failed" if job.state == "failed" else "pending"
                        reason = f" {str(exc)[:200].rstrip('.')}." if permanent else ""
                        doc.error_message = (
                            "Processing failed; retry scheduled."
                            if job.state == "retry"
                            else f"Processing failed.{reason} An administrator can reprocess this document."
                        )
                        db.commit()
            except RuntimeError:
                db.rollback()  # Another worker owns the expired lease.
        finally:
            pulse.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pulse
    return True


async def run():
    while True:
        try:
            worked = await run_once()
        except Exception:
            logger.exception("Ingestion worker database unavailable")
            worked = False
        if not worked:
            await asyncio.sleep(5)
