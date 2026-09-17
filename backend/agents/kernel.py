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


def _responses_configured() -> bool:
    return bool(os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT") and os.getenv("AZURE_OPENAI_RESPONSES_API_KEY"))


def _responses_client():
    from openai import AsyncOpenAI
    endpoint = os.getenv("AZURE_OPENAI_RESPONSES_ENDPOINT", "").rstrip("/")
    return AsyncOpenAI(
        api_key=os.getenv("AZURE_OPENAI_RESPONSES_API_KEY"),
        base_url=f"{endpoint}/openai/v1/",
    )


def _responses_deployment() -> str:
    return os.getenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT", "gpt-5.6-sol")


def _chat_completions_client():
    from openai import AsyncAzureOpenAI
    return AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
    )


async def llm_complete(
    prompt: str,
    *,
    max_tokens: int = 1000,
    temperature: float = 0.3,
    service_id: str = "gpt4o",
    system_prompt: str = "",
) -> str:
    """
    Call the main LLM with exponential-backoff retry.
    Retries up to _LLM_MAX_RETRIES times (delays: 1s, 2s, 4s).
    Raises RuntimeError after all retries are exhausted so callers can
    handle the failure explicitly instead of receiving a silent empty string.
    Returns "" immediately when neither backend is configured.
    """
    import asyncio

    use_responses = _responses_configured()
    if not use_responses and not (os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY")):
        logger.warning("No LLM backend configured — llm_complete unavailable.")
        return ""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    from openai import RateLimitError, APITimeoutError, APIConnectionError

    if use_responses:
        client = _responses_client()
        deployment = _responses_deployment()
    else:
        client = _chat_completions_client()
        deployment_map = {
            "flagship": os.getenv("AZURE_OPENAI_FLAGSHIP_DEPLOYMENT", "gpt-5.6-sol"),
            "gpt4o":    os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT",    "gpt-5.6-terra"),
            "nano":     os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT",     "gpt-5.6-luna"),
        }
        deployment = deployment_map.get(service_id, deployment_map["gpt4o"])

    last_error: Exception = RuntimeError("llm_complete: no attempts made")
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            # NOTE: GPT-5.x models only support the default temperature (1);
            # sending any other value returns a 400, so we do not forward it.
            # reasoning={"effort": "none"} (Responses) / reasoning_effort="none"
            # (Chat Completions) makes these reasoning models count tokens as
            # output-only. Without it, reasoning tokens silently consume the
            # budget and the visible answer comes back empty.
            if use_responses:
                response = await client.responses.create(
                    model=deployment,
                    input=messages,
                    max_output_tokens=max_tokens,
                    reasoning={"effort": "none"},
                )
                return response.output_text or ""
            response = await client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_completion_tokens=max_tokens,
                extra_body={"reasoning_effort": "none"},
            )
            return response.choices[0].message.content or ""
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            last_error = e
            delay = _LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"llm_complete transient error (attempt {attempt}/{_LLM_MAX_RETRIES}): "
                f"{type(e).__name__} — retrying in {delay:.0f}s"
            )
            if attempt < _LLM_MAX_RETRIES:
                await asyncio.sleep(delay)
        except Exception as e:
            # Non-retryable (auth, bad request, etc.) — fail immediately
            logger.error(f"llm_complete non-retryable error: {e}")
            raise RuntimeError(f"LLM call failed: {e}") from e

    logger.error(
        f"llm_complete exhausted {_LLM_MAX_RETRIES} retries. Last error: {last_error}"
    )
    raise RuntimeError(
        f"LLM call failed after {_LLM_MAX_RETRIES} retries: {last_error}"
    ) from last_error


async def llm_complete_stream(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    service_id: str = "gpt4o",
    system_prompt: str = "",
):
    """
    Streaming version of llm_complete with exponential-backoff retry.
    Yields string chunks as they arrive.
    On transient errors, retries up to _LLM_MAX_RETRIES times before raising.
    Raises RuntimeError on non-retryable or exhausted errors so the SSE
    caller can emit a structured error event instead of silently closing.
    """
    import asyncio

    use_responses = _responses_configured()
    if not use_responses and not (os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_API_KEY")):
        logger.warning("No LLM backend configured — llm_complete_stream unavailable.")
        return  # caller treats zero tokens as unconfigured

    stream_messages = []
    if system_prompt:
        stream_messages.append({"role": "system", "content": system_prompt})
    stream_messages.append({"role": "user", "content": prompt})

    from openai import RateLimitError, APITimeoutError, APIConnectionError

    if use_responses:
        client = _responses_client()
        deployment = _responses_deployment()
    else:
        client = _chat_completions_client()
        deployment_map = {
            "flagship": os.getenv("AZURE_OPENAI_FLAGSHIP_DEPLOYMENT", "gpt-5.6-sol"),
            "gpt4o":    os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT",    "gpt-5.6-terra"),
            "nano":     os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT",     "gpt-5.6-luna"),
        }
        deployment = deployment_map.get(service_id, deployment_map["gpt4o"])

    last_error: Exception = RuntimeError("llm_complete_stream: no attempts made")
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            if use_responses:
                stream = await client.responses.create(
                    model=deployment,
                    input=stream_messages,
                    max_output_tokens=max_tokens,
                    reasoning={"effort": "none"},
                    stream=True,
                )
                async for event in stream:
                    if event.type == "response.output_text.delta" and event.delta:
                        yield event.delta
                return
            # GPT-5.x: default temperature only; reasoning_effort="none" so reasoning
            # tokens don't consume the budget and leave the stream empty.
            chat_stream = await client.chat.completions.create(
                model=deployment,
                messages=stream_messages,
                max_completion_tokens=max_tokens,
                stream=True,
                extra_body={"reasoning_effort": "none"},
            )
            async for chunk in chat_stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return  # stream completed successfully
        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            last_error = e
            delay = _LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"llm_complete_stream transient error (attempt {attempt}/{_LLM_MAX_RETRIES}): "
                f"{type(e).__name__} — retrying in {delay:.0f}s"
            )
            if attempt < _LLM_MAX_RETRIES:
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"llm_complete_stream non-retryable error: {e}")
            raise RuntimeError(f"LLM stream failed: {e}") from e

    logger.error(
        f"llm_complete_stream exhausted {_LLM_MAX_RETRIES} retries. Last error: {last_error}"
    )
    raise RuntimeError(
        f"LLM stream failed after {_LLM_MAX_RETRIES} retries: {last_error}"
    ) from last_error
