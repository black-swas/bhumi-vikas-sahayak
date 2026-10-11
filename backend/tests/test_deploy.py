"""Hosted-deployment behaviour (SPEC §16A) and the pre-flight checks. Offline, no keys."""

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

REPO = Path(__file__).resolve().parents[2]


def load_preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight", REPO / "backend/scripts/preflight.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load_preflight()


def levels(findings):
    return {f.check: f.level for f in findings}


# --- vercel.json and packaging ----------------------------------------------------------------


def test_vercel_json_is_the_spec_16a_services_config():
    config = json.loads((REPO / "vercel.json").read_text("utf-8"))
    assert config == {
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "services": {
            "web": {"root": "web/"},
            "api": {"root": "backend/", "entrypoint": "app.main:app"},
        },
        "rewrites": [
            {"source": "/api/(.*)", "destination": {"service": "api"}},
            {"source": "/(.*)", "destination": {"service": "web"}},
        ],
    }
    for invalid in preflight.INVALID_TOP_LEVEL:
        assert invalid not in config  # not valid beside `services`


def test_the_api_rewrite_comes_first_so_api_paths_never_reach_the_spa():
    rewrites = json.loads((REPO / "vercel.json").read_text("utf-8"))["rewrites"]
    assert rewrites[0]["source"].startswith("/api/") and rewrites[-1]["source"] == "/(.*)"


def test_every_route_lives_under_api():
    app = create_app()
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert paths and all(p.startswith("/api") for p in paths), paths


def test_runtime_dependencies_are_runtime_only():
    import tomllib

    data = tomllib.loads((REPO / "backend/pyproject.toml").read_text("utf-8"))
    deps = {preflight._name(d) for d in data["project"]["dependencies"]}
    assert deps == {"fastapi", "uvicorn", "pydantic", "cerebras_cloud_sdk", "anthropic"}
    assert not deps & preflight.DEV_ONLY
    assert {"pytest", "ruff"} <= {preflight._name(d) for d in data["dependency-groups"]["dev"]}
    assert data["tool"]["vercel"]["entrypoint"] == "app.main:app"
    assert (REPO / "backend/.python-version").read_text().strip().startswith("3.12")


def test_static_pdfs_are_in_the_web_public_folder_and_the_build():
    for lang in ("en", "hi"):
        assert (REPO / f"web/public/pdf/rules-{lang}.pdf").stat().st_size > 100_000
    built = REPO / "web/build/pdf"
    if built.is_dir():  # the web build copies public/ to the CDN root
        assert (built / "rules-en.pdf").is_file() and (built / "rules-hi.pdf").is_file()


# --- hosted settings ---------------------------------------------------------------------------


def test_vercel_forces_the_stdout_audit_sink():
    assert get_settings({"VERCEL": "1", "AUDIT_SINK": "file"}).audit_sink == "stdout"
    assert get_settings({"VERCEL": "1"}).audit_sink == "stdout"
    assert get_settings({"AUDIT_SINK": "file"}).audit_sink == "file"
    s = get_settings({"VERCEL": "1", "VERCEL_REGION": "bom1"})
    assert s.hosted and s.region == "bom1"
    assert not get_settings({}).hosted


