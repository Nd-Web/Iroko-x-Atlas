"""
services/memory.py — Thread-safe in-memory conversation history manager.

Provides a singleton ``conversation_memory`` instance used by routes and
agents to persist short-term dialogue context across turns.
"""

from __future__ import annotations

import asyncio
from typing import Optional


class ConversationMemory:
    """
    In-memory conversation memory store.

    Stores the last N messages per conversation_id so that the orchestrator
    can inject recent dialogue context into agent prompts.

    Thread-safe via ``asyncio.Lock`` — safe for use in async FastAPI handlers.

    Parameters
    ----------
    max_messages : int
        Maximum messages to retain per conversation (oldest are evicted).
    """

    def __init__(self, max_messages: int = 50) -> None:
        self._max = max_messages
        self._store: dict[str, list[dict]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Append a message to the conversation history.

        Parameters
        ----------
        conversation_id : str
            Unique identifier for the conversation thread.
        role : str
            ``"user"`` or ``"assistant"``.
        content : str
            Text content of the message.
        """
        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append({"role": role, "content": content})
            # Evict oldest messages if over limit
            if len(self._store[conversation_id]) > self._max:
                self._store[conversation_id] = self._store[conversation_id][-self._max :]

    async def get_history(
        self,
        conversation_id: str,
        last_n: int = 10,
    ) -> list[dict]:
        """
        Return the last N messages for a conversation.

        Parameters
        ----------
        conversation_id : str
            Target conversation thread.
        last_n : int
            Number of most recent messages to return (default 10).

        Returns
        -------
        list[dict]
            Each dict has ``"role"`` and ``"content"`` keys.
        """
        async with self._lock:
            history = self._store.get(conversation_id, [])
            return list(history[-last_n:])

    async def format_for_prompt(
        self,
        conversation_id: str,
        last_n: int = 10,
    ) -> str:
        """
        Return recent history formatted as a plain-text dialogue block
        suitable for injection into an agent system prompt.

        Example output::

            User: What is the IHS tower lease fee?
            Assistant: The monthly fee is NGN 45,000,000 per Article 1.

        Parameters
        ----------
        conversation_id : str
            Target conversation thread.
        last_n : int
            Number of recent messages to include (default 10).

        Returns
        -------
        str
            Formatted dialogue string, or empty string if no history.
        """
        history = await self.get_history(conversation_id, last_n=last_n)
        if not history:
            return ""
        lines: list[str] = []
        for msg in history:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "").strip()
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def clear(self, conversation_id: str) -> None:
        """Remove all stored messages for a conversation."""
        async with self._lock:
            self._store.pop(conversation_id, None)

    async def clear_all(self) -> None:
        """Flush the entire memory store (e.g. on shutdown)."""
        async with self._lock:
            self._store.clear()

    @property
    def active_conversations(self) -> int:
        """Number of conversation threads currently in memory."""
        return len(self._store)


# ── Singleton ─────────────────────────────────────────────────────────────────

conversation_memory = ConversationMemory(max_messages=50)
