"""
Customer Experience API Routes
================================
Exposes complaint analytics, CX metrics, and trend data
for the frontend dashboard.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models.database import get_db, User
from services.auth_utils import get_current_user
from services import network_ops

router = APIRouter(prefix="/api/cx", tags=["Customer Experience"])
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def get_cx_dashboard(
    region: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """CX metrics dashboard — complaint summary, trends, resolution rates."""
    return network_ops.get_complaint_summary(db, region=region, days=days)


@router.get("/complaints")
async def list_complaints(
    category: Optional[str] = None,
    status: Optional[str] = None,
    region: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List complaint tickets with filters."""
    complaints = network_ops.get_complaints(
        db, category=category, status=status, region=region, days=days, limit=limit,
    )
    return {"complaints": complaints, "total": len(complaints)}


@router.get("/correlations")
async def get_complaint_incident_correlations(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find complaint spikes correlated with network incidents."""
    correlations = network_ops.correlate_complaints_to_incidents(db, days=days)
    return {"correlations": correlations, "total": len(correlations)}
