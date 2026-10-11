import pytest
from fastapi.testclient import TestClient

from app.main import IpLimiter, create_app
from app.schemas import AnswerCard

FLAGSHIP = "My plot is 200 sq m on a 9 m road. Front gap, floors and fee?"


@pytest.fixture()
def client(make_pipeline):
    app = create_app(make_pipeline())  # offline pipeline: no models, no network
    with TestClient(app) as c:
        yield c


def test_health_reports_mode_models_and_corpus(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert h["mode"] == "offline" and h["prototype"] is True
    assert h["providers"]["B"]["model"] == "claude-haiku-5-5"
    assert h["providers"]["A"]["configured"] is False
    assert len(h["corpus"]["sha256"]) == 64 and h["corpus"]["rules"] == 106
    assert h["amendments"] == ["2026-08-28-r2-5-c"]
    assert "key" not in str(h).lower().replace("monkey", "")


def test_ask_returns_a_valid_answer_card(client):
    r = client.post("/api/ask", json={"question": FLAGSHIP})
    assert r.status_code == 200
    card = AnswerCard.model_validate(r.json())
    assert card.status == "PARTIAL"
    assert {c.calc_id: c.result.value for c in card.calculations}["permission_fee"] == 3000.0


def test_ask_with_params_override(client):
    r = client.post(
        "/api/ask", json={"question": FLAGSHIP, "params_override": {"road_width_m": 13}}
    )
    card = AnswerCard.model_validate(r.json())
    assert next(c for c in card.calculations if c.calc_id == "front_open_space").result.value == 4.5
    assert card.meta.calls == 0


def test_ask_validation_errors(client):
    assert client.post("/api/ask", json={"question": "x" * 501}).status_code == 422
    assert client.post("/api/ask", json={}).status_code == 422
    assert client.post("/api/ask", json={"question": "hi", "lang": "fr"}).status_code == 422
    r = client.post("/api/ask", json={"question": FLAGSHIP, "params_override": {"sudo": 1}})
    assert r.status_code == 422 and "unknown parameter" in r.json()["detail"]


def test_rule_endpoint(client):
    r = client.get("/api/rule/56")
    assert r.status_code == 200
    body = r.json()
    assert body["rule"] == "56" and body["title"] == "Residential Buildings"
    assert (body["page_start"], body["pdf_en"]) == (77, "/pdf/rules-en.pdf#page=77")
    assert "Front open spaces" in body["text"] and "COMMENTS" not in body["text"]
    assert any(c["id"] == "r56-1-0" for c in body["chunks"])


def test_rule_endpoint_inserted_rule_and_missing_rule(client):
    body = client.get("/api/rule/12-A").json()
    assert body["rule"] == "12-A" and body["parent"] == "12" and body["page_start"] == 21
    assert "186 sqm" in body["text"]
    assert client.get("/api/rule/150").status_code == 404
    assert client.get("/api/rule/26-B").json()["rule"] == "26-B"


def test_feedback_is_acknowledged_and_redacted(make_pipeline, tmp_path):
    from app.audit import AuditLog
    from app.config import get_settings

    settings = get_settings({"AUDIT_SINK": "file", "LOG_DIR": str(tmp_path)})
    app = create_app(make_pipeline(audit=AuditLog(settings)))
    with TestClient(app) as c:
        r = c.post(
            "/api/feedback",
            json={
                "request_id": "abc", "reason": "wrong_number", "consent": True,
                "note": "call 9876543210 the fee is wrong", "question": FLAGSHIP,
            },
        )  # fmt: skip
        assert r.status_code == 200 and r.json()["stored"] is True and len(r.json()["ack_id"]) == 12
        assert (
            c.post("/api/feedback", json={"request_id": "a", "reason": "nope"}).status_code == 422
        )
    logged = (tmp_path / "audit.jsonl").read_text("utf-8")
    assert "9876543210" not in logged and "[REDACTED]" in logged and '"event":"feedback"' in logged


def test_feedback_without_consent_drops_the_question(make_pipeline, tmp_path):
    from app.audit import AuditLog
    from app.config import get_settings

    app = create_app(make_pipeline(audit=AuditLog(get_settings({"LOG_DIR": str(tmp_path)}))))
    with TestClient(app) as c:
        c.post("/api/feedback", json={"request_id": "a", "reason": "other", "question": "secret?"})
    assert "secret?" not in (tmp_path / "audit.jsonl").read_text("utf-8")


def test_eval_latest_without_a_report(client):
    r = client.get("/api/eval/latest")
    assert r.status_code == 200 and "available" in r.json()


def test_no_cors_headers_and_no_docs_pages(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    assert client.get("/docs").status_code == 404 and client.get("/redoc").status_code == 404
    assert client.get("/api/openapi.json").status_code == 200


def test_per_ip_limit():
    lim = IpLimiter(per_minute=3)
    assert [lim.allow("1.1.1.1") for _ in range(4)] == [True, True, True, False]
    assert lim.allow("2.2.2.2")


def test_ask_is_rate_limited_per_ip(make_pipeline):
    app = create_app(make_pipeline())
    with TestClient(app) as c:
        codes = [
            c.post("/api/ask", json={"question": "front gap 9 m road"}).status_code
            for _ in range(22)
        ]
    assert codes[:20] == [200] * 20 and 429 in codes[20:]


def test_audit_line_has_no_question_on_a_hosted_sink(make_pipeline, capsys):
    from app.audit import AuditLog
    from app.config import get_settings

    app = create_app(make_pipeline(audit=AuditLog(get_settings({"AUDIT_SINK": "stdout"}))))
    with TestClient(app) as c:
        c.post("/api/ask", json={"question": FLAGSHIP})
    out = capsys.readouterr().out
    assert '"question_sha256"' in out and "200 sq m" not in out
    assert "api_key" not in out.lower()


def test_serve_web_serves_the_built_app_and_falls_back_to_index(make_pipeline, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app shell</html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("outside", encoding="utf-8")
    app = create_app(make_pipeline(), web_root=tmp_path)
    with TestClient(app) as c:
        assert "app shell" in c.get("/").text
        assert "app shell" in c.get("/accuracy").text  # client-side route: the SPA index
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/health").json()["status"] == "ok"  # the API is not shadowed
        assert c.get("/api/nope").status_code == 404
        # a path that climbs out of the build folder is not served
        assert "outside" not in c.get("/%2e%2e/secret.txt").text
        assert "outside" not in c.get("/../secret.txt").text


def test_no_web_serving_unless_asked(client, monkeypatch):
    monkeypatch.delenv("SERVE_WEB", raising=False)
    assert client.get("/").status_code == 404
