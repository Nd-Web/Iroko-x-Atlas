"""
Fraud Intelligence Routes
"""
from fastapi import APIRouter, Depends
from typing import Optional

from models.database import User
from services.auth_utils import get_current_user
from services.fraud_service import get_fraud_signals, get_fraud_summary

router = APIRouter(prefix="/api/fraud", tags=["Fraud Intelligence"])


@router.get("/summary")
async def fraud_summary(current_user: User = Depends(get_current_user)):
    """Aggregated fraud signal counts and financial exposure."""
    return get_fraud_summary()


@router.get("/signals")
async def fraud_signals(
    category: Optional[str] = None,
    risk: Optional[str] = None,
    region: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """List fraud signals with optional filters."""
    signals = get_fraud_signals(category=category, risk=risk, region=region)
    return {"signals": signals, "total": len(signals)}
