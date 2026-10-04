"""Finite, manual-only queue drain for an on-demand container job."""

import asyncio
import logging
import time
from datetime import datetime

from ingestion.db import Session
from ingestion.models import CrawlRun, Job
from ingestion.worker import run_once, schedule

logger = logging.getLogger(__name__)
PENDING_STATES = ("queued", "retry", "running")


class BatchIncomplete(RuntimeError):
    """The execution stopped without a clean, fully processed batch."""


def _snapshot():
    with Session() as db:
        return {job.id: job.attempts for job in db.query(Job).filter_by(state="failed")}


def _status(started_at, previously_failed):
    with Session() as db:
        pending = db.query(Job).filter(Job.state.in_(PENDING_STATES)).count()
        new_failures = [
            job.id
            for job in db.query(Job).filter_by(state="failed")
            if job.attempts != previously_failed.get(job.id)
        ]
        runs = db.query(CrawlRun).filter(CrawlRun.started_at >= started_at).all()
        source_results = [
            {
                "source_id": run.source_id,
                "status": run.result.get("status"),
                "found": run.result.get("found", 0),
                "accepted": run.result.get("accepted", 0),
                "errors": run.result.get("errors", []),
            }
            for run in runs
        ]
    return pending, new_failures, source_results


async def drain(max_seconds=5400, poll_seconds=5, *, allow_idle=False):
    """Run queued jobs to quiescence, waiting for bounded retries.

    A manual drain (``allow_idle=False``) never schedules recurring sources, and a
    failed source crawl, partial source download or newly exhausted document job
    makes the execution fail visibly.

    A scheduled drain (``allow_idle=True``) first queues sources whose explicitly
    configured interval is due; manual-only sources (interval 0) are never queued.
    Source download problems are reported on the source itself, so only newly
    exhausted jobs fail a scheduled execution. The database retains its durable
    jobs for a later retry or investigation.
    """
    if max_seconds <= 0 or poll_seconds <= 0:
        raise ValueError("Batch duration and poll interval must be positive")
    started_at = datetime.utcnow()
    deadline = time.monotonic() + max_seconds
    previously_failed = _snapshot()
    processed = 0
    if allow_idle:
        _schedule_due_sources()

    while True:
        if time.monotonic() >= deadline:
            pending, failures, results = _status(started_at, previously_failed)
            if allow_idle and not failures:
                _log_sources(results)
                logger.info("Scheduled drain yielded; processed=%s pending=%s", processed, pending)
                return {
                    "processed_jobs": processed,
                    "pending_jobs": pending,
                    "source_results": results,
                }
            raise BatchIncomplete(
                f"Batch timed out with {pending} unfinished jobs, "
                f"{len(failures)} new failed jobs and {len(results)} source runs"
            )
        worked = await run_once(include_scheduled=False)
        if worked:
            processed += 1
            continue

        pending, failures, results = _status(started_at, previously_failed)
        if pending == 0 or allow_idle:
            _log_sources(results)
            bad_sources = [
                result["source_id"]
                for result in results
                if result["status"] != "succeeded" or result["errors"]
            ]
            if not processed and not allow_idle:
                raise BatchIncomplete("No queued work; click Collect now before starting the job")
            if failures or (bad_sources and not allow_idle):
                raise BatchIncomplete(
                    f"Batch incomplete: {len(failures)} failed jobs, "
                    f"{len(bad_sources)} sources with errors; inspect ingestion runs"
                )
            logger.info("Ingestion drain complete: processed=%s pending=%s", processed, pending)
            return {"processed_jobs": processed, "pending_jobs": pending, "source_results": results}

        await asyncio.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))


def _schedule_due_sources():
    """Queue enabled sources whose explicit interval is due; interval 0 stays manual."""
    with Session() as db:
        schedule(db)


def _log_sources(results):
    for result in results:
        log = logger.info if result["status"] == "succeeded" else logger.warning
        log(
            "Source %s: %s; found=%s accepted=%s errors=%s",
            result["source_id"],
            result["status"],
            result["found"],
            result["accepted"],
            len(result["errors"]),
        )
