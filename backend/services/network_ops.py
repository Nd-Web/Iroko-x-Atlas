"""
Network Operations Service
===========================
Unified interface for querying telecom operational data.
Provides site status, cluster health, active incidents, KPI summaries,
and SLA exposure calculations.

Designed to initially work with SQLite seed data, with a clean interface
that can later be backed by live NMS/OSS APIs (Ericsson ENM, Huawei iManager, etc.).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from models.network_models import (
    NetworkSite, NetworkIncident, VendorContract, ComplaintTicket, NetworkKPI,
)

logger = logging.getLogger(__name__)


# ── Site Operations ──────────────────────────────────────────────────────────

def get_all_sites(
    db: Session,
    region: Optional[str] = None,
    cluster: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List all network sites with optional filters."""
    query = db.query(NetworkSite)
    if region:
        query = query.filter(NetworkSite.region == region)
    if cluster:
        query = query.filter(NetworkSite.cluster == cluster)
    if status:
        query = query.filter(NetworkSite.status == status)

    sites = query.order_by(NetworkSite.site_code).limit(limit).all()
    return [_site_to_dict(s) for s in sites]


def get_site_detail(db: Session, site_code: str) -> Optional[Dict[str, Any]]:
    """Get detailed info for a specific site including incident history."""
    site = db.query(NetworkSite).filter(NetworkSite.site_code == site_code).first()
    if not site:
        return None

    result = _site_to_dict(site)

    # Recent incidents
    incidents = (
        db.query(NetworkIncident)
        .filter(NetworkIncident.site_id == site.id)
        .order_by(desc(NetworkIncident.started_at))
        .limit(10)
        .all()
    )
    result["recent_incidents"] = [_incident_to_dict(i) for i in incidents]

    # Latest KPIs
    kpi = (
        db.query(NetworkKPI)
        .filter(NetworkKPI.site_code == site_code)
        .order_by(desc(NetworkKPI.date))
        .first()
    )
    if kpi:
        result["latest_kpis"] = _kpi_to_dict(kpi)

    return result


def get_cluster_health(db: Session, cluster_name: str) -> Dict[str, Any]:
    """Aggregate health summary for a cluster."""
    sites = db.query(NetworkSite).filter(NetworkSite.cluster == cluster_name).all()
    if not sites:
        return {"cluster": cluster_name, "error": "Cluster not found"}

    total = len(sites)
    operational = sum(1 for s in sites if s.status == "operational")
    degraded = sum(1 for s in sites if s.status == "degraded")
    down = sum(1 for s in sites if s.status == "down")
    maintenance = sum(1 for s in sites if s.status == "maintenance")
    total_subscribers = sum(s.subscriber_count or 0 for s in sites)

    # Active incidents in this cluster
    active_incidents = (
        db.query(NetworkIncident)
        .filter(
            NetworkIncident.cluster == cluster_name,
            NetworkIncident.status.in_(["open", "investigating"]),
        )
        .all()
    )

    # Latest cluster KPIs
    kpi = (
        db.query(NetworkKPI)
        .filter(
            NetworkKPI.cluster == cluster_name,
            NetworkKPI.scope_level == "cluster",
        )
        .order_by(desc(NetworkKPI.date))
        .first()
    )

    return {
        "cluster": cluster_name,
        "total_sites": total,
        "operational": operational,
        "degraded": degraded,
        "down": down,
        "maintenance": maintenance,
        "health_pct": round((operational / total) * 100, 1) if total else 0,
        "total_subscribers": total_subscribers,
        "active_incidents": [_incident_to_dict(i) for i in active_incidents],
        "sites": [{"site_code": s.site_code, "name": s.name, "status": s.status} for s in sites],
        "kpis": _kpi_to_dict(kpi) if kpi else None,
    }


# ── Incidents ────────────────────────────────────────────────────────────────

