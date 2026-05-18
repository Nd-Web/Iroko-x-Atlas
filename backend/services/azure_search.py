"""
Azure AI Search client wrapper.
Handles document indexing (hybrid BM25 + 3072-dim vector), semantic search,
Cohere reranking, and corrective-RAG knowledge-gap detection.

Index: iroko-chunks  (created in Azure portal — field schema below)
Fields indexed:
  id, content, title, content_vector (3072), doc_id, doc_type,
  source, language, classification, department, region,
  chunk_index, parent_id, created_at
"""
import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

INDEX_NAME     = os.getenv("AZURE_SEARCH_INDEX_NAME",     "iroko-chunks")
SEMANTIC_CONFIG = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG", "iroko-semantic")

_search_client = None
_cohere_client = None


def _get_cohere_client():
    """Return singleton Cohere client."""
    global _cohere_client
    if _cohere_client is not None:
        return _cohere_client
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return None
    try:
        import cohere
        _cohere_client = cohere.Client(api_key)
        logger.info("Cohere rerank client initialised.")
        return _cohere_client
    except Exception as e:
        logger.warning(f"Failed to init Cohere client: {e}")
        return None


def get_search_client():
    """Return the singleton SearchClient, building it on first call."""
    global _search_client

    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    api_key  = os.getenv("AZURE_SEARCH_API_KEY")

    if not endpoint or not api_key:
        logger.warning("Azure AI Search not configured — running in mock mode.")
        return None

    if _search_client is None:
        try:
            from azure.search.documents import SearchClient
            from azure.core.credentials import AzureKeyCredential
            _search_client = SearchClient(
                endpoint=endpoint,
                index_name=INDEX_NAME,
                credential=AzureKeyCredential(api_key),
            )
            logger.info(f"Azure AI Search client initialised (index: {INDEX_NAME}).")
        except Exception as e:
            logger.error(f"Failed to init Azure Search client: {e}")
            return None

    return _search_client


# ── Indexing ──────────────────────────────────────────────────────────────────

async def index_document_chunks(
    document_id: str,
    title: str,
    chunks: List,          # List[str] (legacy) or List[Dict] from smart_chunk_document()
    metadata: Dict[str, Any],
) -> bool:
    """
    Upload chunks to the iroko-chunks index with hybrid search fields.

    Each document in the index must match the iroko-chunks field schema:
      id (key), content, title, content_vector, doc_id, doc_type,
      source, language, classification, department, region,
      chunk_index, parent_id, created_at
    """
    client = get_search_client()

    # Generate embeddings for all chunks in one batched call
    contents = []
    for chunk in chunks:
        contents.append(chunk.get("content", "") if isinstance(chunk, dict) else chunk)

    from services.embeddings import get_embeddings_batch
    embeddings = await get_embeddings_batch(contents)

    documents = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if isinstance(chunk, dict):
            content      = chunk.get("content", "")
            chunk_index  = chunk.get("chunk_index", i)
        else:
            content      = chunk
            chunk_index  = i

        doc: Dict[str, Any] = {
            "id":             f"{document_id}_chunk_{chunk_index}",
            "content":        content,
            "title":          title,
            "doc_id":         document_id,
            "parent_id":      document_id,
            "doc_type":       metadata.get("doc_type", "document"),
            "source":         metadata.get("source", metadata.get("filename", "")),
            "language":       metadata.get("language", "en"),
            "classification": metadata.get("classification", "internal"),
            "department":     metadata.get("department", ""),
            "region":         metadata.get("region", ""),
            "chunk_index":    chunk_index,
            "created_at":     metadata.get("created_at", ""),
        }

        if embedding is not None:
            doc["content_vector"] = embedding
        # If embedding unavailable (OpenAI not reachable) we still index the
        # text fields so BM25 search continues to work.

        documents.append(doc)

    if client is None:
        logger.info(f"Mock index: {len(documents)} chunks for '{title}'")
        return True

    try:
        result = client.upload_documents(documents=documents)
        succeeded = sum(1 for r in result if r.succeeded)
        failed_results = [r for r in result if not r.succeeded]
        if failed_results:
            sample = failed_results[0]
            logger.error(
                f"Index upload partial failure for '{title}': "
                f"{len(failed_results)}/{len(documents)} failed. "
                f"First error — key={sample.key}, status={sample.status_code}, "
                f"message={getattr(sample, 'error_message', 'n/a')}"
            )
        logger.info(f"Indexed {succeeded}/{len(documents)} chunks for '{title}'")
        return succeeded == len(documents)
    except Exception as e:
        logger.error(f"Failed to index document '{title}': {e}", exc_info=True)
        return False


