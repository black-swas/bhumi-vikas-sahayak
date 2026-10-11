"""Settings from the environment (SPEC §20). Model IDs and limits come from env, never from code.

Nothing here prints or logs a value; keys are only checked for presence.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


def load_dotenv_if_present() -> None:
    """Load KEY=VALUE lines from <repo>/.env or backend/.env without overriding the real env.

    Skipped on Vercel, where settings come from the project environment.
    """
    if os.environ.get("VERCEL"):
        return
    for path in (REPO_DIR / ".env", BACKEND_DIR / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip("'\"")
            if value:
                os.environ.setdefault(key.strip(), value)


def _float(env: Mapping[str, str], key: str, default: float | None) -> float | None:
    raw = env.get(key, "").strip()
    return float(raw) if raw else default


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    llm_provider: str  # live | replay | offline
    understand_provider: str
    answer_provider: str
    cerebras_model: str
    cerebras_fallback_model: str
    anthropic_model: str
    anthropic_effort: str
    anthropic_thinking: str  # default | disabled
    cerebras_timeout_s: float
    anthropic_timeout_s: float
    cerebras_rpm_limit: int
    anthropic_rpm_limit: int | None
    max_tokens_understand: int
    max_tokens_answer: int
    request_deadline_s: float
    bm25_not_found_threshold: float | None
    audit_sink: str  # file | stdout
    log_dir: str
    has_cerebras_key: bool
    has_anthropic_key: bool
    hosted: bool  # running on Vercel (or another read-only function platform)
    region: str | None

    @property
    def mode(self) -> str:
        return {"replay": "replay", "offline": "offline"}.get(self.llm_provider, "live")


def get_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    provider = env.get("LLM_PROVIDER", "live").strip().lower() or "live"
    if env.get("DEMO_REPLAY", "0").strip() == "1":
        provider = "replay"
    return Settings(
        llm_provider=provider,
        understand_provider=env.get("UNDERSTAND_PROVIDER", "cerebras"),
        answer_provider=env.get("ANSWER_PROVIDER", "anthropic"),
        cerebras_model=env.get("CEREBRAS_MODEL_UNDERSTAND", "qwen-3.8-27b"),
        cerebras_fallback_model=env.get("CEREBRAS_FALLBACK_MODEL_ID", "gpt-oss-120b"),
        anthropic_model=env.get("ANTHROPIC_MODEL_ANSWER", "claude-haiku-5-5"),
        anthropic_effort=env.get("ANTHROPIC_EFFORT", "low"),
        anthropic_thinking=env.get("ANTHROPIC_THINKING", "default"),
        cerebras_timeout_s=_float(env, "CEREBRAS_TIMEOUT_S", 15.0) or 15.0,
        anthropic_timeout_s=_float(env, "ANTHROPIC_TIMEOUT_S", 15.0) or 15.0,
        cerebras_rpm_limit=_int(env, "CEREBRAS_RPM_LIMIT", 4),
        anthropic_rpm_limit=_int(env, "ANTHROPIC_RPM_LIMIT", 0) or None,
        max_tokens_understand=_int(env, "MAX_TOKENS_UNDERSTAND", 300),
        max_tokens_answer=_int(env, "MAX_TOKENS_ANSWER", 1500),
        request_deadline_s=_float(env, "REQUEST_DEADLINE_S", 25.0) or 25.0,
        bm25_not_found_threshold=_float(env, "BM25_NOT_FOUND_THRESHOLD", None),
        # A hosted function has no writable disk: the audit line goes to stdout whatever is set.
        audit_sink="stdout" if env.get("VERCEL") else env.get("AUDIT_SINK", "file"),
        log_dir=env.get("LOG_DIR", "logs"),
        has_cerebras_key=bool(env.get("CEREBRAS_API_KEY")),
        has_anthropic_key=bool(env.get("ANTHROPIC_API_KEY")),
        hosted=bool(env.get("VERCEL")),
        region=env.get("VERCEL_REGION") or None,
    )
