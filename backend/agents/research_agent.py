"""
ResearchAgent: thin wrapper around the Researcher class (researcher.py).
Deep-dives topics via Azure AI Search + GPT-4o RAG pipeline.
"""
import json
import logging
from typing import Optional

from agents._compat import Kernel
from agents.base_agent import BaseAgent
from agents.researcher import ResearcherAgent as Researcher

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    """
    Wrapper that delegates to the existing Researcher kernel plugin
    while adding BaseAgent tracing and retry logic.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        super().__init__(kernel=kernel)
        self._researcher = Researcher()

    async def research(self, question: str, top: int = 10) -> list[dict]:
        """
        Search enterprise documents for evidence relevant to a question.

        Parameters
        ----------
        question : str
            Natural-language query to search for.
        top : int
            Maximum number of results to return (after reranking).

        Returns
        -------
        list[dict]
            List of search result dicts with document_id, title, excerpt, etc.
        """
        self._log_trace("Researcher", "search_start", f"Searching: '{question[:60]}'")

        try:
            raw = await self._with_retry(
                self._researcher.search_documents,
                query=question,
                top_k=top,
            )
            parsed = json.loads(raw)
            results = parsed.get("results", [])
        except Exception as exc:
            logger.error(f"ResearchAgent.research failed: {exc}")
            results = []

        self._log_trace(
            "Researcher", "search_end",
            f"Found {len(results)} results"
        )
        return results
