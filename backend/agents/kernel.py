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
            deployment_name=os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.4-mini"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
        )
    )

    # ── GPT-5.4-nano for fast queries (Researcher, Analyst, Watchdog) ──────
    kernel.add_service(
        AzureChatCompletion(
            service_id="nano",
            deployment_name=os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT", "gpt-5.4-nano"),
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
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
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

_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt


async def llm_complete(
    prompt: str,
    *,
    max_tokens: int = 1000,
    temperature: float = 0.3,
    service_id: str = "gpt4o",
    system_prompt: str = "",
) -> str:
    """
    Call Azure OpenAI chat completion with exponential-backoff retry.
    Retries up to _LLM_MAX_RETRIES times (delays: 1s, 2s, 4s).
    Raises RuntimeError after all retries are exhausted so callers can
    handle the failure explicitly instead of receiving a silent empty string.
    Returns "" immediately when Azure OpenAI is not configured at all.
    """
    import asyncio
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if not endpoint or not api_key:
        logger.warning("Azure OpenAI not configured — llm_complete unavailable.")
        return ""

    deployment_map = {
        "gpt4o": os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.4-mini"),
        "nano":  os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT",  "gpt-5.4-nano"),
    }
    deployment = deployment_map.get(service_id, deployment_map["gpt4o"])

    from openai import AsyncAzureOpenAI, RateLimitError, APITimeoutError, APIConnectionError
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error: Exception = RuntimeError("llm_complete: no attempts made")
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
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
    Yields string chunks as they arrive from Azure OpenAI.
    On transient errors, retries up to _LLM_MAX_RETRIES times before raising.
    Raises RuntimeError on non-retryable or exhausted errors so the SSE
    caller can emit a structured error event instead of silently closing.
    """
    import asyncio
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if not endpoint or not api_key:
        logger.warning("Azure OpenAI not configured — llm_complete_stream unavailable.")
        return  # caller treats zero tokens as unconfigured

    deployment_map = {
        "gpt4o": os.getenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.4-mini"),
        "nano":  os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT",  "gpt-5.4-nano"),
    }
    deployment = deployment_map.get(service_id, deployment_map["gpt4o"])

    from openai import AsyncAzureOpenAI, RateLimitError, APITimeoutError, APIConnectionError
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    stream_messages = []
    if system_prompt:
        stream_messages.append({"role": "system", "content": system_prompt})
    stream_messages.append({"role": "user", "content": prompt})

    last_error: Exception = RuntimeError("llm_complete_stream: no attempts made")
    for attempt in range(1, _LLM_MAX_RETRIES + 1):
        try:
            stream = await client.chat.completions.create(
                model=deployment,
                messages=stream_messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
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
