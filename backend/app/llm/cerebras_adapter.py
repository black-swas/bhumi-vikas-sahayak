"""Step A on Cerebras (SPEC §11): understand the question as strict JSON.

Model IDs, timeouts and limits come from Settings (env). Errors are caught most-specific first
and surfaced as LLMError, never as a raw SDK exception. Raw model text is never logged.
"""

import json
import time

from app.config import Settings

from .limiter import RpmLimiter, get_limiter
from .port import LLMError, LLMMetrics
from .schema_json import assert_cerebras_strict

SEED = 7


def _dump(obj) -> dict | None:
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(obj) if isinstance(obj, dict) else None


class CerebrasAdapter:
    provider = "cerebras"

    def __init__(self, settings: Settings, client=None, limiter: RpmLimiter | None = None):
        self.settings = settings
        self.model = settings.cerebras_model
        self._client = client
        self._limiter = limiter or get_limiter("cerebras", settings.cerebras_rpm_limit)

    @property
    def client(self):
        if self._client is None:
            from cerebras.cloud.sdk import Cerebras

            self._client = Cerebras(timeout=self.settings.cerebras_timeout_s, max_retries=1)
        return self._client

    def build_request(self, model: str, messages: list[dict], schema: dict) -> dict:
        assert_cerebras_strict(schema)
        # qwen can switch reasoning off; gpt-oss cannot, so it runs at the lowest effort
        effort = "none" if model.startswith("qwen") else "low"
        return {
            "model": model,
            "messages": messages,
            "max_completion_tokens": self.settings.max_tokens_understand,
            "temperature": 0,
            "seed": SEED,
            "reasoning_effort": effort,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "understand", "strict": True, "schema": schema},
            },
        }

    def complete_json(
        self, step: str, messages: list[dict], schema: dict
    ) -> tuple[dict, LLMMetrics]:
        models = [self.model]
        if self.settings.cerebras_fallback_model not in models:
            models.append(self.settings.cerebras_fallback_model)
        last: LLMError | None = None
        for model in models:
            try:
                return self._call(model, messages, schema)
            except LLMError as e:
                last = e
                if e.kind != "model_not_found":  # only a 404 on the model moves to the fallback
                    raise
        raise LLMError("unavailable", f"no Cerebras model available ({last})")

    def _call(self, model: str, messages: list[dict], schema: dict) -> tuple[dict, LLMMetrics]:
        from cerebras.cloud.sdk import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
        )

        request = self.build_request(model, messages, schema)
        self._limiter.acquire(max_wait_s=self.settings.request_deadline_s * 0.6)
        t0 = time.perf_counter()
        try:
            resp = self.client.chat.completions.create(**request)
        except NotFoundError as e:
            raise LLMError("model_not_found", model) from e
        except RateLimitError as e:
            raise LLMError("rate_limit", "Cerebras 429") from e
        except (AuthenticationError, PermissionDeniedError) as e:
            raise LLMError("auth", "Cerebras rejected the key") from e
        except BadRequestError as e:
            raise LLMError("bad_request", "Cerebras 400: request shape") from e
        except APITimeoutError as e:
            raise LLMError("timeout", "Cerebras timeout") from e
        except APIStatusError as e:
            raise LLMError("unavailable", f"Cerebras HTTP {e.status_code}") from e
        except APIConnectionError as e:
            raise LLMError("unavailable", "Cerebras connection error") from e
        latency = time.perf_counter() - t0

        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        details = getattr(usage, "prompt_tokens_details", None)
        metrics = LLMMetrics(
            provider=self.provider,
            model=getattr(resp, "model", model) or model,
            latency_s=latency,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cached_tokens=getattr(details, "cached_tokens", 0) or 0,
            stop_reason=choice.finish_reason,
            time_info=_dump(getattr(resp, "time_info", None)),
        )
        if choice.finish_reason == "length":
            raise LLMError("truncated", "Cerebras hit max_completion_tokens")
        try:
            data = json.loads(choice.message.content or "")
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMError("invalid", "Cerebras returned text that is not JSON") from e
        if not isinstance(data, dict):
            raise LLMError("invalid", "Cerebras returned JSON that is not an object")
        return data, metrics
