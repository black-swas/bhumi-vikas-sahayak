"""Pre-flight checks before a Vercel deploy or a public push (SPEC §16A, §19, §25).

    uv --directory backend run python scripts/preflight.py

Read-only. Exits 1 if any check FAILs. It never opens ``.env`` (CLAUDE.md #9): it only checks
that ``.env`` is ignored. Secret hits are reported as file:line plus a masked preview, never the
full value. There is no git history here to scan: do that with gitleaks before the first push.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
WEB = REPO / "web"

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass(frozen=True)
class Finding:
    level: str
    check: str
    detail: str = ""


def ok(check: str, detail: str = "") -> Finding:
    return Finding(PASS, check, detail)


def warn(check: str, detail: str) -> Finding:
    return Finding(WARN, check, detail)


def fail(check: str, detail: str) -> Finding:
    return Finding(FAIL, check, detail)


# --- vercel.json ----------------------------------------------------------------------------

EXPECTED_SERVICES = {
    "web": {"root": "web/"},
    "api": {"root": "backend/", "entrypoint": "app.main:app"},
}
EXPECTED_REWRITES = [
    {"source": "/api/(.*)", "destination": {"service": "api"}},
    {"source": "/(.*)", "destination": {"service": "web"}},
]
# Not valid at the top level once `services` exists (Vercel docs, "Top-level configuration in
# services mode"): they belong inside a service.
INVALID_TOP_LEVEL = (
    "functions", "installCommand", "buildCommand", "devCommand", "ignoreCommand",
    "outputDirectory", "framework",
)  # fmt: skip


def check_vercel_json(root: Path = REPO) -> list[Finding]:
    path = root / "vercel.json"
    if not path.is_file():
        return [fail("vercel.json", "missing")]
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [fail("vercel.json", f"not valid JSON: {e}")]
    out = []
    if config.get("services") == EXPECTED_SERVICES:
        out.append(ok("vercel.json services", "web (web/) and api (backend/, app.main:app)"))
    else:
        out.append(fail("vercel.json services", f"expected {EXPECTED_SERVICES}"))
    if config.get("rewrites") == EXPECTED_REWRITES:
        out.append(ok("vercel.json rewrites", "/api/* -> api, everything else -> web"))
    else:
        out.append(fail("vercel.json rewrites", f"expected {EXPECTED_REWRITES}"))
    bad = [k for k in INVALID_TOP_LEVEL if k in config]
    out.append(
        fail("vercel.json top-level keys", f"not valid with services: {bad}")
        if bad
        else ok("vercel.json top-level keys", "no build/runtime keys beside services")
    )
    if re.search(r"VITE_|api[_-]?key|secret", path.read_text(encoding="utf-8"), re.I):
        out.append(fail("vercel.json contents", "mentions a key, secret or VITE_ variable"))
    return out


def check_vercelignore(root: Path = REPO) -> list[Finding]:
    path = root / ".vercelignore"
    if not path.is_file():
        return [warn(".vercelignore", "missing: a CLI deploy would upload the reference folders")]
    lines = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()}
    needed = [
        ".env",
        "OpenHands-main/",
        "bhopal-impact-lab-2026-problem-statements-main/",
        "node_modules/",
    ]
    missing = [n for n in needed if n not in lines]
    return [
        fail(".vercelignore", f"does not exclude {missing}")
        if missing
        else ok(".vercelignore", "excludes .env, the reference folders and node_modules")
    ]


# --- gitignore and secrets -----------------------------------------------------------------------

REQUIRED_IGNORES = [
    ".env", ".env.*", "!.env.example", "logs/", "backend/data/runtime/", "web/build/", ".venv/",
    "__pycache__/", "node_modules/", "OpenHands-main/",
    "bhopal-impact-lab-2026-problem-statements-main/",
]  # fmt: skip


def check_gitignore(root: Path = REPO) -> list[Finding]:
    path = root / ".gitignore"
    if not path.is_file():
        return [fail(".gitignore", "missing")]
    lines = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()}
    missing = [i for i in REQUIRED_IGNORES if i not in lines]
    out = [
        fail(".gitignore", f"missing entries: {missing}")
        if missing
        else ok(".gitignore", "ignores .env, logs, runtime data, build output, venvs, references")
    ]
    if (root / ".env").exists():
        out.append(ok(".env", "present locally and ignored (contents not read)"))
    return out


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Cerebras key", re.compile(r"csk-[A-Za-z0-9]{20,}")),
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("database URL with a password", re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s:@/]+@")),
    (
        "key-like assignment",
        re.compile(
            r"(?i)\b[A-Z0-9_]*(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"']?"
            r"(?P<value>[A-Za-z0-9_\-/+=]{24,})[\"']?"
        ),
    ),
]
PLACEHOLDER = re.compile(r"(?i)your|xxx|change|example|placeholder|dummy|test|<|>|\.\.\.")
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "build", ".react-router", "__pycache__", ".pytest_cache",
    ".ruff_cache", "OpenHands-main", "bhopal-impact-lab-2026-problem-statements-main", "logs",
}  # fmt: skip
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".json", ".jsonl", ".md", ".txt", ".toml",
    ".yml", ".yaml", ".ps1", ".css", ".html", ".example", ".cfg", ".ini", "", ".pem", ".key",
    ".crt", ".p8", ".sh", ".bat", ".cmd", ".conf", ".properties", ".env", ".sql",
}  # fmt: skip


def _is_env_file(path: Path) -> bool:
    return path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example")


def iter_text_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if _is_env_file(path) or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if name == "package-lock.json" or name == "uv.lock" or path.stat().st_size > 2_000_000:
                continue
            yield path


def mask(value: str) -> str:
    return f"{value[:4]}…({len(value)} chars)"


def scan_secrets(root: Path = REPO) -> list[Finding]:
    hits: list[str] = []
    scanned = 0
    for path in iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                value = m.groupdict().get("value") or m.group(0)
                if PLACEHOLDER.search(line) or (
                    label == "key-like assignment" and "os.environ" in line
                ):
                    continue
                hits.append(f"{path.relative_to(root)}:{lineno} {label} {mask(value)}")
    if hits:
        return [
            fail(
                "secret scan",
                "; ".join(hits[:10]) + (f" (+{len(hits) - 10} more)" if len(hits) > 10 else ""),
            )
        ]
    return [ok("secret scan", f"{scanned} text files, no key patterns (git history not scanned)")]


VITE_SECRET = re.compile(r"VITE_[A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|DATABASE|HASH|DSN)")


def check_vite_secrets(root: Path = REPO) -> list[Finding]:
    """Vite compiles every VITE_* variable into the public bundle (CLAUDE.md #11)."""
    hits = []
    for base in (root / "web", root / ".env.example", root / "vercel.json"):
        paths = [base] if base.is_file() else list(iter_text_files(base)) if base.is_dir() else []
        for path in paths:
            if path.name == "check-hygiene.mjs":
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
            ):
                if VITE_SECRET.search(line):
                    hits.append(f"{path.relative_to(root)}:{lineno}")
    web_env = (
        [p for p in (root / "web").glob(".env*") if p.name != ".env.example"]
        if (root / "web").is_dir()
        else []
    )
    out = [
        fail("VITE_ secrets", "secret-looking VITE_ variable at " + ", ".join(hits))
        if hits
        else ok(
            "VITE_ secrets", "no secret-looking VITE_ variable in web/, .env.example or vercel.json"
        )
    ]
    for p in web_env:
        out.append(warn("web env file", f"{p.name} exists: only public VITE_ values may be in it"))
    return out


