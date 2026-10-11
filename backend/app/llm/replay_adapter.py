"""Recorded responses: the demo kill switch (DEMO_REPLAY=1) and free eval reruns (SPEC §11, §18).

A recording is keyed by sha256(provider, model, effort, prompt version, step, messages). The
store is read-only unless ``writable`` is set, which only local scripts do: a stateless host
(Vercel) never writes.
"""

import hashlib
import json
from pathlib import Path

from .port import LLMError, LLMMetrics, LLMPort
from .prompts import PROMPT_VERSION

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "evals" / "recordings"


def recording_key(
    provider: str, model: str, effort: str, step: str, messages: list[dict], schema: dict
) -> str:
    payload = json.dumps(
        [provider, model, effort, PROMPT_VERSION, step, messages, schema],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ReplayAdapter:
    """Serves a recording when one exists; otherwise calls ``inner`` (if any) and may save it."""

    def __init__(
        self,
        provider: str,
        model: str,
        effort: str = "",
        inner: LLMPort | None = None,
        directory: Path | None = None,
        writable: bool = False,
        read_cache: bool = True,
    ):
        self.provider = provider
        self.model = model
        self.effort = effort
        self.inner = inner
        self.dir = Path(directory) if directory else RECORDINGS_DIR
        self.writable = writable
        self.read_cache = read_cache  # False: always call ``inner`` (a fresh run, not a cached one)

    def _path(self, step: str, messages: list[dict], schema: dict) -> Path:
        key = recording_key(self.provider, self.model, self.effort, step, messages, schema)
        return self.dir / f"{key}.json"

    def complete_json(
        self, step: str, messages: list[dict], schema: dict
    ) -> tuple[dict, LLMMetrics]:
        path = self._path(step, messages, schema)
        if self.read_cache and path.is_file():
            rec = json.loads(path.read_text(encoding="utf-8"))
            m = rec["metrics"]
            metrics = LLMMetrics(
                provider=self.provider,
                model=self.model,
                latency_s=m.get("latency_s", 0.0),
                input_tokens=m.get("input_tokens", 0),
                output_tokens=m.get("output_tokens", 0),
                cached_tokens=m.get("cached_tokens", 0),
                stop_reason=m.get("stop_reason"),
                time_info=m.get("time_info"),
                replay=True,
            )
            return rec["response"], metrics
        if self.inner is None:
            raise LLMError("replay_miss", f"no recording for step '{step}'")
        data, metrics = self.inner.complete_json(step, messages, schema)
        if self.writable:
            self.dir.mkdir(parents=True, exist_ok=True)
            rec = {
                "step": step,
                "response": data,
                "metrics": {
                    "latency_s": metrics.latency_s,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "cached_tokens": metrics.cached_tokens,
                    "stop_reason": metrics.stop_reason,
                    "time_info": metrics.time_info,
                },
            }
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return data, metrics
