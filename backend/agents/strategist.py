"""
Routes conversation and orchestrates permission-checked retrieval,
structured drafting, evidence auditing and rendering for every factual chat.
"""
import asyncio
import json
import logging
import time
from typing import Optional, Annotated, List, Dict, AsyncGenerator
from datetime import datetime, timedelta
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)

try:
    from agents.kernel import llm_complete, llm_complete_stream
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    async def llm_complete(prompt, **kw): return ""
    async def llm_complete_stream(prompt, **kw):
        yield ""


try:
    from services.agent_capabilities import capability_guard, AgentCapability
    _CAPS_AVAILABLE = True
except ImportError:
    _CAPS_AVAILABLE = False
    import logging as _log
    _log.getLogger(__name__).warning("[StrategistAgent] agent_capabilities not available")


class StrategistAgent:
    def __init__(self, kernel: Optional[Kernel] = None):
        self.kernel = kernel
        self.trace: list = []
        self.conversation_history: List[Dict] = []
        self._conversation_context: dict = {}
        self.first_name = ""
        # Compliance-graph step for relationship questions (injectable for tests).
        self.graph_step = None
        self.graph_timeout = 1.5  # seconds; past this the answer uses documents only
        self._graph_pending = 0

    def set_history(self, history: List[Dict]):
        self.conversation_history = history[-12:]

    def set_viewer(self, full_name):
        # Account identity only; never infer a name from another project's prompt.
        import re
        first = full_name.strip().split()[0] if isinstance(full_name, str) and full_name.strip() else ""
        self.first_name = first if re.fullmatch(r"[^\W\d_][\w'-]{0,39}", first) else ""

    def _log_trace(self, agent: str, tool: str, description: str, **metadata):
        self.trace.append({"agent": agent, "tool": tool, "description": description, "timestamp": datetime.utcnow().isoformat(), **metadata})
        logger.info(f"[{agent}] {tool}: {description}")

    # -- Main entry point --------------------------------------------------

    @kernel_function(description="Investigate any question with real agent orchestration.")
    async def investigate(self, question: Annotated[str, "The question"], depth: Annotated[str, "quick|standard|thorough"] = "standard") -> str:
        # GAP 4 FIX — capability guard
        if _CAPS_AVAILABLE:
            try:
                capability_guard.require("StrategistAgent", AgentCapability.FETCH_MARKET_INTEL)
            except PermissionError as e:
                logger.warning("[StrategistAgent] Capability check failed: %s", e)

        start = time.time()
        self.trace = []
        is_pidgin = self._detect_pidgin(question)

        try:
            self._log_trace("Strategist", "classify", "Analysing user intent")
            classification = await self._llm_classify(question, is_pidgin)
            intent = classification.get("intent", "document_query")
            topic = classification.get("topic", "")
            resolved_question = classification.get("query") or question
            self._conversation_context = classification.get("conversation_context") or {}
            self._log_trace("Strategist", "intent", f"Intent: {intent} | Topic: {topic}", intent=intent)
            factual = intent not in {"greeting", "social", "conversation_recall", "integrity_boundary", "out_of_domain", "clarification", "catalog", "compliance_records"} and not classification.get("clarification")
            if factual:
                self._log_trace("Strategist", "conversation_context",
                    "Connected the question to the conversation" if resolved_question != question else "Identified the question to investigate",
                    resolved_question=resolved_question)

            if intent == "greeting":
                from services.chat_intent import conversational_reply
                self._log_trace("Strategist", "conversation", "Responding to a conversational message")
                result = conversational_reply(classification.get("conversational_kind") or "acknowledgement", is_pidgin,
                    question=question, first_name=self.first_name)
                result["answer_status"] = "conversational"
            elif intent == "conversation_recall":
                from services.chat_conversation import recall_answer
                result = recall_answer(question, self.conversation_history)
            elif intent == "integrity_boundary":
                from services.chat_conversation import integrity_reply
                result = integrity_reply(question)
            elif intent == "social":
                from services.chat_conversation import social_answer
                result = await social_answer(question, self.conversation_history, llm_complete)
                if result is None:
                    factual = True
                    intent = "document_query"
                    result = await self._orchestrate_agents(question, is_pidgin, depth)
                else:
                    result["answer_status"] = "conversational"
            elif intent == "clarification" or classification.get("clarification"):
                result = {"answer": classification.get("clarification") or "Which question or document would you like me to look at?",
                          "citations": [], "confidence": "low", "_grounded": True, "answer_status": "needs_clarification"}
            elif intent == "catalog":
                # Listed straight from the permitted library: no model, nothing to invent.
                from services.document_catalog import catalog_answer
                from services.grounded_answers import gap
                self._log_trace("Researcher", "catalog", "Listing the documents you can access")
                try:
                    result = await asyncio.to_thread(catalog_answer, classification.get("catalog_topic"))
                except Exception as exc:
                    logger.warning("Document catalog unavailable (%s)", type(exc).__name__)
                    result = gap("access_check_failed")
            elif intent == "compliance_records":
                # The organisation's own records, read straight from the compliance graph: no model.
                from services.compliance_graph.chat import records_answer
                from services.grounded_answers import gap
                self._log_trace("Researcher", "compliance_records", "Reading your organisation's compliance records")
                try:
                    result = await asyncio.to_thread(records_answer, classification.get("records_kinds") or [], question)
                except Exception as exc:
                    logger.warning("Compliance records unavailable (%s)", type(exc).__name__)
                    result = gap("access_check_failed")
            elif intent == "out_of_domain":
                result = {"answer": "I can help you understand regulations, review your organisation's documents, and work through compliance questions. What would you like to check?",
                          "citations": [], "confidence": "low", "_grounded": True, "answer_status": "out_of_scope"}
            else:
                # Every factual intent shares the same permissions and claim audit.
                # Legacy operational tables are unscoped and cannot be chat evidence.
                result = await self._orchestrate_agents(resolved_question, is_pidgin, depth)

            duration_ms = int((time.time() - start) * 1000)
            if "citations" in result:
                result["citations"] = self._dedupe_citations(result["citations"])

            # Displaying an answer does not establish an institution's compliance.
            # No heuristic verdict or second prose model may rewrite audited findings.
            result["verdict"] = "MONITOR"

            opening = next((t.get("conversation_start") for t in self.conversation_history if t.get("conversation_start")), None)
            opening = opening or (self.conversation_history[0]["question"] if self.conversation_history else question)
            research_activity = {"document_search": any(t.get("tool") == "search" for t in self.trace),
                                 "official_research": any(t.get("tool") == "official_research" for t in self.trace),
                                 "source_checks": result.get("source_checks", [])[:12]}
            if factual:
                self._log_trace("Strategist", "research_activity", "Saved the source-check activity for conversation follow-ups", **research_activity)
            self.conversation_history.append({"question": question, "resolved_question": resolved_question if factual else None,
                "intent": intent, "topic": topic, "answer_summary": result.get("answer", "")[:1200],
                "citations": result.get("citations", []), "research_activity": research_activity if factual else {}, "timestamp": datetime.utcnow().isoformat()})
            self.conversation_history = self.conversation_history[-12:]
            self.conversation_history[0]["conversation_start"] = opening

            self._log_trace("Strategist", "answer_outcome", "Completed the response",
                answer_status=result.get("answer_status", "answered"),
                gap_reason=result.get("gap_reason") or result.get("_gap_reason"),
                suggested_followups=result.get("suggested_followups", [])[:3])

            return json.dumps({"question": question, "answer": result["answer"], "knowledge_gap": bool(result.get("knowledge_gap", False)), "confidence": result.get("confidence", "medium"), "verdict": "MONITOR", "is_pidgin": is_pidgin, "agent_trace": self.trace, "citations": result.get("citations", []), "partial_answer": result.get("partial_answer", False), "missing_information": result.get("missing_information", []), "source_checks": result.get("source_checks", []), "research_checked_at": result.get("research_checked_at"), "suggested_actions": result.get("suggested_actions", []), "suggested_followups": result.get("suggested_followups", []), "duration_ms": duration_ms, "agents_used": list(dict.fromkeys(t["agent"] for t in self.trace)), "intent": intent, "topic": topic, "answer_status": result.get("answer_status", "answered"), "gap_reason": result.get("gap_reason") or result.get("_gap_reason")})

        except Exception as e:
            logger.error(f"Strategist failed: {e}", exc_info=True)
            return json.dumps({"question": question, "answer": "The chat service could not complete this request. Please try again.", "is_pidgin": is_pidgin, "agent_trace": self.trace, "error": "request_failed"})

    # -- Streaming entry point ---------------------------------------------

    async def investigate_stream(self, question: str, depth: str = "standard") -> AsyncGenerator[dict, None]:
        """Progress starts immediately; only validated final answers become tokens."""
        yield {"type": "start", "message": "Iroko AI is understanding your message...", "timestamp": datetime.utcnow().isoformat()}
        self.trace = []
        work = asyncio.create_task(asyncio.wait_for(self.investigate(question, depth), timeout=120))
        emitted = 0
        try:
            while not work.done():
                await asyncio.wait({work}, timeout=0.25)
                while emitted < len(self.trace):
                    yield {"type": "agent_action", **self.trace[emitted]}
                    emitted += 1
            result = json.loads(await work)
        finally:
            if not work.done():
                work.cancel()
            await asyncio.gather(work, return_exceptions=True)
        while emitted < len(self.trace):
            yield {"type": "agent_action", **self.trace[emitted]}
            emitted += 1
        if result.get("error"):
            yield {"type": "error", "message": "The AI model could not complete this request. Please try again. If this continues, contact support."}
            return
        answer = result.get("answer", "")
        for offset in range(0, len(answer), 100):
            yield {"type": "token", "content": answer[offset:offset + 100]}
        yield {"type": "complete", **result, "map_data": [], "fraud_data": None}

    # -- Real agent orchestration ------------------------------------------

    async def _orchestrate_agents(self, question: str, is_pidgin: bool, depth: str) -> dict:
        from services.grounded_answers import answer
        from services.regulatory_research import eligible, finish, freshness_requested, needs_internal_records, research
        public_research = eligible(question)
        fresh_public = public_research and freshness_requested(question) and not needs_internal_records(question)
        report = None
        if fresh_public:
            self._log_trace("Researcher", "official_research", "Checking bounded official regulatory sources; customer documents are not sent to external search services")
            report = await research(question)
        # Avoid waiting/paying for an embedding/index lookup whose results would
        # be discarded. Private status/filing queries still retrieve permitted records.
        context = {"sources": [], "knowledge_gap": True} if report and report["sources"] else await self._retrieve_context(question, depth)
        context = await self._graph_context(question, context)
        self._log_trace("Watchdog", "claim_validation", "Checking exact quotes, citation coordinates and claim support before display")
        result = None
        if not (public_research and freshness_requested(question)):
            result = await answer(question, context, llm_complete, is_pidgin,
                                  answer_mode="helpful", conversation_context=self._conversation_context)
        researchable_gap = result and result.get("partial_answer") and set(result.get("missing_information", [])) & {
            "penalty", "current_applicability", "other_requested_fact"
        }
        if public_research and (result is None or result.get("knowledge_gap") or researchable_gap):
            if report is None:
                self._log_trace("Researcher", "official_research", "Checking bounded official regulatory sources; customer documents are not sent to external search services")
                report = await research(question)
            # Freshness requests should not be dominated by the older local corpus.
            internal = [] if fresh_public and report["sources"] else context.get("sources", [])[:6]
            combined = [*report["sources"], *internal]
            self._log_trace("Watchdog", "research_validation", "Separately auditing supported findings and missing facts; never estimating an unsupported penalty")
            earlier_findings = result if result and not result.get("knowledge_gap") else None
            result = await answer(question, {**context, "sources": combined, "knowledge_gap": not combined,
                                  "retrieval_status": "ok" if combined else context.get("retrieval_status", "empty")}, llm_complete, is_pidgin,
                                  allow_partial=True, answer_mode="helpful", conversation_context=self._conversation_context)
            if result.get("knowledge_gap") and earlier_findings:
                # A failed extra research/audit pass cannot erase already audited
                # findings from the permitted local evidence.
                result = earlier_findings
                self._log_trace("Watchdog", "research_gap", "Kept verified document findings; additional research did not establish further facts")
            result = finish(result, report, question, helpful=True)
        if report:
            discovery = [c for c in report.get("discovery_checks", []) if c.get("status") != "disabled"]
            if discovery:
                checked = sum(c.get("status") == "checked" for c in discovery)
                self._log_trace("Researcher", "web_search",
                    f"Bright Data public-topic discovery: {checked}/{len(discovery)} searches succeeded. "
                    "Only fetched official pages can support the answer; search snippets are not evidence.")
        message = ("Reported an evidence/validation gap without a compliance conclusion" if result.get("knowledge_gap")
                   else "Rendered approved partial findings with the remaining gaps" if result.get("partial_answer")
                   else "Rendered verified claims without executive rewriting")
        self._log_trace("Scribe", "format", message)
        if self._graph_pending and not result.get("knowledge_gap") and result.get("answer"):
            # Suggestions are never evidence; they are only counted, deterministically.
            from services.compliance_graph.chat import pending_note
            result["answer"] = result["answer"] + pending_note(self._graph_pending)
        return result

    async def _graph_context(self, question: str, context: dict) -> dict:
        """Relationship questions also follow confirmed compliance-graph links (bounded, database-only)."""
        from services.compliance_graph import chat as graph_chat
        self._graph_pending = 0
        # Checked before any database access: the flag and the question's wording.
        if not context.get("sources") or not graph_chat.wanted(question):
            return context
        step = self.graph_step or graph_chat.expand_context
        try:
            expanded = await asyncio.wait_for(asyncio.to_thread(step, question, context), timeout=self.graph_timeout)
        except Exception as exc:
            logger.warning("Compliance graph step skipped (%s)", type(exc).__name__)
            self._log_trace("Researcher", "graph", "The compliance graph was unavailable; answered from documents only")
            return context
        info = expanded.get("graph") or {}
        self._graph_pending = int(info.get("pending") or 0)
        if info.get("passages") or info.get("records"):
            self._log_trace("Researcher", "graph",
                            f"Followed confirmed links in your compliance graph: {info.get('passages', 0)} passage(s), "
                            f"{info.get('records', 0)} record(s)", graph=info)
        return expanded

    async def _retrieve_context(self, question: str, depth: str) -> dict:
        from services.grounded_answers import retrieve
        self._log_trace("Researcher", "search", "Retrieving accessible extracted source passages")
        return await retrieve(question)

    async def _llm_classify(self, question: str, is_pidgin: bool) -> dict:
        from services.chat_router import route_question
        return await route_question(question, self.conversation_history, llm_complete)

    def _heuristic_classify(self, question: str) -> dict:
        from services.chat_router import heuristic_route
        return heuristic_route(question, self.conversation_history)

    def _extract_entities(self, question: str) -> dict:
        """Extract structured entities (region, cluster, vendor, etc.) from a question."""
        q = question.lower()
        entities = {}

        # Regions
        regions = ["lagos", "abuja", "port harcourt", "kano", "kaduna", "enugu",
                   "ibadan", "benin", "jos", "calabar", "warri", "owerri"]
        for r in regions:
            if r in q:
                entities["region"] = r.title()
                break

        # Clusters (known)
        clusters = ["ikeja", "victoria island", "lekki", "ikoyi", "surulere",
                    "yaba", "apapa", "festac", "ajah", "oshodi"]
        for c in clusters:
            if c in q:
                entities["cluster"] = c.title()
                break

        # Vendors
        vendors = {"interswitch": "Interswitch Nigeria", "flutterwave": "Flutterwave",
                   "crc": "CRC Credit Bureau", "nibss": "NIBSS", "verve": "Verve"}
        for key, name in vendors.items():
            if key in q:
                entities["vendor"] = name
                break

        # Ref codes (e.g. CBN-AML-001, MFB-2026-001)
        import re
        site_match = re.search(r'\b([A-Z]{2,4}[-_]\d{2,4})\b', question, re.IGNORECASE)
        if site_match:
            entities["site_code"] = site_match.group(1).upper()

        # Time ranges
        if any(p in q for p in ["today", "24 hour", "last day"]):
            entities["days"] = 1
        elif any(p in q for p in ["this week", "7 day", "last week"]):
            entities["days"] = 7
        elif any(p in q for p in ["this month", "30 day", "last month"]):
            entities["days"] = 30
        elif any(p in q for p in ["this quarter", "90 day", "q1", "q2", "q3", "q4"]):
            entities["days"] = 90

        return entities


    # -- Utilities ---------------------------------------------------------

    def _detect_pidgin(self, text: str) -> bool:
        return any(m in text.lower() for m in ["wetin","dey","abeg","oga","wahala","sabi","how body","how far","kampe"])

    def _dedupe_citations(self, citations: List[dict]) -> List[dict]:
        seen, out = set(), []
        for c in citations:
            if not isinstance(c, dict):
                continue
            d = c.get("chunk_id") or c.get("document_id")
            if d and d not in seen:
                seen.add(d)
                out.append(c)
        return out

    def _match_canned_scenario(self, question: str) -> Optional[dict]:
        """Compatibility only: canned demo answers have been removed."""
        return None


    # Compatibility entry points all use the same authorised evidence path.
    async def _orchestrate_network_ops(self, question: str, is_pidgin: bool, depth: str) -> dict:
        return await self._orchestrate_agents(question, is_pidgin, depth)

    async def _orchestrate_fraud(self, question: str, is_pidgin: bool) -> dict:
        return await self._orchestrate_agents(question, is_pidgin, "standard")

    async def _orchestrate_regulatory(self, question: str, is_pidgin: bool) -> dict:
        return await self._orchestrate_agents(question, is_pidgin, "standard")

    async def _orchestrate_cx(self, question: str, is_pidgin: bool) -> dict:
        return await self._orchestrate_agents(question, is_pidgin, "standard")

    # -- Morning Briefing --------------------------------------------------

    @kernel_function(description="Generate a dynamic morning briefing from live operational data.")
    async def morning_briefing(self, user_department: Annotated[str, "Department"] = "General") -> str:
        self._log_trace("Strategist", "briefing", "Compiling live operations briefing")
        urgent = []
        deadlines = []
        key_metrics = []
        unavailable = False

        try:
            from models.database import SessionLocal
            from services.network_ops import get_operations_briefing
            db = SessionLocal()
            try:
                ops = get_operations_briefing(db)
            finally:
                db.close()

            ns = ops.get("network_status", {})
            if ns.get("down", 0) > 0 or ns.get("degraded", 0) > 0:
                urgent.append(f"{ns.get('down',0)} site(s) DOWN, {ns.get('degraded',0)} DEGRADED of {ns.get('total',0)} total")

            for inc in ops.get("active_incidents", [])[:3]:
                urgent.append(f"[{inc['severity'].upper()}] {inc['title']} — {inc.get('region','unknown')}")

            for c in ops.get("expiring_contracts", [])[:3]:
                deadlines.append(f"{c['vendor_name']} contract expires {c.get('expiry_date','TBD')} ({c.get('days_to_expiry',0)} days)")

            kpi = ops.get("kpi_summary", {}).get("latest", {})
            if kpi:
                avail = kpi.get("availability_pct", 0)
                avail_target = kpi.get("availability_target", 99.5)
                key_metrics.append(f"Network availability: {avail}% ({'✓' if avail >= avail_target else '✗'} target {avail_target}%)")
                csr = kpi.get("call_setup_success_pct")
                if csr:
                    key_metrics.append(f"Call setup success: {csr}%")

            cx = ops.get("complaint_summary", {})
            if cx:
                key_metrics.append(f"Open complaints (7d): {cx.get('open', 0)} | Resolution rate: {cx.get('resolution_rate_pct', 0)}%")

            sla = ops.get("sla_exposure", {})
            if sla.get("total_exposure_ngn", 0) > 0:
                urgent.append(f"SLA financial exposure: NGN {sla['total_exposure_ngn']:,.0f} across {sla['incident_count']} incident(s)")

        except Exception as e:
            logger.warning(f"Live briefing data failed: {e}")
            unavailable = True

        return json.dumps({
            "generated_at": datetime.utcnow().isoformat(),
            "department": user_department,
            "knowledge_gap": unavailable,
            "sections": [
                {"title": "Urgent Attention Required", "items": urgent or ["No verified issues available" if unavailable else "No critical issues found in available operational records"]},
                {"title": "Deadlines & Renewals", "items": deadlines or ["Deadline data unavailable" if unavailable else "No expiring contracts found in available records"]},
                {"title": "Key Metrics", "items": key_metrics},
            ],
            "agent_trace": self.trace,
        })
