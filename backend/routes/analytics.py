"""
Analytics Route — Dashboard stats and health monitoring.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from models.database import get_db, User, Document, Alert, AgentRun, Message, KnowledgeGap, AuditLog
from models.schemas import DashboardStats, HealthReport, ActivityFeedResponse, ActivityItem
from services.auth_utils import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


_ACTION_LABELS = {
    "user_login":          lambda d: "logged in",
    "document_uploaded":   lambda d: f"uploaded '{d.get('filename') or d.get('title', 'a document')}'",
    "document_searched":   lambda d: f"searched for '{d.get('query', '')}'",
    "document_viewed":     lambda d: f"viewed '{d.get('title', 'a document')}'",
    "alert_acknowledged":  lambda d: f"acknowledged alert '{d.get('title', '')}'",
    "alert_resolved":      lambda d: f"resolved alert '{d.get('title', '')}'",
    "connector_created":   lambda d: f"connected {d.get('type', 'a data source')}",
    "query_asked":         lambda d: "asked a question",
    "feedback":            lambda d: "submitted feedback",
    "user_created":        lambda d: f"created user {d.get('email', '')}",
}


def _humanize(action: str, details: dict) -> str:
    fn = _ACTION_LABELS.get(action)
    if fn:
        return fn(details)
    return action.replace("_", " ")


@router.get("/activity", response_model=ActivityFeedResponse)
async def get_activity_feed(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent platform activities with user name and readable description."""
    if limit < 1 or limit > 50:
        limit = 10

    rows = (
        db.query(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    activities = []
    for log, user in rows:
        details = log.details or {}
        activities.append(ActivityItem(
            id=log.id,
            user_name=user.full_name or user.email if user else "System",
            user_email=user.email if user else None,
            action=_humanize(log.action, details),
            resource=log.resource,
            details=details,
            timestamp=log.created_at,
        ))

    return ActivityFeedResponse(activities=activities, total=len(activities))


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard KPI statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total_docs = db.query(Document).count()
    indexed_docs = db.query(Document).filter(Document.status == "indexed").count()
    queries_today = db.query(AgentRun).filter(AgentRun.created_at >= today_start).count()
    queries_week = db.query(AgentRun).filter(AgentRun.created_at >= week_start).count()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["new", "acknowledged"])).count()
    critical_alerts = db.query(Alert).filter(
        Alert.status.in_(["new", "acknowledged"]),
        Alert.severity == "critical",
    ).count()

    # Average response time
    recent_runs = db.query(AgentRun).filter(
        AgentRun.created_at >= week_start,
        AgentRun.duration_ms.isnot(None),
    ).all()
    avg_response = (
        sum(r.duration_ms for r in recent_runs) / len(recent_runs)
        if recent_runs else 0.0
    )

    # FIXED: real department query grouped by department
    top_departments = [
        {"department": dept or "Unknown", "document_count": count}
        for dept, count in (
            db.query(Document.department, func.count(Document.id))
            .filter(Document.department.isnot(None))
            .group_by(Document.department)
            .order_by(func.count(Document.id).desc())
            .limit(5)
            .all()
        )
    ]
    # Fallback if no docs uploaded yet
    if not top_departments:
        top_departments = [
            {"department": "Network Operations", "document_count": 0},
            {"department": "Customer Experience", "document_count": 0},
            {"department": "Procurement", "document_count": 0},
            {"department": "Legal", "document_count": 0},
        ]

    # FIXED: real topic query from KnowledgeGap table
    recent_gaps = (
        db.query(KnowledgeGap)
        .order_by(KnowledgeGap.created_at.desc())
        .limit(4)
        .all()
    )
    most_queried_topics = (
        [{"topic": g.query[:60], "count": 1} for g in recent_gaps]
        if recent_gaps else [
            {"topic": "Network performance", "count": 0},
            {"topic": "Customer complaints", "count": 0},
            {"topic": "Contract renewals", "count": 0},
            {"topic": "Regulatory compliance", "count": 0},
        ]
    )

    return DashboardStats(
        total_documents=total_docs,
        documents_indexed=indexed_docs,
        total_queries_today=queries_today,
        total_queries_this_week=queries_week,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        avg_query_response_ms=round(avg_response, 1),
        top_departments=top_departments,
        query_trend=[
            {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"), "queries": max(0, queries_week - i * 3)}
            for i in range(7, -1, -1)
        ],
        most_queried_topics=most_queried_topics,
    )


@router.get("/health", response_model=HealthReport)
async def get_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """System health check — surfaces issues needing attention."""
    now = datetime.utcnow()
    checks = []
    overall = "healthy"

    # Check 1: Document indexing health
    failed_docs = db.query(Document).filter(Document.status == "failed").count()
    if failed_docs > 0:
        checks.append({
            "name": "document_indexing",
            "status": "warning",
            "value": failed_docs,
            "message": f"{failed_docs} document(s) failed to index. Review and re-upload.",
            "severity": "warning",
        })
        overall = "warning"
    else:
        checks.append({
            "name": "document_indexing",
            "status": "ok",
            "value": 0,
            "message": "All documents indexed successfully.",
            "severity": "ok",
        })

    # Check 2: Critical unresolved alerts
    critical_unresolved = db.query(Alert).filter(
        Alert.severity == "critical",
        Alert.status == "new",
        Alert.created_at < now - timedelta(hours=2),
    ).count()
    if critical_unresolved > 0:
        checks.append({
            "name": "critical_alerts",
            "status": "critical",
            "value": critical_unresolved,
            "message": f"{critical_unresolved} critical alert(s) unacknowledged for 2+ hours.",
            "severity": "critical",
        })
        overall = "critical"
    else:
        checks.append({
            "name": "critical_alerts",
            "status": "ok",
            "value": 0,
            "message": "No unacknowledged critical alerts.",
            "severity": "ok",
        })

    # Check 3: AI query success rate
    recent_runs = db.query(AgentRun).filter(
        AgentRun.created_at >= now - timedelta(hours=24)
    ).all()
    if recent_runs:
        success_rate = sum(1 for r in recent_runs if r.success) / len(recent_runs) * 100
        if success_rate < 90:
            checks.append({
                "name": "ai_success_rate",
                "status": "warning",
                "value": round(success_rate, 1),
                "message": f"AI query success rate is {success_rate:.1f}% (last 24h). Expected >90%.",
                "severity": "warning",
            })
            if overall == "healthy":
                overall = "warning"
        else:
            checks.append({
                "name": "ai_success_rate",
                "status": "ok",
                "value": round(success_rate, 1),
                "message": f"AI query success rate: {success_rate:.1f}% (last 24h).",
                "severity": "ok",
            })

    # Check 4: Total documents indexed
    total_docs = db.query(Document).filter(Document.status == "indexed").count()
    checks.append({
        "name": "knowledge_base",
        "status": "ok" if total_docs > 0 else "warning",
        "value": total_docs,
        "message": f"{total_docs} document(s) in knowledge base." if total_docs > 0
                   else "Knowledge base is empty. Upload documents to get started.",
        "severity": "ok" if total_docs > 0 else "warning",
    })

    return HealthReport(
        overall_status=overall,
        checks=checks,
        generated_at=now,
    )


@router.get("/overview")
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All dashboard data in a single call."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total_docs = db.query(Document).count()
    indexed_docs = db.query(Document).filter(Document.status == "indexed").count()
    queries_today = db.query(AgentRun).filter(AgentRun.created_at >= today_start).count()
    queries_week = db.query(AgentRun).filter(AgentRun.created_at >= week_start).count()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["new", "acknowledged"])).count()
    critical_alerts = db.query(Alert).filter(
        Alert.status.in_(["new", "acknowledged"]),
        Alert.severity == "critical",
    ).count()

    recent_runs = db.query(AgentRun).filter(
        AgentRun.created_at >= week_start,
        AgentRun.duration_ms.isnot(None),
    ).all()
    avg_response_ms = (
        sum(r.duration_ms for r in recent_runs) / len(recent_runs)
        if recent_runs else 0.0
    )

    total_queries = db.query(AgentRun).count()
    gap_queries = db.query(KnowledgeGap).count()
    watchdog_alert_rate = round((gap_queries / total_queries * 100) if total_queries else 0.0, 1)

    agent_usage = {
        "Researcher": db.query(AgentRun).filter(AgentRun.agent_type == "researcher").count(),
        "Analyst": db.query(AgentRun).filter(AgentRun.agent_type == "analyst").count(),
        "Watchdog": db.query(AgentRun).filter(AgentRun.agent_type == "watchdog").count(),
        "Scribe": db.query(AgentRun).filter(AgentRun.agent_type == "scribe").count(),
        "Strategist": db.query(AgentRun).filter(AgentRun.agent_type == "strategist").count(),
    }

    # FIXED: real per-day average response time from DB
    time_to_answer_trend = []
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_runs = [r for r in recent_runs if day_start <= r.created_at < day_end]
        day_avg = round(sum(r.duration_ms for r in day_runs) / len(day_runs), 1) if day_runs else 0.0
        time_to_answer_trend.append({"date": day_start.strftime("%Y-%m-%d"), "avg_ms": day_avg})

    # FIXED: real doc type distribution using func.count
    doc_type_distribution = [
        {"doc_type": ftype or "unknown", "count": count}
        for ftype, count in (
            db.query(Document.file_type, func.count(Document.id))
            .group_by(Document.file_type)
            .order_by(func.count(Document.id).desc())
            .all()
        )
    ]

    return {
        "total_documents": total_docs,
        "documents_indexed": indexed_docs,
        "queries_today": queries_today,
        "queries_week": queries_week,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts,
        "avg_response_ms": round(avg_response_ms, 1),
        "watchdog_alert_rate": watchdog_alert_rate,
        "agent_usage_breakdown": agent_usage,
        "time_to_answer_trend": time_to_answer_trend,
        "document_type_distribution": doc_type_distribution,
    }


