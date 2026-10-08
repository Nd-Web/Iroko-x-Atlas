"""
services/llm_settings.py

Which models Iroko calls, and how. Shared by every LLM call site
(agents/kernel.py, services/azure_openai.py) so they cannot drift apart.

  Primary  — the Azure Responses API deployment (AZURE_OPENAI_RESPONSES_*),
             e.g. gpt-6.1-sol. Used whenever its endpoint and key are set.
  Fallback — the Chat Completions deployments (AZURE_OPENAI_ENDPOINT/API_KEY,
             e.g. gpt-5.4-nano). Used when the primary is unconfigured, or when
             it is rate-limited, down, or misconfigured, so chat keeps working.

Reasoning effort: GPT-5.x accepts "none"; GPT-6.1 Sol accepts only low, medium,
high, xhigh and max ("none" is rejected). Reasoning tokens count against the
output budget, so any effort above "none" gets extra headroom — otherwise the
reasoning can use the whole budget and return an empty answer.
"""

from __future__ import annotations

import os

VALID_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def responses_configured() -> bool:
    return bool(_env("AZURE_OPENAI_RESPONSES_ENDPOINT") and _env("AZURE_OPENAI_RESPONSES_API_KEY"))


def chat_configured() -> bool:
    return bool(_env("AZURE_OPENAI_ENDPOINT") and _env("AZURE_OPENAI_API_KEY"))


def responses_deployment() -> str:
    return _env("AZURE_OPENAI_RESPONSES_DEPLOYMENT", "gpt-5.6-sol")


def responses_effort() -> str:
    """Reasoning effort for the primary model.

    AZURE_OPENAI_RESPONSES_REASONING_EFFORT overrides; otherwise GPT-6.x gets
    "low" (it has no "none") and older models keep "none".
    """
    explicit = _env("AZURE_OPENAI_RESPONSES_REASONING_EFFORT").lower()
    if explicit in VALID_EFFORTS:
        return explicit
    return "low" if responses_deployment().lower().startswith("gpt-6") else "none"


def reasoning_headroom(effort: str) -> int:
    """Extra output tokens reserved for reasoning when effort is above "none"."""
    if effort == "none":
        return 0
    try:
        return max(0, int(_env("AZURE_OPENAI_REASONING_HEADROOM", "2000")))
    except ValueError:
        return 2000


def responses_kwargs(max_tokens: int) -> dict:
    """max_output_tokens + reasoning arguments for a Responses API call."""
    effort = responses_effort()
    return {"max_output_tokens": max_tokens + reasoning_headroom(effort), "reasoning": {"effort": effort}}


def fallback_deployment() -> str:
    """The Chat Completions deployment used when the primary cannot answer (default: the nano deployment)."""
    return _env("AZURE_OPENAI_FALLBACK_DEPLOYMENT") or _env("AZURE_OPENAI_NANO_DEPLOYMENT", "gpt-5.6-luna")


def fallback_enabled() -> bool:
    """The Chat Completions deployment stands behind the primary unless LLM_FALLBACK=false."""
    return chat_configured() and _env("LLM_FALLBACK", "true").lower() not in {"false", "0", "no", "off"}


def primary_rate_limit_wait() -> float:
    """Seconds the primary may wait out throttling before handing over to the fallback."""
    try:
        return max(0.0, float(_env("LLM_PRIMARY_RATE_LIMIT_WAIT", "8")))
    except ValueError:
        return 8.0


def describe() -> dict:
    """Non-secret summary for health checks and logs."""
    primary = responses_deployment() if responses_configured() else None
    return {
        "primary": primary,
        "primary_reasoning_effort": responses_effort() if primary else None,
        "fallback": fallback_deployment() if fallback_enabled() and primary else None,
        "chat_completions_only": None if primary else (_env("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.6-terra") if chat_configured() else None),
    }
