"""Haiku 5.5 returns a 400 for temperature, top_p, top_k, an assistant prefill and
thinking.budget_tokens. These tests pin the request body the adapter really sends."""

import json
from types import SimpleNamespace

import anthropic
import pytest

from app.config import get_settings
from app.llm.anthropic_adapter import (
    FORBIDDEN_PARAMS,
    AnthropicAdapter,
    assert_request_shape,
)
from app.llm.port import LLMError
from app.llm.prompts import COMPOSE_SYSTEM, build_compose_messages
from app.llm.schema_json import COMPOSE_SCHEMA

ANSWER = {"status": "answered", "answer": "x", "citations": [], "missing_info": []}


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies[min(len(self.requests), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeClient:
    def __init__(self, replies):
        self.messages = FakeMessages(replies)


def response(blocks, stop_reason="end_turn", stop_details=None):
    return SimpleNamespace(
        model="claude-haiku-5-5",
        content=blocks,
        stop_reason=stop_reason,
        stop_details=stop_details,
        usage=SimpleNamespace(input_tokens=900, output_tokens=120, cache_read_input_tokens=512),
    )


def text(data) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=json.dumps(data))


def thinking() -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking="private reasoning", signature="sig")


def adapter(replies, **env):
    s = get_settings({"LLM_PROVIDER": "live", **env})
    client = FakeClient(replies)
    return AnthropicAdapter(s, client=client), client.messages


@pytest.fixture()
def messages(built):
    corpus, index = built
    return build_compose_messages("Lifts above 15 m?", "en", index.resolve_pin("83"), [])


# --- the request body ------------------------------------------------------------------------


def test_request_has_none_of_the_forbidden_parameters(messages):
    a, mock = adapter([response([text(ANSWER)])])
    a.complete_json("compose", messages, COMPOSE_SCHEMA)
    (req,) = mock.requests
    for name in FORBIDDEN_PARAMS:
        assert name not in req, name
    assert "budget_tokens" not in json.dumps(req)
    assert "temperature" not in json.dumps(req) and "top_p" not in json.dumps(req)


def test_request_shape_in_full(messages):
    a, mock = adapter([response([text(ANSWER)])])
    a.complete_json("compose", messages, COMPOSE_SCHEMA)
    (req,) = mock.requests
    assert req["model"] == "claude-haiku-5-5"  # exact ID, no date suffix
    assert req["max_tokens"] == 1500
    assert req["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": COMPOSE_SCHEMA},
    }
    assert "thinking" not in req  # thinking stays on its default
    assert [m["role"] for m in req["messages"]] == ["user"]  # ends with a user turn: no prefill
    assert req["system"] == [
        {"type": "text", "text": COMPOSE_SYSTEM, "cache_control": {"type": "ephemeral"}}
    ]
    assert set(req) == {"model", "max_tokens", "messages", "output_config", "system"}


def test_env_drives_model_effort_and_thinking(messages):
    a, mock = adapter(
        [response([text(ANSWER)])],
        ANTHROPIC_MODEL_ANSWER="claude-haiku-5-5",
        ANTHROPIC_EFFORT="medium",
        ANTHROPIC_THINKING="disabled",
        MAX_TOKENS_ANSWER="2000",
    )
    a.complete_json("compose", messages, COMPOSE_SCHEMA)
    (req,) = mock.requests
    assert req["output_config"]["effort"] == "medium"
    assert req["thinking"] == {"type": "disabled"}  # allowed form; never budget_tokens
    assert req["max_tokens"] == 2000


@pytest.mark.parametrize(
    "extra",
    [
        {"temperature": 0},
        {"top_p": 0.9},
        {"top_k": 5},
        {"budget_tokens": 1000},
        {"thinking": {"type": "enabled", "budget_tokens": 1000}},
    ],
)
def test_guard_rejects_forbidden_parameters(extra):
    base = {"model": "m", "max_tokens": 1, "messages": [{"role": "user", "content": "q"}]}
    assert_request_shape(base)
    with pytest.raises(ValueError, match="forbidden"):
        assert_request_shape(base | extra)


def test_guard_rejects_assistant_prefill_and_system_in_messages():
    with pytest.raises(ValueError, match="user turn"):
        assert_request_shape(
            {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "{"}]}
        )
    with pytest.raises(ValueError):
        assert_request_shape({"messages": []})
    with pytest.raises(ValueError, match="system"):
        assert_request_shape(
            {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]}
        )


