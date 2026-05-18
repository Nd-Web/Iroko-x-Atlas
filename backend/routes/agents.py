"""
routes/agents.py — Agent status and manual trigger endpoints.

GET  /api/agents/status  — Returns live status dict for all 5 agents.
POST /api/agents/run     — Manually triggers the orchestrator pipeline.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.auth_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])

_AGENT_NAMES = [
    "WatchdogAgent", "ResearcherAgent", "AnalystAgent",
    "StrategistAgent", "ScribeAgent",
]

_agent_stats: dict[str, dict] = {
    name: {
        "name": name,
        "display_name": name.replace("Agent", ""),
        "last_run": None,
        "total_runs": 0,
        "avg_response_time": 0.0,
        "status": "idle",
        "_total_ms": 0.0,
    }
    for name in _AGENT_NAMES
}


def update_agent_stats(agent_name: str, duration_ms: float, success: bool = True) -> None:
    if agent_name not in _agent_stats:
        _agent_stats[agent_name] = {
            "name": agent_name,
            "display_name": agent_name.replace("Agent", ""),
            "last_run": None, "total_runs": 0,
            "avg_response_time": 0.0, "status": "idle", "_total_ms": 0.0,
        }
    s = _agent_stats[agent_name]
    s["total_runs"] = s.get("total_runs", 0) + 1
    s["_total_ms"] = s.get("_total_ms", 0.0) + duration_ms
    s["avg_response_time"] = round(s["_total_ms"] / s["total_runs"], 1)
    s["last_run"] = datetime.now(timezone.utc).isoformat()
    s["status"] = "idle" if success else "error"


class AgentStatus(BaseModel):
    name: str
    display_name: str
    last_run: Optional[str]
    total_runs: int
    avg_response_time: float
    status: str


class AgentStatusResponse(BaseModel):
    agents: list[AgentStatus]
    timestamp: str


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    org_id: str = Field(default="MTN Nigeria")


class AgentStep(BaseModel):
    agent: str
    status: str
    message: str
    timestamp: str


class RunResponse(BaseModel):
    query: str
    reasoning_chain: list[AgentStep]
    final_response: str
    risk_score: int
    confidence: str
    duration_ms: float


@router.get("/status", response_model=AgentStatusResponse)
async def agent_status(current_user=Depends(get_current_user)):
    agents_out = []
    for name in _AGENT_NAMES:
        s = _agent_stats.get(name, {})
        agents_out.append(AgentStatus(
            name=name,
            display_name=s.get("display_name", name.replace("Agent", "")),
            last_run=s.get("last_run"),
            total_runs=int(s.get("total_runs", 0)),
            avg_response_time=float(s.get("avg_response_time", 0.0)),
            status=str(s.get("status", "idle")),
        ))
    return AgentStatusResponse(agents=agents_out, timestamp=datetime.now(timezone.utc).isoformat())


@router.post("/run", response_model=RunResponse)
async def run_agents(body: RunRequest, current_user=Depends(get_current_user)):
    start = time.monotonic()
    steps: list[dict] = []
    final_response = ""
    risk_score = 1
    confidence = "medium"

    try:
        from agents.orchestrator import orchestrate_pipeline
        async for event in orchestrate_pipeline(query=body.query, org_id=body.org_id):
            if event.get("type") == "final":
                final_response = event.get("response", "")
                risk_score = int(event.get("risk_score", 1))
                confidence = event.get("confidence", "medium")
                steps.extend(event.get("reasoning_steps", []))
            else:
                steps.append(event)
    except Exception as exc:
        logger.error(f"agents/run error: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Agent pipeline error: {exc}")

    duration_ms = (time.monotonic() - start) * 1000
    seen = {s["agent"] for s in steps if "agent" in s}
    for name in seen:
        update_agent_stats(name, duration_ms / max(len(seen), 1))

    chain = [
        AgentStep(
            agent=s.get("agent", "unknown"),
            status=s.get("status", "done"),
            message=s.get("message", ""),
            timestamp=s.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
        for s in steps if "agent" in s
    ]

    return RunResponse(
        query=body.query,
        reasoning_chain=chain,
        final_response=final_response,
        risk_score=risk_score,
        confidence=confidence,
        duration_ms=round(duration_ms, 1),
    )
