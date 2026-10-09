"""
Model-token budgets and pacing for graph extraction.

Tokens are reserved and committed BEFORE each paid call, the way OCR pages are
(ingestion.pipeline.reserve_ocr), so failed calls still count. The estimate is
the prompt plus the maximum output Azure counts against quota, including the
reasoning headroom llm_settings adds for gpt-6.x models.

The worker shares the model's per-minute quota with live chat, so a per-minute
token bucket keeps a backfill from starving chat answers.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from services.compliance_graph.common import LAGOS, lagos_today


class BudgetExhausted(Exception):
    """The daily budget is used up; retry after `until` (naive UTC)."""

    def __init__(self, scope: str, until: datetime):
        super().__init__(f"Daily model budget reached for {scope}")
        self.scope = scope
        self.until = until


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def daily_limit() -> int:
    return _int_env("GRAPH_DAILY_TOKEN_BUDGET", 2_000_000)


def workspace_daily_limit() -> int:
    return _int_env("GRAPH_WORKSPACE_DAILY_TOKEN_BUDGET", 1_000_000)


def per_minute_limit() -> int:
    return _int_env("GRAPH_TOKENS_PER_MINUTE", 30_000)


_ENCODER = None


def estimate_tokens(text: str) -> int:
    global _ENCODER
    if not text:
        return 0
    if _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODER = False  # no encoding available (e.g. no egress): estimate, and do not retry each call
    if _ENCODER:
        try:
            return len(_ENCODER.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 3)


def call_tokens(prompt: str, system: str, max_tokens: int) -> int:
    from services.llm_settings import responses_configured, responses_kwargs

    output = responses_kwargs(max_tokens)["max_output_tokens"] if responses_configured() else max_tokens
    return estimate_tokens(system) + estimate_tokens(prompt) + output


def next_lagos_midnight_utc() -> datetime:
    """When the next Lagos day starts, as naive UTC (the queue's clock)."""
    tomorrow = lagos_today() + timedelta(days=1)
    local_midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=LAGOS)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def reserve(db, workspace_id: str | None, tokens: int) -> None:
    """Reserve tokens against the global and workspace budgets, or raise BudgetExhausted."""
    from models.compliance_graph import GraphBudget

    day = lagos_today().isoformat()
    scopes = [("global", daily_limit())]
    if workspace_id:
        scopes.append((workspace_id, workspace_daily_limit()))
    rows = []
    for scope, limit in scopes:
        row = (
            db.query(GraphBudget)
            .filter(GraphBudget.day == day, GraphBudget.scope == scope)
            .with_for_update()
            .first()
        )
        if row is None:
            row = GraphBudget(day=day, scope=scope, tokens=0)
            db.add(row)
        if row.tokens + tokens > limit:
            db.rollback()
            raise BudgetExhausted(scope, next_lagos_midnight_utc())
        rows.append(row)
    for row in rows:
        row.tokens = (row.tokens or 0) + tokens
    db.commit()  # Reserve before paid work, including failed calls.


def used_today(db, scope: str = "global") -> int:
    from models.compliance_graph import GraphBudget

    row = db.get(GraphBudget, (lagos_today().isoformat(), scope))
    return row.tokens if row else 0


class Pacer:
    """In-process per-minute token bucket (the worker runs one job at a time)."""

    def __init__(self):
        self.window: deque[tuple[float, int]] = deque()

    def _used(self, now: float) -> int:
        while self.window and now - self.window[0][0] >= 60:
            self.window.popleft()
        return sum(tokens for _t, tokens in self.window)

    async def wait(self, tokens: int) -> None:
        limit = per_minute_limit()
        if limit <= 0:
            return
        while True:
            now = time.monotonic()
            used = self._used(now)
            if not self.window or used + tokens <= limit:
                self.window.append((now, tokens))
                return
            await asyncio.sleep(min(5.0, max(0.5, 60 - (now - self.window[0][0]))))


pacer = Pacer()
