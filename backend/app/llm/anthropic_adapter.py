"""Step B on Anthropic Claude Haiku 5.5 (SPEC §11).

Haiku 5.5 returns a 400 for temperature, top_p, top_k, an assistant prefill and
thinking.budget_tokens, so ``build_request`` never emits them and ``assert_request_shape``
guards the final body. Thinking is on by default and counts toward max_tokens, so the answer is
read from the blocks of type "text", never from content[0].
"""

import json
import time

from app.config import Settings

from .limiter import RpmLimiter, get_limiter
from .port import LLMError, LLMMetrics

FORBIDDEN_PARAMS = ("temperature", "top_p", "top_k", "budget_tokens")
MAX_TOKENS_RETRY_FACTOR = 2


def assert_request_shape(request: dict) -> None:
    """Raise ValueError if the body would be a 400 on Haiku 5.5."""
    bad = [k for k in FORBIDDEN_PARAMS if k in request]
    thinking = request.get("thinking")
    if isinstance(thinking, dict) and "budget_tokens" in thinking:
        bad.append("thinking.budget_tokens")
    if bad:
        raise ValueError(f"forbidden parameter(s) for Haiku 5.5: {bad}")
    messages = request.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        raise ValueError("messages must end with a user turn (no assistant prefill)")
    if any(m.get("role") not in ("user", "assistant") for m in messages):
        raise ValueError("system text goes in the system parameter, not in messages")


class AnthropicAdapter:
    provider = "anthropic"

    def __init__(self, settings: Settings, client=None, limiter: RpmLimiter | None = None):
        self.settings = settings
        self.model = settings.anthropic_model
        self._client = client
        rpm = settings.anthropic_rpm_limit
        self._limiter = limiter or (get_limiter("anthropic", rpm) if rpm else None)

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                timeout=self.settings.anthropic_timeout_s, max_retries=1
            )
        return self._client

    def build_request(
        self, messages: list[dict], schema: dict, max_tokens: int | None = None
    ) -> dict:
        system = [
            {"type": "text", "text": m["content"], "cache_control": {"type": "ephemeral"}}
            for m in messages
            if m["role"] == "system"
        ]
        turns = [
            {"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"
        ]
        request: dict = {
            "model": self.model,
            "max_tokens": max_tokens or self.settings.max_tokens_answer,
            "messages": turns,
            "output_config": {
                "effort": self.settings.anthropic_effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }
        if system:
            request["system"] = system
        if self.settings.anthropic_thinking == "disabled":
            request["thinking"] = {"type": "disabled"}
        assert_request_shape(request)
        return request

    def complete_json(
        self, step: str, messages: list[dict], schema: dict
    ) -> tuple[dict, LLMMetrics]:
        max_tokens = self.settings.max_tokens_answer
        for attempt in (1, 2):
            request = self.build_request(messages, schema, max_tokens)
            data, metrics = self._call(request)
            if metrics.stop_reason == "max_tokens":
                # thinking can use up the cap: one retry with a larger one, never a truncated answer
                if attempt == 1:
                    max_tokens *= MAX_TOKENS_RETRY_FACTOR
                    continue
                raise LLMError("truncated", "Haiku hit max_tokens twice")
            return data, metrics
        raise LLMError("truncated", "Haiku hit max_tokens")  # unreachable

    def _call(self, request: dict) -> tuple[dict, LLMMetrics]:
        import anthropic

        if self._limiter:
            self._limiter.acquire(max_wait_s=self.settings.request_deadline_s * 0.6)
        t0 = time.perf_counter()
        try:
            resp = self.client.messages.create(**request)
        except anthropic.NotFoundError as e:
            raise LLMError("unavailable", "model not found", request_id=e.request_id) from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate_limit", "Anthropic 429", request_id=e.request_id) from e
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            raise LLMError("auth", "Anthropic rejected the key", request_id=e.request_id) from e
        except anthropic.BadRequestError as e:
            # a request-shape bug: never retried unchanged
            raise LLMError("bad_request", "Anthropic 400", request_id=e.request_id) from e
        except anthropic.APITimeoutError as e:
            raise LLMError("timeout", "Anthropic timeout") from e
        except anthropic.APIStatusError as e:  # 402, 500, 529 and the rest
            raise LLMError(
                "unavailable", f"Anthropic HTTP {e.status_code}", request_id=e.request_id
            ) from e
        except anthropic.APIConnectionError as e:
            raise LLMError("unavailable", "Anthropic connection error") from e
        latency = time.perf_counter() - t0

        usage = resp.usage
        metrics = LLMMetrics(
            provider=self.provider,
            model=resp.model,
            latency_s=latency,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cached_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            stop_reason=resp.stop_reason,
        )
        if resp.stop_reason == "refusal":
            category = getattr(getattr(resp, "stop_details", None), "category", None)
            raise LLMError("refusal", f"Haiku refused (category: {category})")
        if resp.stop_reason == "max_tokens":
            return {}, metrics  # the caller retries once with a larger cap
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMError("invalid", "Haiku returned text that is not JSON") from e
        if not isinstance(data, dict):
            raise LLMError("invalid", "Haiku returned JSON that is not an object")
        return data, metrics