def test_hosted_health_reports_the_runtime(make_pipeline, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_REGION", "iad1")
    with TestClient(create_app(make_pipeline())) as c:
        runtime = c.get("/api/health").json()["runtime"]
    assert runtime == {"hosted": True, "region": "iad1"}


def test_hosted_answers_write_nothing_and_log_one_json_line_without_the_question(
    make_pipeline, monkeypatch, tmp_path, capsys
):
    from app.audit import AuditLog

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("AUDIT_SINK", "file")  # a stray setting must not matter
    monkeypatch.chdir(tmp_path)
    settings = get_settings()
    question = "My plot is 200 sq m on a 9 m road. Front gap and fee?"
    with TestClient(create_app(make_pipeline(audit=AuditLog(settings)))) as c:
        assert c.post("/api/ask", json={"question": question}).json()["status"] == "PARTIAL"
    out = capsys.readouterr().out.strip().splitlines()
    audit = [json.loads(line) for line in out if line.startswith("{")]
    assert len(audit) == 1  # one line per question
    line = audit[0]
    assert "question" not in line and len(line["question_sha256"]) == 16
    assert line["question_len"] == len(question) and line["status"] == "PARTIAL"
    assert question not in "\n".join(out)
    assert list(tmp_path.iterdir()) == []  # no logs/ folder, no recordings, nothing


def test_data_paths_do_not_depend_on_the_working_directory(monkeypatch, tmp_path):
    from app.corpus import build_corpus

    monkeypatch.chdir(tmp_path)
    corpus, index = build_corpus()
    assert len(corpus.rules) == 106 and index.by_id["r56-1-0"]
    with TestClient(create_app(web_root=None)):
        pass  # the lifespan builds the whole pipeline from the same paths


# --- proxy headers -------------------------------------------------------------------------------


def post(client, ip=None, **headers):
    if ip:
        headers["x-vercel-forwarded-for"] = ip
    return client.post("/api/ask", json={"question": "front gap 9 m road"}, headers=headers)


def test_on_vercel_each_clerk_gets_their_own_rate_limit(make_pipeline, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with TestClient(create_app(make_pipeline())) as c:
        assert [post(c, "203.0.113.7").status_code for _ in range(21)][-1] == 429
        assert post(c, "198.51.100.9").status_code == 200  # a different clerk is not throttled


def test_on_vercel_the_forwarded_for_header_is_the_fallback(make_pipeline, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with TestClient(create_app(make_pipeline())) as c:
        codes = [
            post(c, **{"x-forwarded-for": "203.0.113.7, 10.0.0.1"}).status_code for _ in range(21)
        ]
        assert codes[-1] == 429
        assert post(c, **{"x-forwarded-for": "198.51.100.9"}).status_code == 200


def test_off_vercel_a_forged_forwarded_for_header_changes_nothing(make_pipeline, monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    with TestClient(create_app(make_pipeline())) as c:
        codes = [
            post(
                c,
                **{"x-forwarded-for": f"198.51.100.{i}", "x-vercel-forwarded-for": f"192.0.2.{i}"},
            ).status_code
            for i in range(22)
        ]
    assert codes[:20] == [200] * 20 and 429 in codes[20:]  # one socket, one bucket


def test_serve_web_is_ignored_on_vercel(make_pipeline, monkeypatch):
    monkeypatch.setenv("SERVE_WEB", "1")
    monkeypatch.setenv("VERCEL", "1")
    with TestClient(create_app(make_pipeline())) as c:
        assert c.get("/").status_code == 404  # the CDN serves the web service, not the function
        assert c.get("/api/health").status_code == 200


# --- pre-flight: every check can fail ------------------------------------------------------------


def test_preflight_passes_on_this_repo():
    findings = preflight.run_all(with_entrypoint=True)
    failed = [f for f in findings if f.level == preflight.FAIL]
    assert not failed, failed
    assert len(findings) >= 30


def fake_key(prefix: str, n: int = 30) -> str:
    return prefix + "A1b2" * (n // 4 + 1)  # built at run time so this file holds no key pattern


def test_secret_scan_finds_planted_keys_and_masks_them(tmp_path):
    (tmp_path / "app.py").write_text(f'KEY = "{fake_key("sk-ant-")}"\n', encoding="utf-8")
    (tmp_path / "ui.ts").write_text(f"const k = '{fake_key('csk-', 24)}';\n", encoding="utf-8")
    # pieces are joined at run time so this file itself holds no secret-looking line
    (tmp_path / "cfg.toml").write_text("api_" + 'key = "Zq8wXe4Rt7Yu1Io3Pa5Sd6Fg9Hj2Kl"\n')
    (tmp_path / "db.md").write_text("postgresql://" + "admin:hunter2pass@db.internal.net/x\n")
    (tmp_path / "id.pem").write_text("-----BEGIN " + "RSA PRIVATE KEY-----\n", encoding="utf-8")
    result = preflight.scan_secrets(tmp_path)
    assert [f.level for f in result] == [preflight.FAIL]
    detail = result[0].detail
    for name in ("app.py:1", "ui.ts:1", "cfg.toml:1", "db.md:1", "id.pem:1"):
        assert name in detail, name
    assert fake_key("sk-ant-") not in detail and "A1b2A1b2A1b2" not in detail  # masked


def test_secret_scan_ignores_placeholders_env_files_and_skipped_folders(tmp_path):
    (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={fake_key('sk-ant-')}\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text(f"X_API_KEY={fake_key('sk-ant-')}\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text(
        "ANTHROPIC_API_KEY=\nCEREBRAS_API_KEY=\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "set ANTHROPIC_API_KEY=your-key-goes-here-123456789012\n", encoding="utf-8"
    )
    (tmp_path / "settings.py").write_text(
        'key = os.environ["CEREBRAS_API_KEY"]\n', encoding="utf-8"
    )
    for skipped in ("node_modules", ".venv", "OpenHands-main", "build"):
        (tmp_path / skipped).mkdir()
        (tmp_path / skipped / "x.js").write_text(f"k='{fake_key('sk-ant-')}'\n", encoding="utf-8")
    assert [f.level for f in preflight.scan_secrets(tmp_path)] == [preflight.PASS]


def test_the_scanner_never_prints_a_full_value():
    secret = fake_key("sk-ant-", 40)
    assert secret not in preflight.mask(secret) and preflight.mask(secret).startswith("sk-a")


def test_vite_secret_check(tmp_path):
    (tmp_path / "web/src").mkdir(parents=True)
    (tmp_path / "web/src/a.ts").write_text(
        "const k = import.meta.env.VITE_API_BASE_URL;\n", encoding="utf-8"
    )
    assert levels(preflight.check_vite_secrets(tmp_path))["VITE_ secrets"] == preflight.PASS
    (tmp_path / "web/src/b.ts").write_text(
        "const k = import.meta.env.VITE_CEREBRAS_API_KEY;\n", encoding="utf-8"
    )
    result = preflight.check_vite_secrets(tmp_path)
    assert levels(result)["VITE_ secrets"] == preflight.FAIL
    assert (
        "web/src/b.ts:1".replace("/", "\\") in result[0].detail
        or "web/src/b.ts:1" in result[0].detail
    )


def test_vercel_json_check_catches_a_wrong_config(tmp_path):
    good = (REPO / "vercel.json").read_text("utf-8")
    (tmp_path / "vercel.json").write_text(good, encoding="utf-8")
    assert all(f.level == preflight.PASS for f in preflight.check_vercel_json(tmp_path))
    broken = json.loads(good)
    broken["installCommand"] = "npm ci"
    broken["rewrites"].reverse()
    (tmp_path / "vercel.json").write_text(json.dumps(broken), encoding="utf-8")
    result = levels(preflight.check_vercel_json(tmp_path))
    assert result["vercel.json top-level keys"] == preflight.FAIL
    assert result["vercel.json rewrites"] == preflight.FAIL
    assert preflight.check_vercel_json(tmp_path / "missing")[0].level == preflight.FAIL


def test_gitignore_check_requires_env_to_be_ignored(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    result = preflight.check_gitignore(tmp_path)
    assert result[0].level == preflight.FAIL and ".env" in result[0].detail
    (tmp_path / ".gitignore").write_text((REPO / ".gitignore").read_text("utf-8"), encoding="utf-8")
    assert preflight.check_gitignore(tmp_path)[0].level == preflight.PASS


def test_env_example_check_rejects_a_filled_in_key(tmp_path):
    (tmp_path / ".env.example").write_text(
        "ANTHROPIC_API_KEY=abc\nLLM_PROVIDER=live\n", encoding="utf-8"
    )
    result = levels(preflight.check_env_example(tmp_path))
    assert (
        result[".env.example secrets"] == preflight.FAIL
        and result[".env.example"] == preflight.FAIL
    )


def test_packaging_check_rejects_dev_tools_in_runtime_dependencies(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    src = (REPO / "backend/pyproject.toml").read_text("utf-8")
    (backend / "pyproject.toml").write_text(
        src.replace('"anthropic",', '"anthropic",\n    "pytest",'), encoding="utf-8"
    )
    (backend / ".python-version").write_text("3.13\n", encoding="utf-8")
    result = levels(preflight.check_backend_packaging(backend))
    assert result["runtime dependencies"] == preflight.FAIL
    assert result[".python-version"] == preflight.FAIL and result["uv.lock"] == preflight.FAIL


def test_cwd_dependent_paths_are_caught(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "good.py").write_text(
        "from pathlib import Path\nP = Path(__file__).parent\n", encoding="utf-8"
    )
    assert preflight.check_paths_use_file(tmp_path)[0].level == preflight.PASS
    (app / "bad.py").write_text(
        'import os\nx = open("data/rules.jsonl")\ny = os.getcwd()\n', encoding="utf-8"
    )
    result = preflight.check_paths_use_file(tmp_path)[0]
    assert (
        result.level == preflight.FAIL
        and "bad.py:2" in result.detail
        and "bad.py:3" in result.detail
    )


def test_asset_check_catches_a_changed_pdf(tmp_path):
    for rel in ("web/public/pdf", "backend/data/source"):
        (tmp_path / rel).mkdir(parents=True)
    for lang in ("en", "hi"):
        (tmp_path / f"web/public/pdf/rules-{lang}.pdf").write_bytes(b"%PDF-tampered" * 20000)
    manifest = json.loads((REPO / "backend/data/source/MANIFEST.json").read_text("utf-8"))
    (tmp_path / "backend/data/source/MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    result = levels(preflight.check_assets(tmp_path))
    assert result["PDF rules-en"] == preflight.FAIL and result["PDF rules-hi"] == preflight.FAIL
    assert result["backend data"] == preflight.FAIL


@pytest.mark.skipif(not (REPO / "run.ps1").is_file(), reason="no launcher")
def test_launcher_runs_every_step_in_order():
    text = (REPO / "run.ps1").read_text("utf-8")
    steps = [
        "uv --directory backend sync",
        "npm ci --prefix web",
        "npm run build --prefix web",
        'SERVE_WEB = "1"',
        "uvicorn app.main:app",
    ]
    positions = [text.index(s) for s in steps]
    assert positions == sorted(positions)
    assert "--host 127.0.0.1" in text and "--port $Port" in text
    assert "Node 24" in text and "3.12" in text
    assert "http://127.0.0.1:$Port" in text
