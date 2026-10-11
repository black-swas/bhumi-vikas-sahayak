"""Audit lines (SPEC §19, CLAUDE.md #12).

Local: one JSON line appended to logs/audit.jsonl, with the question after PII redaction.
Hosted (AUDIT_SINK=stdout): the same line on stdout, with the question replaced by its hash and
length, because log retention there is outside our control. Never raw model text, never a key.
"""

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import REPO_DIR, Settings

IST = timezone(timedelta(hours=5, minutes=30))


def ist_now() -> datetime:
    return datetime.now(IST)


class AuditLog:
    def __init__(self, settings: Settings):
        self.sink = settings.audit_sink
        log_dir = Path(settings.log_dir)
        self.path = (log_dir if log_dir.is_absolute() else REPO_DIR / log_dir) / "audit.jsonl"

    def write(self, event: dict) -> None:
        event = {"ts_ist": ist_now().isoformat(timespec="seconds"), **event}
        question = event.pop("question", None)
        if question is not None:
            if self.sink == "stdout":
                event["question_sha256"] = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
                event["question_len"] = len(question)
            else:
                event["question"] = question
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        try:
            if self.sink == "stdout":
                print(line, file=sys.stdout, flush=True)
            elif self.sink == "file":
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            # any other sink value (for example "none") discards the line
        except OSError:
            pass  # auditing must never break an answer
