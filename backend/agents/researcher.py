"""
Researcher Agent
Finds and retrieves information from the organisation's indexed enterprise documents.
Includes Cohere reranking and corrective-RAG knowledge-gap detection.
Capability-scoped via CapabilityGuard (Integration 12).
"""
import json
import os
import asyncio
import logging
from typing import Optional, Annotated
from agents._compat import kernel_function, Kernel
from services.azure_search import get_search_client, hybrid_search_detailed, rerank_results, check_retrieval_quality

logger = logging.getLogger(__name__)

try:
    from services.agent_capabilities import capability_guard, AgentCapability
    _CAPS_AVAILABLE = True
except ImportError:
    _CAPS_AVAILABLE = False
    logger.warning("[ResearcherAgent] agent_capabilities not available — scoping unenforced")

_KNOWLEDGE_GAP_MESSAGE = (
    "No matching passages were found in the documents available to you. "
    "Try a document title or a more specific question, or upload the relevant document."
)

_RETRIEVAL_MESSAGES = {
    "empty": _KNOWLEDGE_GAP_MESSAGE,
    "unavailable": "Document search is temporarily unavailable. Please try again shortly.",
    "access_check_failed": (
        "I could not verify access to the document evidence. Please try again shortly."
    ),
}


def _retrieval_gap(status: str) -> str:
    """Return safe diagnostics without revealing backend errors or foreign records."""
    if status not in _RETRIEVAL_MESSAGES:
        status = "unavailable"
    return json.dumps({
        "results": [],
        "knowledge_gap": True,
        "retrieval_status": status,
        "message": _RETRIEVAL_MESSAGES[status],
    })


