"""
OrchestratorAgent: classifies user intent and delegates to specialist agents.

This module provides TWO interfaces:

1. **OrchestratorAgent** (class) — lightweight wrapper that delegates to
   StrategistAgent.investigate() for the existing route layer.

2. **orchestrate_pipeline()** (async generator) — streaming 5-agent pipeline
   that yields reasoning steps for SSE consumption by FastAPI.

Agent execution order:
  WatchdogAgent → ResearcherAgent → AnalystAgent → StrategistAgent → ScribeAgent

Each agent receives the accumulated context from all previous agents.
"""

import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from agents._compat import Kernel
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. OrchestratorAgent class (preserved from existing codebase)
# ═══════════════════════════════════════════════════════════════════════════════

class OrchestratorAgent(BaseAgent):
    """
    Top-level agent that orchestrates the full investigate pipeline.

    Internally delegates to :class:`StrategistAgent` which already
    coordinates Researcher → Analyst + Watchdog (parallel) → Scribe.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        super().__init__(kernel=kernel)

    async def orchestrate(
        self,
        question: str,
        conversation_history: list | None = None,
    ) -> dict:
        """
        Run the full multi-agent investigation pipeline.

        Steps (handled internally by StrategistAgent):
          1. ResearchAgent — retrieves evidence from Azure AI Search
          2. AnalystAgent + MonitorAgent — run in parallel via asyncio.gather
          3. Scribe — formats the final answer with citations

        Parameters
        ----------
        question : str
            User's natural-language question.
        conversation_history : list, optional
            Previous Q&A turns for multi-turn context.

        Returns
        -------
        dict
            Keys: answer, citations, confidence, suggested_actions,
            suggested_followups, trace.
        """
        self._log_trace(
            "Orchestrator", "start",
            f"Orchestrating investigation: '{question[:60]}'"
        )

        try:
            # Import here to avoid circular imports at module level
            from agents.strategist import StrategistAgent

            strategist = StrategistAgent(kernel=self.kernel)

            # Inject conversation history if provided
            if conversation_history:
                strategist.set_history(conversation_history)

            # Delegate to the existing, battle-tested investigation pipeline
            raw_result = await self._with_retry(
                strategist.investigate,
                question=question,
            )

            result = json.loads(raw_result)

            # Merge strategist trace into our own trace
            self.trace.extend(result.get("agent_trace", []))

            self._log_trace(
                "Orchestrator", "complete",
                f"Investigation complete — confidence: {result.get('confidence', 'unknown')}"
            )

            return {
                "answer": result.get("answer", ""),
                "citations": result.get("citations", []),
                "confidence": result.get("confidence", "medium"),
                "suggested_actions": result.get("suggested_actions", []),
                "suggested_followups": result.get("suggested_followups", []),
                "trace": self.trace,
            }

        except Exception as exc:
            logger.error(f"OrchestratorAgent.orchestrate failed: {exc}", exc_info=True)
            self._log_trace("Orchestrator", "error", str(exc))
            return {
                "answer": "I encountered an error during investigation. Please try again.",
                "citations": [],
                "confidence": "low",
                "suggested_actions": [],
                "suggested_followups": ["Try rephrasing your question"],
                "trace": self.trace,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Streaming pipeline (async generator for FastAPI SSE)
# ═══════════════════════════════════════════════════════════════════════════════

def _step(
    agent: str,
    status: str,
    message: str,
) -> dict:
    """Build a reasoning step dict."""
    return {
        "agent": agent,
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


async def orchestrate_pipeline(
    query: str,
    org_id: str = "MTN Nigeria",
) -> AsyncGenerator[dict, None]:
    """
    Async generator that runs the 5-agent pipeline sequentially and yields
    reasoning step dicts after each agent completes.

    Execution order:
      1. WatchdogAgent — confidence gating & proactive checks
      2. ResearcherAgent — hybrid search for evidence
      3. AnalystAgent — quantitative analysis
      4. StrategistAgent — investigation planning & orchestration
      5. ScribeAgent — final answer synthesis

    Yields
    ------
    dict
        Reasoning steps: ``{"agent": "...", "status": "thinking"|"done"|"handoff", ...}``
        Final result:    ``{"type": "final", "response": "...", "risk_score": 1-10, ...}``
    """
    reasoning_steps: list[dict] = []
    pipeline_context: dict = {
        "query": query,
        "org_id": org_id,
        "watchdog_result": None,
        "research_result": None,
        "analyst_result": None,
        "strategist_result": None,
        "scribe_result": None,
    }

    # ── 1. Watchdog — confidence gating ───────────────────────────────────────

    yield _step("WatchdogAgent", "thinking", "Running proactive checks and confidence gating…")

    try:
        from agents.watchdog import WatchdogAgent
        watchdog = WatchdogAgent()

        # Run all proactive checks for the organisation
        raw_checks = await watchdog.run_all_checks(organisation=org_id)
        watchdog_result = json.loads(raw_checks)
        pipeline_context["watchdog_result"] = watchdog_result

        alert_count = watchdog_result.get("total_alerts", 0)
        critical = watchdog_result.get("critical_count", 0)
        msg = f"Completed: {alert_count} alerts found ({critical} critical)."

        step = _step("WatchdogAgent", "done", msg)
        reasoning_steps.append(step)
        yield step
    except Exception as exc:
        logger.warning(f"Watchdog pipeline stage failed: {exc}")
        step = _step("WatchdogAgent", "done", f"Completed with warnings: {str(exc)[:120]}")
        reasoning_steps.append(step)
        yield step

    yield _step("WatchdogAgent", "handoff", "Handing off to ResearcherAgent…")

    # ── 2. Researcher — hybrid search ─────────────────────────────────────────

    yield _step("ResearcherAgent", "thinking", f"Searching knowledge base for: \"{query[:80]}\"")

    try:
        from agents.researcher import ResearcherAgent
        researcher = ResearcherAgent()

        raw_search = await researcher.search_documents(query=query, top_k=10)
        search_result = json.loads(raw_search)
        pipeline_context["research_result"] = search_result

        result_count = len(search_result.get("results", []))
        is_mock = search_result.get("source") == "mock"
        source_label = "seed corpus" if is_mock else "Azure AI Search"
        msg = f"Retrieved {result_count} relevant documents from {source_label}."

        step = _step("ResearcherAgent", "done", msg)
        reasoning_steps.append(step)
        yield step
    except Exception as exc:
        logger.warning(f"Researcher pipeline stage failed: {exc}")
        step = _step("ResearcherAgent", "done", f"Search completed with errors: {str(exc)[:120]}")
        reasoning_steps.append(step)
        yield step

    yield _step("ResearcherAgent", "handoff", "Handing off to AnalystAgent…")

    # ── 3. Analyst — quantitative analysis ────────────────────────────────────

    yield _step("AnalystAgent", "thinking", "Analysing retrieved documents for quantitative insights…")

    try:
        from agents.analyst import AnalystAgent
        analyst = AnalystAgent()

        # Build context from research results for the analyst
        research_results = pipeline_context.get("research_result", {}).get("results", [])
        evidence_text = "\n".join(
            f"[{r.get('title', 'Untitled')}] {r.get('excerpt', '')[:300]}"
            for r in research_results[:5]
        )

        raw_analysis = await analyst.analyse_documents(
            query=query,
            evidence=evidence_text or "No documents retrieved.",
        )
        analyst_result = json.loads(raw_analysis) if raw_analysis else {}
        pipeline_context["analyst_result"] = analyst_result

        msg = "Quantitative analysis complete."
        if analyst_result.get("metrics"):
            msg += f" Extracted {len(analyst_result['metrics'])} metrics."

        step = _step("AnalystAgent", "done", msg)
        reasoning_steps.append(step)
        yield step
    except Exception as exc:
        logger.warning(f"Analyst pipeline stage failed: {exc}")
        step = _step("AnalystAgent", "done", f"Analysis completed with warnings: {str(exc)[:120]}")
        reasoning_steps.append(step)
        yield step

    yield _step("AnalystAgent", "handoff", "Handing off to StrategistAgent…")

    # ── 4. Strategist — investigation planning ────────────────────────────────

    yield _step("StrategistAgent", "thinking", "Planning investigation strategy and coordinating agents…")

    try:
        from agents.strategist import StrategistAgent
        strategist = StrategistAgent()

        raw_strategy = await strategist.investigate(question=query)
        strategy_result = json.loads(raw_strategy) if raw_strategy else {}
        pipeline_context["strategist_result"] = strategy_result

        confidence = strategy_result.get("confidence", "unknown")
        msg = f"Investigation complete — confidence: {confidence}."

        step = _step("StrategistAgent", "done", msg)
        reasoning_steps.append(step)
        yield step
    except Exception as exc:
        logger.warning(f"Strategist pipeline stage failed: {exc}")
        step = _step("StrategistAgent", "done", f"Strategy completed with warnings: {str(exc)[:120]}")
        reasoning_steps.append(step)
        yield step

    yield _step("StrategistAgent", "handoff", "Handing off to ScribeAgent for final synthesis…")

    # ── 5. Scribe — final answer synthesis ────────────────────────────────────

    yield _step("ScribeAgent", "thinking", "Synthesising final answer with citations…")

    final_response = ""
    risk_score = 1

    try:
        # Use the Strategist's result as the primary answer if available
        strat = pipeline_context.get("strategist_result", {})
        if strat.get("answer"):
            final_response = strat["answer"]
        else:
            # Fallback: use Scribe directly
            from agents.scribe import ScribeAgent
            scribe = ScribeAgent()

            research_results = pipeline_context.get("research_result", {}).get("results", [])
            evidence_block = "\n\n".join(
                f"[{r.get('title', 'Untitled')}] (id: {r.get('document_id', 'N/A')})\n"
                f"{r.get('excerpt', '')}"
                for r in research_results[:5]
            )

            raw_draft = await scribe.draft_answer(
                query=query,
                evidence=evidence_block or "No evidence available.",
            )
            scribe_result = json.loads(raw_draft) if raw_draft else {}
            pipeline_context["scribe_result"] = scribe_result
            final_response = scribe_result.get("answer", "Unable to generate a response.")

        # Compute risk score from watchdog alerts
        watchdog_data = pipeline_context.get("watchdog_result", {})
        critical_count = watchdog_data.get("critical_count", 0)
        warning_count = watchdog_data.get("warning_count", 0)
        risk_score = min(10, max(1, critical_count * 3 + warning_count))

        step = _step("ScribeAgent", "done", "Final answer synthesised with citations.")
        reasoning_steps.append(step)
        yield step

    except Exception as exc:
        logger.warning(f"Scribe pipeline stage failed: {exc}")
        final_response = "I was unable to fully synthesise an answer. Please try again."
        step = _step("ScribeAgent", "done", f"Synthesis completed with warnings: {str(exc)[:120]}")
        reasoning_steps.append(step)
        yield step

    # ── Final result ──────────────────────────────────────────────────────────

    strat = pipeline_context.get("strategist_result", {})

    yield {
        "type": "final",
        "response": final_response,
        "risk_score": risk_score,
        "citations": strat.get("citations", []),
        "confidence": strat.get("confidence", "medium"),
        "suggested_actions": strat.get("suggested_actions", []),
        "suggested_followups": strat.get("suggested_followups", []),
        "reasoning_steps": reasoning_steps,
    }
