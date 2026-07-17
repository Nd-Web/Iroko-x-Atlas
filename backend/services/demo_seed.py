"""
services/demo_seed.py — one-call, self-healing demo data seeding.

The demo runs on a realistic seeded MTN dataset (no production data access),
and the live DB is SQLite on ephemeral storage — so it must re-seed itself on
boot, or graph/analytics/productivity/workflows go blank after any restart.

This module:
  1. Runs the full master seed (users, documents, contracts, sites, incidents,
     complaints, KPIs, alerts, conversations, org-memory, gaps, audit) — reusing
     scripts/seed_all so there is ONE source of truth for the demo dataset.
  2. Adds a realistic Strategist query history so productivity metrics
     (time saved, avg answer time, trends) compute to meaningful numbers.
  3. Converts the seeded alerts into routed, SLA-tracked workflow tasks so the
     Workflows board is populated out of the box.

It is idempotent: it skips when the DB already holds documents (so it seeds
once on a persistent DB, and re-seeds each cold start on an ephemeral one).
It never pushes to Azure Search — the index is external and persists on its own.
"""
import contextlib
import io
import logging
import random
from datetime import datetime, timedelta

from models.database import SessionLocal, Document, Alert, AgentRun

logger = logging.getLogger(__name__)

# Realistic MTN questions for the Strategist query history (drives productivity).
_DEMO_QUERIES = [
    "What caused the Ikeja cluster outage and what is our SLA exposure?",
    "Which vendor contracts expire in the next 90 days?",
    "Are we ready to submit the NCC QoS return for Q1 2026?",
    "What is our penalty exposure on the ATC Lagos contract if it lapses?",
    "Summarise the MoMo deduction complaints trend in Lagos this quarter",
    "Does storing subscriber CDRs in a US cloud region comply with the NDPA?",
    "What are the Ericsson RAN maintenance MTTR thresholds under the 2026 SLA?",
    "Draft the IHS SLA breach notice for the February Ikeja outage",
    "What is the status and delay risk of the Kano-Kaduna fibre rollout?",
    "Which enterprise customers carry the highest SLA credit exposure?",
    "What is our NDPA Article 24 review status and audit risk?",
    "How did CSAT and complaint volume trend during the Ikeja incident?",
    "What is the holdover risk if the ATC towers contract is not renewed?",
    "Which network clusters are below the NCC 95% availability threshold?",
    "What data-localization obligations apply to the new analytics pipeline?",
]


def _seed_strategist_history(db) -> int:
    """Insert a realistic Strategist query log spread over the last ~20 days."""
    # Only add if the history is sparse (seed_all adds a single strategist row).
    existing = db.query(AgentRun).filter(AgentRun.agent_type == "strategist").count()
    if existing >= 40:
        return 0

    rng = random.Random(42)  # deterministic demo history
    now = datetime.utcnow()
    created = 0
    for i in range(55):
        q = _DEMO_QUERIES[i % len(_DEMO_QUERIES)]
        day = int((i * 0.36) % 20)          # weighted toward recent days
        ts = now - timedelta(days=day, hours=(i * 3) % 24, minutes=(i * 13) % 60)
        db.add(AgentRun(
            agent_type="strategist",
            input_query=q,
            output="Answered from the indexed corpus with grounded citations.",
            steps=[{"tool": "search"}, {"tool": "analyse"}, {"tool": "synthesise"}],
            duration_ms=rng.randint(2400, 7600),
            token_count=rng.randint(1500, 4200),
            success=True,
            created_at=ts,
        ))
        created += 1
    db.commit()
    return created


def _seed_workflow_tasks(db) -> int:
    """Convert seeded alerts into routed, SLA-tracked workflow tasks."""
    from services.workflow_service import create_task_from_alert

    alerts = db.query(Alert).all()
    created = 0
    for a in alerts:
        alert_data = {
            "title": a.title,
            "summary": a.summary,
            "severity": a.severity,
            "alert_type": a.alert_type,
            "suggested_actions": a.suggested_actions or [],
            "related_document_ids": a.related_document_ids or [],
        }
        if create_task_from_alert(db, a.id, alert_data, a.organisation or "MTN Nigeria"):
            created += 1
    db.commit()
    return created


def seed_demo_data(force: bool = False) -> dict:
    """
    Populate the full demo dataset. Idempotent — skips when documents already
    exist unless ``force=True``. Safe to call on every boot.
    """
    db = SessionLocal()
    try:
        if db.query(Document).count() > 0 and not force:
            # Already seeded — but ensure the runtime-only pieces exist
            # (workflow tasks + rich history are not part of the base seed).
            hist = _seed_strategist_history(db)
            tasks = _seed_workflow_tasks(db)
            return {"seeded": False, "reason": "documents present",
                    "history_added": hist, "workflow_tasks_added": tasks}

        # ── Full master seed (single source of truth: scripts/seed_all) ──
        from scripts.seed_all import (
            seed_users, seed_documents, seed_contracts, seed_sites,
            seed_incidents, seed_complaints, seed_kpis, seed_alerts,
            seed_conversations, seed_agent_runs, seed_org_memory,
            seed_knowledge_gaps, seed_audit_logs,
        )

        # The master seeders print progress with unicode glyphs; capture their
        # stdout so a non-UTF-8 console (e.g. Windows cp1252) can't crash the seed.
        with contextlib.redirect_stdout(io.StringIO()):
            users = seed_users(db)
            seed_documents(db, users)
            seed_contracts(db)
            sites = seed_sites(db)
            ikj_incident = seed_incidents(db, sites)
            seed_complaints(db, ikj_incident)
            seed_kpis(db)
            seed_alerts(db, users)
            seed_conversations(db, users)
            seed_agent_runs(db)
            seed_org_memory(db)
            seed_knowledge_gaps(db)
            seed_audit_logs(db, users)

        # ── Enhancements that light up the new features ──
        history = _seed_strategist_history(db)
        tasks = _seed_workflow_tasks(db)

        return {
            "seeded": True,
            "documents": db.query(Document).count(),
            "alerts": db.query(Alert).count(),
            "strategist_history": history,
            "workflow_tasks": tasks,
        }
    finally:
        db.close()
