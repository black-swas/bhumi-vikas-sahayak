"""Tiny .env loader for the smoke scripts (no extra dependency). Never prints values."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_env() -> None:
    for path in (REPO / ".env", REPO / "backend" / ".env"):
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