def get_active_incidents(
    db: Session,
    severity: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get all open/investigating incidents."""
    query = db.query(NetworkIncident).filter(
        NetworkIncident.status.in_(["open", "investigating"])
    )
    if severity:
        query = query.filter(NetworkIncident.severity == severity)
    if region:
        query = query.filter(NetworkIncident.region == region)

    incidents = query.order_by(
        desc(NetworkIncident.severity == "critical"),
        desc(NetworkIncident.started_at),
    ).limit(limit).all()

    return [_incident_to_dict(i) for i in incidents]


def get_all_incidents(
    db: Session,
    status: Optional[str] = None,
    region: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Get incidents within a time window."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(NetworkIncident).filter(NetworkIncident.started_at >= since)

    if status:
        query = query.filter(NetworkIncident.status == status)
    if region:
        query = query.filter(NetworkIncident.region == region)

    incidents = query.order_by(desc(NetworkIncident.started_at)).limit(limit).all()
    return [_incident_to_dict(i) for i in incidents]


# ── KPIs ─────────────────────────────────────────────────────────────────────

def get_kpi_summary(
    db: Session,
    scope_level: str = "region",
    region: Optional[str] = "Lagos",
    cluster: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """Get aggregated KPI summary for a given scope. Defaults to Lagos region."""
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(NetworkKPI).filter(
        NetworkKPI.scope_level == scope_level,
        NetworkKPI.date >= since,
    )

    # Apply scope-specific filters
    if scope_level == "region" and region:
        query = query.filter(NetworkKPI.region == region)
    elif scope_level == "cluster" and cluster:
        query = query.filter(NetworkKPI.cluster == cluster)

    kpis = query.order_by(desc(NetworkKPI.date)).all()

    if not kpis:
        # Fallback: try national if region/cluster has no data yet
        if scope_level != "national":
            return get_kpi_summary(db, scope_level="national", days=days)
        return {"scope": scope_level, "region": region, "period_days": days, "data": []}

    latest = kpis[0]

    avail_values = [k.availability_pct for k in kpis if k.availability_pct is not None]
    csr_values = [k.call_setup_success_pct for k in kpis if k.call_setup_success_pct is not None]
    throughput_values = [k.data_throughput_mbps for k in kpis if k.data_throughput_mbps is not None]
    complaint_values = [k.complaint_count for k in kpis if k.complaint_count is not None]

    def _avg(vals):
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "scope": scope_level,
        "region": region,
        "cluster": cluster,
        "period_days": days,
        "latest": _kpi_to_dict(latest),
        "averages": {
            "availability_pct": _avg(avail_values),
            "call_setup_success_pct": _avg(csr_values),
            "data_throughput_mbps": _avg(throughput_values),
            "daily_complaints": _avg(complaint_values),
        },
        "targets": {
            "availability_pct": latest.availability_target,
            "call_setup_success_pct": latest.csr_target,
        },
        "compliance": {
            "availability": (_avg(avail_values) or 0) >= (latest.availability_target or 99.5),
            "csr": (_avg(csr_values) or 0) >= (latest.csr_target or 95.0),
        },
        "trend": [_kpi_to_dict(k) for k in kpis[:days]],
    }



def get_kpi_timeseries(
    db: Session,
    site_code: Optional[str] = None,
    cluster: Optional[str] = None,
    region: Optional[str] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """Get KPI time series data for charting."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(NetworkKPI).filter(NetworkKPI.date >= since)

    if site_code:
        query = query.filter(NetworkKPI.site_code == site_code)
    elif cluster:
        query = query.filter(NetworkKPI.cluster == cluster, NetworkKPI.scope_level == "cluster")
    elif region:
        query = query.filter(NetworkKPI.region == region, NetworkKPI.scope_level == "region")
    else:
        query = query.filter(NetworkKPI.scope_level == "national")

    kpis = query.order_by(NetworkKPI.date).all()
    return [_kpi_to_dict(k) for k in kpis]


# ── Contracts ────────────────────────────────────────────────────────────────

def get_contracts(
    db: Session,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List vendor contracts with filters."""
    query = db.query(VendorContract)

    if status:
        query = query.filter(VendorContract.status == status)
    if vendor:
        query = query.filter(VendorContract.vendor_name.ilike(f"%{vendor}%"))
    if expiring_within_days:
        cutoff = datetime.utcnow() + timedelta(days=expiring_within_days)
        query = query.filter(VendorContract.expiry_date <= cutoff)

    contracts = query.order_by(VendorContract.expiry_date).all()
    return [_contract_to_dict(c) for c in contracts]


def calculate_sla_exposure(
    db: Session,
    incident_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate total SLA financial exposure.
    If incident_id is provided, calculate for that specific incident.
    Otherwise, calculate across all open/recent incidents.
    """
    if incident_id:
        incidents = db.query(NetworkIncident).filter(NetworkIncident.id == incident_id).all()
    else:
        since = datetime.utcnow() - timedelta(days=90)
        incidents = (
            db.query(NetworkIncident)
            .filter(
                NetworkIncident.started_at >= since,
                NetworkIncident.sla_breached == True,
            )
            .all()
        )

    total_exposure = sum(i.sla_exposure_ngn or 0 for i in incidents)
    vendor_breaches = sum(1 for i in incidents if i.vendor_sla_breached)

    return {
        "total_exposure_ngn": total_exposure,
        "incident_count": len(incidents),
        "vendor_sla_breaches": vendor_breaches,
        "incidents": [
            {
                "incident_ref": i.incident_ref,
                "title": i.title,
                "exposure_ngn": i.sla_exposure_ngn,
                "duration_hours": i.duration_hours,
                "sla_breached": i.sla_breached,
            }
            for i in incidents
        ],
    }


# ── Complaints ───────────────────────────────────────────────────────────────

def get_complaint_summary(
    db: Session,
    region: Optional[str] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """Summarise complaint metrics for dashboard."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(ComplaintTicket).filter(ComplaintTicket.reported_at >= since)

    if region:
        query = query.filter(ComplaintTicket.customer_region == region)

    tickets = query.all()
    total = len(tickets)

    if total == 0:
        return {"total": 0, "period_days": days}

    open_count = sum(1 for t in tickets if t.status in ("open", "investigating", "escalated"))
    resolved_count = sum(1 for t in tickets if t.status in ("resolved", "closed"))
    total_disputed = sum(t.disputed_amount_ngn or 0 for t in tickets)
    total_refunded = sum(t.refund_amount_ngn or 0 for t in tickets)

    # Category breakdown
    categories: Dict[str, int] = {}
    for t in tickets:
        categories[t.category] = categories.get(t.category, 0) + 1

    # Region breakdown
    regions: Dict[str, int] = {}
    for t in tickets:
        r = t.customer_region or "Unknown"
        regions[r] = regions.get(r, 0) + 1

    # Resolution rate
    resolution_rate = round((resolved_count / total) * 100, 1) if total else 0

    return {
        "total": total,
        "period_days": days,
        "open": open_count,
        "resolved": resolved_count,
        "resolution_rate_pct": resolution_rate,
        "total_disputed_ngn": total_disputed,
        "total_refunded_ngn": total_refunded,
        "by_category": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "by_region": dict(sorted(regions.items(), key=lambda x: -x[1])),
        "top_category": max(categories, key=categories.get) if categories else None,
        "top_region": max(regions, key=regions.get) if regions else None,
    }


def get_complaints(
    db: Session,
    category: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List complaint tickets with filters."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(ComplaintTicket).filter(ComplaintTicket.reported_at >= since)

    if category:
        query = query.filter(ComplaintTicket.category == category)
    if status:
        query = query.filter(ComplaintTicket.status == status)
    if region:
        query = query.filter(ComplaintTicket.customer_region == region)

    tickets = query.order_by(desc(ComplaintTicket.reported_at)).limit(limit).all()
    return [_complaint_to_dict(t) for t in tickets]


def correlate_complaints_to_incidents(db: Session, days: int = 30) -> List[Dict[str, Any]]:
    """Find complaint spikes that correlate with network incidents by region + timeframe."""
    since = datetime.utcnow() - timedelta(days=days)

    incidents = (
        db.query(NetworkIncident)
        .filter(NetworkIncident.started_at >= since)
        .all()
    )

    correlations = []
    for inc in incidents:
        if not inc.region or not inc.started_at:
            continue

        window_start = inc.started_at - timedelta(hours=1)
        window_end = (inc.resolved_at or datetime.utcnow()) + timedelta(hours=24)

        complaint_count = (
            db.query(func.count(ComplaintTicket.id))
            .filter(
                ComplaintTicket.customer_region == inc.region,
                ComplaintTicket.reported_at >= window_start,
                ComplaintTicket.reported_at <= window_end,
            )
            .scalar()
        )

        if complaint_count and complaint_count > 0:
            correlations.append({
                "incident_ref": inc.incident_ref,
                "incident_title": inc.title,
                "region": inc.region,
                "incident_start": inc.started_at.isoformat(),
                "complaint_count": complaint_count,
                "correlation_window": f"{window_start.isoformat()} to {window_end.isoformat()}",
            })

    return sorted(correlations, key=lambda x: -x["complaint_count"])


# ── Agent-Friendly Summary (used by Strategist) ─────────────────────────────

def get_operations_briefing(db: Session) -> Dict[str, Any]:
    """
    Generate a comprehensive operations briefing for the Strategist agent.
    This is what makes the morning briefing dynamic instead of hardcoded.
    """
    now = datetime.utcnow()

    # Active incidents
    active = get_active_incidents(db, limit=10)

    # KPI summary (last 7 days) — Lagos region scope by default
    kpis = get_kpi_summary(db, scope_level="region", region="Lagos", days=7)

    # Complaint summary (last 7 days)
    cx = get_complaint_summary(db, days=7)

    # Expiring contracts (next 90 days)
    expiring = get_contracts(db, expiring_within_days=90)

    # Total sites status
    all_sites = db.query(NetworkSite).all()
    site_status = {
        "total": len(all_sites),
        "operational": sum(1 for s in all_sites if s.status == "operational"),
        "degraded": sum(1 for s in all_sites if s.status == "degraded"),
        "down": sum(1 for s in all_sites if s.status == "down"),
    }

    # SLA exposure
    sla = calculate_sla_exposure(db)

    return {
        "generated_at": now.isoformat(),
        "network_status": site_status,
        "active_incidents": active,
        "kpi_summary": kpis,
        "complaint_summary": cx,
        "expiring_contracts": [_contract_to_dict(c) for c in
                               db.query(VendorContract)
                               .filter(VendorContract.expiry_date <= now + timedelta(days=90))
                               .all()] if expiring else [],
        "sla_exposure": sla,
    }


# ── Heatmap ──────────────────────────────────────────────────────────────────

_REGION_GEO: Dict[str, tuple] = {
    "lagos":         ("Lagos",         6.40,  3.40),
    "ibadan":        ("Ibadan",        7.40,  3.90),
    "abuja":         ("Abuja",         9.10,  7.50),
    "port harcourt": ("Port Harcourt", 4.80,  7.00),
    "kano":          ("Kano",         12.00,  8.50),
    "kaduna":        ("Kaduna",       10.50,  7.40),
    "enugu":         ("Enugu",         6.40,  7.50),
    "benin":         ("Benin City",    6.30,  5.60),
    "jos":           ("Jos",           9.90,  8.90),
    "calabar":       ("Calabar",       4.95,  8.30),
    "warri":         ("Warri",         5.50,  5.70),
    "owerri":        ("Owerri",        5.50,  7.00),
    "maiduguri":     ("Maiduguri",    11.80, 13.20),
    "sokoto":        ("Sokoto",       13.10,  5.20),
    "ilorin":        ("Ilorin",        8.50,  4.50),
}


def get_heatmap_data(db: Session) -> List[Dict[str, Any]]:
    """Return per-region network health aggregated from live OMC-R data."""
    from collections import defaultdict

    all_sites = db.query(NetworkSite).filter(NetworkSite.region.isnot(None)).all()
    active_incidents = (
        db.query(NetworkIncident)
        .filter(NetworkIncident.status.in_(["open", "investigating"]))
        .all()
    )
    kpis_by_region: Dict[str, Any] = {}
    for kpi in (
        db.query(NetworkKPI)
        .filter(NetworkKPI.scope_level == "region")
        .order_by(desc(NetworkKPI.date))
        .all()
    ):
        key = (kpi.region or "").lower()
        if key not in kpis_by_region:
            kpis_by_region[key] = kpi

    region_sites: Dict[str, list] = defaultdict(list)
    for s in all_sites:
        region_sites[(s.region or "").lower()].append(s)

    region_incidents: Dict[str, list] = defaultdict(list)
    for inc in active_incidents:
        region_incidents[(inc.region or "").lower()].append(inc)

    result = []
    for raw_key, sites in region_sites.items():
        geo = _REGION_GEO.get(raw_key)
        if not geo:
            for k, v in _REGION_GEO.items():
                if k in raw_key or raw_key in k:
                    geo = v
                    break
        if not geo:
            continue

        display, lat, lng = geo
        site_count  = len(sites)
        operational = sum(1 for s in sites if s.status == "operational")
        degraded    = sum(1 for s in sites if s.status == "degraded")
        down        = sum(1 for s in sites if s.status == "down")
        incidents   = region_incidents.get(raw_key, [])
        critical    = sum(1 for i in incidents if i.severity == "critical")

        kpi = kpis_by_region.get(raw_key)
        availability = (
            kpi.availability_pct if kpi and kpi.availability_pct
            else round(operational / site_count * 100, 1) if site_count else 0.0
        )

        if down > 0:
            status = "down"
        elif degraded > 0 or critical > 0:
            status = "degraded"
        else:
            status = "operational"

        result.append({
            "region":             display,
            "latitude":           lat,
            "longitude":          lng,
            "site_count":         site_count,
            "operational":        operational,
            "degraded":           degraded,
            "down":               down,
            "availability_pct":   round(float(availability), 1),
            "active_incidents":   len(incidents),
            "critical_incidents": critical,
            "status":             status,
            "subscribers":        sum(s.subscriber_count or 0 for s in sites),
        })

    return sorted(result, key=lambda x: x["subscribers"], reverse=True)


# ── Serialisation helpers ────────────────────────────────────────────────────

def _site_to_dict(site: NetworkSite) -> Dict[str, Any]:
    return {
        "id": site.id,
        "site_code": site.site_code,
        "name": site.name,
        "site_type": site.site_type,
        "cluster": site.cluster,
        "region": site.region,
        "zone": site.zone,
        "latitude": site.latitude,
        "longitude": site.longitude,
        "tower_vendor": site.tower_vendor,
        "ran_vendor": site.ran_vendor,
        "status": site.status,
        "subscriber_count": site.subscriber_count,
        "technology": site.technology,
        "backhaul_type": site.backhaul_type,
        "last_alarm_at": site.last_alarm_at.isoformat() if site.last_alarm_at else None,
        "last_alarm_severity": site.last_alarm_severity,
    }


def _incident_to_dict(inc: NetworkIncident) -> Dict[str, Any]:
    return {
        "id": inc.id,
        "incident_ref": inc.incident_ref,
        "title": inc.title,
        "description": inc.description,
        "cluster": inc.cluster,
        "region": inc.region,
        "severity": inc.severity,
        "status": inc.status,
        "priority": inc.priority,
        "root_cause_category": inc.root_cause_category,
        "root_cause_detail": inc.root_cause_detail,
        "affected_sites_count": inc.affected_sites_count,
        "affected_subscribers": inc.affected_subscribers,
        "sla_breached": inc.sla_breached,
        "sla_exposure_ngn": inc.sla_exposure_ngn,
        "duration_hours": inc.duration_hours,
        "started_at": inc.started_at.isoformat() if inc.started_at else None,
        "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        "assigned_team": inc.assigned_team,
        "escalation_level": inc.escalation_level,
    }


def _contract_to_dict(c: VendorContract) -> Dict[str, Any]:
    days_left = None
    if c.expiry_date:
        days_left = (c.expiry_date - datetime.utcnow()).days

    return {
        "id": c.id,
        "contract_ref": c.contract_ref,
        "title": c.title,
        "vendor_name": c.vendor_name,
        "vendor_type": c.vendor_type,
        "monthly_value_ngn": c.monthly_value_ngn,
        "annual_value_ngn": c.annual_value_ngn,
        "sla_uptime_pct": c.sla_uptime_pct,
        "sla_response_hours": c.sla_response_hours,
        "penalty_formula": c.penalty_formula,
        "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
        "days_to_expiry": days_left,
        "status": c.status,
        "department": c.department,
    }


def _kpi_to_dict(kpi: NetworkKPI) -> Dict[str, Any]:
    return {
        "date": kpi.date.isoformat() if kpi.date else None,
        "scope_level": kpi.scope_level,
        "site_code": kpi.site_code,
        "cluster": kpi.cluster,
        "region": kpi.region,
        "availability_pct": kpi.availability_pct,
        "call_setup_success_pct": kpi.call_setup_success_pct,
        "drop_call_rate_pct": kpi.drop_call_rate_pct,
        "data_throughput_mbps": kpi.data_throughput_mbps,
        "latency_ms": kpi.latency_ms,
        "subscriber_count": kpi.subscriber_count,
        "complaint_count": kpi.complaint_count,
        "csat_score": kpi.csat_score,
        "availability_target": kpi.availability_target,
        "csr_target": kpi.csr_target,
    }


def _complaint_to_dict(t: ComplaintTicket) -> Dict[str, Any]:
    return {
        "id": t.id,
        "ticket_ref": t.ticket_ref,
        "category": t.category,
        "subcategory": t.subcategory,
        "description": t.description,
        "customer_segment": t.customer_segment,
        "customer_region": t.customer_region,
        "status": t.status,
        "priority": t.priority,
        "resolution": t.resolution,
        "refund_amount_ngn": t.refund_amount_ngn,
        "disputed_amount_ngn": t.disputed_amount_ngn,
        "channel": t.channel,
        "reported_at": t.reported_at.isoformat() if t.reported_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
    }