def check_env_example(root: Path = REPO) -> list[Finding]:
    path = root / ".env.example"
    if not path.is_file():
        return [fail(".env.example", "missing")]
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    required = [
        "LLM_PROVIDER", "UNDERSTAND_PROVIDER", "ANSWER_PROVIDER", "CEREBRAS_API_KEY",
        "ANTHROPIC_API_KEY", "CEREBRAS_MODEL_UNDERSTAND", "ANTHROPIC_MODEL_ANSWER",
        "AUDIT_SINK", "SERVE_WEB", "REQUEST_DEADLINE_S",
    ]  # fmt: skip
    missing = [k for k in required if k not in values]
    secrets = [
        k for k in values if re.search(r"KEY|SECRET|PASSWORD_HASH|DATABASE_URL", k) and values[k]
    ]
    out = []
    out.append(
        fail(".env.example", f"missing variables: {missing}")
        if missing
        else ok(".env.example", "has every variable the hosted copy needs")
    )
    out.append(
        fail(".env.example secrets", f"has a value for {secrets}")
        if secrets
        else ok(".env.example secrets", "all key and password variables are blank")
    )
    return out


# --- backend packaging --------------------------------------------------------------------------

RUNTIME_ALLOWED = {"fastapi", "uvicorn", "pydantic", "cerebras_cloud_sdk", "anthropic", "psycopg"}
DEV_ONLY = {"pytest", "ruff", "httpx", "mypy", "black", "coverage"}


def _name(requirement: str) -> str:
    return re.split(r"[\s<>=!~\[;]", requirement.strip(), maxsplit=1)[0].lower().replace("-", "_")


