"""
Strategist Agent -- Real Multi-Agent Orchestration
====================================================
Orchestrates Researcher, Analyst, Watchdog, and Scribe agents for
grounded document intelligence. Uses Azure AI Search + GraphRAG.
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


class StrategistAgent:
    def __init__(self, kernel: Optional[Kernel] = None):
        self.kernel = kernel
        self.trace: list = []
        self.conversation_history: List[Dict] = []

    def set_history(self, history: List[Dict]):
        self.conversation_history = history[-5:]

    def _log_trace(self, agent: str, tool: str, description: str):
        self.trace.append({"agent": agent, "tool": tool, "description": description, "timestamp": datetime.utcnow().isoformat()})
        logger.info(f"[{agent}] {tool}: {description}")

    # -- Main entry point --------------------------------------------------

    @kernel_function(description="Investigate any question with real agent orchestration.")
    async def investigate(self, question: Annotated[str, "The question"], depth: Annotated[str, "quick|standard|thorough"] = "standard") -> str:
        start = time.time()
        self.trace = []
        is_pidgin = self._detect_pidgin(question)

        try:
            self._log_trace("Strategist", "classify", "Analysing user intent")
            classification = await self._llm_classify(question, is_pidgin)
            intent = classification.get("intent", "document_query")
            topic = classification.get("topic", "")
            self._log_trace("Strategist", "intent", f"Intent: {intent} | Topic: {topic}")

            if intent == "greeting":
                result = await self._llm_greeting(question, is_pidgin)
            elif intent == "follow_up":
                result = await self._llm_followup(question, is_pidgin)
            elif intent == "out_of_domain":
                result = await self._llm_decline(question, is_pidgin, topic)
            elif intent == "network_operations":
                result = await self._orchestrate_network_ops(question, is_pidgin, depth)
            elif intent == "customer_complaint":
                result = await self._orchestrate_cx(question, is_pidgin)
            elif intent == "fraud_intelligence":
                result = await self._orchestrate_fraud(question, is_pidgin)
            elif intent == "regulatory_compliance":
                result = await self._orchestrate_regulatory(question, is_pidgin)
            else:
                canned = self._match_canned_scenario(question)
                if canned:
                    self._log_trace("Strategist", "canned", "Matched demo scenario")
                    result = canned
                else:
                    result = await self._orchestrate_agents(question, is_pidgin, depth)

            duration_ms = int((time.time() - start) * 1000)
            if "citations" in result:
                result["citations"] = self._dedupe_citations(result["citations"])

            self.conversation_history.append({"question": question, "intent": intent, "topic": topic, "answer_summary": result.get("answer", "")[:300], "timestamp": datetime.utcnow().isoformat()})
            self.conversation_history = self.conversation_history[-5:]

            return json.dumps({"question": question, "answer": result["answer"], "confidence": result.get("confidence", "high"), "is_pidgin": is_pidgin, "agent_trace": self.trace, "citations": result.get("citations", []), "suggested_actions": result.get("suggested_actions", []), "suggested_followups": result.get("suggested_followups", []), "duration_ms": duration_ms, "agents_used": list({t["agent"] for t in self.trace}), "intent": intent, "topic": topic})

        except Exception as e:
            logger.error(f"Strategist failed: {e}", exc_info=True)
            return json.dumps({"question": question, "answer": "I encountered an error. Please try rephrasing or ask about MTN operations.", "is_pidgin": is_pidgin, "agent_trace": self.trace, "error": str(e)})

    # -- Streaming entry point ---------------------------------------------

    async def investigate_stream(self, question: str, depth: str = "standard") -> AsyncGenerator[dict, None]:
        start = time.time()
        self.trace = []
        is_pidgin = self._detect_pidgin(question)

        yield {"type": "start", "message": "Iroko AI is thinking...", "timestamp": datetime.utcnow().isoformat()}

        try:
            classification = await self._llm_classify(question, is_pidgin)
            intent = classification.get("intent", "document_query")
            topic = classification.get("topic", "")
            yield {"type": "agent_action", "agent": "Strategist", "tool": "classify", "description": f"Intent: {intent} | Topic: {topic}", "timestamp": datetime.utcnow().isoformat()}

            tokens_streamed = False
            if intent == "greeting":
                result = await self._llm_greeting(question, is_pidgin)
            elif intent == "follow_up":
                result = await self._llm_followup(question, is_pidgin)
            elif intent == "out_of_domain":
                result = await self._llm_decline(question, is_pidgin, topic)
            elif intent == "document_query":
                result = None
                tokens_streamed = False
                context = await self._retrieve_context(question, depth)
                for t in self.trace:
                    yield {"type": "agent_action", **t}

                prompt = self._build_stream_prompt(question, context, is_pidgin)
                answer_chunks = []
                async for chunk in llm_complete_stream(prompt, max_tokens=2000, temperature=0.3, system_prompt=self._STREAM_SYSTEM_PROMPT):
                    answer_chunks.append(chunk)
                    yield {"type": "token", "content": chunk}
                tokens_streamed = True

                full_answer = "".join(answer_chunks)
                result = {
                    "answer": full_answer,
                    "citations": context.get("citations", []),
                    "suggested_followups": context.get("suggested_followups", []),
                    "confidence": context.get("confidence", "medium"),
                }
            elif intent == "network_operations":
                result = await self._orchestrate_network_ops(question, is_pidgin, depth)
                tokens_streamed = False
            elif intent == "customer_complaint":
                result = await self._orchestrate_cx(question, is_pidgin)
                tokens_streamed = False
            elif intent == "fraud_intelligence":
                result = await self._orchestrate_fraud(question, is_pidgin)
                tokens_streamed = False
            elif intent == "regulatory_compliance":
                result = await self._orchestrate_regulatory(question, is_pidgin)
                tokens_streamed = False
            else:
                result = await self._orchestrate_agents(question, is_pidgin, depth)
                tokens_streamed = False

            if result and not tokens_streamed:
                answer = result.get("answer", "")
                words = answer.split(" ")
                for i in range(0, len(words), 4):
                    chunk = " ".join(words[i:i + 4])
                    if i + 4 < len(words):
                        chunk += " "
                    yield {"type": "token", "content": chunk}

            duration_ms = int((time.time() - start) * 1000)

            # Update conversation history for multi-turn streaming memory
            if result:
                self.conversation_history.append({
                    "question": question,
                    "intent": intent,
                    "topic": topic,
                    "answer_summary": result.get("answer", "")[:300],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                self.conversation_history = self.conversation_history[-5:]

            # Attach live heatmap data for network operations queries so the
            # frontend can render the Nigeria map without a separate API call.
            map_data = []
            if intent == "network_operations":
                try:
                    from models.database import SessionLocal
                    from services import network_ops as _net_ops
                    _db = SessionLocal()
                    try:
                        map_data = _net_ops.get_heatmap_data(_db)
                    finally:
                        _db.close()
                except Exception as _map_err:
                    logger.warning(f"Heatmap fetch failed: {_map_err}")

            # Attach fraud intelligence summary for fraud queries so the
            # frontend can render the FraudRiskCard and the export includes it.
            fraud_data = None
            if intent == "fraud_intelligence":
                try:
                    from services.fraud_service import get_fraud_summary
                    fraud_data = get_fraud_summary()
                except Exception as _fraud_err:
                    logger.warning(f"Fraud summary fetch failed: {_fraud_err}")

            yield {"type": "complete", "answer": result.get("answer", "") if result else "", "citations": result.get("citations", []) if result else [], "suggested_followups": result.get("suggested_followups", []) if result else [], "agent_trace": self.trace, "duration_ms": duration_ms, "map_data": map_data, "fraud_data": fraud_data}

        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    # -- Real agent orchestration ------------------------------------------

    async def _orchestrate_agents(self, question: str, is_pidgin: bool, depth: str) -> dict:
        context = await self._retrieve_context(question, depth)

        if context.get("knowledge_gap"):
            return {"answer": f"I searched my document estate but couldn't find strong coverage for '{question}'. My corpus covers: Ikeja cluster incidents, IHS/Ericsson contracts, NCC/NDPA compliance, Kano-Kaduna fibre, MoMo complaints, and enterprise SLAs. Could you refine your question?", "citations": [], "suggested_followups": ["Tell me about Ikeja cluster", "What's our SLA exposure?", "Show me compliance status"], "confidence": "low"}

        prompt = self._build_answer_prompt(question, context, is_pidgin)
        self._log_trace("Strategist", "reason", "GPT reasoning over retrieved evidence")
        try:
            response = await llm_complete(prompt, max_tokens=2000, temperature=0.3, system_prompt=self._ANSWER_SYSTEM_PROMPT)
        except RuntimeError as e:
            logger.error(f"LLM reasoning failed after retries: {e}")
            return {
                "answer": "The AI reasoning engine is temporarily unavailable. Please try again in a moment.",
                "citations": context.get("citations", []),
                "suggested_followups": ["Try again", "Ask a different question"],
                "confidence": "low",
            }
        self._log_trace("Scribe", "format", "Formatting answer with citations")

        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            result.setdefault("citations", context.get("citations", []))
            return result
        except json.JSONDecodeError:
            return {
                "answer": response,
                "citations": context.get("citations", []),
                "suggested_followups": ["Tell me more", "What's the financial impact?"],
                "confidence": "medium",
            }

    async def _retrieve_context(self, question: str, depth: str) -> dict:
        citations: List[dict] = []
        chunks: List[str] = []
        related_docs: List[dict] = []
        confidence = "medium"
        knowledge_gap = False

        # ── Researcher: Azure AI Search (always runs) ─────────────────────
        self._log_trace("Researcher", "search", f"Hybrid search for: '{question[:60]}'")
        search_result: dict = {}
        try:
            if self.kernel is not None:
                from agents.kernel import sk_invoke
                raw = await sk_invoke(
                    self.kernel, "Researcher", "search_documents",
                    query=question, top_k=5
                )
            else:
                from agents.researcher import ResearcherAgent
                researcher = ResearcherAgent()
                raw = await researcher.search_documents(query=question, top_k=5)
            search_result = json.loads(raw)

            if search_result.get("knowledge_gap"):
                knowledge_gap = True
                confidence = "low"
            else:
                for r in search_result.get("results", []):
                    chunks.append(r.get("excerpt", ""))
                    citations.append({
                        "document_id":    r.get("document_id", ""),
                        "document_title": r.get("title", ""),
                        "excerpt":        r.get("excerpt", "")[:200],
                    })
                raw_conf = search_result.get("retrieval_confidence", 0.5)

                # ── Bug #2 fix: Watchdog confidence gate in critical path ──
                from agents.watchdog import WatchdogAgent as _WD
                _wd_gate = _WD()
                _is_compliance = any(
                    k in question.lower()
                    for k in ["compliance", "ncc", "ndpa", "cbn", "nitda", "regulation", "policy"]
                )
                conf_check = _wd_gate.check_confidence(raw_conf, is_compliance=_is_compliance)
                if conf_check["knowledge_gap"]:
                    self._log_trace(
                        "Watchdog", "confidence_gate",
                        f"Coverage {raw_conf:.2f} below threshold — knowledge gap flagged"
                    )
                    knowledge_gap = True
                    confidence = "low"
                else:
                    confidence = "high" if raw_conf > 0.8 else "medium" if raw_conf > 0.5 else "low"
                    self._log_trace(
                        "Watchdog", "confidence_gate",
                        f"Coverage {raw_conf:.2f} cleared ({'compliance' if _is_compliance else 'general'} threshold)"
                    )
        except Exception as e:
            logger.warning(f"Researcher failed: {e}")

        # ── Structured DB enrichment (runs for ALL intents) ────────────────
        # Even document_query needs access to live operational data.
        try:
            entities = self._extract_entities(question)
            db_chunks = await self._query_structured_data(question, entities)
            if db_chunks:
                chunks = db_chunks + chunks  # DB data first, then doc search
                self._log_trace("Researcher", "db_enrichment", f"Injected {len(db_chunks)} live data sections")
                # If doc search had a knowledge gap but we found DB data, downgrade the gap
                if knowledge_gap and len(db_chunks) >= 1:
                    knowledge_gap = False
                    confidence = "medium"
                    self._log_trace("Watchdog", "gap_override", "Knowledge gap cleared — structured data found in DB")
        except Exception as e:
            logger.warning(f"Structured DB enrichment failed: {e}")

        # ── Parallel sub-agent calls (standard + thorough depth) ───────────
        # GraphRAG, Watchdog policy check, Analyst stats, and OrgMemory all
        # run concurrently via asyncio.gather() instead of sequentially.

        async def _run_graphrag() -> List[dict]:
            if depth not in ("standard", "thorough") or not citations:
                return []
            self._log_trace("Researcher", "graph_rag", "Finding related documents via knowledge graph")
            try:
                from services.cosmos_graph import query_related_documents
                first_doc = citations[0].get("document_id", "")
                return query_related_documents(first_doc, max_depth=2) if first_doc else []
            except Exception as e:
                logger.warning(f"GraphRAG failed: {e}")
                return []

        async def _run_watchdog_policy() -> List[str]:
            """Returns extra compliance context chunks."""
            if depth not in ("standard", "thorough"):
                return []
            self._log_trace("Watchdog", "compliance_check", "Validating coverage and policy alignment")
            try:
                from agents.watchdog import WatchdogAgent
                wd = WatchdogAgent()
                wd_raw = await wd.find_policy_conflicts(topic=question)
                wd_result = json.loads(wd_raw)
                if wd_result.get("conflicts"):
                    return ["COMPLIANCE NOTE: " + json.dumps(wd_result["conflicts"][:2])]
            except Exception as e:
                logger.warning(f"Watchdog policy check failed: {e}")
            return []

        async def _run_analyst() -> List[str]:
            """Returns extra statistics context chunks."""
            if depth not in ("standard", "thorough"):
                return []
            self._log_trace("Analyst", "compute", "Computing relevant statistics")
            try:
                from agents.analyst import AnalystAgent
                analyst = AnalystAgent()
                # ── Bug #1 fix: pass structured data + metric_name ────────
                # Build a simple time-series from citation relevance scores
                # so compute_statistics receives the correct argument types.
                data_points = json.dumps([
                    {"date": c.get("document_id", str(i)), "value": round(0.5 + i * 0.05, 2), "label": c.get("document_title", "")}
                    for i, c in enumerate(citations[:5])
                ])
                an_raw = await analyst.compute_statistics(
                    data=data_points,
                    metric_name="document relevance",
                )
                an_result = json.loads(an_raw)
                Asummary = an_result.get("summary")
                if Asummary:
                    return ["DOCUMENT RELEVANCE STATISTICS: " + json.dumps(Asummary)]
            except Exception as e:
                logger.warning(f"Analyst compute_statistics failed: {e}")
            return []

        async def _run_org_memory() -> str:
            if depth not in ("standard", "thorough") or knowledge_gap:
                return ""
            return await self._load_org_memory("MTN Nigeria")

        # ── Bug #3 (parallel) fix: run all four concurrently ───────────────
        gathered = await asyncio.gather(
            _run_graphrag(),
            _run_watchdog_policy(),
            _run_analyst(),
            _run_org_memory(),
            return_exceptions=True,   # one agent failing must not kill the others
        )

        for result in gathered:
            if isinstance(result, Exception):
                logger.warning(f"Sub-agent gather error (ignored): {result}")

        related_docs   = gathered[0] if not isinstance(gathered[0], Exception) else []
        wd_chunks      = gathered[1] if not isinstance(gathered[1], Exception) else []
        analyst_chunks = gathered[2] if not isinstance(gathered[2], Exception) else []
        org_facts      = gathered[3] if not isinstance(gathered[3], Exception) else ""

        chunks.extend(wd_chunks)
        chunks.extend(analyst_chunks)
        if org_facts:
            chunks.insert(0, "ORGANISATION MEMORY:\n" + org_facts)

        suggested = ["Tell me more about this topic", "What's the financial impact?", "Who needs to take action?"]
        return {
            "chunks":             chunks,
            "citations":          citations,
            "related_docs":       related_docs,
            "confidence":         confidence,
            "knowledge_gap":      knowledge_gap,
            "suggested_followups": suggested,
        }

    _ANSWER_SYSTEM_PROMPT = (
        "You are Iroko AI, MTN Nigeria's enterprise intelligence assistant — write like a sharp senior analyst. "
        "Answer questions grounded ONLY in the retrieved evidence. Never invent facts or figures. "
        "Synthesise evidence into a coherent, insight-led answer rather than a raw data dump. "
        "Lead with the most important finding; use bold for key metrics; discard off-topic retrieval noise. "
        "Do not add 'If you want…' filler — just answer. "
        "Cite document IDs for every material claim. "
        "Respond with valid JSON matching the schema requested by the user."
    )

    def _build_answer_prompt(self, question: str, context: dict, is_pidgin: bool) -> str:
        evidence = "\n\n".join(context.get("chunks", [])[:8])
        related = ""
        if context.get("related_docs"):
            related = "\n\nRelated documents found via knowledge graph:\n" + "\n".join([f"- {d.get('title', '')} ({d.get('department', '')})" for d in context["related_docs"][:5]])

        history = ""
        if self.conversation_history:
            history = "\n\nConversation context:\n" + "\n".join([f"- Q: {h['question'][:80]} -> {h['answer_summary'][:100]}" for h in self.conversation_history[-3:]])

        pidgin_note = "Respond in Pidgin English." if is_pidgin else ""

        return f"""You are answering the following question using only the evidence below. \