class ResearcherAgent:
    """
    The Researcher is Atlas's information retrieval specialist.
    It searches indexed documents, reranks results via Cohere for true
    relevance, and applies corrective-RAG quality checks to detect when
    Atlas simply doesn't have enough information to answer a question.
    """

    SYSTEM_PROMPT = """You are Iroko AI, the Researcher agent. Your job is to find the most
relevant documents from the organisation's enterprise document corpus for any query. Execute hybrid search
(lexical + vector) against Azure AI Search. Return top-k chunks with relevance scores and
source metadata. Every chunk you return must have a document ID and section reference.
If confidence is below threshold, flag for Watchdog review. You do not generate answers —
you retrieve evidence."""

    @kernel_function(
        description="""Search across all indexed enterprise documents for information
        relevant to a query. Use this to find facts, regulatory returns, contracts, RCA
        reports, policies, complaints, network data, or any written information. Returns
        top matching document excerpts with source citations."""
    )
    async def search_documents(
        self,
        query: Annotated[str, "The search query — what you're looking for"],
        top_k: Annotated[int, "Number of results to return (default 5)"] = 5,
        department: Annotated[Optional[str], "Filter by department name (optional)"] = None,
        doc_type: Annotated[Optional[str], "Filter by document type: contract, report, policy, complaint, maintenance (optional)"] = None,
    ) -> str:
        """
        Hybrid search (keyword + semantic) with Cohere reranking.
        Retrieves top 20 candidates, reranks to top_k, then checks whether
        the results are actually good enough to answer the question.
        """
        # GAP 4 FIX — capability guard
        if _CAPS_AVAILABLE:
            try:
                capability_guard.require("ResearcherAgent", AgentCapability.FETCH_REGULATORY)
            except PermissionError as e:
                logger.warning("[ResearcherAgent] Capability check failed (%s)", type(e).__name__)
                return _retrieval_gap("access_check_failed")
        try:
            filters = []
            if department:
                filters.append("department eq '" + department.replace("'", "''") + "'")
            if doc_type:
                filters.append("doc_type eq '" + doc_type.replace("'", "''") + "'")
            filter_str = " and ".join(filters) if filters else None

            mem_context = None  # Only extracted source text may enter document Q&A.

            # Retrieve candidate set via hybrid (BM25 + vector) search
            retrieval = await hybrid_search_detailed(query=query, top=20, filter_str=filter_str)
            raw = retrieval["results"]

            # Empty retrieval is a knowledge gap, never permission to fabricate evidence.
            if not raw:
                return _retrieval_gap(retrieval["retrieval_status"])

            # ── Corrective RAG: check quality BEFORE reranking ────────────
            quality = check_retrieval_quality(query, raw)
            # Retrieval confidence is ranking telemetry, not an answerability probability.
            # Exact-source claim validation determines whether a question can be answered.

            # ── Rerank top 20 → top_k ─────────────────────────────────────
            reranked = rerank_results(query, raw, top_n=top_k)

            formatted = []
            for r in reranked:
                formatted.append({
                    "document_id":  r.get("doc_id", r.get("id", "")),
                    "chunk_id":     r.get("id", ""),
                    "title":        r.get("title", "Untitled"),
                    "department":   r.get("department", "Unknown"),
                    "doc_type":     r.get("doc_type", "document"),
                    "excerpt":      r.get("content", ""),
                    "source":       r.get("source", ""),
                    "language":     r.get("language", "en"),
                    "classification": r.get("classification", "internal"),
                    "region":       r.get("region", ""),
                    "chunk_index":  r.get("chunk_index", 0),
                    "provenance":   r.get("provenance"),
                    "created_at":   str(r.get("created_at", "")),
                    "relevance_score": round(
                        r.get("rerank_score", r.get("@search.score", 0)), 3
                    ),
                })

            if not formatted:
                return _retrieval_gap("empty")

            return json.dumps({
                "results": formatted,
                "total_found": len(formatted),
                "retrieval_confidence": quality["confidence"],
                "retrieval_status": "ok",
                "historical_context": mem_context,
            })

        except Exception as e:
            logger.warning("Researcher search failed (%s)", type(e).__name__)
            return _retrieval_gap("unavailable")

    @kernel_function(
        description="""Get the complete full text of a specific document by its ID.
        Use this when you need to read the entire document, not just an excerpt."""
    )
    async def get_full_document(
        self,
        document_id: Annotated[str, "The document ID to retrieve"],
    ) -> str:
        try:
            from ingestion.access import require_document
            from ingestion.db import Session
            with Session() as db:
                require_document(db, document_id)
            from ingestion.queue import enabled
            if enabled():
                from ingestion.db import Session
                from ingestion.models import Page, Revision
                from models.database import Document
                with Session() as db:
                    revision = db.get(Revision, document_id)
                    if revision:
                        document = db.get(Document, document_id)
                        if not document or document.status != "indexed" or not revision.is_current:
                            return json.dumps({"error": "Document is not an approved current source"})
                        pages = db.query(Page).filter_by(document_id=document_id).order_by(Page.position).all()
                        return json.dumps({"id": document_id, "title": document.title,
                                           "content": "\n\n".join(p.text for p in pages),
                                           "provenance": revision.provenance})
            client = get_search_client()
            if client is None:
                return json.dumps({"error": "Search client not configured"})

            safe = document_id.replace("'", "''")
            chunks = await asyncio.to_thread(lambda: list(client.search(
                search_text="*", filter=f"doc_id eq '{safe}'",
            )))
            from services.azure_search import eligible_results
            chunks = await asyncio.to_thread(eligible_results, chunks)
            if not chunks:
                return json.dumps({"error": "Document not found"})
            chunks.sort(key=lambda c: c.get("chunk_index", 0))
            doc = dict(chunks[0])
            doc["content"] = "\n\n".join(c.get("content", "") for c in chunks)
            return json.dumps({
                "id":             doc.get("id"),
                "doc_id":         doc.get("doc_id", doc.get("id")),
                "title":          doc.get("title"),
                "content":        doc.get("content"),
                "department":     doc.get("department"),
                "doc_type":       doc.get("doc_type", "document"),
                "classification": doc.get("classification", "internal"),
                "region":         doc.get("region", ""),
                "language":       doc.get("language", "en"),
                "source":         doc.get("source", ""),
                "created_at":     str(doc.get("created_at")),
            })
        except Exception as e:
            logger.error(f"Researcher get_document failed: {e}")
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""List all available documents filtered by department or type.
        Use this to understand what documents exist before searching."""
    )
    async def list_documents(
        self,
        department: Annotated[Optional[str], "Filter by department (optional)"] = None,
        doc_type: Annotated[Optional[str], "Filter by type: contract, report, policy, complaint, maintenance (optional)"] = None,
        limit: Annotated[int, "Maximum number to return"] = 20,
    ) -> str:
        try:
            client = get_search_client()
            if client is None:
                return json.dumps({"documents": [], "error": "Search unavailable"})

            from ingestion.access import search_filter
            acl = await asyncio.to_thread(search_filter)
            if not acl:
                return json.dumps({"documents": []})
            filters = [acl]
            if department:
                filters.append("department eq '" + department.replace("'", "''") + "'")
            if doc_type:
                filters.append("doc_type eq '" + doc_type.replace("'", "''") + "'")

            results = client.search(
                search_text="*",
                top=limit,
                filter=" and ".join(filters) if filters else None,
                select=["id", "doc_id", "content", "title", "department", "doc_type", "created_at"],
            )

            from services.azure_search import eligible_results
            results = eligible_results(list(results))

            docs = [
                {
                    "id": r["id"],
                    "title": r.get("title"),
                    "department": r.get("department"),
                    "type": r.get("doc_type"),
                    "date": str(r.get("created_at", "")),
                }
                for r in results
            ]

            return json.dumps({"documents": docs, "total": len(docs)})

        except Exception as e:
            logger.warning(
                "[ResearcherAgent] list_documents Azure call failed (%s) — "
                "returning an empty document list.", e
            )
            return self._mock_document_list()

    # ── Knowledge Gap Logging ─────────────────────────────────────────────────

    async def _log_knowledge_gap(
        self,
        query: str,
        confidence: float,
        department_filter: Optional[str] = None,
    ) -> None:
        """Persist a knowledge gap record so admins can see unanswerable queries."""
        try:
            from models.database import SessionLocal, KnowledgeGap
            db = SessionLocal()
            try:
                gap = KnowledgeGap(
                    query=query,
                    department_filter=department_filter,
                    confidence_score=confidence,
                )
                db.add(gap)
                db.commit()
                logger.info(f"Knowledge gap logged: '{query[:60]}' (confidence={confidence})")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log knowledge gap: {e}")

    # ── Mock data ─────────────────────────────────────────────────────────────

    def _mock_search(self, query: str) -> str:
        return json.dumps({"results": [], "knowledge_gap": True, "source": "unavailable"})

    def _mock_document_list(self) -> str:
        return json.dumps({"documents": [], "total": 0, "error": "Search unavailable"})
