"""
MonitorAgent: thin wrapper around the Watchdog class (watchdog.py).
Watches connected data sources and fires proactive insight events.
"""
import json
import logging
from typing import Optional

from agents._compat import Kernel
from agents.base_agent import BaseAgent
from agents.watchdog import WatchdogAgent as Watchdog

logger = logging.getLogger(__name__)


class MonitorAgent(BaseAgent):
    """
    Wrapper that delegates to the existing Watchdog kernel plugin
    while adding BaseAgent tracing and retry logic.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        super().__init__(kernel=kernel)
        self._watchdog = Watchdog()

    async def monitor(self, question: str, evidence: list[dict]) -> dict:
        """
        Evaluate evidence confidence and check for policy / compliance flags.

        Parameters
        ----------
        question : str
            The user's original question (used for compliance detection).
        evidence : list[dict]
            Retrieved evidence to evaluate.

        Returns
        -------
        dict
            Contains ``confidence``, ``knowledge_gap``, and any ``flags``.
        """
        self._log_trace("Watchdog", "monitor_start", f"Monitoring: '{question[:60]}'")

        try:
            # Determine if compliance-grade threshold should apply
            compliance_keywords = [
                "compliance", "ncc", "ndpa", "cbn", "nitda",
                "regulation", "policy",
            ]
            is_compliance = any(kw in question.lower() for kw in compliance_keywords)

            # Compute an average confidence from evidence relevance scores
            scores = [
                e.get("relevance_score", 0.5)
                for e in evidence
                if isinstance(e.get("relevance_score"), (int, float))
            ]
            avg_confidence = sum(scores) / len(scores) if scores else 0.5

            conf_check = self._watchdog.check_confidence(
                avg_confidence, is_compliance=is_compliance
            )

            # Run proactive alert checks if evidence is sufficient
            flags: list[dict] = []
            if not conf_check.get("knowledge_gap") and evidence:
                try:
                    raw = await self._with_retry(
                        self._watchdog.find_policy_conflicts,
                        topic=question,
                    )
                    parsed = json.loads(raw)
                    flags = parsed.get("conflicts", parsed.get("alerts", []))
                except Exception as exc:
                    logger.warning(f"MonitorAgent policy check failed: {exc}")

            result = {
                "confidence": avg_confidence,
                "knowledge_gap": conf_check.get("knowledge_gap", False),
                "threshold": conf_check.get("threshold"),
                "is_compliance": is_compliance,
                "flags": flags,
            }
        except Exception as exc:
            logger.error(f"MonitorAgent.monitor failed: {exc}")
            result = {"confidence": 0.0, "knowledge_gap": True, "error": str(exc), "flags": []}

        self._log_trace(
            "Watchdog", "monitor_end",
            f"Confidence: {result.get('confidence', 0):.2f} | "
            f"Gap: {result.get('knowledge_gap')}"
        )
        return result
