"""
agent_capabilities.py — Per-agent capability scoping (Heimdall pattern).

Defines what each specialist agent is ALLOWED to access, preventing scope
creep where an agent calls tools outside its domain.

Usage
-----
From an agent module::

    from services.agent_capabilities import capability_guard, AgentCapability

    # Raises PermissionError if ResearcherAgent doesn't have FETCH_REGULATORY
    capability_guard.require("ResearcherAgent", AgentCapability.FETCH_REGULATORY)

Or with the decorator::

    from services.agent_capabilities import requires_capability, AgentCapability

    @requires_capability("WatchdogAgent", AgentCapability.FETCH_FRAUD_SIGNALS)
    async def my_handler(...):
        ...
"""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability enum
# ---------------------------------------------------------------------------

class AgentCapability(Enum):
    """Atomic capabilities that can be granted to an agent."""

    FETCH_REGULATORY  = auto()
    FETCH_COMPETITOR  = auto()
    FETCH_VENDOR_RISK = auto()
    FETCH_FRAUD_SIGNALS = auto()
    FETCH_MARKET_INTEL  = auto()
    SEARCH_AZURE      = auto()
    WRITE_AUDIT       = auto()
    READ_AUDIT        = auto()
    GENERATE_REPORT   = auto()
    DEBATE            = auto()


# ---------------------------------------------------------------------------
# Static capability map
# ---------------------------------------------------------------------------

AGENT_CAPABILITY_MAP: dict[str, set[AgentCapability]] = {
    "ResearcherAgent": {
        AgentCapability.FETCH_REGULATORY,
        AgentCapability.SEARCH_AZURE,
        AgentCapability.READ_AUDIT,
    },
    "WatchdogAgent": {
        AgentCapability.FETCH_COMPETITOR,
        AgentCapability.FETCH_FRAUD_SIGNALS,
        AgentCapability.WRITE_AUDIT,
        AgentCapability.READ_AUDIT,
    },
    "AnalystAgent": {
        AgentCapability.FETCH_VENDOR_RISK,
        AgentCapability.SEARCH_AZURE,
        AgentCapability.DEBATE,
        AgentCapability.WRITE_AUDIT,
    },
    "StrategistAgent": {
        AgentCapability.FETCH_MARKET_INTEL,
        AgentCapability.READ_AUDIT,
        AgentCapability.GENERATE_REPORT,
        AgentCapability.WRITE_AUDIT,
    },
    "ScribeAgent": {
        AgentCapability.READ_AUDIT,
        AgentCapability.GENERATE_REPORT,
    },
}

# Maps each FETCH_* capability to the exact function name in web_intelligence.py
_CAPABILITY_TO_FETCHER: dict[AgentCapability, str] = {
    AgentCapability.FETCH_REGULATORY:    "fetch_regulatory_signals",
    AgentCapability.FETCH_COMPETITOR:    "fetch_competitor_signals",
    AgentCapability.FETCH_VENDOR_RISK:   "fetch_vendor_risk_signals",
    AgentCapability.FETCH_FRAUD_SIGNALS: "fetch_fraud_signals",
    AgentCapability.FETCH_MARKET_INTEL:  "fetch_market_intelligence",
}


# ---------------------------------------------------------------------------
# CapabilityGuard
# ---------------------------------------------------------------------------

class CapabilityGuard:
    """
    Runtime enforcer for agent capability scoping.

    All public methods are synchronous — capability checks happen before any
    async I/O, so there's no need for async wrappers.
    """

    # ── Core checks ──────────────────────────────────────────────────────────

    def check(self, agent_name: str, capability: AgentCapability) -> bool:
        """
        Return True if *agent_name* holds *capability*, False otherwise.

        Unknown agent names always return False (fail-closed).
        """
        allowed = AGENT_CAPABILITY_MAP.get(agent_name, set())
        return capability in allowed

    def require(self, agent_name: str, capability: AgentCapability) -> None:
        """
        Assert that *agent_name* holds *capability*.

        Raises
        ------
        PermissionError
            If the agent does not have the requested capability.
        """
        granted = self.check(agent_name, capability)
        self.audit_access_attempt(agent_name, capability, granted)
        if not granted:
            raise PermissionError(
                f"{agent_name} does not have capability {capability.name}"
            )

    # ── Utility helpers ──────────────────────────────────────────────────────

    def get_allowed_web_fetchers(self, agent_name: str) -> list[str]:
        """
        Return the list of ``web_intelligence.py`` function names that
        *agent_name* is permitted to call.

        Returns an empty list for unknown agents.
        """
        allowed = AGENT_CAPABILITY_MAP.get(agent_name, set())
        return [
            fn_name
            for cap, fn_name in _CAPABILITY_TO_FETCHER.items()
            if cap in allowed
        ]

    def audit_access_attempt(
        self,
        agent_name: str,
        capability: AgentCapability,
        granted: bool,
    ) -> dict:
        """
        Build and return a structured log entry for an access attempt.

        The entry is also emitted at DEBUG level (granted) or WARNING level
        (denied) so it shows up in the application log stream.
        """
        entry: dict = {
            "agent":      agent_name,
            "capability": capability.name,
            "granted":    granted,
            "timestamp":  datetime.now(tz=timezone.utc).isoformat(),
        }
        if granted:
            logger.debug(
                "[CapabilityGuard] GRANTED  %s → %s",
                agent_name,
                capability.name,
            )
        else:
            logger.warning(
                "[CapabilityGuard] DENIED   %s → %s",
                agent_name,
                capability.name,
            )
        return entry

    # ── Introspection ────────────────────────────────────────────────────────

    def list_capabilities(self, agent_name: str) -> list[str]:
        """Return the sorted list of capability names held by *agent_name*."""
        return sorted(
            cap.name for cap in AGENT_CAPABILITY_MAP.get(agent_name, set())
        )

    def all_agents(self) -> list[str]:
        """Return all registered agent names."""
        return list(AGENT_CAPABILITY_MAP.keys())


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def requires_capability(
    agent_name: str,
    capability: AgentCapability,
) -> Callable:
    """
    Decorator that enforces a capability check before the decorated function
    runs.  Works with both regular and async functions.

    Example::

        @requires_capability("WatchdogAgent", AgentCapability.FETCH_FRAUD_SIGNALS)
        async def fetch_live_fraud(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if _is_async(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                capability_guard.require(agent_name, capability)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                capability_guard.require(agent_name, capability)
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator


def _is_async(func: Callable) -> bool:
    """Return True if *func* is a native coroutine function."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

capability_guard = CapabilityGuard()
