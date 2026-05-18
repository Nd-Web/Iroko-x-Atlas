"""
OMC-R Connector Routes
=======================
Exposes the OMC-R integration endpoints:

  GET  /api/connectors/omcr/status    — connection health + last sync stats
  POST /api/connectors/omcr/sync      — trigger an immediate sync
  GET  /api/connectors/omcr/snapshot  — live passthrough (raw omcr-demo data)

The omcr-demo at OMCR_API_URL acts as a stand-in for a real RAN OSS/NMS feed.
"""
import os
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException

from models.database import User
from services.auth_utils import get_current_user
from services.omcr_sync import fetch_snapshot, get_last_sync, run_omcr_sync, OMCR_API_URL

router = APIRouter(prefix="/api/connectors/omcr", tags=["OMC-R Connector"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def omcr_status(current_user: User = Depends(get_current_user)):
    """
    Returns the OMC-R connector configuration and last sync result.
    Use this to confirm the connection to the omcr-demo is working.
    """
    configured = bool(OMCR_API_URL)
    last = get_last_sync()

    # Quick connectivity ping
    reachable = False
    latency_ms = None
    try:
        t0 = datetime.utcnow()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OMCR_API_URL}/api/omcr/simulator")
            reachable = resp.status_code == 200
        latency_ms = round((datetime.utcnow() - t0).total_seconds() * 1000)
    except Exception:
        pass

    return {
        "connector": "omcr",
        "configured": configured,
        "omcr_url": OMCR_API_URL,
        "reachable": reachable,
        "latency_ms": latency_ms,
        "last_sync": last,
    }


@router.post("/sync")
async def omcr_sync(current_user: User = Depends(get_current_user)):
    """
    Trigger an immediate OMC-R sync.
    Fetches the latest snapshot from omcr-demo and upserts sites,
    incidents and KPIs into the atlascore database.
    """
    try:
        result = await run_omcr_sync()
        return {"message": "OMC-R sync complete", **result}
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach omcr-demo at {OMCR_API_URL}: {exc}",
        )
    except Exception as exc:
        logger.exception("OMC-R sync failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/snapshot")
async def omcr_live_snapshot(current_user: User = Depends(get_current_user)):
    """
    Live passthrough — returns the raw snapshot from omcr-demo without
    touching the database. Useful for debugging the feed in real time.
    """
    try:
        snapshot = await fetch_snapshot()
        return {
            "source": f"{OMCR_API_URL}/api/omcr/snapshot",
            "fetched_at": datetime.utcnow().isoformat(),
            "data": snapshot,
        }
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach omcr-demo: {exc}",
        )