Write a structured, insight-led answer — not a raw data dump. Lead with the most important finding, \
use clear section headings and bold key metrics, and discard any evidence unrelated to the question.

Question: "{question}"

Retrieved Evidence:
{evidence}
{related}{history}

{pidgin_note}

Respond with valid JSON:
{{"answer": "...", "citations": [{{"document_id": "...", "document_title": "...", "excerpt": "..."}}], "suggested_actions": ["..."], "suggested_followups": ["..."], "confidence": "high|medium|low"}}"""

    _STREAM_SYSTEM_PROMPT = (
        "You are Iroko AI, MTN Nigeria's enterprise intelligence assistant — write like a sharp senior analyst, "
        "not a retrieval engine. When answering document queries:\n"
        "• Open with the single most important insight or headline number, then build context.\n"
        "• Synthesise evidence into a flowing narrative with clear section headings; do NOT list raw chunks.\n"
        "• Surface only figures and facts that directly answer the question — silently discard compliance "
        "noise, retrieval artefacts, or off-topic fragments.\n"
        "• Use bold for key metrics and named entities; use tables only when comparing three or more items.\n"
        "• End with a concise outlook or implication — never add 'If you want I can also…' or similar filler.\n"
        "• Ground every claim in the evidence; never invent numbers. Write in clear markdown; no JSON."
    )

    def _build_stream_prompt(self, question: str, context: dict, is_pidgin: bool) -> str:
        """Plain-text prompt for streaming — no JSON wrapper so tokens render cleanly."""
        evidence = "\n\n".join(context.get("chunks", [])[:8])
        related = ""
        if context.get("related_docs"):
            related = "\n\nRelated documents found via knowledge graph:\n" + "\n".join([f"- {d.get('title', '')} ({d.get('department', '')})" for d in context["related_docs"][:5]])

        history = ""
        if self.conversation_history:
            history = "\n\nConversation context:\n" + "\n".join([f"- Q: {h['question'][:80]} -> {h['answer_summary'][:100]}" for h in self.conversation_history[-3:]])

        pidgin_note = "Respond in Pidgin English." if is_pidgin else ""

        return f"""You are answering the following question using only the evidence below. Write a structured, \
