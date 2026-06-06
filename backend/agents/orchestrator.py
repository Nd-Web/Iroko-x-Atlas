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


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Web Intelligence streaming pipeline (async generator for FastAPI SSE)
# ═══════════════════════════════════════════════════════════════════════════════

def _wi_step(
    agent: str,
    step: str,
    content: str,
    status: str = "running",
    **extra,
) -> dict:
    """
    Build a standardised web-intel pipeline step dict.

    All extra keyword arguments are merged at the top level, allowing
    individual steps to attach structured payloads (signal counts, entity
    lists, verdict dicts, etc.) without breaking the base contract.
    """
    return {
        "agent":     agent,
        "step":      step,
        "content":   content,
        "status":    status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **extra,
    }


def _wi_error(step: str, exc: Exception) -> dict:
    """Standardised error frame emitted when a pipeline step fails."""
    logger.error("[web_intel_pipeline] step=%s error=%r", step, exc, exc_info=True)
    return {
        "agent":     "Pipeline",
        "step":      step,
        "status":    "error",
        "error":     str(exc)[:300],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def _count_signals(all_signals: dict) -> dict[str, int]:
    """Return per-category signal counts from run_all_signals() output."""
    return {
        category: len(signals) if isinstance(signals, list) else 0
        for category, signals in all_signals.items()
        if not category.startswith("_")
    }


def _top_signal(all_signals: dict) -> dict:
    """
    Return the single highest-priority signal across all categories for use
    as the historical-context probe.  Priority order: fraud > regulatory >
    vendor_risk > competitor > market.
    """
    priority_order = ["fraud_signals", "regulatory_signals", "vendor_risk_signals",
                      "competitor_signals", "market_signals"]
    for key in priority_order:
        bucket = all_signals.get(key, [])
        if bucket:
            return bucket[0]
    # Fallback: first signal found anywhere
    for v in all_signals.values():
        if isinstance(v, list) and v:
            return v[0]
    return {}


def _derive_verdict_inputs(
    all_signals: dict,
    compound_risks: list[dict],
    compliance_result: dict,
) -> tuple[float, dict]:
    """
    Compute confidence score and a compliance_result dict suitable for
    VerdictEngine.compute_verdict() from the three upstream outputs.

    Returns (confidence_score, normalised_compliance_result).
    """
    # --- confidence: weighted mix of signal volume + compound-risk density ---
    signal_counts = _count_signals(all_signals)
    total = sum(signal_counts.values()) or 1

    # Fraud and regulatory signals carry higher weight
    weighted = (
        signal_counts.get("fraud_signals", 0) * 1.0
        + signal_counts.get("regulatory_signals", 0) * 0.8
        + signal_counts.get("vendor_risk_signals", 0) * 0.7
        + signal_counts.get("competitor_signals", 0) * 0.4
        + signal_counts.get("market_signals", 0) * 0.3
    )
    base_confidence = min(0.95, weighted / max(total, 1))

    # Compound risks bump confidence because correlated signals are stronger
    compound_boost = min(0.15, len(compound_risks) * 0.05)
    confidence = min(0.95, base_confidence + compound_boost)

    # --- normalise compliance_result to what VerdictEngine expects ---
    norm = {
        "verdict":   compliance_result.get("verdict", "MONITOR"),
        "compliant": compliance_result.get("compliant", True),
        "violations": compliance_result.get("violations", []),
    }
    # Hard escalate: any compound risk with score > 0.7 forces NO-GO
    if any(r.get("compound_risk_score", 0) > 0.7 for r in compound_risks):
        norm["verdict"] = "NO-GO"
        norm["compliant"] = False

    return confidence, norm


async def web_intel_pipeline(
    query: str,
    db,
    workspace_id: str | None = None,
) -> "AsyncGenerator[dict, None]":
    """
    Streaming six-stage web intelligence pipeline.

    Each stage yields one or more dicts that a FastAPI SSE endpoint can
    forward directly to the browser.  Every stage is wrapped in its own
    try/except so a partial failure emits an error frame and continues —
    the pipeline never dies silently.

    Stages
    ------
    1. FETCH      — run_all_signals() across 5 Bright Data domains
    2. REGULATORY — compile_live_enforcement_rules() + NCC corpus diff
    3. GRAPH      — build signal correlation graph, find compound risks
    4. MEMORY     — inject institutional historical context
    5. COMPLIANCE — check query against live NCC rules
    6. VERDICT    — compute final GO/NO-GO/MONITOR + log to audit trail

    Parameters
    ----------
    query : str
        The user's natural-language intelligence query.
    db : sqlalchemy.orm.Session
        Active DB session (passed from the FastAPI dependency).
    workspace_id : str, optional
        Tenant/workspace scoping for audit trail entries.

    Yields
    ------
    dict
        Step frames with at minimum: agent, step, content, status, timestamp.
        Final "done" frame includes a full ``summary`` dict.
    """
    # Accumulated state threaded through stages
    all_signals:       dict       = {}
    regulatory_data:   dict       = {}
    compound_risks:    list[dict] = []
    historical_ctx:    str        = "No historical context available."
    compliance_result: dict       = {}
    final_verdict_output: dict    = {}

    # ── Stage 1 — FETCH WEB SIGNALS ──────────────────────────────────────────

    yield _wi_step(
        "WebIntelligence", "fetch",
        "Activating Bright Data connectors across 5 intelligence domains…",
    )

    try:
        from services.web_intelligence import run_all_signals
        from services.brightdata import bright_data_client

        all_signals = await run_all_signals(bright_data_client)
        counts = _count_signals(all_signals)
        total_signals = sum(counts.values())

        summary_parts = ", ".join(
            f"{v} {k.replace('_signals', '').replace('_', ' ')}"
            for k, v in counts.items() if v > 0
        )
        yield _wi_step(
            "WebIntelligence", "fetch",
            f"Signal sweep complete — {total_signals} signals ingested: {summary_parts}.",
            status="done",
            signal_counts=counts,
            total_signals=total_signals,
        )
    except Exception as exc:
        yield _wi_error("fetch", exc)
        # Non-fatal: continue with empty signals so downstream stages degrade
        # gracefully rather than aborting the whole pipeline.

    # ── Stage 2 — REGULATORY SCAN ────────────────────────────────────────────

    yield _wi_step(
        "Regulatory", "ncc_scan",
        "Fetching live NCC enforcement updates and diffing against corpus…",
    )

    try:
        from services.ncc_live_rules import ncc_rules_service

        regulatory_data = await ncc_rules_service.compile_live_enforcement_rules()
        live_updates   = regulatory_data.get("live_updates",        [])
        high_priority  = regulatory_data.get("high_priority_alerts", [])
        new_obligations = regulatory_data.get("new_obligations",    [])
        base_regs      = regulatory_data.get("base_regulations",    [])

        # Build a human-readable delta summary
        delta_parts = []
        if live_updates:
            delta_parts.append(f"{len(live_updates)} live update(s)")
        if high_priority:
            delta_parts.append(f"{len(high_priority)} high-priority alert(s)")
        if new_obligations:
            delta_parts.append(f"{len(new_obligations)} new obligation(s)")

        delta_str = (
            ", ".join(delta_parts) + " detected"
            if delta_parts
            else "corpus is current — no new changes"
        )

        yield _wi_step(
            "Regulatory", "ncc_scan",
            (
                f"NCC scan complete. {len(base_regs)} base regulations in corpus. "
                f"Delta: {delta_str}."
            ),
            status="done",
            regulatory_summary={
                "base_regulation_count": len(base_regs),
                "live_update_count":     len(live_updates),
                "high_priority_count":   len(high_priority),
                "new_obligation_count":  len(new_obligations),
            },
        )
    except Exception as exc:
        yield _wi_error("ncc_scan", exc)

    # ── Stage 3 — SIGNAL GRAPH ANALYSIS ──────────────────────────────────────

    yield _wi_step(
        "SignalGraph", "correlation",
        "Building directed signal-entity graph and detecting compound risks…",
    )

    try:
        from services.signal_graph import signal_graph_service

        graph = signal_graph_service.build_signal_graph(all_signals)
        compound_risks = signal_graph_service.get_high_risk_entities(graph, threshold=0.5)

        node_count = graph.number_of_nodes() if graph else 0
        edge_count = graph.number_of_edges() if graph else 0

        # Surface top entities for the step payload
        top_entities = [
            {
                "entity":              r.get("entity"),
                "entity_type":         r.get("entity_type"),
                "signal_count":        r.get("signal_count"),
                "compound_risk_score": round(r.get("compound_risk_score", 0), 3),
            }
            for r in compound_risks[:5]
        ]

        yield _wi_step(
            "SignalGraph", "correlation",
            (
                f"Graph analysis complete — {node_count} nodes, {edge_count} edges. "
                f"{len(compound_risks)} compound risk(s) detected"
                + (f": {', '.join(e['entity'] for e in top_entities[:3])}." if top_entities else ".")
            ),
            status="done",
            compound_risk_count=len(compound_risks),
            top_entities=top_entities,
            graph_stats={"nodes": node_count, "edges": edge_count},
        )
    except Exception as exc:
        yield _wi_error("correlation", exc)
        compound_risks = []

    # ── Stage 4 — HISTORICAL CONTEXT ─────────────────────────────────────────

    yield _wi_step(
        "Memory", "historical_context",
        "Querying institutional memory for analogous past regulatory events…",
    )

    try:
        from services.regulatory_memory import regulatory_memory

        top_sig = _top_signal(all_signals)
        # Augment the top signal with the user query so memory search is richer
        probe_signal = {**top_sig, "query": query} if top_sig else {"query": query}

        historical_ctx = await regulatory_memory.generate_historical_context(
            db=db, current_signal=probe_signal
        )

        has_match = "No similar historical events" not in historical_ctx
        yield _wi_step(
            "Memory", "historical_context",
            (
                "Historical match found — injecting institutional context into downstream analysis."
                if has_match
                else "No historical precedents matched. Proceeding without memory augmentation."
            ),
            status="done",
            historical_context=historical_ctx,
            memory_hit=has_match,
        )
    except Exception as exc:
        yield _wi_error("historical_context", exc)
        historical_ctx = "Historical context unavailable due to service error."

    # ── Stage 5 — COMPLIANCE CHECK ────────────────────────────────────────────

    yield _wi_step(
        "Compliance", "ncc_check",
        f"Running query against live NCC rule corpus: \"{query[:100]}\"…",
    )

    try:
        from services.ncc_live_rules import ncc_rules_service
        from services.audit_service import AuditService

        compliance_result = await ncc_rules_service.check_decision_against_rules(query)

        # Extract meaningful fields for the step payload
        is_compliant  = compliance_result.get("compliant", True)
        verdict_str   = compliance_result.get("verdict", "MONITOR")
        violations    = compliance_result.get("violations", [])
        ncc_refs      = [v.get("regulation_id", "") for v in violations if v.get("regulation_id")]
        confidence_sc = compliance_result.get("confidence_score", None)

        # Write to audit trail — failure here must not abort the pipeline
        try:
            await AuditService.log_decision(
                db=db,
                agent_name="WebIntelPipeline",
                action_type="compliance_check",
                decision_summary=f"Web intel compliance check for query: {query[:200]}",
                verdict=verdict_str,
                ncc_ref=ncc_refs[0] if ncc_refs else None,
                confidence=confidence_sc,
                workspace_id=workspace_id,
            )
        except Exception as audit_exc:
            logger.warning("[web_intel_pipeline] Audit log write failed: %r", audit_exc)

        yield _wi_step(
            "Compliance", "ncc_check",
            (
                f"Compliance check complete — verdict: {verdict_str}. "
                + (
                    f"{len(violations)} violation(s) flagged: "
                    + ", ".join(v.get("reason", "")[:60] for v in violations[:3])
                    if violations
                    else "No violations detected."
                )
            ),
            status="done",
            compliant=is_compliant,
            verdict=verdict_str,
            violation_count=len(violations),
            violations=violations[:10],  # cap payload size
            ncc_refs=ncc_refs,
        )
    except Exception as exc:
        yield _wi_error("ncc_check", exc)
        compliance_result = {"compliant": True, "verdict": "MONITOR", "violations": []}

    # ── Stage 6 — VERDICT ─────────────────────────────────────────────────────

    yield _wi_step(
        "VerdictEngine", "verdict",
        "Computing final compound verdict from all signal streams…",
    )

    try:
        from services.verdict_engine import verdict_engine

        confidence_score, norm_compliance = _derive_verdict_inputs(
            all_signals, compound_risks, compliance_result
        )

        final_verdict = verdict_engine.compute_verdict(
            confidence=confidence_score,
            compliance_result=norm_compliance,
            signal_strength=min(10, sum(_count_signals(all_signals).values())),
        )

        # Build a rich finding dict for format_verdict_output
        top_entities_summary = (
            ", ".join(r.get("entity", "") for r in compound_risks[:3])
            or "none"
        )
        violation_count = len(compliance_result.get("violations", []))

        finding = {
            "summary": (
                f"Web intelligence query: \"{query[:120]}\". "
                f"Compound risks: {len(compound_risks)} entity/entities flagged "
                f"({top_entities_summary}). "
                f"NCC violations: {violation_count}. "
                f"Historical context: {historical_ctx[:200]}."
            ),
            "confidence_score":     confidence_score,
            "action_type":          "web_intelligence_scan",
            "ncc_regulation_ref":   (
                compliance_result.get("violations", [{}])[0].get("regulation_id")
                if compliance_result.get("violations") else None
            ),
        }

        signal_sources = [
            {"title": s.get("title", "Signal"), "url": s.get("url", "")}
            for bucket in all_signals.values()
            if isinstance(bucket, list)
            for s in bucket[:2]  # 2 sources per category max
        ][:10]

        ncc_refs_final = list({
            v.get("regulation_id", "")
            for v in compliance_result.get("violations", [])
            if v.get("regulation_id")
        })

        final_verdict_output = verdict_engine.format_verdict_output(
            finding=finding,
            verdict=final_verdict,
            sources=signal_sources,
            ncc_refs=ncc_refs_final,
            confidence_score=confidence_score,
        )

        yield _wi_step(
            "VerdictEngine", "final",
            (
                f"Final verdict: {final_verdict} "
                f"(confidence {confidence_score:.0%}). "
                f"{len(compound_risks)} compound risk(s), "
                f"{violation_count} NCC violation(s)."
            ),
            status="complete",
            verdict=final_verdict,
            confidence_score=round(confidence_score, 4),
            compound_risk_count=len(compound_risks),
            violation_count=violation_count,
            verdict_output=final_verdict_output,
        )
    except Exception as exc:
        yield _wi_error("verdict", exc)
        final_verdict_output = {}

    # ── Done — emit full summary frame ────────────────────────────────────────

    signal_counts_final = _count_signals(all_signals)

    yield {
        "agent":     "Pipeline",
        "step":      "done",
        "content":   "Web intelligence pipeline complete.",
        "status":    "done",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "query":                query,
            "workspace_id":         workspace_id,
            "signal_counts":        signal_counts_final,
            "total_signals":        sum(signal_counts_final.values()),
            "compound_risks":       compound_risks,
            "compound_risk_count":  len(compound_risks),
            "compliance_verdict":   compliance_result.get("verdict", "UNKNOWN"),
            "compliance_violations": compliance_result.get("violations", []),
            "historical_context":   historical_ctx,
            "final_verdict":        final_verdict_output,
            "regulatory_summary":   {
                "live_updates":      len(regulatory_data.get("live_updates", [])),
                "high_priority":     len(regulatory_data.get("high_priority_alerts", [])),
                "new_obligations":   len(regulatory_data.get("new_obligations", [])),
            },
            "pipeline_completed_at": datetime.utcnow().isoformat() + "Z",
        },
    }
