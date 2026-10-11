"""Scripted LLM for offline unit tests (CLAUDE.md #8: tests never call a real API)."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .port import LLMError, LLMMetrics

Response = dict | Exception | Callable[[str, list[dict], dict], dict]


class FakeLLM:
    """Plays back scripted responses, in order, per step ("understand", "compose", "repair").

    A response may be a dict, an exception to raise (an LLMError, usually), or a callable
    ``(step, messages, schema) -> dict``. When a step's queue runs dry the last item repeats
    unless ``strict`` is set. Every call is recorded in ``calls``.
    """

    def __init__(
        self,
        script: dict[str, list[Response] | Response] | None = None,
        provider: str = "fake",
        model: str = "fake-model",
        strict: bool = False,
    ):
        self.provider = provider
        self.model = model
        self.strict = strict
        self.script: dict[str, list[Response]] = {
            k: list(v) if isinstance(v, list) else [v] for k, v in (script or {}).items()
        }
        self._used: dict[str, int] = defaultdict(int)
        self.calls: list[dict[str, Any]] = []

    def complete_json(
        self, step: str, messages: list[dict], schema: dict
    ) -> tuple[dict, LLMMetrics]:
        self.calls.append({"step": step, "messages": messages, "schema": schema})
        queue = self.script.get(step)
        if not queue:
            raise LLMError("unavailable", f"FakeLLM has no script for step '{step}'")
        i = self._used[step]
        if i >= len(queue) and self.strict:
            raise AssertionError(f"FakeLLM script for '{step}' exhausted")
        self._used[step] += 1
        item = queue[min(i, len(queue) - 1)]
        if isinstance(item, Exception):
            raise item
        data = item(step, messages, schema) if callable(item) else item
        return dict(data), LLMMetrics(
            provider=self.provider,
            model=self.model,
            latency_s=0.01,
            input_tokens=100,
            output_tokens=50,
            stop_reason="end_turn",
        )

    def calls_for(self, step: str) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["step"] == step]
