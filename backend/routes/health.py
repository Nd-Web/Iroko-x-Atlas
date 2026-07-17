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


@router.get("/full", summary="Full-stack health check")
async def health_full() -> dict:
    """
    Checks every external dependency with per-component status + latency:
    database, Azure AI Search, Azure OpenAI chat, embeddings, blob storage,
    Cosmos Gremlin graph, and Bright Data web intelligence.

    Components degrade independently — one failure never hides the others.
    """
    import asyncio
    import os
    import time

    results: dict[str, dict] = {}

    def _record(name: str, ok: bool, started: float, detail: str = ""):
        results[name] = {
            "status": "ok" if ok else "error",
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            **({"detail": detail[:200]} if detail else {}),
        }

    # ── 1. Database ─────────────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        from models.database import engine as sync_engine
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _record("database", True, t)
    except Exception as exc:
        _record("database", False, t, str(exc))

    # ── 2. Azure AI Search ──────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        from services.azure_search import get_search_client
        client = get_search_client()
        if client is None:
            _record("azure_search", False, t, "not configured")
        else:
            stats = client.get_document_count()  # cheap data-plane call
            results["azure_search"] = {
                "status": "ok",
                "latency_ms": round((time.perf_counter() - t) * 1000, 1),
                "documents_indexed": int(stats),
            }
    except Exception as exc:
        _record("azure_search", False, t, str(exc))

    # ── 3. Azure OpenAI chat (1-token live probe) ───────────────────────────
    t = time.perf_counter()
    try:
        from agents.kernel import llm_complete
        r = await asyncio.wait_for(
            llm_complete("ping", max_tokens=4, service_id="nano"), timeout=20
        )
        _record("azure_openai_chat", bool(r is not None), t)
    except Exception as exc:
        _record("azure_openai_chat", False, t, str(exc))

    # ── 4. Embeddings ───────────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        from services.embeddings import get_embeddings_batch
        vecs = await asyncio.wait_for(get_embeddings_batch(["ping"]), timeout=20)
        _record("embeddings", bool(vecs and vecs[0]), t)
    except Exception as exc:
        _record("embeddings", False, t, str(exc))

    # ── 5. Blob storage ─────────────────────────────────────────────────────
    t = time.perf_counter()
    try:
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            _record("blob_storage", False, t, "not configured")
        else:
            from azure.storage.blob import BlobServiceClient
            svc = BlobServiceClient.from_connection_string(conn_str)
            container = os.getenv("AZURE_STORAGE_CONTAINER", "iroko-documents")
            exists = svc.get_container_client(container).exists()
            _record("blob_storage", bool(exists), t, "" if exists else f"container '{container}' missing")
    except Exception as exc:
        _record("blob_storage", False, t, str(exc))

    # ── 6. Cosmos Gremlin knowledge graph ───────────────────────────────────
    t = time.perf_counter()
    try:
        from services.cosmos_graph import _get_client as _get_gremlin
        client = _get_gremlin()
        if client is None:
            _record("cosmos_graph", False, t, "not configured")
        else:
            def _count():
                return client.submit("g.V().limit(1).count()").all().result()
            await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, _count), timeout=15)
            _record("cosmos_graph", True, t)
    except Exception as exc:
        _record("cosmos_graph", False, t, str(exc))

    # ── 7. Bright Data web intelligence ─────────────────────────────────────
    t = time.perf_counter()
    try:
        from services.brightdata import bright_data_client
        if bright_data_client.mock_mode:
            _record("web_intelligence", False, t, "not configured (mock mode)")
        else:
            r = await asyncio.wait_for(
                bright_data_client.serp_search("ping", num_results=1), timeout=25
            )
            _record("web_intelligence", isinstance(r, list), t)
    except Exception as exc:
        _record("web_intelligence", False, t, str(exc))

    core = ("database", "azure_search", "azure_openai_chat", "embeddings")
    core_ok = all(results.get(c, {}).get("status") == "ok" for c in core)
    all_ok = all(v.get("status") == "ok" for v in results.values())
    overall = "ok" if all_ok else ("degraded" if core_ok else "critical")

    return {
        "status": overall,
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": results,
        "note": "core = database, search, chat, embeddings; other components degrade gracefully.",
    }