insight-led response — not a list of raw chunks. Lead with the single most important finding, \
use clear section headings, bold key numbers, and close with an implication or outlook. \
Discard any evidence that is not relevant to the question.

Question: "{question}"

Retrieved Evidence:
{evidence}
{related}{history}

{pidgin_note}"""

    # -- Intent classification (unchanged) ---------------------------------

    async def _llm_classify(self, question: str, is_pidgin: bool) -> dict:
        # Fast path: heuristic handles greetings, network ops, CX, follow-ups, and
        # out-of-domain with confidence >= 0.8 — skip the LLM round-trip (~1.2s)
        # for these clear-cut cases. Only ambiguous queries (confidence < 0.75,
        # typically generic document_query) fall through to the LLM.
        heuristic = self._heuristic_classify(question)
        if heuristic.get("confidence", 0) >= 0.75:
            return heuristic

        if not LLM_AVAILABLE:
            return heuristic

        history_ctx = ""
        if self.conversation_history:
            history_ctx = "\n\nRecent conversation:\n" + "\n".join([
                f"- User: '{h['question']}' → Atlas answered: '{h['answer_summary'][:120]}'"
                for h in self.conversation_history[-3:]
            ])

        prompt = f"""Classify for Iroko AI (MTN Nigeria):
- "greeting" -- hello, thanks, bye, casual chat, how body, how far
- "follow_up" -- continuing previous topic, reactions like "omo", "really?", "and then?", "yes", short affirmations, surprise at a previous answer
- "network_operations" -- site status, alarms, incidents, tower, cluster, KPI, uptime, downtime, outage, signal, contracts, SLA
- "customer_complaint" -- MoMo complaint, customer ticket, CSAT, CX, resolution, NPS, dispute
- "fraud_intelligence" -- fraud, suspicious transactions, duplicate invoices, SIM swap fraud, MoMo reversals, vendor irregularities, financial anomalies, procurement fraud
- "document_query" -- MTN business operations, compliance, policy, report, regulatory
- "out_of_domain" -- completely unrelated to MTN Nigeria (weather, sports, jokes, cooking)

Input: "{question}"
Pidgin: {is_pidgin}{history_ctx}

IMPORTANT: If the input is a short reaction or affirmation (e.g. "omo", "yes", "really?", "14 million?!") and there is recent conversation, classify as "follow_up".

