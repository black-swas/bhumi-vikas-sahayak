import json
from types import SimpleNamespace

import cerebras.cloud.sdk as cs
import pytest

from app.config import get_settings
from app.llm.cerebras_adapter import CerebrasAdapter
from app.llm.fake_adapter import FakeLLM
from app.llm.limiter import RpmLimiter
from app.llm.port import LLMError, LLMMetrics
from app.llm.replay_adapter import ReplayAdapter, recording_key
from app.llm.schema_json import (
    COMPOSE_SCHEMA,
    UNDERSTAND_SCHEMA,
    assert_cerebras_strict,
)
from tests.helpers import understand_json

# --- strict schemas --------------------------------------------------------------------------


def test_understand_schema_is_valid_for_cerebras_strict_mode():
    assert_cerebras_strict(UNDERSTAND_SCHEMA)
    assert len(json.dumps(UNDERSTAND_SCHEMA, separators=(",", ":"))) <= 5000
    assert UNDERSTAND_SCHEMA["additionalProperties"] is False
    assert UNDERSTAND_SCHEMA["properties"]["params"]["additionalProperties"] is False
    assert set(UNDERSTAND_SCHEMA["required"]) == {"in_scope", "intent", "search_query_en", "params"}
    assert "out_of_scope" in UNDERSTAND_SCHEMA["properties"]["intent"]["enum"]


def test_compose_schema_is_strict_too():
    assert_cerebras_strict(COMPOSE_SCHEMA)
    assert set(COMPOSE_SCHEMA["properties"]["status"]["enum"]) == {
        "answered", "not_found", "need_more_info",
    }  # fmt: skip


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "object", "properties": {"a": {"type": "string", "pattern": "x"}},
         "required": ["a"], "additionalProperties": False},
        {"type": "object",
         "properties": {"a": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
         "required": ["a"], "additionalProperties": False},
        {"type": "object", "properties": {"a": {"oneOf": [{"type": "string"}]}},
         "required": ["a"], "additionalProperties": False},
        {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
        {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
         "required": ["a"], "additionalProperties": False},
        {"type": "object", "properties": {"a": {"type": "string", "enum": ["x" * 5000]}},
         "required": ["a"], "additionalProperties": False},
    ],
)  # fmt: skip
def test_strict_validator_rejects_unsupported_schemas(bad):
    with pytest.raises(ValueError):
        assert_cerebras_strict(bad)


# --- Cerebras request and errors -------------------------------------------------------------


class FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        reply = self.replies[min(len(self.requests), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


def cerebras_response(content, finish="stop", model="qwen-3.8-27b"):
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=700,
            completion_tokens=90,
            prompt_tokens_details=SimpleNamespace(cached_tokens=64),
        ),
        time_info=SimpleNamespace(model_dump=lambda: {"total_time": 0.21, "queue_time": 0.01}),
    )


def cerebras(replies, **env):
    s = get_settings({"CEREBRAS_RPM_LIMIT": "100", **env})
    completions = FakeCompletions(replies)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return CerebrasAdapter(s, client=client, limiter=RpmLimiter(100)), completions


MESSAGES = [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]


def test_cerebras_request_and_metrics():
    reply = cerebras_response(json.dumps(understand_json("lifts")))
    a, comp = cerebras([reply])
    data, m = a.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert data["intent"] == "lifts"
    (req,) = comp.requests
    assert req["model"] == "qwen-3.8-27b" and req["reasoning_effort"] == "none"
    assert req["max_completion_tokens"] == 300
    assert req["response_format"]["type"] == "json_schema"
    assert req["response_format"]["json_schema"]["strict"] is True
    assert req["response_format"]["json_schema"]["schema"] == UNDERSTAND_SCHEMA
    assert "tools" not in req  # never combined with response_format
    assert m.provider == "cerebras" and m.time_info == {"total_time": 0.21, "queue_time": 0.01}
    assert (m.input_tokens, m.output_tokens, m.cached_tokens) == (700, 90, 64)
    assert m.model_time_s == 0.21


def test_cerebras_falls_back_to_the_second_model_only_on_a_404():
    not_found = cs.NotFoundError.__new__(cs.NotFoundError)
    Exception.__init__(not_found, "x")
    ok = cerebras_response(json.dumps(understand_json("lifts")), model="gpt-oss-120b")
    a, comp = cerebras([not_found, ok])
    data, m = a.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert [r["model"] for r in comp.requests] == ["qwen-3.8-27b", "gpt-oss-120b"]
    assert comp.requests[1]["reasoning_effort"] == "low"  # gpt-oss cannot switch reasoning off
    assert m.model == "gpt-oss-120b"


