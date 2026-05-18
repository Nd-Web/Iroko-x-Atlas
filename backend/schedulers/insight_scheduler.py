"""
schedulers/insight_scheduler.py — Proactive insight generation for Iroko AI.

Runs every 15 minutes via APScheduler's ``AsyncIOScheduler``.  On each tick:

1. Finds all organisations that have at least one indexed document.
2. Runs the WatchdogAgent against each organisation's documents.
3. If findings have severity >= 7, creates an Alert record in the database.
4. Deduplicates: skips if an identical alert (same org + title) was created
   in the last 2 hours.

Start via ``start_insight_scheduler()`` in the FastAPI lifespan handler.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# ── Scheduler singleton ───────────────────────────────────────────────────────

_scheduler: Optional[AsyncIOScheduler] = None


def _get_scheduler() -> AsyncIOScheduler:
    """Return the singleton AsyncIOScheduler, creating it if needed."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


# ── Severity mapping ──────────────────────────────────────────────────────────
# The WatchdogAgent returns severity as "critical" | "warning" | "info".
# Map these to numeric scores for the >= 7 threshold check.

_SEVERITY_SCORE = {
    "critical": 9,
    "warning": 6,
    "info": 3,
}

_SCORE_TO_SEVERITY = {
    9: "critical",
    6: "warning",
    3: "info",
}


# ── Insight job ───────────────────────────────────────────────────────────────

async def _generate_insights():
    """
    For each organisation with indexed documents, run the WatchdogAgent
    and persist high-severity findings as Alert records.
    """
    from models.database import SessionLocal, Document, Alert
    from sqlalchemy import func, distinct

    db = SessionLocal()
    try:
        # Find all organisations that have at least one indexed document
        org_rows = (
            db.query(distinct(Document.department))
            .filter(Document.status == "indexed")
            .all()
        )

        # Also check the organisation field on Users who own documents
        from models.database import User
        user_orgs = (
            db.query(distinct(User.organisation))
            .join(Document, Document.uploaded_by_id == User.id)
            .filter(Document.status == "indexed")
            .all()
        )

        # Merge into a unique set of org identifiers
        organisations = set()
        for (dept,) in org_rows:
            if dept:
                organisations.add(dept)
        for (org,) in user_orgs:
            if org:
                organisations.add(org)

        # Fallback: always check MTN Nigeria (the primary tenant)
        if not organisations:
            organisations = {"MTN Nigeria"}

        logger.info(
            f"Insight scheduler: checking {len(organisations)} organisation(s)."
        )

        total_alerts_created = 0
        total_alerts_skipped = 0

        for org_name in organisations:
            try:
                alerts_created, alerts_skipped = await _check_organisation(
                    org_name, db
                )
                total_alerts_created += alerts_created
                total_alerts_skipped += alerts_skipped
            except Exception as exc:
                logger.error(
                    f"Insight scheduler: failed for org '{org_name}': {exc}",
                    exc_info=True,
                )

        logger.info(
            f"Insight scheduler complete: {total_alerts_created} alerts created, "
            f"{total_alerts_skipped} duplicates skipped."
        )

    except Exception as exc:
        logger.error(f"Insight scheduler tick failed: {exc}", exc_info=True)
    finally:
        db.close()


async def _check_organisation(org_name: str, db) -> tuple[int, int]:
    """
    Run the WatchdogAgent for a single organisation and persist alerts.

    Returns
    -------
    tuple[int, int]
        (alerts_created, alerts_skipped_as_duplicates)
    """
    from agents.watchdog import WatchdogAgent
    from models.database import Alert

    watchdog = WatchdogAgent()

    raw_result = await watchdog.run_all_checks(organisation=org_name)
    result = json.loads(raw_result)

    alerts = result.get("alerts", [])
    if not alerts:
        return 0, 0

    now = datetime.utcnow()
    dedup_window = now - timedelta(hours=2)
    created = 0
    skipped = 0

    for alert_data in alerts:
        severity_label = alert_data.get("severity", "info")
        severity_score = _SEVERITY_SCORE.get(severity_label, 3)

        # Only persist alerts with severity >= 7 (i.e., "critical")
        if severity_score < 7:
            continue

        title = alert_data.get("title", "").strip()
        if not title:
            continue

        # Deduplication: check if an identical alert exists within 2 hours
        existing = (
            db.query(Alert)
            .filter(
                Alert.title == title,
                Alert.organisation == org_name,
                Alert.created_at >= dedup_window,
            )
            .first()
        )

        if existing:
            skipped += 1
            continue

        # Create the alert record
        new_alert = Alert(
            title=title,
            summary=alert_data.get("summary", ""),
            severity=severity_label,
            alert_type=alert_data.get("alert_type", "watchdog_insight"),
            extra_metadata={
                **(alert_data.get("metadata", {})),
                "agent_source": "watchdog",
                "generated_by": "insight_scheduler",
            },
            suggested_actions=alert_data.get("suggested_actions", []),
            organisation=org_name,
            status="new",
        )
        db.add(new_alert)
        created += 1

    if created > 0:
        db.commit()
        logger.info(
            f"Insight scheduler: {created} alert(s) created for '{org_name}'."
        )

    return created, skipped


# ── Public API ────────────────────────────────────────────────────────────────

def start_insight_scheduler():
    """
    Start the insight scheduler.  Call this once during FastAPI lifespan startup.

    Adds a job that runs ``_generate_insights`` every 15 minutes.
    """
    scheduler = _get_scheduler()

    if scheduler.running:
        logger.debug("Insight scheduler already running — skipping start.")
        return

    scheduler.add_job(
        _generate_insights,
        IntervalTrigger(minutes=15),
        id="insight_generation",
        replace_existing=True,
        max_instances=1,
        name="Proactive insight generation (WatchdogAgent)",
    )
    scheduler.start()
    logger.info("Insight scheduler started (15-minute interval).")


def stop_insight_scheduler():
    """Gracefully shut down the insight scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Insight scheduler stopped.")
    _scheduler = None