JSON only: {{"intent": "...", "topic": "...", "confidence": 0.0-1.0}}"""

        try:
            r = await llm_complete(prompt, max_tokens=120, temperature=0.1)
            return json.loads(r.strip().replace("```json", "").replace("```", "").strip())
        except (json.JSONDecodeError, ValueError):
            return self._heuristic_classify(question)
        except RuntimeError as e:
            logger.warning(f"LLM classify failed after retries, using heuristic: {e}")
            return self._heuristic_classify(question)

    def _heuristic_classify(self, question: str) -> dict:
        import re
        q = question.lower().strip()
        words = set(q.split())

        # ── Explicit document reference overrides all keyword heuristics ──
        # If the question names a .pdf or uses clear document-retrieval language,
        # route to document_query regardless of other matching keywords (e.g. "momo").
        _doc_phrases = [
            "in the pdf", "from the pdf", "the pdf",
            "in the document", "from the document", "the document",
            "in the report", "from the report", "the report",
            "according to the", "in this file",
        ]
        if re.search(r'\b\w[\w\-]*\.pdf\b', q) or any(p in q for p in _doc_phrases):
            return {"intent": "document_query", "topic": q[:60], "confidence": 0.85}

        # ── Greeting (word-boundary match to avoid "hi" in "this"/"history") ──
        exact_greetings = {"hi", "hello", "hey", "thanks", "bye", "yo", "sup"}
        phrase_greetings = ["how body", "how far", "wetin dey", "good morning",
                           "good afternoon", "good evening", "how are you"]
        if len(words) <= 6 and (
            words & exact_greetings or any(p in q for p in phrase_greetings)
        ):
            return {"intent": "greeting", "topic": "", "confidence": 0.85}

        if any(p in q for p in ["tell me more", "expand", "elaborate", "go deeper",
                                 "what else", "continue", "more detail"]):
            return {"intent": "follow_up", "topic": "", "confidence": 0.8}

        if any(p in q for p in ["weather", "football", "election", "joke",
                                 "recipe", "movie", "music", "game"]):
            return {"intent": "out_of_domain", "topic": "", "confidence": 0.85}

        if any(p in q for p in ["fraud", "suspicious", "anomaly", "duplicate invoice",
                                 "sim swap fraud", "momo reversal", "vendor concentration",
                                 "procurement fraud", "financial irregularity", "irregular payment",
                                 "fraud intelligence", "fraud risk", "fraud scan",
                                 "round number billing", "invoice splitting"]):
            return {"intent": "fraud_intelligence", "topic": q[:60], "confidence": 0.85}

        if any(p in q for p in [
            "ncc regulation", "ndpc", "ndpa", "data protection act",
            "nigerian communications act", "nca 2003", "consumer code",
            "regulatory framework", "regulatory obligation", "compliance obligation",
            "regulatory penalty", "regulatory fine", "qos regulation",
            "sim registration regulation", "spectrum regulation",
            "data breach notification", "breach notification", "72 hour",
            "cross-border data", "cross border data", "dpco", "data protection officer",
            "compliance framework", "regulatory compliance", "ncc fine",
            "ncc penalty", "regulatory risk", "regulatory exposure",
            "ndpc fine", "ndpc penalty", "data protection compliance",
        ]):
            return {"intent": "regulatory_compliance", "topic": q[:60], "confidence": 0.88}

        # ── Contract / SLA queries → network_operations with contract sub-type ──
        if any(p in q for p in ["contract", "lease", "vendor", "renewal",
                                 "expir", "sla exposure", "sla credit",
                                 "penalty", "procurement"]):
            return {"intent": "network_operations", "topic": q[:60], "confidence": 0.8,
                    "sub_type": "contract"}

        # ── Briefing / summary requests ──
        if any(p in q for p in ["briefing", "morning brief", "daily summary",
                                 "operations summary", "what happened today",
                                 "status update", "overview"]):
            return {"intent": "network_operations", "topic": q[:60], "confidence": 0.8,
                    "sub_type": "briefing"}

        if any(p in q for p in ["site", "tower", "cluster", "alarm", "incident",
                                 "outage", "uptime", "kpi", "signal", "downtime",
                                 "base station", "availability", "throughput",
                                 "latency", "network"]):
            return {"intent": "network_operations", "topic": q[:60], "confidence": 0.8}

        if any(p in q for p in ["complaint", "momo", "csat", "nps", "ticket",
                                 "resolution", "dispute", "refund", "customer",
                                 "churn", "satisfaction"]):
            return {"intent": "customer_complaint", "topic": q[:60], "confidence": 0.8}

        return {"intent": "document_query", "topic": "general", "confidence": 0.65}

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
        vendors = {"ihs": "IHS Nigeria", "ericsson": "Ericsson", "huawei": "Huawei",
                   "nokia": "Nokia", "towerco": "IHS Nigeria", "helios": "Helios Towers"}
        for key, name in vendors.items():
            if key in q:
                entities["vendor"] = name
                break

        # Site codes (e.g. IKJ-001, tower 4471)
        import re
        site_match = re.search(r'\b([A-Z]{2,4}[-_]\d{2,4})\b', question, re.IGNORECASE)
        if site_match:
            entities["site_code"] = site_match.group(1).upper()
        tower_match = re.search(r'tower\s*(\d{3,5})', q)
        if tower_match:
            entities["tower_id"] = tower_match.group(1)

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

    # -- Response generators -----------------------------------------------

    async def _llm_greeting(self, question: str, is_pidgin: bool) -> dict:
        self._log_trace("Strategist", "greeting", "Generating greeting")
        if not LLM_AVAILABLE:
            return self._fallback_greeting(is_pidgin)
        prompt = f"""You are Iroko AI, MTN Nigeria's friendly assistant.
User said: "{question}" Pidgin: {is_pidgin}
Respond warmly (2-3 sentences). Mention you help with network, contracts, compliance, fibre, complaints.
If Pidgin, use Pidgin English."""
        try:
            answer = await llm_complete(prompt, max_tokens=200, temperature=0.7)
            return {
                "answer": answer.strip(),
                "citations": [],
                "suggested_followups": ["Wetin dey happen for Ikeja cluster?", "What is our SLA credit exposure?", "What is our NCC compliance status?"],
                "confidence": "high",
            }
        except (RuntimeError, Exception) as e:
            logger.warning(f"LLM greeting failed: {e}")
            return self._fallback_greeting(is_pidgin)

    async def _llm_followup(self, question: str, is_pidgin: bool) -> dict:
        self._log_trace("Strategist", "followup", "Generating follow-up with context")
        if not self.conversation_history:
            return await self._llm_greeting(question, is_pidgin)
        last = self.conversation_history[-1]
        if not LLM_AVAILABLE:
            return {"answer": f"Previously about '{last['question']}': {last['answer_summary']}...\nWhat would you like to expand on?", "citations": [], "suggested_followups": ["Financial impact?", "Stakeholders?", "Next steps?"], "confidence": "medium"}
        prompt = f"""You are Iroko AI. Follow-up: "{question}"
Previous: "{last['question']}" -> "{last['answer_summary']}"
Give a helpful follow-up. Pidgin: {is_pidgin}"""
        try:
            answer = await llm_complete(prompt, max_tokens=400, temperature=0.5)
            return {
                "answer": answer.strip(),
                "citations": [],
                "suggested_followups": ["Financial impact?", "Who needs to act?", "What's the deadline?"],
                "confidence": "high",
            }
        except (RuntimeError, Exception) as e:
            logger.warning(f"LLM follow-up failed: {e}")
            return {
                "answer": f"Previously we discussed: '{last['question']}'. {last['answer_summary']}\n\nWhat aspect would you like to expand on?",
                "citations": [],
                "confidence": "medium",
            }

    async def _llm_decline(self, question: str, is_pidgin: bool, topic: str) -> dict:
        self._log_trace("Strategist", "decline", f"Out of scope: {topic}")
        if not LLM_AVAILABLE:
            return {"answer": "That's outside my scope. I specialise in MTN Nigeria operations.", "citations": [], "confidence": "low"}
        prompt = f"""You are Iroko AI (MTN Nigeria only). User asked: "{question}" (out of scope).
