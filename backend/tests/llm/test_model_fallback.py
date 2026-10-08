"""Primary model (Responses API, gpt-6.1-sol) with the Chat Completions fallback (gpt-5.4-nano)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

import agents.kernel as kernel
from services import llm_settings

REQ = httpx.Request("POST", "https://example.invalid/v1")


def _err(cls, status, headers=None):
    return cls("boom", response=httpx.Response(status, request=REQ, headers=headers or {}), body=None)


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    async def create(self, **kw):
        self.calls.append(kw)
        out = self.outcomes.pop(0) if self.outcomes else SimpleNamespace(output_text="primary answer", status="completed")
        if isinstance(out, Exception):
            raise out
        if kw.get("stream"):
            return _aiter(out)
        return out


class FakeChat:
    def __init__(self, outcomes=()):
        self.outcomes, self.calls = list(outcomes), []
        self.completions = self

    async def create(self, **kw):
        self.calls.append(kw)
        out = self.outcomes.pop(0) if self.outcomes else None
        if isinstance(out, Exception):
            raise out
        if kw.get("stream"):
            return _aiter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=t))]) for t in ("fall", "back")])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback answer"))])


async def _aiter(items):
    for item in items:
        if isinstance(item, Exception):
            raise item
        yield item


@pytest.fixture
def env(monkeypatch):
    for k, v in {
        "AZURE_OPENAI_RESPONSES_ENDPOINT": "https://primary.invalid", "AZURE_OPENAI_RESPONSES_API_KEY": "k",
        "AZURE_OPENAI_RESPONSES_DEPLOYMENT": "gpt-6.1-sol", "AZURE_OPENAI_ENDPOINT": "https://fallback.invalid",
        "AZURE_OPENAI_API_KEY": "k", "AZURE_OPENAI_NANO_DEPLOYMENT": "gpt-5.4-nano", "LLM_PRIMARY_RATE_LIMIT_WAIT": "0",
    }.items():
        monkeypatch.setenv(k, v)
    for k in ("AZURE_OPENAI_RESPONSES_REASONING_EFFORT", "AZURE_OPENAI_REASONING_HEADROOM", "LLM_FALLBACK", "AZURE_OPENAI_FALLBACK_DEPLOYMENT"):
        monkeypatch.delenv(k, raising=False)

    async def no_sleep(_):
        return None
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    return monkeypatch


def _wire(env, primary_outcomes=(), chat_outcomes=()):
    responses = FakeResponses(primary_outcomes)
    chat = FakeChat(chat_outcomes)
    env.setattr(kernel, "_responses_client", lambda: SimpleNamespace(responses=responses))
    env.setattr(kernel, "_chat_completions_client", lambda: SimpleNamespace(chat=chat))
    return responses, chat


def run(coro):
    return asyncio.run(coro)


def test_primary_uses_low_effort_with_reasoning_headroom(env):
    responses, chat = _wire(env)
    assert run(kernel.llm_complete("q", max_tokens=1200)) == "primary answer"
    call = responses.calls[0]
    assert call["model"] == "gpt-6.1-sol"
    assert call["reasoning"] == {"effort": "low"}  # gpt-6.1-sol rejects "none"
    assert call["max_output_tokens"] == 1200 + 2000
    assert chat.calls == []


def test_effort_defaults_and_override(env):
    assert llm_settings.responses_effort() == "low"
    env.setenv("AZURE_OPENAI_RESPONSES_DEPLOYMENT", "gpt-5.6-sol")
    assert llm_settings.responses_effort() == "none"
    assert llm_settings.responses_kwargs(500) == {"max_output_tokens": 500, "reasoning": {"effort": "none"}}
    env.setenv("AZURE_OPENAI_RESPONSES_REASONING_EFFORT", "medium")
    assert llm_settings.responses_effort() == "medium"


def test_rate_limited_primary_falls_back_to_nano(env):
    limited = _err(openai.RateLimitError, 429, {"retry-after": "1"})
    responses, chat = _wire(env, primary_outcomes=[limited, limited])
    assert run(kernel.llm_complete("q", json_schema={"type": "object"})) == "fallback answer"
    call = chat.calls[0]
    assert call["model"] == "gpt-5.4-nano" and call["extra_body"] == {"reasoning_effort": "none"}
    assert call["response_format"]["type"] == "json_schema"


def test_misconfigured_primary_falls_back_immediately(env):
    responses, chat = _wire(env, primary_outcomes=[_err(openai.AuthenticationError, 401)])
    assert run(kernel.llm_complete("q")) == "fallback answer"
    assert len(responses.calls) == 1


def test_bad_request_does_not_fall_back(env):
    responses, chat = _wire(env, primary_outcomes=[_err(openai.BadRequestError, 400)])
    with pytest.raises(RuntimeError):
        run(kernel.llm_complete("q"))
    assert chat.calls == []


def test_empty_incomplete_output_falls_back(env):
    responses, chat = _wire(env, primary_outcomes=[SimpleNamespace(output_text="", status="incomplete")])
    assert run(kernel.llm_complete("q")) == "fallback answer"


def test_fallback_can_be_switched_off(env):
    env.setenv("LLM_FALLBACK", "false")
    _wire(env, primary_outcomes=[_err(openai.AuthenticationError, 401)])
    with pytest.raises(RuntimeError):
        run(kernel.llm_complete("q"))


def test_without_primary_uses_chat_deployments(env):
    env.delenv("AZURE_OPENAI_RESPONSES_ENDPOINT")
    env.setenv("AZURE_OPENAI_GPT4O_DEPLOYMENT", "gpt-5.4-nano")
    responses, chat = _wire(env)
    assert run(kernel.llm_complete("q")) == "fallback answer"
    assert responses.calls == [] and chat.calls[0]["model"] == "gpt-5.4-nano"


def _collect(gen):
    async def go():
        return [c async for c in gen]
    return run(go())


def test_stream_falls_back_only_before_first_token(env):
    responses, chat = _wire(env, primary_outcomes=[_err(openai.RateLimitError, 429, {"retry-after": "1"})] * 2)
    assert "".join(_collect(kernel.llm_complete_stream("q"))) == "fallback"

    # once the primary has started answering, an error is not papered over with another model
    delta = SimpleNamespace(type="response.output_text.delta", delta="half ")
    responses, chat = _wire(env, primary_outcomes=[[delta, openai.APIConnectionError(request=REQ)]])
    with pytest.raises(RuntimeError):
        _collect(kernel.llm_complete_stream("q"))
    assert chat.calls == []


def test_probe_reports_each_model(env):
    _wire(env, primary_outcomes=[_err(openai.NotFoundError, 404)])
    models = run(kernel.llm_probe())
    assert models["primary"]["status"] == "error" and models["primary"]["deployment"] == "gpt-6.1-sol"
    assert models["fallback"] == {**models["fallback"], "status": "ok", "deployment": "gpt-5.4-nano"}
    assert llm_settings.describe() == {"primary": "gpt-6.1-sol", "primary_reasoning_effort": "low",
                                       "fallback": "gpt-5.4-nano", "chat_completions_only": None}
