"""
routes/search.py — Document search endpoints for Iroko AI.

POST /search         — Hybrid search returning structured results.
POST /search/context — Returns a formatted context string for LLM injection.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


# ── Request / Response schemas ────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    org_id: str = Field(default="MTN Nigeria")
    category: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    content: str
    source: str
    score: float
    document_id: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


class ContextRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    org_id: str = Field(default="MTN Nigeria")
    top_k: int = Field(default=5, ge=1, le=20)


class ContextResponse(BaseModel):
    query: str
    context: str
    result_count: int


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=SearchResponse)
async def search(body: SearchRequest):
    """
    Run a hybrid (BM25 + semantic) search against the Azure AI Search index.

    If ``category`` is provided the results are additionally filtered by
    document type (e.g. ``"SLA"``, ``"compliance"``, ``"contract"``).

    Returns the top-k results with ``content``, ``source``, ``score``, and
    ``document_id`` for each hit.
    """
    try:
        if body.category:
            from services.search import search_by_category

            raw = await search_by_category(
                query=body.query,
                org_id=body.org_id,
                category=body.category,
                top_k=body.top_k,
            )
        else:
            from services.search import search_documents

            raw = await search_documents(
                query=body.query,
                org_id=body.org_id,
                top_k=body.top_k,
            )
    except Exception as exc:
        logger.error(f"search endpoint error: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Search service unavailable: {exc}")

    results = [
        SearchResult(
            content=r.get("content", ""),
            source=r.get("source", "Unknown"),
            score=float(r.get("score", 0.0)),
            document_id=str(r.get("document_id", "")),
        )
        for r in raw
    ]

    return SearchResponse(query=body.query, results=results, total=len(results))


@router.post("/context", response_model=ContextResponse)
async def search_context(body: ContextRequest):
    """
    Search documents and return a single formatted context string suitable
    for injection into an LLM prompt.

    Format::

        [Source: filename]
        content chunk 1

        [Source: filename]
        content chunk 2
    """
    try:
        from services.search import get_context_for_query

        context_str = await get_context_for_query(
            query=body.query,
            org_id=body.org_id,
            top_k=body.top_k,
        )
    except Exception as exc:
        logger.error(f"search_context endpoint error: {exc}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Search service unavailable: {exc}")

    # Count source blocks as a proxy for result count
    result_count = context_str.count("[Source:")

    return ContextResponse(
        query=body.query,
        context=context_str,
        result_count=result_count,
    )
