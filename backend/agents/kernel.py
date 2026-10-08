"""
Atlas — Semantic Kernel Setup
Initialises the kernel with all agents registered as plugins.
Only used when Semantic Kernel is installed and Azure OpenAI is configured.
"""
import os
import logging
from typing import Optional

try:
    from semantic_kernel import Kernel
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureTextEmbedding
    SK_AVAILABLE = True
except ImportError:
    Kernel = object  # type: ignore[assignment,misc]
    AzureChatCompletion = None  # type: ignore[assignment]
    AzureTextEmbedding = None  # type: ignore[assignment]
    SK_AVAILABLE = False

logger = logging.getLogger(__name__)

_kernel_instance: Optional[object] = None


def build_kernel():
    """
    Build and return a configured Semantic Kernel instance
    with Azure OpenAI services attached.
    Returns None gracefully if SK is not installed.
    """
    if not SK_AVAILABLE:
        logger.warning("Semantic Kernel not installed — kernel unavailable.")
        return None

    kernel = Kernel()

    # ── GPT-5.4-mini for complex reasoning (Strategist, Scribe) ───────────
    kernel.add_service(
        AzureChatCompletion(
            service_id="gpt4o",
            deployment_name=os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.6-terra"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    # ── GPT-5.4-nano for fast queries (Researcher, Analyst, Watchdog) ──────
    kernel.add_service(
        AzureChatCompletion(
            service_id="nano",
            deployment_name=os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT", "gpt-5.6-luna"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    # ── Embeddings for semantic memory ─────────────────────────────────────
    kernel.add_service(
        AzureTextEmbedding(
            service_id="embeddings",
            deployment_name=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
            endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_EMBEDDING_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION") or os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    logger.info("Semantic Kernel built with GPT-5.4-mini, nano, and embeddings.")
    return kernel


def get_kernel():
    """Return the singleton kernel instance, building it on first call."""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = build_kernel()
        if _kernel_instance is not None:
            _register_agents(_kernel_instance)
    return _kernel_instance


def _register_agents(kernel):
    """Register all agent plugins with the kernel."""
    from agents.researcher import ResearcherAgent
    from agents.analyst import AnalystAgent
    from agents.watchdog import WatchdogAgent
    from agents.scribe import ScribeAgent
    from agents.strategist import StrategistAgent

    kernel.add_plugin(ResearcherAgent(), plugin_name="Researcher")
    kernel.add_plugin(AnalystAgent(), plugin_name="Analyst")
    kernel.add_plugin(WatchdogAgent(), plugin_name="Watchdog")
    kernel.add_plugin(ScribeAgent(), plugin_name="Scribe")
    kernel.add_plugin(StrategistAgent(kernel), plugin_name="Strategist")

    logger.info("All 5 agents registered with kernel.")


async def sk_invoke(kernel, plugin_name: str, function_name: str, **kwargs) -> str:
    """Invoke a registered SK plugin function through the kernel."""
    if kernel is None:
        return ""
    try:
        from semantic_kernel.functions import KernelArguments
        args = KernelArguments(**kwargs)
        result = await kernel.invoke(
            plugin_name=plugin_name,
            function_name=function_name,
            arguments=args,
        )
        return str(result)
    except Exception as e:
        logger.warning(f"SK invoke {plugin_name}.{function_name} failed: {e}")
        return ""


# ── Standalone LLM completion (used by Strategist) ──────────────────────────
#
# Backed by the Azure AI Foundry Responses API (unified /openai/v1/ surface,
# no api-version query param) rather than Chat Completions. The Foundry
# resource behind this only has one text deployment (AZURE_OPENAI_RESPONSES_
# DEPLOYMENT, default gpt-5.6-sol) — unlike the old flagship/gpt4o/nano
# three-tier split, every service_id now resolves to that same deployment.
# Falls back to the old Chat Completions resource if the Responses API isn't
# configured.

_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt
# A token-per-minute quota frees up within its window, so a throttled call waits
# for Azure's retry hint instead of failing after a few quick, doomed retries.
_RATE_LIMIT_WAIT_BUDGET = 30.0  # seconds one call may spend waiting out throttling
_LLM_REQUEST_TIMEOUT = 90.0  # seconds; the SDK default (600) could stall a request


def _retry_delay(error: Exception, attempt: int) -> float:
    """Seconds to wait before retrying: Azure's rate-limit hint, else exponential backoff."""
    from openai import RateLimitError
    if isinstance(error, RateLimitError):
        headers = getattr(getattr(error, "response", None), "headers", None) or {}
        for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
            try:
                return min(max(1.0, float(headers.get(name)) * scale), _RATE_LIMIT_WAIT_BUDGET)
            except (TypeError, ValueError):
                continue
    return _LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))


def _should_retry(error: Exception, attempt: int, waited: float, delay: float, budget: float = _RATE_LIMIT_WAIT_BUDGET) -> bool:
    from openai import RateLimitError
    if isinstance(error, RateLimitError):
        return waited + delay <= budget
    return attempt < _LLM_MAX_RETRIES


def _responses_configured() -> bool:
    from services.llm_settings import responses_configured
    return responses_configured()


# The retry loops below are the only retry policy; nested SDK retries would fire
# inside the same exhausted quota window and multiply the wait unpredictably.
def _responses_client():
    from openai import AsyncOpenAI
    endpoint = os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT", "").rstrip("/")
    return AsyncOpenAI(
        api_key=os.getenv("AZURE_OPENAI_RESPONSES_API_KEY"),
        base_url=f"{endpoint}/openai/v1/",
        max_retries=0,
        timeout=_LLM_REQUEST_TIMEOUT,
    )


def _responses_deployment() -> str:
    from services.llm_settings import responses_deployment
    return responses_deployment()


def _chat_completions_client():
    from openai import AsyncAzureOpenAI
    return AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        max_retries=0,
        timeout=_LLM_REQUEST_TIMEOUT,
    )


def _chat_deployment(service_id: str) -> str:
    deployment_map = {
        "flagship": os.getenv("AZURE_OPENAI_FLAGSHIP_DEPLOYMENT", "gpt-5.6-sol"),
        "gpt4o":    os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT",    "gpt-5.6-terra"),
        "nano":     os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT",     "gpt-5.6-luna"),
    }
    return deployment_map.get(service_id, deployment_map["gpt4o"])


class _Backend:
    """One model to try: the primary (Responses API) or the fallback (Chat Completions)."""

    def __init__(self, kind: str, deployment: str, role: str):
        self.kind, self.deployment, self.role = kind, deployment, role

    def __repr__(self) -> str:
        return f"{self.role}:{self.deployment}"


def _backends(service_id: str) -> list:
    """Models to try, in order: the Responses deployment (e.g. gpt-6.1-sol)
    first, the Chat Completions deployment (e.g. gpt-5.4-nano) behind it."""
    from services.llm_settings import (
        chat_configured,
        fallback_deployment,
        fallback_enabled,
        responses_configured,
    )
    if responses_configured():
        backends = [_Backend("responses", _responses_deployment(), "primary")]
        if fallback_enabled():
            backends.append(_Backend("chat", fallback_deployment(), "fallback"))
        return backends
    if chat_configured():
        return [_Backend("chat", _chat_deployment(service_id), "primary")]
    return []


class _UseFallback(Exception):
    """This model cannot answer right now (throttled, down, misconfigured, or empty output)."""


def _fallback_worthy_immediately(error: Exception) -> bool:
    # A wrong key, missing permission or unknown deployment will not fix itself on
    # retry; the fallback keeps Iroko answering while the error is logged loudly.
    from openai import AuthenticationError, NotFoundError, PermissionDeniedError
    return isinstance(error, (AuthenticationError, PermissionDeniedError, NotFoundError))


async def _complete_on(backend, messages, max_tokens, json_schema, wait_budget):
    import asyncio

    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    from services.llm_settings import responses_kwargs

    client = _responses_client() if backend.kind == "responses" else _chat_completions_client()
    attempt, waited = 0, 0.0
    while True:
        attempt += 1
        try:
            if backend.kind == "responses":
                output_options = {}
                if json_schema is not None:
                    output_options["text"] = {"format": {"type": "json_schema", "name": "grounded_output", "schema": json_schema, "strict": True}}
                response = await client.responses.create(
                    model=backend.deployment,
                    input=messages,
                    **responses_kwargs(max_tokens),
                    **output_options,
                )
                text = response.output_text or ""
                if not text and getattr(response, "status", "") == "incomplete":
                    # Reasoning used the whole output budget; another model can still answer.
                    raise _UseFallback(f"{backend} returned no text (output budget used up by reasoning)")
                return text
            # GPT-5.x on Chat Completions: default temperature only (others 400), and
            # reasoning_effort="none" so reasoning tokens don't consume the budget.
            output_options = {}
            if json_schema is not None:
                output_options["response_format"] = {"type": "json_schema", "json_schema": {"name": "grounded_output", "schema": json_schema, "strict": True}}
            response = await client.chat.completions.create(
                model=backend.deployment,
                messages=messages,
                max_completion_tokens=max_tokens,
                extra_body={"reasoning_effort": "none"},
                **output_options,
            )
            return response.choices[0].message.content or ""
        except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as e:
            delay = _retry_delay(e, attempt)
            if not _should_retry(e, attempt, waited, delay, wait_budget):
                raise _UseFallback(f"{backend} unavailable after {attempt} attempt(s), {waited:.0f}s waiting: {e}") from e
            logger.warning(f"llm_complete {backend} transient error (attempt {attempt}): {type(e).__name__} — retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
            waited += delay
        except _UseFallback:
            raise
        except Exception as e:
            if _fallback_worthy_immediately(e):
                logger.error(f"llm_complete {backend} is misconfigured ({type(e).__name__}): {e}")
                raise _UseFallback(f"{backend} misconfigured: {e}") from e
            # Non-retryable (bad request, content filter, ...): another model would not help.
            logger.error(f"llm_complete non-retryable error on {backend}: {e}")
            raise RuntimeError(f"LLM call failed: {e}") from e


async def llm_complete(
    prompt: str,
    *,
    max_tokens: int = 1000,
    temperature: float = 0.3,
    service_id: str = "gpt4o",
    system_prompt: str = "",
    json_schema: Optional[dict] = None,
) -> str:
    """
    Call the LLM: the primary model (Responses API, e.g. gpt-6.1-sol) first,
    then the fallback Chat Completions deployment (e.g. gpt-5.4-nano) if the
    primary is throttled, down or misconfigured.
    Connection/timeout/server errors retry up to _LLM_MAX_RETRIES times (1s, 2s).
    Rate limits wait for Azure's retry hint — briefly on the primary when a
    fallback exists, up to _RATE_LIMIT_WAIT_BUDGET on the last model.
    Raises RuntimeError when every model fails so callers can handle the
    failure explicitly instead of receiving a silent empty string.
    Returns "" immediately when no backend is configured.
    """
    from services.llm_settings import primary_rate_limit_wait

    backends = _backends(service_id)
    if not backends:
        logger.warning("No LLM backend configured — llm_complete unavailable.")
        return ""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last: Exception = RuntimeError("llm_complete: no attempts made")
    for i, backend in enumerate(backends):
        has_next = i < len(backends) - 1
        budget = primary_rate_limit_wait() if has_next else _RATE_LIMIT_WAIT_BUDGET
        try:
            return await _complete_on(backend, messages, max_tokens, json_schema, budget)
        except _UseFallback as e:
            last = e
            if has_next:
                logger.warning(f"LLM fallback: {e} — answering with {backends[i + 1]}")
    logger.error(f"llm_complete: every model failed. Last error: {last}")
    raise RuntimeError(f"LLM call failed: {last}") from last


async def llm_complete_stream(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    service_id: str = "gpt4o",
    system_prompt: str = "",
):
    """
    Streaming version of llm_complete, with the same primary → fallback order.
    Yields string chunks as they arrive. The fallback is used only if the
    primary fails before streaming anything — a half-written answer is never
    spliced with another model's.
    Raises RuntimeError on non-retryable or exhausted errors so the SSE
    caller can emit a structured error event instead of silently closing.
    """
    import asyncio

    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    from services.llm_settings import primary_rate_limit_wait, responses_kwargs

    backends = _backends(service_id)
    if not backends:
        logger.warning("No LLM backend configured — llm_complete_stream unavailable.")
        return  # caller treats zero tokens as unconfigured

    stream_messages = []
    if system_prompt:
        stream_messages.append({"role": "system", "content": system_prompt})
    stream_messages.append({"role": "user", "content": prompt})

    last: Exception = RuntimeError("llm_complete_stream: no attempts made")
    for i, backend in enumerate(backends):
        has_next = i < len(backends) - 1
        budget = primary_rate_limit_wait() if has_next else _RATE_LIMIT_WAIT_BUDGET
        client = _responses_client() if backend.kind == "responses" else _chat_completions_client()
        attempt, waited, yielded = 0, 0.0, False
        while True:
            attempt += 1
            try:
                if backend.kind == "responses":
                    stream = await client.responses.create(
                        model=backend.deployment,
                        input=stream_messages,
                        stream=True,
                        **responses_kwargs(max_tokens),
                    )
                    async for event in stream:
                        if event.type == "response.output_text.delta" and event.delta:
                            yielded = True
                            yield event.delta
                    return
                # GPT-5.x: default temperature only; reasoning_effort="none" so reasoning
                # tokens don't consume the budget and leave the stream empty.
                chat_stream = await client.chat.completions.create(
                    model=backend.deployment,
                    messages=stream_messages,
                    max_completion_tokens=max_tokens,
                    stream=True,
                    extra_body={"reasoning_effort": "none"},
                )
                async for chunk in chat_stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        yielded = True
                        yield chunk.choices[0].delta.content
                return  # stream completed successfully
            except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as e:
                if yielded:
                    raise RuntimeError(f"LLM stream interrupted: {e}") from e
                last = e
                delay = _retry_delay(e, attempt)
                if not _should_retry(e, attempt, waited, delay, budget):
                    break
                logger.warning(
                    f"llm_complete_stream {backend} transient error (attempt {attempt}): "
                    f"{type(e).__name__} — retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                waited += delay
            except Exception as e:
                if not yielded and _fallback_worthy_immediately(e):
                    logger.error(f"llm_complete_stream {backend} is misconfigured ({type(e).__name__}): {e}")
                    last = e
                    break
                logger.error(f"llm_complete_stream non-retryable error on {backend}: {e}")
                raise RuntimeError(f"LLM stream failed: {e}") from e
        if has_next:
            logger.warning(f"LLM fallback (stream): {backend} unavailable ({last}) — answering with {backends[i + 1]}")

    logger.error(f"llm_complete_stream: every model failed. Last error: {last}")
    raise RuntimeError(f"LLM stream failed: {last}") from last


async def llm_probe() -> dict:
    """Ping each configured model separately (for /health/full), so a working
    fallback cannot hide a broken primary."""
    import asyncio
    import time

    out = {}
    for backend in _backends("nano"):
        t = time.perf_counter()
        try:
            await asyncio.wait_for(
                _complete_on(backend, [{"role": "user", "content": "ping"}], 16, None, 0.0), timeout=20
            )
            out[backend.role] = {"deployment": backend.deployment, "status": "ok",
                                 "latency_ms": round((time.perf_counter() - t) * 1000, 1)}
        except Exception as e:  # a health probe reports; it never raises
            out[backend.role] = {"deployment": backend.deployment, "status": "error", "detail": str(e)[:300]}
    return out
