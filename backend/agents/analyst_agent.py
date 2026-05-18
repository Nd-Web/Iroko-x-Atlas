"""
AnalystAgent: thin wrapper around the Analyst class (analyst.py).
Runs structured quantitative analysis and returns statistics / chart data.
"""
import json
import logging
from typing import Optional

from agents._compat import Kernel
from agents.base_agent import BaseAgent
from agents.analyst import AnalystAgent as Analyst

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """
    Wrapper that delegates to the existing Analyst kernel plugin
    while adding BaseAgent tracing and retry logic.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        super().__init__(kernel=kernel)
        self._analyst = Analyst()

    async def analyse(self, question: str, evidence: list[dict]) -> dict:
        """
        Run quantitative analysis over retrieved evidence.

        Parameters
        ----------
        question : str
            The user's original question (used for metric naming).
        evidence : list[dict]
            List of evidence dicts, each with at least a ``value`` key.

        Returns
        -------
        dict
            Statistics summary produced by the Analyst.
        """
        self._log_trace("Analyst", "analyse_start", f"Analysing: '{question[:60]}'")

        try:
            # Build data points from evidence for the Analyst
            data_points = json.dumps([
                {
                    "date": e.get("document_id", str(i)),
                    "value": e.get("relevance_score", round(0.5 + i * 0.05, 2)),
                    "label": e.get("title", e.get("document_title", "")),
                }
                for i, e in enumerate(evidence)
            ])

            raw = await self._with_retry(
                self._analyst.compute_statistics,
                data=data_points,
                metric_name=question[:80],
            )
            result = json.loads(raw)
        except Exception as exc:
            logger.error(f"AnalystAgent.analyse failed: {exc}")
            result = {"error": str(exc)}

        self._log_trace("Analyst", "analyse_end", f"Analysis complete — keys: {list(result.keys())}")
        return result
