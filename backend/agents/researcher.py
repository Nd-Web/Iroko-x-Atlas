"""
Researcher Agent
Finds and retrieves information from indexed MTN enterprise documents.
Includes Cohere reranking and corrective-RAG knowledge-gap detection.
"""
import json
import logging
from typing import Optional, Annotated
from agents._compat import kernel_function, Kernel
from services.azure_search import get_search_client, hybrid_search, rerank_results, check_retrieval_quality

logger = logging.getLogger(__name__)

_KNOWLEDGE_GAP_MESSAGE = (
    "Atlas does not have sufficient documents to answer this question confidently. "
    "Consider uploading relevant documents to the knowledge base."
)


class ResearcherAgent:
    """
    The Researcher is Atlas's information retrieval specialist.
    It searches indexed documents, reranks results via Cohere for true
    relevance, and applies corrective-RAG quality checks to detect when
    Atlas simply doesn't have enough information to answer a question.
    """

    SYSTEM_PROMPT = """You are Iroko AI, the Researcher agent. Your job is to find the most
relevant documents from MTN Nigeria's indexed estate for any query. Execute hybrid search
(lexical + vector) against Azure AI Search. Return top-k chunks with relevance scores and
source metadata. Every chunk you return must have a document ID and section reference.
If confidence is below threshold, flag for Watchdog review. You do not generate answers —
you retrieve evidence."""

    @kernel_function(
        description="""Search across all MTN enterprise documents for information
        relevant to a query. Use this to find facts, contracts, reports, policies,
        complaints, maintenance logs, or any written information. Returns top matching
        document excerpts with source citations."""
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
        try:
            client = get_search_client()
            if client is None:
                return self._mock_search(query)

            filters = []
            if department:
                filters.append(f"department eq '{department}'")
            if doc_type:
                filters.append(f"doc_type eq '{doc_type}'")
            filter_str = " and ".join(filters) if filters else None

            # Retrieve candidate set via hybrid (BM25 + vector) search
            raw = await hybrid_search(query=query, top=20, filter_str=filter_str)

            # ── Corrective RAG: check quality BEFORE reranking ────────────
            quality = check_retrieval_quality(query, raw)
            if quality["knowledge_gap"]:
                logger.warning(
                    f"Knowledge gap detected for query '{query[:80]}' "
                    f"(confidence={quality['confidence']})"
                )
                await self._log_knowledge_gap(query, quality["confidence"], department)
                return json.dumps({
                    "results": [],
                    "knowledge_gap": True,
                    "confidence": quality["confidence"],
                    "message": _KNOWLEDGE_GAP_MESSAGE,
                })

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
                    "excerpt":      r.get("content", "")[:600],
                    "source":       r.get("source", ""),
                    "language":     r.get("language", "en"),
                    "classification": r.get("classification", "internal"),
                    "region":       r.get("region", ""),
                    "chunk_index":  r.get("chunk_index", 0),
                    "created_at":   str(r.get("created_at", "")),
                    "relevance_score": round(
                        r.get("rerank_score", r.get("@search.score", 0)), 3
                    ),
                })

            if not formatted:
                return json.dumps({"results": [], "message": "No documents found matching this query."})

            return json.dumps({
                "results": formatted,
                "total_found": len(formatted),
                "retrieval_confidence": quality["confidence"],
            })

        except Exception as e:
            logger.error(f"Researcher search failed: {e}")
            return json.dumps({"error": str(e), "results": []})

    @kernel_function(
        description="""Get the complete full text of a specific document by its ID.
        Use this when you need to read the entire document, not just an excerpt."""
    )
    async def get_full_document(
        self,
        document_id: Annotated[str, "The document ID to retrieve"],
    ) -> str:
        try:
            client = get_search_client()
            if client is None:
                return json.dumps({"error": "Search client not configured"})

            doc = client.get_document(key=document_id)
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
                return self._mock_document_list()

            filters = []
            if department:
                filters.append(f"department eq '{department}'")
            if doc_type:
                filters.append(f"doc_type eq '{doc_type}'")

            results = client.search(
                search_text="*",
                top=limit,
                filter=" and ".join(filters) if filters else None,
                select=["id", "title", "department", "doc_type", "created_at"],
            )

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
            return json.dumps({"error": str(e), "documents": []})

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
        mock_results = [
            {
                "document_id": "doc_001",
                "title": "Ikeja Cluster RCA — Power Outage Q1 2026",
                "department": "Network Operations",
                "doc_type": "report",
                "excerpt": (
                    "Incident Reference: INC-2026-IKJ-0147. On 14 February 2026 at 02:14 WAT, "
                    "a utility power failure on the AES-owned feeder supplying the Ikeja base "
                    "station cluster caused a full outage across 6 sites (IKJ-001 to IKJ-006). "
                    "Tower 4471 is the anchor site. Duration: 4.2 hours (02:14–06:23 WAT). "
                    "IHS Nigeria tower lease reference: IHS/MTN/IKJ/2024-001. "
                    "Enterprise customer SLA exposure: NGN 2.1M."
                ),
                "section_heading": "1. INCIDENT SUMMARY",
                "page_number": 1,
                "relevance_score": 0.96,
            },
            {
                "document_id": "doc_002",
                "title": "TowerCo Tower Lease Agreement — IHS Nigeria",
                "department": "Procurement",
                "doc_type": "contract",
                "excerpt": (
                    "Contract Reference: IHS/MTN/IKJ/2024-001. Parties: IHS Nigeria Limited "
                    "and MTN Nigeria Communications Plc. Commencement Date: 1 July 2024. "
                    "Expiry Date: 30 June 2026. Monthly Lease Fee: NGN 28,000,000. "
                    "Uptime SLA: 99.5%. Penalty: 2% fee reduction per 0.1% below SLA threshold. "
                    "Renewal Notice: 90 days prior to expiry date."
                ),
                "section_heading": "3. CONTRACT TERMS AND CONDITIONS",
                "page_number": 3,
                "relevance_score": 0.93,
            },
            {
                "document_id": "doc_003",
                "title": "Customer Complaints — MoMo Deductions Q1 2026",
                "department": "Customer Experience",
                "doc_type": "complaint",
                "excerpt": (
                    "Report Period: January–March 2026. Total complaints received: 2,847. "
                    "Total disputed transaction value: NGN 45,000,000. "
                    "Top complaint category: Unauthorised MoMo wallet deductions (61%). "
                    "Overall resolution rate: 73% (NGN 32.8M refunded). "
                    "Highest volume region: Lagos (1,143 complaints, 40.1% of total). "
                    "Root cause: transaction retry duplicates during network reconnection."
                ),
                "section_heading": "2. COMPLAINT ANALYSIS SUMMARY",
                "page_number": 2,
                "relevance_score": 0.91,
            },
            {
                "document_id": "doc_004",
                "title": "NCC QoS Quarterly Return — Q4 2025",
                "department": "Legal/Regulatory",
                "doc_type": "policy",
                "excerpt": (
                    "Submission Reference: MTN-NCC-QOS-Q4-2025. Reporting Period: "
                    "October–December 2025. Network Availability: 99.1% (benchmark: 99.0% — COMPLIANT). "
                    "Call Setup Success Rate: 97.3% (benchmark: 95.0% — COMPLIANT). "
                    "Section 7.3: Data records supporting this return must be retained for a "
                    "minimum of 7 (seven) years from the submission date, per NCC Regulation 2023."
                ),
                "section_heading": "7. DATA RETENTION AND COMPLIANCE",
                "page_number": 8,
                "relevance_score": 0.89,
            },
            {
                "document_id": "doc_005",
                "title": "MTN Nigeria NDPA Article 24 Processing Record",
                "department": "Legal/Regulatory",
                "doc_type": "policy",
                "excerpt": (
                    "Document Reference: MTN-NDPA-ART24-2026-001. Prepared by: Data Protection Office. "
                    "Processing Purpose: Subscriber billing, service delivery, fraud prevention. "
                    "Data Categories: Identity, financial, location, usage. "
                    "Retention Period: 5 years (under review — NCC 7-year requirement pending). "
                    "Cross-border transfers: South Africa (MTN Group), AWS Ireland. "
                    "Safeguards: Standard Contractual Clauses — DPO sign-off PENDING. "
                    "DPO Contact: dpo@mtn.com.ng."
                ),
                "section_heading": "4. CROSS-BORDER DATA TRANSFERS",
                "page_number": 5,
                "relevance_score": 0.87,
            },
            {
                "document_id": "doc_006",
                "title": "Ericsson RAN Maintenance SLA — 2026",
                "department": "Procurement",
                "doc_type": "contract",
                "excerpt": (
                    "Contract Reference: ERIC/MTN/RAN/2026-001. Vendor: Ericsson Nigeria Limited. "
                    "Scope: Corrective and preventive maintenance for 847 base stations nationwide. "
                    "Monthly Fee: NGN 15,000,000. Response SLA: 4 hours for critical faults. "
                    "Parts Availability: 95% of critical spares held in Lagos depot. "
                    "Contract Expiry: 31 December 2026."
                ),
                "section_heading": "2. SCOPE OF SERVICES",
                "page_number": 2,
                "relevance_score": 0.92,
            },
            {
                "document_id": "doc_007",
                "title": "Kano-Kaduna Fibre Route BoQ",
                "department": "Network Operations",
                "doc_type": "report",
                "excerpt": (
                    "Project Reference: MTN-FIBRE-KNO-KAD-2025-007. Route: Kano to Kaduna. "
                    "Total Route Length: 287 km. POP Sites: 12. "
                    "Total Project Value: NGN 4,200,000,000. "
                    "Main Contractor: Julius Berger Nigeria Plc. "
                    "Target Completion: Q3 2026 (30 September 2026). "
                    "Current Status: Civil works 33% complete; RoW clearances pending (3 sections)."
                ),
                "section_heading": "1. PROJECT OVERVIEW",
                "page_number": 1,
                "relevance_score": 0.85,
            },
            {
                "document_id": "doc_008",
                "title": "Enterprise Customer SLA Register — EBU",
                "department": "Enterprise Business",
                "doc_type": "contract",
                "excerpt": (
                    "Document Reference: MTN-EBU-SLA-REG-2026. Total Enterprise Customers: 47. "
                    "Total Annual Contract Value: NGN 890,000,000. "
                    "Tier 1 Uptime SLA: 99.9%. SLA Credit Formula: 10% of monthly contract "
                    "value per hour of downtime below contracted uptime. "
                    "Top Customers: Zenith Bank (NGN 95M/yr), GTBank (NGN 82M/yr), "
                    "NNPC (NGN 78M/yr), Dangote Group (NGN 65M/yr)."
                ),
                "section_heading": "3. SLA TERMS AND CREDIT SCHEDULE",
                "page_number": 4,
                "relevance_score": 0.94,
            },
        ]
        return json.dumps({
            "results": mock_results,
            "total_found": len(mock_results),
            "retrieval_confidence": 0.91,
            "source": "mock",
        })

    def _mock_document_list(self) -> str:
        docs = [
            {"id": "doc_001", "title": "Ikeja Cluster RCA — Power Outage Q1 2026", "department": "Network Operations", "type": "report"},
            {"id": "doc_002", "title": "TowerCo Tower Lease Agreement — IHS Nigeria", "department": "Procurement", "type": "contract"},
            {"id": "doc_003", "title": "Customer Complaints — MoMo Deductions Q1 2026", "department": "Customer Experience", "type": "complaint"},
            {"id": "doc_004", "title": "NCC QoS Quarterly Return — Q4 2025", "department": "Legal/Regulatory", "type": "policy"},
            {"id": "doc_005", "title": "MTN Nigeria NDPA Article 24 Processing Record", "department": "Legal/Regulatory", "type": "policy"},
            {"id": "doc_006", "title": "Ericsson RAN Maintenance SLA — 2026", "department": "Procurement", "type": "contract"},
            {"id": "doc_007", "title": "Kano-Kaduna Fibre Route BoQ", "department": "Network Operations", "type": "report"},
            {"id": "doc_008", "title": "Enterprise Customer SLA Register — EBU", "department": "Enterprise Business", "type": "contract"},
        ]
        return json.dumps({"documents": docs, "total": len(docs)})
