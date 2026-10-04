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

    def set_history(self, history: List[Dict]):
        self.conversation_history = history[-5:]

    def _log_trace(self, agent: str, tool: str, description: str):
        self.trace.append({"agent": agent, "tool": tool, "description": description, "timestamp": datetime.utcnow().isoformat()})
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
            self._log_trace("Strategist", "intent", f"Intent: {intent} | Topic: {topic}")

            if intent == "greeting":
                result = await self._llm_greeting(question, is_pidgin)
            elif intent == "follow_up":
                previous = self.conversation_history[-1]["question"] if self.conversation_history else ""
                result = await self._orchestrate_agents(f"{previous}\nFollow-up: {question}", is_pidgin, depth)
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
                result = await self._orchestrate_agents(question, is_pidgin, depth)

            duration_ms = int((time.time() - start) * 1000)
            if "citations" in result:
                result["citations"] = self._dedupe_citations(result["citations"])

            # ── Wire VerdictEngine ────────────────────────────────────────────────
            try:
                from services.verdict_engine import verdict_engine
                conf_val = 0.85 if result.get("confidence") == "high" else (0.6 if result.get("confidence") == "medium" else 0.4)
                comp_res = {"verdict": "MONITOR", "compliant": True}
                if intent == "regulatory_compliance" or "compliance" in topic.lower():
                    if "NO-GO" in result.get("answer", "") or "violation" in result.get("answer", "").lower():
                        comp_res = {"verdict": "NO-GO", "compliant": False}
                verdict = verdict_engine.compute_verdict(
                    confidence=conf_val,
                    compliance_result=comp_res,
                    signal_strength=max(1, len(result.get("citations", [])))
                )
                result["verdict"] = "MONITOR" if result.get("_grounded") else verdict
                self._log_trace("Strategist", "verdict", f"Result verdict: {result['verdict']}")
            except Exception as e:
                logger.warning(f"Verdict engine failed in strategist: {e}")

            # ── Wire Boardroom Formatter (business intents only) ──────────────────
            _BOARDROOM_INTENTS = {"network_operations", "regulatory_compliance",
                                  "fraud_intelligence", "customer_complaint", "document_query"}
            if intent in _BOARDROOM_INTENTS and not result.get("_grounded"):
                try:
                    from services.boardroom_formatter import boardroom_formatter
                    result = await boardroom_formatter.format_executive_summary(result, is_pidgin)
                    self._log_trace("Strategist", "formatter", "Applied executive language transformation")
                except Exception as e:
                    logger.warning(f"Boardroom formatter failed in strategist: {e}")

            self.conversation_history.append({"question": question, "intent": intent, "topic": topic, "answer_summary": result.get("answer", "")[:300], "timestamp": datetime.utcnow().isoformat()})
            self.conversation_history = self.conversation_history[-5:]

            return json.dumps({"question": question, "answer": result["answer"], "knowledge_gap": bool(result.get("knowledge_gap", False)), "confidence": result.get("confidence", "high"), "verdict": result.get("verdict", "MONITOR"), "is_pidgin": is_pidgin, "agent_trace": self.trace, "citations": result.get("citations", []), "partial_answer": result.get("partial_answer", False), "missing_information": result.get("missing_information", []), "source_checks": result.get("source_checks", []), "research_checked_at": result.get("research_checked_at"), "suggested_actions": result.get("suggested_actions", []), "suggested_followups": result.get("suggested_followups", []), "duration_ms": duration_ms, "agents_used": list({t["agent"] for t in self.trace}), "intent": intent, "topic": topic})

        except Exception as e:
            logger.error(f"Strategist failed: {e}", exc_info=True)
            return json.dumps({"question": question, "answer": "I encountered an error. Please try rephrasing or ask about your organisation's documents, network operations, or regulatory filings.", "is_pidgin": is_pidgin, "agent_trace": self.trace, "error": str(e)})

    # -- Streaming entry point ---------------------------------------------

    async def investigate_stream(self, question: str, depth: str = "standard") -> AsyncGenerator[dict, None]:
        """Progress starts immediately; only validated final answers become tokens."""
        yield {"type": "start", "message": "Iroko AI is checking the extracted evidence...", "timestamp": datetime.utcnow().isoformat()}
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
        self._log_trace("Watchdog", "claim_validation", "Checking exact quotes, citation coordinates and claim support before display")
        result = None
        if not (public_research and freshness_requested(question)):
            result = await answer(question, context, llm_complete, is_pidgin)
        if public_research and (result is None or result.get("knowledge_gap")):
            if report is None:
                self._log_trace("Researcher", "official_research", "Checking bounded official regulatory sources; customer documents are not sent to external search services")
                report = await research(question)
            # Freshness requests should not be dominated by the older local corpus.
            internal = [] if fresh_public and report["sources"] else context.get("sources", [])[:6]
            combined = [*report["sources"], *internal]
            self._log_trace("Watchdog", "research_validation", "Separately auditing supported findings and missing facts; never estimating an unsupported penalty")
            result = await answer(question, {**context, "sources": combined, "knowledge_gap": not combined}, llm_complete, is_pidgin, allow_partial=True)
            result = finish(result, report, question)
        message = ("Reported an evidence/validation gap without a compliance conclusion" if result.get("knowledge_gap")
                   else "Rendered approved partial findings with the remaining gaps" if result.get("partial_answer")
                   else "Rendered verified claims without executive rewriting")
        self._log_trace("Scribe", "format", message)
        return result

    async def _retrieve_context(self, question: str, depth: str) -> dict:
        from services.grounded_answers import retrieve
        self._log_trace("Researcher", "search", "Retrieving accessible extracted source passages")
        return await retrieve(question)

    _ANSWER_SYSTEM_PROMPT = (
        "You are Iroko AI, a compliance and document-intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech — write like a sharp senior analyst. "
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
        "You are Iroko AI, a compliance and document-intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech — write like a sharp senior analyst, "
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

        prompt = f"""Classify for Iroko AI (compliance & document intelligence for a CBN/SEC-regulated microfinance bank or fintech):
- "greeting" -- hello, thanks, bye, casual chat, how body, how far
- "follow_up" -- continuing previous topic, reactions like "omo", "really?", "and then?", "yes", short affirmations, surprise at a previous answer
- "network_operations" -- operational incidents, branch/system outages, uptime, KPIs, alerts, vendor SLA status
- "customer_complaint" -- customer ticket, loan/deduction dispute, CSAT, CX, resolution, NPS, complaint trends
- "fraud_intelligence" -- fraud, account takeover, suspicious transactions, duplicate invoices, agent collusion, vendor irregularities, procurement fraud
- "document_query" -- contracts, RCA reports, CBN returns, NDPA records, policy documents, regulatory filings
- "regulatory_compliance" -- CBN/SEC/NDPA regulatory obligations, capital adequacy, lending/exposure limits, AML/CFT & KYC, SAR filings, data protection & privacy law, data localization/residency, cross-border data transfer, breach notification, licensing regulations, penalty or fine exposure, AI governance, model explainability, training-data sourcing, automated-decision transparency
- "out_of_domain" -- completely unrelated to the organisation's operations or regulation (weather, sports, jokes, cooking)

Input: "{question}"
Pidgin: {is_pidgin}{history_ctx}

IMPORTANT: If the input is a short reaction or affirmation (e.g. "omo", "yes", "really?", "14 million?!") and there is recent conversation, classify as "follow_up".

JSON only: {{"intent": "...", "topic": "...", "confidence": 0.0-1.0}}"""

        try:
            r = await llm_complete(prompt, max_tokens=120, temperature=0.1, service_id="nano")
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
        # route to document_query regardless of other matching keywords (e.g. "agent_wallet").
        _doc_phrases = [
            "circular", "letter", "gazette", "guidance", "framework", "template", "worksheet",
            "document", "extracted", "section", "s.i.",
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
                                 "sim swap fraud", "agent wallet reversal", "vendor concentration",
                                 "procurement fraud", "financial irregularity", "irregular payment",
                                 "fraud intelligence", "fraud risk", "fraud scan",
                                 "round number billing", "invoice splitting"]):
            return {"intent": "fraud_intelligence", "topic": q[:60], "confidence": 0.85}

        if any(p in q for p in [
            "cbn regulation", "sec regulation", "ndpc", "ndpa", "ndpr", "data protection act",
            "microfinance guideline", "mfb guideline", "consumer code",
            "regulatory framework", "regulatory obligation", "compliance obligation",
            "regulatory penalty", "regulatory fine",
            "capital adequacy", "capital requirement", "single obligor",
            "prudential return", "cash reserve ratio", "liquidity ratio",
            "aml", "cft", "anti-money laundering", "kyc", "know your customer",
            "sar filing", "suspicious activity report", "sanctions screening",
            "data breach notification", "breach notification", "72 hour",
            "cross-border data", "cross border data", "cross-border transfer",
            "dpco", "data protection officer",
            "compliance framework", "regulatory compliance", "cbn fine",
            "cbn penalty", "sec fine", "sec penalty", "regulatory risk", "regulatory exposure",
            "ndpc fine", "ndpc penalty", "data protection compliance",
            # data-protection / privacy-law / AI-governance signals
            "data localization", "data localisation", "data residency",
            "data sovereignty", "privacy law", "personal data", "lawful basis",
            "dpia", "data protection impact", "privacy impact",
            "gaid", "type approval", "licensing condition", "licence condition",
            # AI-governance signals (NDPR alignment of AI tooling)
            "training data", "model explainability", "explainability",
            "ai governance", "ai act", "automated decision", "automated processing",
            "algorithmic", "model transparency", "responsible ai",
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

        if any(p in q for p in ["complaint", "agent_wallet", "csat", "nps", "ticket",
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

    # -- Response generators -----------------------------------------------

    async def _llm_greeting(self, question: str, is_pidgin: bool) -> dict:
        self._log_trace("Strategist", "greeting", "Generating greeting")
        if not LLM_AVAILABLE:
            return self._fallback_greeting(is_pidgin)
        prompt = f"""You are Iroko AI, a compliance and document-intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech.
User said: "{question}" Pidgin: {is_pidgin}
Respond warmly (2-3 sentences). Mention you help with regulatory filings (CBN, SEC, NDPA), AML/CFT & KYC checks, vendor contracts, customer complaints, and document search.
If Pidgin, use Pidgin English."""
        try:
            answer = await llm_complete(prompt, max_tokens=200, temperature=0.7, service_id="nano")
            return {
                "answer": answer.strip(),
                "citations": [],
                "suggested_followups": ["What is our AML/CFT filing status this quarter?", "Which vendor contracts expire in the next 90 days?", "Are we meeting the CBN capital adequacy ratio?"],
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
            answer = await llm_complete(prompt, max_tokens=400, temperature=0.5, service_id="nano")
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
            return {"answer": "That's outside my scope. I specialise in your organisation's documents, network operations, and regulatory intelligence.", "citations": [], "confidence": "low"}
        prompt = f"""You are Iroko AI (compliance & document intelligence for a CBN/SEC-regulated microfinance bank or fintech). User asked: "{question}" (out of scope).
Politely decline, explain your scope (CBN/SEC/NDPA regulatory filings, AML/CFT & KYC, vendor contracts, customer complaints, document search).
Pidgin: {is_pidgin}"""
        try:
            answer = await llm_complete(prompt, max_tokens=200, temperature=0.6, service_id="nano")
            return {
                "answer": answer.strip(),
                "citations": [],
                "suggested_followups": ["What is our AML/CFT filing status this quarter?", "Which regulatory filings are due this quarter?"],
                "confidence": "low",
            }
        except (RuntimeError, Exception) as e:
            logger.warning(f"LLM decline failed: {e}")
            return {
                "answer": "That's outside my scope. I specialise in your organisation's documents — CBN/SEC/NDPA filings, AML/CFT & KYC checks, vendor contracts, and customer experience.",
                "citations": [],
                "confidence": "low",
            }

    # -- Fallbacks ---------------------------------------------------------

    def _fallback_greeting(self, is_pidgin: bool) -> dict:
        a = "Ah, my body dey kampe! I be Iroko AI. Wetin you wan investigate?" if is_pidgin else "Hello! I'm Iroko AI — your enterprise document-intelligence assistant. What can I help with?"
        return {"answer": a, "citations": [], "suggested_followups": ["What caused the Ikeja cluster outage?", "Which regulatory filings are due this quarter?", "Show me today's active alerts"], "confidence": "high"}

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
        from ingestion.queue import enabled
        if enabled():
            return []  # Legacy operational tables require their own tenant migration.
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
                if any(k in q_lower for k in ["complaint", "agent_wallet", "customer",
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

        self._log_trace("Strategist", "reason", "Synthesising regulatory operations answer")
        try:
            response = await llm_complete(prompt, max_tokens=2000, temperature=0.2,
                                          system_prompt="You are Iroko AI, an operations & document intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech. Lead with live operational data. Give specific branch/system names, incident references, availability figures, contract amounts. Suggest concrete next actions.")
        except RuntimeError as e:
            logger.error(f"LLM network ops reasoning failed after retries: {e}")
            return {
                "answer": ops_context or "The AI reasoning engine is temporarily unavailable. Please check the Network Intelligence dashboard directly.",
                "citations": [], "confidence": "low",
                "suggested_followups": ["Show active alerts", "How is the Ikeja cluster performing?", "NCC QoS return status?"],
            }
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(clean)
            result.setdefault("citations", doc_context.get("citations", []))
            return result
        except json.JSONDecodeError:
            # GPT-5.x usually returns well-formatted prose rather than strict JSON
            # when it fails to comply — use that text instead of leaking raw JSON.
            return {
                "answer": clean or ops_context or "Live operational data is currently unavailable. Please check the Network Intelligence dashboard.",
                "citations": doc_context.get("citations", []), "confidence": "medium",
                "suggested_followups": ["Show active alerts", "How is the Ikeja cluster performing?", "NCC QoS return status?"],
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
        elif any(k in q_lower for k in ["momo", "mobile money", "reversal", "agent wallet"]):
            category = "agent_wallet_fraud"
        elif any(k in q_lower for k in ["compliance", "cbn", "sec", "regulatory", "submission"]):
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
                    "You are Iroko AI, a fraud intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech. "
                    "Write a concise, insight-led fraud risk report. Lead with the highest-risk findings first. "
                    "Always cite: signal ID, specific amounts in NGN, agent/branch codes where relevant, region. "
                    "End with concrete recommended actions: suspend agent codes, file a SAR with the NFIU, escalate to EFCC/ICPC, "
                    "initiate internal audit, notify CFO/compliance. Never soften fraud findings."
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
                f"**Fraud Intelligence Report — Network & MoMo Operations**\n",
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
                    "What is the total SIM-swap exposure?",
                    "How do we handle the interconnect bypass indicators?",
                ],
                "confidence": "high",
            }

    async def _orchestrate_regulatory(self, question: str, is_pidgin: bool) -> dict:
        """Use the same verified source policy as document Q&A."""
        return await self._orchestrate_agents(question, is_pidgin, "standard")

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
                # (keywords map onto the seeded complaint categories)
                q_lower = question.lower()
                category = None
                _category_map = {
                    "momo": "momo_deduction",
                    "deduction": "momo_deduction",
                    "billing": "data_billing",
                    "voice": "voice_quality",
                    "coverage": "network_coverage",
                }
                for kw, cat_key in _category_map.items():
                    if kw in q_lower:
                        category = cat_key
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
                                          system_prompt="You are Iroko AI, a customer experience intelligence assistant for a CBN/SEC-regulated microfinance bank or fintech. Give specific numbers: complaint counts, resolution rates, disputed amounts. Highlight top complaint categories and regions. Link complaints to operational incidents where correlation exists.")
        except RuntimeError as e:
            logger.error(f"LLM CX reasoning failed after retries: {e}")
            return {
                "answer": cx_context or "The AI reasoning engine is temporarily unavailable. Please check the CX dashboard directly.",
                "citations": [], "confidence": "low",
                "suggested_followups": ["Top complaint categories?", "Lagos complaint trends?", "MoMo deduction resolution rate?"],
            }
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # GPT-5.x usually returns well-formatted prose rather than strict JSON
            # when it fails to comply — use that text instead of leaking raw JSON.
            return {
                "answer": clean or cx_context or "CX data is currently unavailable.",
                "citations": [], "confidence": "medium",
                "suggested_followups": ["Top complaint categories?", "Lagos complaint trends?", "MoMo deduction resolution rate?"],
            }

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