def test_cerebras_length_and_invalid_json_are_errors():
    a, _ = cerebras([cerebras_response("{", finish="length")])
    with pytest.raises(LLMError) as e:
        a.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert e.value.kind == "truncated"
    a, _ = cerebras([cerebras_response("not json")])
    with pytest.raises(LLMError) as e:
        a.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert e.value.kind == "invalid"


@pytest.mark.parametrize(
    "cls,kind",
    [
        (cs.RateLimitError, "rate_limit"),
        (cs.AuthenticationError, "auth"),
        (cs.BadRequestError, "bad_request"),
        (cs.InternalServerError, "unavailable"),
    ],
)
def test_cerebras_sdk_errors_become_llm_errors(cls, kind):
    err = cls.__new__(cls)
    Exception.__init__(err, "x")
    err.status_code = 500
    a, _ = cerebras([err])
    with pytest.raises(LLMError) as e:
        a.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert e.value.kind == kind


# --- limiter ---------------------------------------------------------------------------------


def test_rpm_limiter_blocks_the_fifth_call_until_the_window_moves():
    now = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    lim = RpmLimiter(4, clock=lambda: now[0], sleep=sleep)
    for _ in range(4):
        assert lim.acquire() == 0.0
    waited = lim.acquire(max_wait_s=120)  # the fifth must wait for the first to age out
    assert waited >= 59 and sum(slept) >= 59


def test_rpm_limiter_gives_up_rather_than_exceed_the_wait_budget():
    now = [0.0]
    lim = RpmLimiter(1, clock=lambda: now[0], sleep=lambda s: None)
    lim.acquire()
    with pytest.raises(LLMError) as e:
        lim.acquire(max_wait_s=5)
    assert e.value.kind == "rate_limit"


# --- replay and fake -------------------------------------------------------------------------


def test_replay_records_then_serves_without_the_inner_model(tmp_path):
    inner = FakeLLM({"understand": understand_json("lifts")})
    rec = ReplayAdapter("cerebras", "m", "none", inner=inner, directory=tmp_path, writable=True)
    first, _ = rec.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert len(inner.calls) == 1 and len(list(tmp_path.glob("*.json"))) == 1

    replay = ReplayAdapter("cerebras", "m", "none", directory=tmp_path)  # no inner, read-only
    again, metrics = replay.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert again == first and metrics.replay is True


def test_replay_miss_is_an_error_and_never_writes(tmp_path):
    replay = ReplayAdapter("cerebras", "m", "none", directory=tmp_path)
    with pytest.raises(LLMError) as e:
        replay.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert e.value.kind == "replay_miss" and not list(tmp_path.iterdir())
    inner = FakeLLM({"understand": understand_json("lifts")})
    read_only = ReplayAdapter("c", "m", "", inner=inner, directory=tmp_path, writable=False)
    read_only.complete_json("understand", MESSAGES, UNDERSTAND_SCHEMA)
    assert not list(tmp_path.iterdir())  # a stateless host never writes


def test_recording_key_depends_on_every_input():
    base = recording_key("p", "m", "low", "compose", MESSAGES, {})
    assert base == recording_key("p", "m", "low", "compose", MESSAGES, {})
    for other in (
        recording_key("q", "m", "low", "compose", MESSAGES, {}),
        recording_key("p", "n", "low", "compose", MESSAGES, {}),
        recording_key("p", "m", "high", "compose", MESSAGES, {}),
        recording_key("p", "m", "low", "repair", MESSAGES, {}),
        recording_key("p", "m", "low", "compose", [*MESSAGES, MESSAGES[0]], {}),
    ):
        assert other != base


def test_prompt_ids_are_deterministic_so_recordings_hit(built):
    from app.llm.prompts import build_compose_messages

    _, index = built
    chunks = index.resolve_pin("83")
    a = build_compose_messages("lifts?", "en", chunks, [])
    b = build_compose_messages("lifts?", "en", chunks, [])
    assert a == b
    assert a != build_compose_messages("lifts above 15 m?", "en", chunks, [])


def test_fake_llm_script_behaviour():
    fake = FakeLLM({"compose": [{"a": 1}, LLMError("timeout")]}, strict=True)
    assert fake.complete_json("compose", [], {})[0] == {"a": 1}
    with pytest.raises(LLMError):
        fake.complete_json("compose", [], {})
    with pytest.raises(AssertionError):
        fake.complete_json("compose", [], {})
    with pytest.raises(LLMError):
        fake.complete_json("understand", [], {})
    assert isinstance(FakeLLM({"x": {}}).complete_json("x", [], {})[1], LLMMetrics)
