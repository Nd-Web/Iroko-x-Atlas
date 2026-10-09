"""
The one way graph extraction calls a model.

* Reserves budget first (budget.reserve commits), then paces.
* Never holds a database lock across the call: reserve() commits, and callers
  must not have uncommitted row locks when they call ask_json.
* A malformed reply is returned as None for the stage to handle (halve the
  batch, then skip it). json.JSONDecodeError is a ValueError, which the worker
  would otherwise treat as a permanent failure.
* "No model configured" and "every model failed" both raise ModelUnavailable,
  which the job turns into a deferral instead of a failure.
"""

from __future__ import annotations

import json
import logging

from services.compliance_graph import budget

logger = logging.getLogger(__name__)


class ModelUnavailable(Exception):
    pass


def default_complete():
    from agents.kernel import llm_complete

    return llm_complete


def model_name() -> str:
    from services.llm_settings import responses_configured, responses_deployment

    if responses_configured():
        return responses_deployment()
    import os

    return os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT", "") or os.getenv("AZURE_OPENAI_DEPLOYMENT", "") or "unconfigured"


async def ask_json(db, *, workspace_id, prompt, system, schema, max_tokens, complete=None, usage=None):
    """Call the model with a strict JSON schema. Returns a dict, or None when the reply is unusable."""
    complete = complete or default_complete()
    tokens = budget.call_tokens(prompt, system, max_tokens)
    budget.reserve(db, workspace_id, tokens)
    await budget.pacer.wait(tokens)
    if usage is not None:
        usage["tokens"] = usage.get("tokens", 0) + tokens
        usage["calls"] = usage.get("calls", 0) + 1
    try:
        raw = await complete(prompt, max_tokens=max_tokens, system_prompt=system, json_schema=schema,
                             service_id="gpt4o")
    except RuntimeError as exc:
        raise ModelUnavailable(str(exc)[:300]) from exc
    if not raw:
        raise ModelUnavailable("No language model is configured for graph extraction")
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("Graph extraction: model returned invalid JSON (%d chars)", len(raw))
        return None
    return data if isinstance(data, dict) else None