def check_backend_packaging(backend: Path = BACKEND) -> list[Finding]:
    out = []
    data = tomllib.loads((backend / "pyproject.toml").read_text(encoding="utf-8"))
    deps = {_name(d) for d in data["project"]["dependencies"]}
    extra = deps - RUNTIME_ALLOWED
    dev = deps & DEV_ONLY
    out.append(
        fail("runtime dependencies", f"not allowed at runtime: {sorted(extra | dev)}")
        if extra or dev
        else ok("runtime dependencies", ", ".join(sorted(deps)))
    )
    out.append(
        ok("dev tools", "pytest and ruff are in the dev group, not in dependencies")
        if {"pytest", "ruff"}
        <= {_name(d) for d in data.get("dependency-groups", {}).get("dev", [])}
        else fail("dev tools", "pytest and ruff should be in [dependency-groups].dev")
    )
    out.append(
        ok("python version", data["project"]["requires-python"])
        if "3.12" in data["project"]["requires-python"]
        and "<3.13" in data["project"]["requires-python"]
        else fail("python version", f"requires-python is {data['project']['requires-python']}")
    )
    pin = (
        (backend / ".python-version").read_text(encoding="utf-8").strip()
        if (backend / ".python-version").is_file()
        else ""
    )
    out.append(
        ok(".python-version", pin)
        if pin.startswith("3.12")
        else fail(".python-version", f"is {pin!r}, want 3.12")
    )
    out.append(
        ok("uv.lock", "present") if (backend / "uv.lock").is_file() else fail("uv.lock", "missing")
    )
    entry = data.get("tool", {}).get("vercel", {}).get("entrypoint")
    out.append(
        ok("[tool.vercel] entrypoint", entry)
        if entry == "app.main:app"
        else fail("[tool.vercel] entrypoint", f"is {entry!r}, want app.main:app")
    )
    return out


CWD_PATTERNS = re.compile(r"os\.getcwd\(|Path\.cwd\(|os\.chdir\(|(?<![\w.])open\(\s*[\"'][^\"']")


