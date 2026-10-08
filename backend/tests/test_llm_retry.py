"""Model-call retry policy; a fake client stands in for Azure, nothing sleeps for real."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from agents import kernel

REQUEST = httpx.Request("POST", "https://example.invalid/openai")


def throttled(retry_after_ms="4000"):
    response = httpx.Response(429, headers={"retry-after-ms": retry_after_ms, "retry-after": "30"}, request=REQUEST)
    return openai.RateLimitError("throttled", response=response, body=None)


def completion(text="ok"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AZURE_OPENAI_RESPONSES_ENDPOINT", raising=False)
    create = AsyncMock()
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(kernel, "_chat_completions_client", lambda: client)
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", sleep)
    return create, sleeps


async def test_throttled_call_waits_for_azure_hint_then_succeeds(azure):
    create, sleeps = azure
    create.side_effect = [throttled(), throttled(), completion("answer")]
    assert await kernel.llm_complete("question") == "answer"
    assert sleeps == [4.0, 4.0]


async def test_persistent_throttling_gives_up_within_the_wait_budget(azure):
    create, sleeps = azure
    create.side_effect = throttled("9000")
    with pytest.raises(RuntimeError):
        await kernel.llm_complete("question")
    assert sum(sleeps) <= kernel._RATE_LIMIT_WAIT_BUDGET
    assert len(sleeps) == 3  # 9s x 3 = 27s fits; a fourth wait would exceed 30s


async def test_missing_hint_falls_back_to_backoff(azure):
    create, sleeps = azure
    create.side_effect = [throttled(retry_after_ms="not-a-number"), completion()]
    # The plain retry-after header (30s) is the next hint and is capped by the budget.
    assert await kernel.llm_complete("question") == "ok"
    assert sleeps == [30.0]


async def test_connection_errors_retry_a_bounded_number_of_times(azure):
    create, sleeps = azure
    create.side_effect = openai.APIConnectionError(request=REQUEST)
    with pytest.raises(RuntimeError):
        await kernel.llm_complete("question")
    assert create.await_count == kernel._LLM_MAX_RETRIES
    assert sleeps == [1.0, 2.0]


async def test_bad_request_fails_immediately(azure):
    create, sleeps = azure
    response = httpx.Response(404, request=REQUEST)
    create.side_effect = openai.NotFoundError("DeploymentNotFound", response=response, body=None)
    with pytest.raises(RuntimeError):
        await kernel.llm_complete("question")
    assert create.await_count == 1
    assert sleeps == []


def test_clients_leave_retries_to_this_policy_and_bound_request_time(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    client = kernel._chat_completions_client()
    assert client.max_retries == 0
    assert client.timeout == kernel._LLM_REQUEST_TIMEOUT
