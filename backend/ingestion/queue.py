"""Durable jobs with bounded retries, crash recovery and lease fencing."""

import os
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, update

from ingestion.models import Job

LEASE_SECONDS = 300
MAX_ATTEMPTS = 5


def enqueue(db, kind, target_id):
    key = f"{kind}:{target_id}"
    job = db.get(Job, key)
    if job:
        if job.state in {"running", "queued", "retry"}:
            return job
        job.state, job.attempts, job.error = "queued", 0, None
        job.available_at = datetime.utcnow()
    else:
        job = Job(id=key, kind=kind, target_id=target_id)
        db.add(job)
    return job


def claim(db):
    now = datetime.utcnow()
    eligible = or_(
        and_(Job.state.in_(["queued", "retry"]), Job.available_at <= now),
        and_(Job.state == "running", Job.lease_until < now),
    )
    # Exhausted crashed workers must not leave jobs running forever.
    from models.database import Document

    exhausted_ids = db.query(Job.target_id).filter(
        eligible, Job.attempts >= MAX_ATTEMPTS, Job.kind == "document"
    )
    db.query(Document).filter(Document.id.in_(exhausted_ids)).update(
        {
            "status": "failed",
            "error_message": "Processing interrupted too many times; reprocess to retry.",
        },
        synchronize_session=False,
    )
    db.execute(
        update(Job)
        .where(eligible, Job.attempts >= MAX_ATTEMPTS)
        .values(
            state="failed",
            error="Retry limit reached; reprocess after investigating.",
            lease_token=None,
            lease_until=None,
        )
    )
    job = (
        db.query(Job)
        .filter(eligible, Job.attempts < MAX_ATTEMPTS)
        .order_by(Job.available_at)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not job:
        db.commit()
        return None
    token = str(uuid4())
    changed = db.execute(
        update(Job)
        .where(Job.id == job.id, eligible)
        .values(
            state="running",
            lease_token=token,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
            attempts=Job.attempts + 1,
        )
    ).rowcount
    key = job.id
    db.commit()
    return (key, token) if changed else None


def heartbeat(db, key, token):
    count = db.execute(
        update(Job)
        .where(
            Job.id == key,
            Job.lease_token == token,
            Job.state == "running",
            Job.lease_until > datetime.utcnow(),
        )
        .values(lease_until=datetime.utcnow() + timedelta(seconds=LEASE_SECONDS))
    ).rowcount
    db.commit()
    return bool(count)


def owned(db, key, token):
    job = (
        db.query(Job)
        .filter(
            Job.id == key,
            Job.lease_token == token,
            Job.state == "running",
            Job.lease_until > datetime.utcnow(),
        )
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not job:
        raise RuntimeError("Processing lease lost")
    return job


def finish(db, key, token, error=None, state="done"):
    job = owned(db, key, token)
    job.lease_token, job.lease_until = None, None
    job.error = error
    job.state = ("failed" if job.attempts >= MAX_ATTEMPTS else "retry") if error else state
    if error:
        job.available_at = datetime.utcnow() + timedelta(seconds=min(3600, 30 * 2**job.attempts))
    db.commit()


def enabled():
    return os.getenv("DOCUMENT_PIPELINE_ENABLED", "false").lower() == "true"
