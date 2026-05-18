"""
BaseAgent: shared Semantic Kernel planner wiring + retry / tracing logic.

Every specialist agent inherits from BaseAgent to get:
- Optional Kernel reference for SK-based invocations
- Structured trace list for the agent execution timeline
- Exponential-backoff retry helper for transient Azure failures
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from agents._compat import Kernel

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all Iroko AI agents.
    Provides tracing, retry logic, and optional Semantic Kernel integration.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        self.kernel = kernel
        self.trace: list[dict] = []

    # ── Tracing ───────────────────────────────────────────────────────────────

    def _log_trace(self, agent: str, tool: str, description: str) -> None:
        """Append a structured trace entry and emit a log line."""
        entry = {
            "agent": agent,
            "tool": tool,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.trace.append(entry)
        logger.info(f"[{agent}] {tool}: {description}")

    # ── Retry helper ──────────────────────────────────────────────────────────

    async def _with_retry(self, coro_func, *args, retries: int = 3, delay: float = 1.0, **kwargs):
        """
        Retry an async callable with exponential backoff.

        Parameters
        ----------
        coro_func : callable
            An async function (NOT an already-awaited coroutine).
        retries : int
            Maximum number of attempts.
        delay : float
            Initial delay in seconds; doubles on each retry.
        """
        last_error: Exception = RuntimeError("No attempts made")
        for attempt in range(1, retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    wait = delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Retry {attempt}/{retries} failed: {exc!r} — "
                        f"retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"All {retries} retry attempts exhausted. "
                        f"Last error: {last_error!r}"
                    )
        raise last_error