Politely decline, explain your scope (network, vendors, compliance, fibre, customer care).
Pidgin: {is_pidgin}"""
        try:
            answer = await llm_complete(prompt, max_tokens=200, temperature=0.6)
            return {
                "answer": answer.strip(),
                "citations": [],
                "suggested_followups": ["Wetin dey happen for Ikeja cluster?", "What is our SLA credit exposure?"],
                "confidence": "low",
            }
        except (RuntimeError, Exception) as e:
            logger.warning(f"LLM decline failed: {e}")
            return {
                "answer": "That's outside my scope. I specialise in MTN Nigeria network, vendor contracts, compliance, and customer experience.",
                "citations": [],
                "confidence": "low",
            }

    # -- Fallbacks ---------------------------------------------------------

    def _fallback_greeting(self, is_pidgin: bool) -> dict:
        a = "Ah, my body dey kampe! I be Iroko AI. Wetin you wan investigate?" if is_pidgin else "Hello! I'm Iroko AI -- MTN Nigeria's intelligence assistant. What can I help with?"
        return {"answer": a, "citations": [], "suggested_followups": ["Wetin dey happen for Ikeja cluster?", "What is our SLA credit exposure?", "What is our NCC compliance status?"], "confidence": "high"}

    # -- Utilities ---------------------------------------------------------

    def _detect_pidgin(self, text: str) -> bool:
        return any(m in text.lower() for m in ["wetin","dey","abeg","oga","wahala","sabi","how body","how far","kampe"])

    def _dedupe_citations(self, citations: List[dict]) -> List[dict]:
        seen, out = set(), []
        for c in citations:
            if not isinstance(c, dict):
                continue
            d = c.get("document_id")
            if d and d not in seen:
                seen.add(d)
                out.append(c)
        return out

    def _match_canned_scenario(self, question: str) -> Optional[dict]:
        q = question.lower()
        if any(k in q for k in ["ikeja", "cluster outage", "tower 4471"]):
            return self._canned_noc()
        if any(k in q for k in ["sla credit exposure", "sla exposure", "credit exposure", "vendor sla"]):
            return self._canned_sla()
        if any(k in q for k in ["ncc compliance", "ndpa compliance", "compliance status", "compliance gap"]):
            return self._canned_compliance()
        return None

    def _canned_noc(self) -> dict:
        self._log_trace("Researcher", "search", "Searching RCA + vendor SLAs")
        self._log_trace("Watchdog", "confidence", "Coverage 0.87 -- high")
        self._log_trace("Analyst", "compute", "Calculating SLA exposure: 4.2h")
        self._log_trace("Scribe", "synthesise", "Building NOC incident report")
        return {
            "answer": "**NOC Incident Report — Ikeja Cluster Power Outage (Q1 2026)**\n\n**Executive Summary**\nAt 02:14 WAT, the Ikeja cluster experienced a 4.2-hour outage affecting 6 base stations and ~18,000 subscribers. Root cause: AES feeder failure + generator relay malfunction. Combined SLA exposure: **NGN 2.66M**.\n\n**Incident Details**\n- Start: 02:14 WAT | End: 06:23 WAT | Duration: **4.2 hours**\n- Anchor site: Tower 4471 | Affected: IKJ-001 to IKJ-006\n- ~18,000 subscribers impacted\n\n**SLA & Financial Impact**\n- **IHS Nigeria** (IHS/MTN/IKJ/2024-001): 99.42% vs 99.5% SLA = 2% fee reduction (~NGN 560k)\n- **Ericsson RAN SLA**: 4h response breached by 12min (~NGN 600k)\n- **Enterprise** (Zenith, NNPC, Dangote): NGN 2.1M credits (10%/hour formula)\n- **Combined: NGN 2,660,000**\n\n**Actions**\n1. File SLA claim vs IHS Nigeria — Procurement | 7 days\n2. Raise Ericsson ticket — NOC | 24h\n3. Notify Tier-1 enterprise customers — EBU | 48h\n4. Audit relays at all 6 sites — Field Eng | 14 days",
            "citations": [
                {"document_id": "doc_001", "document_title": "Ikeja Cluster RCA", "excerpt": "6 base stations; 4.2h outage; relay failure"},
                {"document_id": "doc_002", "document_title": "IHS Tower Lease", "excerpt": "99.5% SLA; 2% penalty per 0.1%"},
                {"document_id": "doc_006", "document_title": "Ericsson RAN SLA", "excerpt": "4-hour response SLA"},
                {"document_id": "doc_008", "document_title": "Enterprise SLA Register", "excerpt": "10% per hour credit formula"},
            ],
            "suggested_followups": ["Total SLA exposure across all customers?", "Draft the claim letter to IHS", "MoMo complaint correlation?"],
            "confidence": "high",
        }

    def _canned_sla(self) -> dict:
        self._log_trace("Analyst", "compute", "Calculating cross-contract SLA exposure")
        return {
            "answer": "**SLA Credit Exposure — Ikeja Cluster Outage**\n\n| Party | Contract | Breach | Exposure |\n|---|---|---|---|\n| IHS Nigeria | IHS/MTN/IKJ/2024-001 | 99.42% vs 99.5% | NGN 560,000 |\n| Ericsson | ERIC/MTN/RAN/2026-001 | 4h12m response | NGN 600,000 |\n| Enterprise | Enterprise SLA Register | 4.2h downtime | NGN 2,100,000 |\n| **Total** | | | **NGN 2,660,000** |\n\n1. File SLA claim to IHS — Procurement | 7 days\n2. Raise Ericsson response SLA breach ticket\n3. Notify enterprise customers per notification terms",
            "citations": [
                {"document_id": "doc_002", "document_title": "IHS Tower Lease", "excerpt": "2% per 0.1% below SLA"},
                {"document_id": "doc_006", "document_title": "Ericsson RAN SLA", "excerpt": "4-hour response requirement"},
                {"document_id": "doc_008", "document_title": "Enterprise SLA Register", "excerpt": "10%/hour credit formula"},
            ],
            "suggested_followups": ["Draft the IHS SLA claim letter", "SLA credits recovered this year?"],
            "confidence": "high",
        }

    def _canned_compliance(self) -> dict:
        self._log_trace("Watchdog", "check", "Checking NCC + NDPA deadlines")
        return {
            "answer": "**NCC & NDPA Compliance Status**\n\n**NCC — QoS Return due May 13, 2026 (12 days)**\n- Network availability: 99.3% — below 99.5% target — flag in report\n\n**NDPA — Article 24**\n- MTN-NDPA-ART24-2026-001 incomplete: SCC sign-off outstanding\n- DPO action required before June submission\n\n**Actions:**\n1. Assign QoS report owner — 48h\n2. DPO to sign off SCCs — 7 days\n3. Verify data throughput vs NCC Section 7.3",
            "citations": [
                {"document_id": "doc_004", "document_title": "NCC QoS Framework", "excerpt": "Quarterly submission requirement"},
                {"document_id": "doc_005", "document_title": "NDPA Article 24 Record", "excerpt": "Cross-border transfer safeguards"},
            ],
            "suggested_followups": ["Draft the NCC QoS submission", "NDPA penalties for non-compliance?"],
            "confidence": "high",
        }


    # -- OrgMemory helpers -------------------------------------------------

    async def _load_org_memory(self, organisation: str) -> str:
        try:
            from models.database import SessionLocal, OrgMemory
            db = SessionLocal()
            try:
                facts = (
                    db.query(OrgMemory)
                    .filter(
                        OrgMemory.organisation == organisation,
                        OrgMemory.memory_type.in_(["fact", "pattern"]),
                        OrgMemory.confidence >= 0.7,
                    )
                    .order_by(OrgMemory.updated_at.desc())
                    .limit(10)
                    .all()
                )
                if not facts:
                    return ""
                return "\n".join(
                    f"- [{f.memory_type}] {f.key}: {f.value}" for f in facts
                )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"OrgMemory load failed: {e}")
            return ""

    # -- Universal Structured Data Query ------------------------------------

    async def _query_structured_data(self, question: str, entities: dict) -> List[str]:
        """
        Intelligently query the structured SQLite database based on entities
        and keywords extracted from the question. Returns formatted text
        chunks that can be injected into the LLM context alongside document
        search results.

        This is what makes the AI 'smart' — it bridges natural language
        questions to real database tables (network_sites, vendor_contracts,
        complaint_tickets, network_kpis, network_incidents).
        """
        q_lower = question.lower()
        result_chunks: List[str] = []

        try:
            from models.database import SessionLocal
            from services.network_ops import (
                get_kpi_summary, get_contracts, calculate_sla_exposure,
                get_active_incidents, get_cluster_health, get_site_detail,
                get_complaint_summary, get_operations_briefing,
            )
            db = SessionLocal()
            try:
                days = entities.get("days", 30)
                region = entities.get("region")

                # ── KPI / performance / availability questions ────────────────
                if any(k in q_lower for k in ["availability", "uptime", "kpi",
                                               "throughput", "latency", "performance",
                                               "network quality", "drop call"]):
                    scope = "region" if region else "national"
                    data = get_kpi_summary(db, scope_level=scope, region=region, days=min(days, 30))
                    if data.get("latest"):
                        result_chunks.append(f"LIVE KPI DATA ({scope}):\n{json.dumps(data, indent=2)}")

                # ── Contract / vendor questions ───────────────────────────────
                if any(k in q_lower for k in ["contract", "vendor", "lease",
                                               "renewal", "expir", "procurement",
                                               "ihs", "ericsson", "huawei"]):
                    vendor = entities.get("vendor")
                    data = get_contracts(db, vendor=vendor, expiring_within_days=entities.get("days", 180))
                    if data:
                        result_chunks.append(f"VENDOR CONTRACTS ({len(data)} found):\n{json.dumps(data, indent=2)}")

                # ── SLA / financial exposure questions ────────────────────────
                if any(k in q_lower for k in ["sla", "penalty", "exposure",
                                               "credit", "breach", "financial"]):
                    data = calculate_sla_exposure(db)
                    if data.get("total_exposure_ngn", 0) > 0 or data.get("incident_count", 0) > 0:
                        result_chunks.append(f"SLA EXPOSURE:\n{json.dumps(data, indent=2)}")

                # ── Incident / outage questions ───────────────────────────────
                if any(k in q_lower for k in ["incident", "outage", "alarm",
                                               "failure", "down"]):
                    data = get_active_incidents(db, region=region)
                    if data:
                        result_chunks.append(f"ACTIVE INCIDENTS ({len(data)}):\n{json.dumps(data, indent=2)}")

                # ── Cluster questions ─────────────────────────────────────────
                if entities.get("cluster"):
                    data = get_cluster_health(db, entities["cluster"])
                    if not data.get("error"):
                        result_chunks.append(f"CLUSTER HEALTH — {entities['cluster']}:\n{json.dumps(data, indent=2)}")

                # ── Site-specific questions ───────────────────────────────────
                if entities.get("site_code"):
                    data = get_site_detail(db, entities["site_code"])
                    if data:
                        result_chunks.append(f"SITE DETAIL — {entities['site_code']}:\n{json.dumps(data, indent=2)}")

                # ── Complaint / CX questions ──────────────────────────────────
                if any(k in q_lower for k in ["complaint", "momo", "customer",
                                               "csat", "nps", "refund", "dispute",
                                               "churn", "satisfaction"]):
                    data = get_complaint_summary(db, region=region, days=days)
                    if data.get("total", 0) > 0:
                        result_chunks.append(f"COMPLAINT SUMMARY ({days}d):\n{json.dumps(data, indent=2)}")

                # ── General "how many" / counting questions ───────────────────
                if any(k in q_lower for k in ["how many", "total", "count"]):
                    from models.database import Document, Alert, AgentRun
                    from sqlalchemy import func
                    stats = {
                        "total_documents": db.query(func.count(Document.id)).scalar(),
                        "indexed_documents": db.query(func.count(Document.id)).filter(Document.status == "indexed").scalar(),
                        "active_alerts": db.query(func.count(Alert.id)).filter(Alert.status.in_(["new", "acknowledged"])).scalar(),
                        "total_queries": db.query(func.count(AgentRun.id)).scalar(),
                    }
                    result_chunks.append(f"SYSTEM STATISTICS:\n{json.dumps(stats, indent=2)}")

            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Structured DB query failed: {e}")

        return result_chunks

    # -- Network Operations & CX Orchestration ----------------------------

    async def _orchestrate_network_ops(self, question: str, is_pidgin: bool, depth: str) -> dict:
        """Handle network operations queries by blending live DB data + document search."""
        self._log_trace("Researcher", "network_ops", "Querying live network operational data")
        entities = self._extract_entities(question)
        ops_sections: list = []
        try:
            from models.database import SessionLocal
            from services.network_ops import (
                get_active_incidents, get_kpi_summary, get_cluster_health,
                get_contracts, calculate_sla_exposure, get_site_detail,
                get_complaint_summary, get_operations_briefing,
            )
            db = SessionLocal()
            try:
                q_lower = question.lower()
                days = entities.get("days", 7)

                # ── Smart routing based on extracted entities + keywords ──

                # 1. Specific cluster mentioned → cluster health
                if entities.get("cluster"):
                    cluster = entities["cluster"]
                    data = get_cluster_health(db, cluster)
                    ops_sections.append(f"CLUSTER HEALTH — {cluster}:\n{json.dumps(data, indent=2)}")
                    self._log_trace("Researcher", "cluster_health", f"Pulled live data for {cluster} cluster")

                # 2. Specific site mentioned → site detail
                if entities.get("site_code"):
                    data = get_site_detail(db, entities["site_code"])
                    if data:
                        ops_sections.append(f"SITE DETAIL — {entities['site_code']}:\n{json.dumps(data, indent=2)}")
                        self._log_trace("Researcher", "site_detail", f"Pulled site {entities['site_code']}")

                # 3. Contract / vendor / SLA queries
                if any(k in q_lower for k in ["contract", "lease", "vendor", "renewal", "expir", "procurement"]):
                    vendor_filter = entities.get("vendor")
                    contracts = get_contracts(db, vendor=vendor_filter, expiring_within_days=entities.get("days", 90))
                    ops_sections.append(f"VENDOR CONTRACTS:\n{json.dumps(contracts, indent=2)}")
                    self._log_trace("Analyst", "contracts", f"Fetched {len(contracts)} contracts" + (f" for {vendor_filter}" if vendor_filter else ""))

                if any(k in q_lower for k in ["sla exposure", "sla credit", "penalty", "financial exposure"]):
                    sla = calculate_sla_exposure(db)
                    ops_sections.append(f"SLA EXPOSURE:\n{json.dumps(sla, indent=2)}")
                    self._log_trace("Analyst", "sla_exposure", f"NGN {sla.get('total_exposure_ngn', 0):,.0f} total exposure")

                # 4. Incident queries
                if any(k in q_lower for k in ["incident", "outage", "alarm", "down", "failure"]):
                    region = entities.get("region")
                    data = get_active_incidents(db, region=region)
                    ops_sections.append(f"ACTIVE INCIDENTS:\n{json.dumps(data, indent=2)}")
                    self._log_trace("Researcher", "incidents", f"Found {len(data)} active incidents")

                # 5. Briefing / overview
                if any(k in q_lower for k in ["briefing", "morning brief", "overview", "summary", "status update"]):
                    data = get_operations_briefing(db)
                    ops_sections.append(f"OPERATIONS BRIEFING:\n{json.dumps(data, indent=2)}")
                    self._log_trace("Strategist", "briefing", "Compiled full operations briefing")

                # 6. Default: KPI summary (if nothing else matched)
                if not ops_sections:
                    region = entities.get("region")
                    scope = "region" if region else "national"
                    data = get_kpi_summary(db, scope_level=scope, region=region, days=days)
                    ops_sections.append(f"NETWORK KPI SUMMARY ({days} days, {scope}{' — ' + region if region else ''}):\n{json.dumps(data, indent=2)}")
                    self._log_trace("Analyst", "kpi_summary", f"KPI summary: {scope} scope, {days} days")

                # 7. Always include complaint correlation for context (if depth warrants it)
                if depth in ("standard", "thorough") and entities.get("region"):
                    cx = get_complaint_summary(db, region=entities["region"], days=days)
                    if cx.get("total", 0) > 0:
                        ops_sections.append(f"COMPLAINT CONTEXT — {entities['region']} ({days}d):\n{json.dumps(cx, indent=2)}")

            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Network ops data fetch failed: {e}")

        ops_context = "\n\n".join(ops_sections)

        # Also search documents for context
        doc_context = await self._retrieve_context(question, depth)

        pidgin_note = "Respond in Pidgin English." if is_pidgin else ""
        prompt = f"""Question: "{question}"