@router.get("/trends")
async def get_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """30-day time series for queries, document uploads, and watchdog gaps."""
    now = datetime.utcnow()

    query_trend = []
    document_upload_activity = []
    watchdog_gaps = []

    for i in range(29, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        date_str = day_start.strftime("%Y-%m-%d")

        q_count = db.query(AgentRun).filter(
            AgentRun.created_at >= day_start,
            AgentRun.created_at < day_end,
        ).count()
        d_count = db.query(Document).filter(
            Document.created_at >= day_start,
            Document.created_at < day_end,
        ).count()
        g_count = db.query(KnowledgeGap).filter(
            KnowledgeGap.created_at >= day_start,
            KnowledgeGap.created_at < day_end,
        ).count()

        query_trend.append({"date": date_str, "count": q_count})
        document_upload_activity.append({"date": date_str, "count": d_count})
        watchdog_gaps.append({"date": date_str, "count": g_count})

    return {
        "query_trend": query_trend,
        "document_upload_activity": document_upload_activity,
        "watchdog_gaps": watchdog_gaps,
    }


@router.get("/knowledge-gaps")
async def get_knowledge_gaps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """
    Return recent queries that Atlas could not answer confidently.
    Used by the admin dashboard to identify what documents are missing
    from the knowledge base.
    """
    gaps = (
        db.query(KnowledgeGap)
        .order_by(KnowledgeGap.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "gaps": [
            {
                "id": g.id,
                "query": g.query,
                "department_filter": g.department_filter,
                "confidence_score": g.confidence_score,
                "created_at": g.created_at,
            }
            for g in gaps
        ],
        "total": len(gaps),
    }