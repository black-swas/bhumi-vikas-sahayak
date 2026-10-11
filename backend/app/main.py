"""FastAPI app (SPEC §15). Every route lives under /api; the backend is stateless.

The corpus and index load once, in the lifespan hook. No route writes to disk except the audit
line, and that goes to stdout on a hosted deployment (AUDIT_SINK=stdout).
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .audit import AuditLog
from .config import REPO_DIR, get_settings, load_dotenv_if_present
from .corpus.index import rule_key
from .i18n import redact_pii
from .pipeline import OverrideError, Pipeline, build_pipeline
from .schemas import AnswerCard, AskRequest

log = logging.getLogger(__name__)

PER_IP_PER_MINUTE = 20
EVAL_REPORT = Path(__file__).resolve().parents[1] / "evals" / "report.json"


class IpLimiter:
    """Best-effort per-IP limit, in memory, per instance (SPEC §19)."""

    def __init__(self, per_minute: int = PER_IP_PER_MINUTE):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[ip]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


class FeedbackIn(BaseModel):
    request_id: str = Field(max_length=40)
    reason: Literal["wrong_number", "wrong_rule", "rule_not_found", "bad_hindi", "unclear", "other"]
    note: str = Field(default="", max_length=300)
    question: str = Field(default="", max_length=500)
    consent: bool = False


class FeedbackAck(BaseModel):
    ack_id: str
    stored: bool


def create_app(pipeline: Pipeline | None = None, web_root: Path | None = None) -> FastAPI:
    load_dotenv_if_present()
    settings = get_settings()
    limiter = IpLimiter()
    runtime = {"hosted": settings.hosted, "region": settings.region}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pipeline = pipeline or build_pipeline(settings, AuditLog(settings))
        yield

    app = FastAPI(
        title="Bhumi Vikas Sahayak",
        description="Prototype, not legal advice.",
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url=None,
        redoc_url=None,
    )

    def pipe(request: Request) -> Pipeline:
        return request.app.state.pipeline

    def client_ip(request: Request) -> str:
        # Behind Vercel every request arrives from the platform's proxy, so the socket address
        # would put all clerks in one bucket. Vercel sets these headers itself (a client cannot
        # forge them), so they are trusted only there; anywhere else they are ignored.
        if settings.hosted:
            forwarded = request.headers.get("x-vercel-forwarded-for") or request.headers.get(
                "x-forwarded-for", ""
            )
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        return request.client.host if request.client else "unknown"

    @app.get("/api/health")
    def health(request: Request) -> dict:
        p = pipe(request)
        s = p.settings
        return {
            "status": "ok",
            "mode": p.mode,
            "prototype": True,
            "providers": {
                "A": {
                    "provider": s.understand_provider,
                    "model": s.cerebras_model,
                    "configured": p.understand is not None,
                },
                "B": {
                    "provider": s.answer_provider,
                    "model": s.anthropic_model,
                    "configured": p.compose is not None,
                },
            },
            "corpus": {
                "sha256": p.corpus.sha256,
                "rules": len(p.corpus.rules),
                "chunks": len(p.corpus.chunks),
                "pages": p.corpus.n_pages,
            },
            "runtime": runtime,
            "amendments_source": "baseline",
            "amendments": [a["id"] for a in p.amendments],
            "last_eval": _eval_summary(),
        }

    @app.post("/api/ask", response_model=AnswerCard)
    def ask(req: AskRequest, request: Request):
        if not limiter.allow(client_ip(request)):
            raise HTTPException(status_code=429, detail="Too many questions: wait a minute.")
        try:
            return pipe(request).ask(req)
        except OverrideError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @app.get("/api/rule/{rule_id}")
    def rule(rule_id: str, request: Request) -> dict:
        p = pipe(request)
        key = rule_key(rule_id)
        chunks = p.index.by_key.get(key)
        if not chunks:
            raise HTTPException(status_code=404, detail="No such rule")
        real = p.corpus.rule_by_id(chunks[0].parent or chunks[0].rule)
        inserted = chunks[0].parent is not None
        if inserted:
            text = "\n\n".join(c.text for c in chunks)
            pages = sorted({pg for c in chunks for pg in c.pages})
            page_start, page_end = pages[0], pages[-1]
            title = chunks[0].title
        else:
            text, page_start, page_end, title = (
                real.text,
                real.page_start,
                real.page_end,
                real.title,
            )
        return {
            "rule": chunks[0].rule,
            "title": title,
            "parent": chunks[0].parent,
            "part": None if inserted else real.part,
            "page_start": page_start,
            "page_end": page_end,
            "text": text,
            "chunks": [{"id": c.id, "label": c.label, "pages": list(c.pages)} for c in chunks],
            "pdf_en": f"/pdf/rules-en.pdf#page={page_start}",
            "pdf_hi": f"/pdf/rules-hi.pdf#page={page_start}",
        }

    @app.post("/api/feedback", response_model=FeedbackAck)
    def feedback(body: FeedbackIn, request: Request):
        """A clerk's report on an answer. Stateless: the redacted report goes to the audit sink."""
        if not limiter.allow(client_ip(request)):
            raise HTTPException(status_code=429, detail="Too many reports: wait a minute.")
        note, _ = redact_pii(body.note)
        question, _ = redact_pii(body.question) if body.consent else ("", 0)
        ack = hashlib.sha256(f"{body.request_id}|{time.time_ns()}".encode()).hexdigest()[:12]
        audit = pipe(request).audit
        if audit is not None:
            audit.write(
                {
                    "event": "feedback",
                    "ack_id": ack,
                    "request_id": body.request_id,
                    "reason": body.reason,
                    "note": note,
                    "question": question or None,
                }
            )
        return FeedbackAck(ack_id=ack, stored=audit is not None)

    @app.get("/api/eval/latest")
    def eval_latest() -> JSONResponse:
        if not EVAL_REPORT.is_file():
            return JSONResponse({"available": False})
        return JSONResponse({"available": True, **json.loads(EVAL_REPORT.read_text("utf-8"))})

    _mount_web(app, web_root)
    return app


def _eval_summary() -> dict | None:
    if not EVAL_REPORT.is_file():
        return None
    data = json.loads(EVAL_REPORT.read_text("utf-8"))
    return data.get("summary")


def _mount_web(app: FastAPI, web_root: Path | None = None) -> None:
    """SERVE_WEB=1: the counter PC serves the built SPA from web/build/ on the same origin.

    ``web_root`` forces it on for a given folder (used by tests).
    """
    if web_root is None and (os.environ.get("SERVE_WEB") != "1" or os.environ.get("VERCEL")):
        return  # on Vercel the CDN serves the web service; the function never does
    root = (web_root or REPO_DIR / "web" / "build").resolve()
    if not root.is_dir():
        log.warning("SERVE_WEB=1 but web/build/ does not exist; build the web app first")
        return

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/") or path == "api":
            raise HTTPException(status_code=404)
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            return FileResponse(target)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404)


app = create_app()
