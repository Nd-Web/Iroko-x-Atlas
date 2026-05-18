"""
services/search.py — High-level search service for Iroko AI.

Wraps ``services.azure_search`` to provide three public async functions:

- ``search_documents``   — hybrid (keyword + semantic) search filtered by org
- ``search_by_category`` — same but additionally filtered by a category field
- ``get_context_for_query`` — formats top hits into a single LLM-ready context string

All functions are async and use ``core.config.settings`` for Azure credentials.
"""

import logging
from typing import Optional

from core.exceptions import AzureServiceException

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_filter(
    org_id: Optional[str] = None,
    category: Optional[str] = None,
) -> Optional[str]:
    """
    Build an OData filter string for Azure AI Search.

    The ``iroko-chunks`` index stores the organisation in the ``department``
    field (each department maps to an org context in the MTN deployment).
    The ``doc_type`` field is used for category filtering (SLA, compliance, etc.).
    """
    parts: list[str] = []

    if org_id:
        safe = org_id.replace("'", "''")
        parts.append(f"department eq '{safe}'")

    if category:
        safe = category.replace("'", "''")
        parts.append(f"doc_type eq '{safe}'")

    return " and ".join(parts) if parts else None


def _normalise_hit(raw: dict) -> dict:
    """
    Normalise a raw Azure AI Search result into the clean schema expected
    by callers: ``{content, source, score, document_id}``.
    """
    # Content — prefer the full text, fall back to excerpt
    content = raw.get("content") or raw.get("excerpt") or ""

    # Source — human-readable origin
    source = raw.get("source") or raw.get("title") or "Unknown"

    # Score — best available relevance signal
    score: float = 0.0
    if "rerank_score" in raw:
        score = float(raw["rerank_score"])
    elif "@search.reranker_score" in raw:
        score = min(1.0, float(raw["@search.reranker_score"]) / 4.0)
    elif "@search.score" in raw:
        score = float(raw["@search.score"])

    # Document ID
    document_id = raw.get("doc_id") or raw.get("parent_id") or raw.get("id") or ""

    return {
        "content": content,
        "source": source,
        "score": round(score, 4),
        "document_id": document_id,
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def search_documents(
    query: str,
    org_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Run a hybrid search (BM25 + semantic vector) against Azure AI Search,
    filtered by ``org_id``.

    Parameters
    ----------
    query : str
        Natural-language search query.
    org_id : str
        Organisation / department identifier for row-level filtering.
    top_k : int
        Maximum number of results to return (default 5).

    Returns
    -------
    list[dict]
        Each dict contains: ``content``, ``source``, ``score``, ``document_id``.

    Raises
    ------
    AzureServiceException
        If Azure AI Search is unreachable or returns an unrecoverable error.
    """
    from services.azure_search import hybrid_search, rerank_results

    filter_str = _build_filter(org_id=org_id)

    try:
        # Fetch more candidates than needed so reranking has room
        raw_results = await hybrid_search(
            query=query,
            top=max(top_k * 3, 20),
            filter_str=filter_str,
        )
    except Exception as exc:
        logger.error(f"search_documents: Azure Search failed — {exc}", exc_info=True)
        raise AzureServiceException(
            detail=f"Document search failed: {exc}",
            service="Azure AI Search",
        )

    # Apply Cohere reranking if available
    if raw_results:
        raw_results = rerank_results(query=query, results=raw_results, top_n=top_k)
    else:
        raw_results = raw_results[:top_k]

    return [_normalise_hit(r) for r in raw_results]


async def search_by_category(
    query: str,
    org_id: str,
    category: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Hybrid search filtered by both ``org_id`` and a ``category`` metadata field.

    Categories map to the ``doc_type`` field in the Azure AI Search index
    (e.g. ``"SLA"``, ``"compliance"``, ``"complaints"``, ``"contract"``).

    Parameters
    ----------
    query : str
        Natural-language search query.
    org_id : str
        Organisation / department identifier.
    category : str
        Document category to filter on (maps to ``doc_type``).
    top_k : int
        Maximum results (default 5).

    Returns
    -------
    list[dict]
        Same schema as ``search_documents``.
    """
    from services.azure_search import hybrid_search, rerank_results

    filter_str = _build_filter(org_id=org_id, category=category)

    try:
        raw_results = await hybrid_search(
            query=query,
            top=max(top_k * 3, 20),
            filter_str=filter_str,
        )
    except Exception as exc:
        logger.error(
            f"search_by_category: Azure Search failed — {exc}", exc_info=True
        )
        raise AzureServiceException(
            detail=f"Category search failed: {exc}",
            service="Azure AI Search",
        )

    if raw_results:
        raw_results = rerank_results(query=query, results=raw_results, top_n=top_k)
    else:
        raw_results = raw_results[:top_k]

    return [_normalise_hit(r) for r in raw_results]


async def get_context_for_query(
    query: str,
    org_id: str,
    top_k: int = 5,
) -> str:
    """
    Search for relevant documents and format the results into a single
    context string suitable for injecting into an LLM prompt.

    Format per result::

        [Source: filename]
        content

    Parameters
    ----------
    query : str
        Natural-language query.
    org_id : str
        Organisation / department identifier.
    top_k : int
        Maximum results to include in context.

    Returns
    -------
    str
        Formatted context block.  Returns a "no results" message if the
        search yields nothing (callers should still pass this to the LLM
        so it can generate a graceful "insufficient data" response).
    """
    results = await search_documents(query=query, org_id=org_id, top_k=top_k)

    if not results:
        return (
            "[No relevant documents found]\n"
            "The knowledge base does not contain sufficient information "
            "to answer this query with confidence."
        )

    blocks: list[str] = []
    for r in results:
        source = r.get("source", "Unknown")
        content = r.get("content", "").strip()
        if content:
            blocks.append(f"[Source: {source}]\n{content}")

    return "\n\n".join(blocks)
