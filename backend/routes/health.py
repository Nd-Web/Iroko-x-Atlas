"""
routes/health.py — Health check endpoints for Iroko AI.

GET  /health       — Shallow ping (always fast, no DB).
GET  /health/deep  — Deep check: verifies DB connection + Azure AI Search.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Shallow health check")
async def health_shallow() -> dict:
    """
    Returns ``{"status": "ok"}`` immediately — no I/O.
    Used by load-balancer / Kubernetes liveness probes.
    """
    return {
        "status": "ok",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/deep", summary="Deep health check")
async def health_deep() -> dict:
    """
    Checks DB connectivity and Azure AI Search availability.
    Returns ``"ok"`` if all checks pass, ``"degraded"`` if any fail.
    """
    checks: dict[str, bool] = {}

    # ── 1. Database ───────────────────────────────────────────────────────────
    try:
        from models.database import engine as sync_engine
        from sqlalchemy import text

        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        logger.warning(f"health_deep: DB check failed — {exc}")
        checks["database"] = False

    # ── 2. Azure AI Search ────────────────────────────────────────────────────
    try:
        from services.azure_search import get_search_client

        client = get_search_client()
        if client is None:
            checks["azure_search"] = False
        else:
            # A cheap call: retrieve index statistics
            result = client.get_index_statistics()  # type: ignore[attr-defined]
            checks["azure_search"] = result is not None
    except Exception as exc:
        logger.warning(f"health_deep: Azure Search check failed — {exc}")
        checks["azure_search"] = False

    overall = "ok" if all(checks.values()) else "degraded"

    return {
        "status": overall,
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
