"""
Network Operations API Routes
===============================
Exposes telecom operational data to the frontend dashboard:
sites, incidents, KPIs, contracts, and cluster health.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models.database import get_db, User
from services.auth_utils import get_current_user
from services import network_ops

router = APIRouter(prefix="/api/network", tags=["Network Operations"])
logger = logging.getLogger(__name__)


# ── Sites ────────────────────────────────────────────────────────────────────

@router.get("/sites")
async def list_sites(
    region: Optional[str] = None,
    cluster: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all network sites with optional filters."""
    sites = network_ops.get_all_sites(db, region=region, cluster=cluster, status=status)
    return {
        "sites": sites,
        "total": len(sites),
    }


@router.get("/sites/{site_code}")
async def get_site(
    site_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed site info including incidents and KPIs."""
    site = network_ops.get_site_detail(db, site_code)
    if not site:
        return {"error": f"Site {site_code} not found"}
    return site


# ── Clusters ─────────────────────────────────────────────────────────────────

@router.get("/clusters/{cluster_name}/health")
async def get_cluster_health(
    cluster_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate health summary for a cluster."""
    return network_ops.get_cluster_health(db, cluster_name)


# ── Incidents ────────────────────────────────────────────────────────────────

@router.get("/incidents")
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter: open|investigating|resolved|closed"),
    severity: Optional[str] = Query(None, description="Filter: critical|major|minor|warning"),
    region: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List network incidents."""
    if status in ("open", "investigating"):
        incidents = network_ops.get_active_incidents(db, severity=severity, region=region)
    else:
        incidents = network_ops.get_all_incidents(db, status=status, region=region, days=days)

    return {
        "incidents": incidents,
        "total": len(incidents),
    }


@router.get("/incidents/active")
async def get_active_incidents(
    severity: Optional[str] = None,
    region: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all currently active incidents."""
    incidents = network_ops.get_active_incidents(db, severity=severity, region=region)
    critical = [i for i in incidents if i["severity"] == "critical"]
    return {
        "incidents": incidents,
        "total": len(incidents),
        "critical_count": len(critical),
    }


# ── KPIs ─────────────────────────────────────────────────────────────────────

@router.get("/kpis")
async def get_kpi_dashboard(
    scope: str = Query("region", description="Scope: national|region|cluster|site"),
    region: Optional[str] = Query("Lagos", description="Region name (default: Lagos)"),
    cluster: Optional[str] = Query(None, description="Cluster name e.g. Ikeja"),
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time KPI dashboard data. Defaults to Lagos region scope."""
    if scope == "cluster" and cluster:
        # return cluster-scoped KPIs
        from services.network_ops import get_kpi_timeseries
        data = get_kpi_timeseries(db, cluster=cluster, days=days)
        return {"scope": scope, "cluster": cluster, "region": region, "data": data, "total": len(data)}
    if scope == "region":
        return network_ops.get_kpi_summary(db, scope_level="region", days=days)
    return network_ops.get_kpi_summary(db, scope_level=scope, days=days)


@router.get("/kpis/timeseries")
async def get_kpi_timeseries(
    site_code: Optional[str] = None,
    cluster: Optional[str] = None,
    region: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """KPI time series data for charts."""
    data = network_ops.get_kpi_timeseries(
        db, site_code=site_code, cluster=cluster, region=region, days=days,
    )
    return {"data": data, "total": len(data)}


# ── Contracts ────────────────────────────────────────────────────────────────

@router.get("/contracts")
async def list_contracts(
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    expiring_days: Optional[int] = Query(None, description="Show contracts expiring within N days"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List vendor contracts with SLA terms."""
    contracts = network_ops.get_contracts(
        db, status=status, vendor=vendor, expiring_within_days=expiring_days,
    )
    return {"contracts": contracts, "total": len(contracts)}


@router.get("/sla-exposure")
async def get_sla_exposure(
    incident_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate SLA financial exposure."""
    return network_ops.calculate_sla_exposure(db, incident_id=incident_id)


# ── Heatmap ─────────────────────────────────────────────────────────────────

@router.get("/heatmap")
async def get_network_heatmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-region network health aggregated from live OMC-R data — powers the Nigeria map."""
    regions = network_ops.get_heatmap_data(db)
    return {"regions": regions, "total_regions": len(regions)}


# ── Operations Briefing ─────────────────────────────────────────────────────

@router.get("/briefing")
async def get_operations_briefing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full operations briefing — used by the Strategist agent and dashboard."""
    return network_ops.get_operations_briefing(db)