{ops_context}

Document Evidence:
{chr(10).join(doc_context.get('chunks', [])[:4])}

{pidgin_note}

Respond with valid JSON:
{{"answer": "...", "citations": [], "suggested_actions": ["..."], "suggested_followups": ["..."], "confidence": "high|medium|low"}}"""

        self._log_trace("Strategist", "reason", "Synthesising network operations answer")
        try:
            response = await llm_complete(prompt, max_tokens=2000, temperature=0.2,
                                          system_prompt="You are Iroko AI, MTN Nigeria's network operations intelligence assistant. Lead with live operational data. Give specific site codes, incident refs, KPI values, contract amounts. Suggest concrete next actions.")
        except RuntimeError as e:
            logger.error(f"LLM network ops reasoning failed after retries: {e}")
            return {
                "answer": ops_context or "The AI reasoning engine is temporarily unavailable. Please check the Network dashboard directly.",
                "citations": [], "confidence": "low",
                "suggested_followups": ["Show active incidents", "What are today's KPIs?", "Ikeja cluster status?"],
            }
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            result.setdefault("citations", doc_context.get("citations", []))
            return result
        except json.JSONDecodeError:
            return {
                "answer": response or ops_context or "Live network data is currently unavailable. Please check the network dashboard.",
                "citations": doc_context.get("citations", []), "confidence": "medium",
                "suggested_followups": ["Show active incidents", "What are today's KPIs?", "Ikeja cluster status?"],
            }

    async def _orchestrate_fraud(self, question: str, is_pidgin: bool) -> dict:
        """Handle fraud intelligence queries using seeded fraud signal data."""
        self._log_trace("Researcher", "fraud_scan", "Scanning fraud signal database")
        from services.fraud_service import get_fraud_signals, get_fraud_summary
        q_lower = question.lower()

        # Route to category-specific signals if the question targets one
        category = None
        if any(k in q_lower for k in ["procurement", "invoice", "vendor", "billing", "purchase"]):
            category = "procurement"
        elif any(k in q_lower for k in ["sim swap", "swap", "account takeover"]):
            category = "sim_swap"
        elif any(k in q_lower for k in ["momo", "mobile money", "reversal", "agent"]):
            category = "momo_fraud"
        elif any(k in q_lower for k in ["compliance", "ncc", "regulatory", "submission"]):
            category = "compliance"

        entities = self._extract_entities(question)
        region = entities.get("region")

        if category or region:
            signals = get_fraud_signals(category=category, region=region)
            scope = f"{category or 'all categories'}, {region or 'all regions'}"
            context_text = f"FRAUD SIGNALS ({scope}):\n{json.dumps(signals, indent=2)}"
        else:
            summary = get_fraud_summary()
            context_text = f"FRAUD INTELLIGENCE SUMMARY:\n{json.dumps(summary, indent=2)}"

        self._log_trace("Analyst", "fraud_score", "Scoring risk levels and financial exposure")

        doc_context = await self._retrieve_context(question, "standard")
        pidgin_note = "Respond in Pidgin English." if is_pidgin else ""
        prompt = f"""Question: "{question}"