def check_paths_use_file(backend: Path = BACKEND) -> list[Finding]:
    """Vercel runs functions from the project base, not the file's folder (SPEC §16A.2)."""
    hits = []
    for path in sorted((backend / "app").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CWD_PATTERNS.search(line):
                hits.append(f"{path.relative_to(backend)}:{lineno}")
    return [
        fail("data paths", "working-directory dependent code at " + ", ".join(hits))
        if hits
        else ok("data paths", "backend/app resolves every path from __file__")
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_assets(root: Path = REPO) -> list[Finding]:
    out = []
    manifest_path = root / "backend/data/source/MANIFEST.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    for lang in ("en", "hi"):
        pdf = root / f"web/public/pdf/rules-{lang}.pdf"
        want = manifest.get(f"pdf/rules-{lang}.pdf")
        if not pdf.is_file():
            out.append(fail(f"PDF rules-{lang}", f"missing {pdf.relative_to(root)}"))
        elif want and _sha256(pdf) != want:
            out.append(fail(f"PDF rules-{lang}", "does not match MANIFEST.json"))
        else:
            out.append(
                ok(
                    f"PDF rules-{lang}",
                    f"web/public/pdf/rules-{lang}.pdf served at /pdf/rules-{lang}.pdf",
                )
            )
    built = root / "web/build"
    if built.is_dir():
        missing = [
            n
            for n in ("pdf/rules-en.pdf", "pdf/rules-hi.pdf", "index.html")
            if not (built / n).is_file()
        ]
        out.append(
            fail("web build artifacts", f"web/build is missing {missing}")
            if missing
            else ok("web build artifacts", "index.html and both PDFs are in web/build")
        )
    else:
        out.append(
            warn("web build artifacts", "web/build does not exist (run npm run build --prefix web)")
        )
    data = root / "backend/data"
    needed = ["source/bhumi_vikas_rules.jsonl", "source/bhumi_vikas_rules_fulltext_by_page.txt",
              "amendments.json", "glossary.json", "templates.json", "tables/56_1_a_front_open_space.json"]  # fmt: skip
    absent = [n for n in needed if not (data / n).is_file()]
    out.append(
        fail("backend data", f"missing {absent}")
        if absent
        else ok(
            "backend data", "rules, page text, tables, glossary, templates and amendments present"
        )
    )
    src = data / "source/bhumi_vikas_rules.jsonl"
    if src.is_file() and manifest.get("bhumi_vikas_rules.jsonl"):
        out.append(
            ok("corpus fingerprint", _sha256(src)[:12])
            if _sha256(src) == manifest["bhumi_vikas_rules.jsonl"]
            else fail("corpus fingerprint", "rules JSONL does not match MANIFEST.json")
        )
    report = root / "backend/evals/report.json"
    out.append(
        ok("eval report", "backend/evals/report.json present for /api/eval/latest")
        if report.is_file()
        else warn("eval report", "no evals/report.json: /accuracy will say no report yet")
    )
    return out


def check_entrypoint() -> list[Finding]:
    """Import the app as Vercel would, in hosted mode, and check its surface."""
    code = r"""
import json, os
os.environ["VERCEL"] = "1"
os.environ.pop("SERVE_WEB", None)
os.environ["LLM_PROVIDER"] = "offline"
from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app
paths = sorted({r.path for r in app.routes if hasattr(r, "path")})
s = get_settings()
with TestClient(app) as c:
    health = c.get("/api/health").json()
    ask = c.post("/api/ask", json={"question": "front gap 9 m road, plot 200 sq m"}).json()
print(json.dumps({"paths": paths, "audit_sink": s.audit_sink, "hosted": s.hosted,
                  "mode": health["mode"], "hosted_flag": health["runtime"]["hosted"],
                  "status": ask["status"], "openapi": app.openapi_url}))
"""
    env = {
        k: v for k, v in os.environ.items() if k not in ("CEREBRAS_API_KEY", "ANTHROPIC_API_KEY")
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import sys\nsys.path.insert(0, '.')\n" + code],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    if proc.returncode != 0:
        return [fail("app.main:app import", (proc.stderr.strip().splitlines() or ["failed"])[-1])]
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    out = []
    outside = [p for p in info["paths"] if not p.startswith("/api")]
    out.append(
        fail("routes under /api", f"routes outside /api: {outside}")
        if outside
        else ok("routes under /api", f"{len(info['paths'])} routes, all under /api")
    )
    out.append(
        ok("hosted audit sink", "stdout (forced when VERCEL is set)")
        if info["audit_sink"] == "stdout" and info["hosted"]
        else fail("hosted audit sink", f"audit_sink is {info['audit_sink']!r} on a hosted runtime")
    )
    out.append(
        ok(
            "hosted cold start",
            f"health ok, mode {info['mode']}, an offline question answers {info['status']}",
        )
        if info["hosted_flag"] and info["status"] in ("ANSWERED", "PARTIAL")
        else fail("hosted cold start", f"unexpected result: {info}")
    )
    out.append(
        ok("openapi", info["openapi"])
        if info["openapi"] == "/api/openapi.json"
        else fail("openapi", str(info["openapi"]))
    )
    return out


def check_launcher_and_docs(root: Path = REPO) -> list[Finding]:
    out = []
    run = root / "run.ps1"
    if not run.is_file():
        out.append(fail("run.ps1", "missing"))
    else:
        text = run.read_text(encoding="utf-8")
        needed = ["uv --directory backend sync", "npm ci --prefix web", "npm run build --prefix web",
                  'SERVE_WEB = "1"', "uvicorn app.main:app", "127.0.0.1"]  # fmt: skip
        missing = [n for n in needed if n not in text]
        out.append(
            fail("run.ps1", f"missing steps: {missing}")
            if missing
            else ok("run.ps1", "sync, ci, build, SERVE_WEB=1, uvicorn on 127.0.0.1")
        )
        if os.name == "nt":
            cmd = (
                "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]"
                f"::ParseFile('{run}',[ref]$t,[ref]$e);if($e.Count){{$e|%{{$_.Message}};exit 1}}"
            )
            parsed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True
            )
            out.append(
                ok("run.ps1 syntax", "parses")
                if parsed.returncode == 0
                else fail("run.ps1 syntax", parsed.stdout.strip()[:200])
            )
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "docs/DEPLOY.md", "docs/ASSUMPTIONS.md"):
        out.append(ok(name, "present") if (root / name).is_file() else fail(name, "missing"))
    return out


def run_all(with_entrypoint: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    for fn in (
        check_vercel_json, check_vercelignore, check_gitignore, check_env_example, scan_secrets,
        check_vite_secrets, check_backend_packaging, check_paths_use_file, check_assets,
        check_launcher_and_docs,
    ):  # fmt: skip
        findings += fn()
    if with_entrypoint:
        findings += check_entrypoint()
    return findings


def main() -> int:
    findings = run_all()
    width = max(len(f.check) for f in findings)
    for f in findings:
        print(f"{f.level:<4}  {f.check:<{width}}  {f.detail}")
    counts = {lvl: sum(f.level == lvl for f in findings) for lvl in (PASS, WARN, FAIL)}
    print(f"\n{counts[PASS]} passed, {counts[WARN]} warning(s), {counts[FAIL]} failed")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