# ── Semantic + Vector Search ──────────────────────────────────────────────────

async def hybrid_search(
    query: str,
    top: int = 20,
    filter_str: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid search: BM25 lexical + HNSW vector retrieval, re-ranked by semantic scorer.
    Falls back to BM25-only if embeddings are unavailable.
    """
    client = get_search_client()
    if client is None:
        return []

    # Generate query embedding for the vector leg of hybrid search
    from services.embeddings import get_embedding
    query_vector = await get_embedding(query)

    search_kwargs: Dict[str, Any] = {
        "search_text":                  query,
        "top":                          top,
        "filter":                       filter_str,
        "query_type":                   "semantic",
        "semantic_configuration_name":  SEMANTIC_CONFIG,
        "select": [
            "id", "title", "department", "doc_type", "doc_id",
            "content", "created_at", "language", "classification",
            "region", "source", "chunk_index",
        ],
    }

    if query_vector is not None:
        from azure.search.documents.models import VectorizedQuery
        search_kwargs["vector_queries"] = [
            VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top,
                fields="content_vector",
            )
        ]

    try:
        return list(client.search(**search_kwargs))
    except Exception as e:
        logger.warning(f"Azure Search semantic query failed, falling back to simple: {e}")
        try:
            # Fallback: simple BM25 search without semantic or vector ranking
            simple_kwargs = {
                "search_text": search_kwargs["search_text"],
                "top":         search_kwargs.get("top", 10),
                "filter":      search_kwargs.get("filter"),
                "select":      search_kwargs.get("select"),
            }
            return list(client.search(**simple_kwargs))
        except Exception as e2:
            logger.error(f"Azure Search fallback query also failed: {e2}")
            return []


# ── Document Search (endpoint-oriented) ──────────────────────────────────────

async def search_documents(
    query: str,
    top: int = 10,
    department: Optional[str] = None,
    doc_type: Optional[str] = None,
    language: Optional[str] = None,
    classification: Optional[str] = None,
    source: Optional[str] = None,
    apply_rerank: bool = True,
) -> Dict[str, Any]:
    """
    High-level document search used directly by the /api/documents/search endpoint.

    Builds an OData filter from the caller's facet params, runs hybrid search
    (BM25 + vector + semantic), applies optional Cohere reranking, scores
    retrieval quality, and returns a clean dict ready for the API response.

    Returns:
        {
            "results": List[Dict],   # normalised hits
            "total_hits": int,
            "knowledge_gap": bool,
            "confidence": float,
        }
    """
    # ── Build OData filter ────────────────────────────────────────────────────
    filters: List[str] = []
    if department:
        safe = department.replace("'", "''")
        filters.append(f"department eq '{safe}'")
    if doc_type:
        safe = doc_type.replace("'", "''")
        filters.append(f"doc_type eq '{safe}'")
    if language:
        safe = language.replace("'", "''")
        filters.append(f"language eq '{safe}'")
    if classification:
        safe = classification.replace("'", "''")
        filters.append(f"classification eq '{safe}'")
    if source:
        safe = source.replace("'", "''")
        filters.append(f"source eq '{safe}'")

    filter_str = " and ".join(filters) if filters else None

    # ── Run hybrid search ─────────────────────────────────────────────────────
    raw_results = await hybrid_search(query=query, top=max(top * 2, 20), filter_str=filter_str)

    # ── Optional Cohere reranking ─────────────────────────────────────────────
    if apply_rerank and raw_results:
        raw_results = rerank_results(query=query, results=raw_results, top_n=top)
    else:
        raw_results = raw_results[:top]

    # ── Quality / knowledge-gap assessment ───────────────────────────────────
    quality = check_retrieval_quality(query=query, results=raw_results)

    # ── Normalise hits into a clean schema ───────────────────────────────────
    hits = []
    for r in raw_results:
        hit = {
            "chunk_id":      r.get("id", ""),
            "doc_id":        r.get("doc_id", r.get("parent_id", "")),
            "title":         r.get("title", ""),
            "excerpt":       (r.get("content") or r.get("excerpt") or "")[:800],
            "source":        r.get("source"),
            "department":    r.get("department"),
            "doc_type":      r.get("doc_type"),
            "language":      r.get("language"),
            "classification": r.get("classification"),
            "chunk_index":   r.get("chunk_index"),
            "search_score":  round(float(r["@search.score"]), 4) if "@search.score" in r else None,
            "rerank_score":  round(float(r["rerank_score"]), 4) if "rerank_score" in r else None,
            "created_at":    r.get("created_at"),
        }
        hits.append(hit)

    return {
        "results":       hits,
        "total_hits":    len(hits),
        "knowledge_gap": quality["knowledge_gap"],
        "confidence":    quality["confidence"],
    }


# ── Legacy word-count chunker (kept for compatibility) ───────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── Cohere Reranking ──────────────────────────────────────────────────────────

def rerank_results(
    query: str,
    results: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Reorder results by true relevance using Cohere Rerank.
    Falls back to original order (capped at top_n) when unavailable.
    """
    if not results:
        return results[:top_n]

    co = _get_cohere_client()
    if co is None:
        return results[:top_n]

    try:

        documents = [r.get("content", r.get("excerpt", "")) for r in results]
        non_empty = [(i, d) for i, d in enumerate(documents) if d.strip()]
        if not non_empty:
            return results[:top_n]

        indices, docs = zip(*non_empty)
        rerank_response = co.rerank(
            query=query,
            documents=list(docs),
            top_n=min(top_n, len(docs)),
            model="rerank-english-v3.0",
        )

        reranked = []
        for hit in rerank_response.results:
            original_index = indices[hit.index]
            result = dict(results[original_index])
            result["rerank_score"] = round(hit.relevance_score, 4)
            reranked.append(result)

        logger.info(f"Cohere rerank: {len(results)} → {len(reranked)} for '{query[:60]}'")
        return reranked

    except Exception as e:
        logger.warning(f"Cohere rerank failed (falling back): {e}")
        return results[:top_n]


# ── Corrective-RAG Quality Check ──────────────────────────────────────────────

def check_retrieval_quality(
    query: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Score whether retrieved results can answer the query.
    Returns {"confidence": float, "knowledge_gap": bool}
    """
    if not results:
        return {"confidence": 0.0, "knowledge_gap": True}

    scores = []
    for r in results:
        if "rerank_score" in r:
            scores.append(float(r["rerank_score"]))
        elif "@search.reranker_score" in r:
            # Azure semantic reranker: 0-4 scale → normalise to 0-1
            scores.append(min(1.0, float(r["@search.reranker_score"]) / 4.0))
        elif "@search.score" in r:
            scores.append(min(1.0, float(r["@search.score"])))
        elif "relevance_score" in r:
            scores.append(float(r["relevance_score"]))

    if not scores:
        return {"confidence": 0.7, "knowledge_gap": False}

    max_score  = max(scores)
    top3_avg   = sum(sorted(scores, reverse=True)[:3]) / min(3, len(scores))
    confidence = round(0.6 * max_score + 0.4 * top3_avg, 3)

    return {
        "confidence":    confidence,
        "knowledge_gap": confidence < 0.01,  # Coarse first-pass only; Watchdog handles fine-grained gating at 0.7/0.85
    }