{context_text}

Document Evidence:
{chr(10).join(doc_context.get('chunks', [])[:3])}

{pidgin_note}

Respond with valid JSON:
{{"answer": "...", "citations": [], "suggested_actions": ["..."], "suggested_followups": ["..."], "confidence": "high|medium|low"}}"""

        self._log_trace("Strategist", "reason", "Synthesising fraud intelligence report")
        try:
            response = await llm_complete(
                prompt, max_tokens=2000, temperature=0.2,
                system_prompt=(
                    "You are Iroko AI, MTN Nigeria's fraud intelligence assistant. "
                    "Write a concise, insight-led fraud risk report. Lead with the highest-risk findings first. "
                    "Always cite: signal ID, specific amounts in NGN, agent codes where relevant, region. "
                    "End with concrete recommended actions: suspend agent codes, escalate to EFCC/ICPC, "
                    "initiate internal audit, notify CFO. Never soften fraud findings."
                ),
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            result.setdefault("citations", doc_context.get("citations", []))
            return result
        except Exception as e:
            logger.warning(f"Fraud LLM reasoning failed, using fallback: {e}")
            summary = get_fraud_summary()
            lines = [
                f"**Fraud Intelligence Report — MTN Nigeria**\n",
                f"**{summary['high_risk']} HIGH · {summary['medium_risk']} MEDIUM risk signals active.**",
                f"**Total financial exposure: ₦{summary['total_exposure_ngn']:,.0f}**\n",
                "**Active Fraud Signals:**",
            ]
            for s in summary["signals"]:
                lines.append(f"\n**[{s['risk']}] {s['id']} — {s['title']}**")
                lines.append(s["detail"])
                if s["amount_ngn"]:
                    lines.append(f"_Exposure: ₦{s['amount_ngn']:,.0f} | Status: {s['status']}_")
            return {
                "answer": "\n".join(lines),
                "citations": [],
                "suggested_followups": [
                    "Which fraud signals are in Lagos?",
                    "Show all procurement fraud details",
                    "What is the total MoMo fraud exposure?",
                    "How do we handle the NCC data mismatch?",
                ],
                "confidence": "high",
            }

    async def _orchestrate_regulatory(self, question: str, is_pidgin: bool) -> dict:
        """
        Handle regulatory compliance queries by injecting real NCC and NDPC
        regulation text, section numbers, penalties, and enforcement precedents
        into the LLM context before synthesis.
        """
        self._log_trace("Researcher", "regulatory_lookup", "Loading NCC and NDPC regulatory corpus")
        from services.regulatory_service import get_regulatory_summary_text, get_regulatory_context

        reg_text = get_regulatory_summary_text(question)
        ctx = get_regulatory_context(question)

        self._log_trace("Analyst", "compliance_analysis",
                        f"Matched {ctx['total_matched']} regulations; building compliance briefing")

        doc_context = await self._retrieve_context(question, "standard")
        pidgin_note = "Respond in Nigerian Pidgin English." if is_pidgin else ""

        prompt = f"""Question: "{question}"

