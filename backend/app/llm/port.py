"""The LLM port (SPEC §7, §11): one narrow interface for both providers and the test doubles."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(Exception):
    """A provider call failed in a way the pipeline handles by degrading.

    ``kind`` is one of: auth, rate_limit, timeout, bad_request, unavailable, refusal, truncated,
    invalid, replay_miss. The message never contains question text or keys.
    """

    def __init__(self, kind: str, message: str = "", *, request_id: str | None = None):
        super().__init__(f"{kind}: {message}" if message else kind)
        self.kind = kind
        self.request_id = request_id


@dataclass
class LLMMetrics:
    provider: str
    model: str
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    stop_reason: str | None = None
    time_info: dict[str, Any] | None = None  # Cerebras server-side timing
    replay: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def model_time_s(self) -> float:
        """Time attributed to the model: Cerebras total_time when reported, else wall clock."""
        if self.time_info and isinstance(self.time_info.get("total_time"), (int, float)):
            return float(self.time_info["total_time"])
        return self.latency_s


class LLMPort(Protocol):
    provider: str
    model: str

    def complete_json(
        self, step: str, messages: list[dict], schema: dict
    ) -> tuple[dict, LLMMetrics]:
        """Run one step ("understand", "compose" or "repair") and return parsed JSON + metrics.

        Raises LLMError. No tools, no streaming, no model-chosen URLs.
        """
        ...
