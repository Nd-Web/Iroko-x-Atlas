"""
services/azure_openai.py — Async wrapper around Azure OpenAI for Iroko AI.

Provides two high-level functions:

- ``get_chat_completion(messages, system_prompt)`` — GPT-4o chat completion
- ``get_embedding(text)`` — text-embedding-3-large vector embedding

Both read configuration from ``core.config.settings`` and include a single
automatic retry (2-second backoff) on rate-limit errors.
"""

import asyncio
import logging
from typing import Optional

from openai import (
    AsyncAzureOpenAI,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
)

from core.config import settings

logger = logging.getLogger(__name__)

# ── Lazy singleton client ─────────────────────────────────────────────────────

_client: Optional[AsyncAzureOpenAI] = None


def _get_client() -> AsyncAzureOpenAI:
    """Return a lazily-initialised AsyncAzureOpenAI client."""
    global _client
    if _client is None:
        if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
            raise RuntimeError(
                "Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT "
                "and AZURE_OPENAI_API_KEY in your .env file."
            )
        _client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    return _client


# ── Retry config ──────────────────────────────────────────────────────────────

_RETRY_DELAY_SECONDS = 2
_RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError)


# ── Chat completion ───────────────────────────────────────────────────────────

async def get_chat_completion(
    messages: list[dict[str, str]],
    system_prompt: str = "",
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    deployment: Optional[str] = None,
) -> str:
    """
    Call Azure OpenAI GPT-4o deployment and return the assistant's response.

    Parameters
    ----------
    messages : list[dict]
        Conversation messages (``[{"role": "user", "content": "..."}]``).
    system_prompt : str
        Optional system message prepended to the conversation.
    max_tokens : int
        Maximum tokens in the completion.
    temperature : float
        Sampling temperature.
    deployment : str, optional
        Override the deployment name (defaults to ``settings.AZURE_OPENAI_DEPLOYMENT``).

    Returns
    -------
    str
        The model's text response.

    Raises
    ------
    RuntimeError
        If both the initial call and the retry fail.
    """
    client = _get_client()
    model = deployment or settings.AZURE_OPENAI_DEPLOYMENT

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    for attempt in range(2):  # initial + 1 retry
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except _RETRYABLE_ERRORS as exc:
            if attempt == 0:
                logger.warning(
                    f"Azure OpenAI rate-limit/transient error: {exc} "
                    f"— retrying in {_RETRY_DELAY_SECONDS}s"
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Azure OpenAI retry exhausted: {exc}")
                raise RuntimeError(f"Azure OpenAI call failed after retry: {exc}") from exc
        except Exception as exc:
            logger.error(f"Azure OpenAI non-retryable error: {exc}")
            raise RuntimeError(f"Azure OpenAI call failed: {exc}") from exc

    # Should not reach here, but safety net
    raise RuntimeError("Azure OpenAI call failed unexpectedly")


# ── Embedding ─────────────────────────────────────────────────────────────────

async def get_embedding(
    text: str,
    *,
    deployment: Optional[str] = None,
) -> list[float]:
    """
    Generate a vector embedding for the given text using Azure OpenAI.

    Parameters
    ----------
    text : str
        Input text to embed.
    deployment : str, optional
        Override the embedding deployment name.

    Returns
    -------
    list[float]
        The embedding vector (3072 dimensions for text-embedding-3-large).
    """
    client = _get_client()
    model = deployment or settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT

    for attempt in range(2):  # initial + 1 retry
        try:
            response = await client.embeddings.create(
                model=model,
                input=text,
            )
            return response.data[0].embedding
        except _RETRYABLE_ERRORS as exc:
            if attempt == 0:
                logger.warning(
                    f"Embedding rate-limit/transient error: {exc} "
                    f"— retrying in {_RETRY_DELAY_SECONDS}s"
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Embedding retry exhausted: {exc}")
                raise RuntimeError(f"Embedding call failed after retry: {exc}") from exc
        except Exception as exc:
            logger.error(f"Embedding non-retryable error: {exc}")
            raise RuntimeError(f"Embedding call failed: {exc}") from exc

    raise RuntimeError("Embedding call failed unexpectedly")


# ── Streaming (for SSE routes) ────────────────────────────────────────────────

async def stream_chat_completion(
    messages: list[dict[str, str]],
    system_prompt: str = "",
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    deployment: Optional[str] = None,
):
    """
    Async generator that yields string chunks from a streaming GPT-4o call.

    Usage::

        async for chunk in stream_chat_completion(messages, system_prompt):
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\\n\\n"
    """
    client = _get_client()
    model = deployment or settings.AZURE_OPENAI_DEPLOYMENT

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    for attempt in range(2):
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    yield chunk.choices[0].delta.content
            return  # stream completed successfully
        except _RETRYABLE_ERRORS as exc:
            if attempt == 0:
                logger.warning(
                    f"Stream rate-limit/transient error: {exc} "
                    f"— retrying in {_RETRY_DELAY_SECONDS}s"
                )
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
            else:
                raise RuntimeError(f"Stream failed after retry: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Stream failed: {exc}") from exc