def test_every_request_in_a_repair_sequence_is_clean(messages):
    bad = response([text(ANSWER)], stop_reason="max_tokens")
    a, mock = adapter([bad, response([text(ANSWER)])])
    a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert len(mock.requests) == 2
    for req in mock.requests:
        assert_request_shape(req)
        assert not set(FORBIDDEN_PARAMS) & set(req)


def test_compose_schema_uses_no_unsupported_keywords():
    blob = json.dumps(COMPOSE_SCHEMA)
    for keyword in ("minLength", "maxLength", "minimum", "maximum", "$ref", "oneOf", "pattern"):
        assert keyword not in blob
    assert COMPOSE_SCHEMA["additionalProperties"] is False
    assert COMPOSE_SCHEMA["properties"]["citations"]["items"]["additionalProperties"] is False


# --- reading the response --------------------------------------------------------------------


def test_text_is_read_by_block_type_not_by_position(messages):
    # thinking is on by default, so the response starts with thinking blocks
    a, _ = adapter([response([thinking(), thinking(), text(ANSWER)])])
    data, metrics = a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert data == ANSWER
    assert metrics.provider == "anthropic" and metrics.model == "claude-haiku-5-5"
    assert (metrics.input_tokens, metrics.output_tokens, metrics.cached_tokens) == (900, 120, 512)
    assert metrics.stop_reason == "end_turn"


def test_response_without_a_text_block_is_invalid_not_a_crash(messages):
    a, _ = adapter([response([thinking()])])
    with pytest.raises(LLMError) as e:
        a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert e.value.kind == "invalid"


def test_non_json_text_is_invalid(messages):
    a, _ = adapter([response([SimpleNamespace(type="text", text="not json")])])
    with pytest.raises(LLMError) as e:
        a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert e.value.kind == "invalid"


def test_refusal_raises_without_retry_and_never_returns_an_answer(messages):
    refusal = response(
        [text({"oops": 1})],
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
    )
    a, mock = adapter([refusal])
    with pytest.raises(LLMError) as e:
        a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert e.value.kind == "refusal" and "cyber" in str(e.value)
    assert len(mock.requests) == 1  # no retry


def test_max_tokens_retries_once_with_a_larger_cap(messages):
    cut = response([thinking()], stop_reason="max_tokens")
    a, mock = adapter([cut, response([thinking(), text(ANSWER)])])
    data, _ = a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert data == ANSWER
    assert [r["max_tokens"] for r in mock.requests] == [1500, 3000]


def test_max_tokens_twice_is_truncated_never_a_partial_answer(messages):
    cut = response([thinking(), text({"status": "answ"})], stop_reason="max_tokens")
    a, mock = adapter([cut, cut])
    with pytest.raises(LLMError) as e:
        a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert e.value.kind == "truncated" and len(mock.requests) == 2


# --- errors: most specific first, never a raw SDK exception ----------------------------------


def _sdk_error(cls, status=400):
    err = cls.__new__(cls)
    Exception.__init__(err, "boom")
    err.status_code = status
    err.request_id = "req_123"
    return err


@pytest.mark.parametrize(
    "cls,status,kind",
    [
        (anthropic.BadRequestError, 400, "bad_request"),
        (anthropic.AuthenticationError, 401, "auth"),
        (anthropic.PermissionDeniedError, 403, "auth"),
        (anthropic.NotFoundError, 404, "unavailable"),
        (anthropic.RateLimitError, 429, "rate_limit"),
        (anthropic.InternalServerError, 500, "unavailable"),
    ],
)
def test_sdk_errors_become_llm_errors(messages, cls, status, kind):
    a, mock = adapter([_sdk_error(cls, status)])
    with pytest.raises(LLMError) as e:
        a.complete_json("compose", messages, COMPOSE_SCHEMA)
    assert e.value.kind == kind
    assert e.value.request_id == "req_123"
    assert len(mock.requests) == 1  # a 400 is never retried unchanged


def test_client_is_built_with_the_configured_timeout(monkeypatch):
    seen = {}

    class Spy:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr(anthropic, "Anthropic", Spy)
    AnthropicAdapter(get_settings({"ANTHROPIC_TIMEOUT_S": "9"})).client  # noqa: B018
    assert seen == {"timeout": 9.0, "max_retries": 1}