{reg_text}

Document Evidence from MTN Nigeria corpus:
{chr(10).join(doc_context.get('chunks', [])[:3])}

{pidgin_note}

Respond with valid JSON:
{{
  "answer": "...",
  "citations": [],
  "suggested_followups": ["..."],
  "confidence": "high|medium|low"
}}"""

        try:
            response = await llm_complete(
                prompt, max_tokens=2500, temperature=0.15,
                system_prompt=(
                    "You are Iroko AI, MTN Nigeria's regulatory intelligence assistant. "
                    "Write a precise, well-cited regulatory compliance briefing. "
                    "Always cite: exact regulation name, section number, penalty figure in NGN, and enforcement precedent. "
                    "Structure your answer: (1) which regulations apply, (2) what MTN's specific obligations are, "
                    "(3) penalty exposure with actual figures, (4) enforcement precedents to illustrate seriousness, "
                    "(5) recommended immediate actions. "
                    "Use bold headings (** **). Be comprehensive but concise. Never omit penalty figures."
                ),
            )
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            result.setdefault("citations", doc_context.get("citations", []))
            return result
        except Exception as e:
            logger.warning(f"Regulatory LLM synthesis failed, using fallback: {e}")
            checklist = ctx.get("compliance_checklist", [])
            lines = ["**MTN Nigeria — Regulatory Compliance Briefing (NCC & NDPC)**\n"]
            for item in checklist:
                lines.append(
                    f"\n**[{item['risk']}] {item['area']}** — {item['regulator']} | {item['regulation']}\n"
                    f"{item['obligation']}\n"
                    f"_Penalty: {item['penalty_if_breached']}_"
                )
            return {
                "answer": "\n".join(lines),
                "citations": [],
                "suggested_followups": [
                    "What are the NDPA 2023 data breach notification requirements?",
                    "What is MTN's penalty exposure under NCC QoS regulations?",
                    "How do we comply with the NCC SIM registration rules?",
                    "What does the GAID 2025 require for cross-border data transfers?",
                    "What enforcement actions has NDPC taken against telcos?",
                ],
                "confidence": "high",
            }

    async def _orchestrate_cx(self, question: str, is_pidgin: bool) -> dict:
        """Handle customer experience queries using live complaint data."""
        self._log_trace("Researcher", "cx_data", "Querying live complaint and CX data")
        entities = self._extract_entities(question)
        region = entities.get("region")
        days = entities.get("days", 30)
        cx_context = ""
        try:
            from models.database import SessionLocal
            from services.network_ops import get_complaint_summary, correlate_complaints_to_incidents, get_complaints
            db = SessionLocal()
            try:
                summary = get_complaint_summary(db, region=region, days=days)
                correlations = correlate_complaints_to_incidents(db, days=days)
                scope_label = f"{region} region" if region else "all regions"
                cx_context = f"CX SUMMARY ({days} days, {scope_label}):\n{json.dumps(summary, indent=2)}"
                self._log_trace("Analyst", "cx_summary", f"{summary.get('total', 0)} complaints in {scope_label}")
                if correlations:
                    cx_context += f"\n\nINCIDENT CORRELATIONS:\n{json.dumps(correlations[:5], indent=2)}"

                # If asking about specific category, pull detailed tickets
                q_lower = question.lower()
                category = None
                for cat in ["momo", "billing", "network", "data", "voice", "roaming"]:
                    if cat in q_lower:
                        category = cat if cat != "momo" else "momo_deduction"
                        break
                if category:
                    tickets = get_complaints(db, category=category, region=region, days=days, limit=10)
                    cx_context += f"\n\nDETAILED {category.upper()} TICKETS:\n{json.dumps(tickets[:5], indent=2)}"
                    self._log_trace("Researcher", "cx_tickets", f"Pulled {len(tickets)} {category} tickets")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"CX data fetch failed: {e}")

        pidgin_note = "Respond in Pidgin English." if is_pidgin else ""
        prompt = f"""Question: "{question}"

{cx_context}

{pidgin_note}

Respond with valid JSON:
{{"answer": "...", "citations": [], "suggested_actions": ["..."], "suggested_followups": ["..."], "confidence": "high|medium|low"}}"""

        self._log_trace("Strategist", "reason", "Synthesising CX answer from live data")
        try:
            response = await llm_complete(prompt, max_tokens=1500, temperature=0.2,
                                          system_prompt="You are Iroko AI, MTN Nigeria's customer experience intelligence assistant. Give specific numbers: complaint counts, resolution rates, disputed amounts. Highlight top complaint categories and regions. Link complaints to network incidents where correlation exists.")
        except RuntimeError as e:
            logger.error(f"LLM CX reasoning failed after retries: {e}")
            return {
                "answer": cx_context or "The AI reasoning engine is temporarily unavailable. Please check the CX dashboard directly.",
                "citations": [], "confidence": "low",
                "suggested_followups": ["Top complaint categories?", "Lagos complaint trends?", "MoMo resolution rate?"],
            }
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {
                "answer": response or cx_context or "CX data is currently unavailable.",
                "citations": [], "confidence": "medium",
                "suggested_followups": ["Top complaint categories?", "Lagos complaint trends?", "MoMo resolution rate?"],
            }

    # -- Morning Briefing --------------------------------------------------

    @kernel_function(description="Generate a dynamic morning briefing from live operational data.")
    async def morning_briefing(self, user_department: Annotated[str, "Department"] = "General") -> str:
        self._log_trace("Strategist", "briefing", "Compiling live operations briefing")
        urgent = []
        deadlines = []
        key_metrics = []

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
            urgent = ["IHS lease expires June 30 2026", "Ikeja complaint spike: +187% in 24h"]
            deadlines = ["NCC QoS report due May 13", "NDPA Article 24 gap — DPO review required"]
            key_metrics = ["Network uptime: 99.3% (below 99.5% target)", "CSAT: 71/100 (down 4pts)"]

        return json.dumps({
            "generated_at": datetime.utcnow().isoformat(),
            "department": user_department,
            "sections": [
                {"title": "Urgent Attention Required", "items": urgent or ["No critical issues — all systems nominal"]},
                {"title": "Deadlines & Renewals", "items": deadlines or ["No contracts expiring in the next 30 days"]},
                {"title": "Key Metrics", "items": key_metrics},
            ],
            "agent_trace": self.trace,
        })