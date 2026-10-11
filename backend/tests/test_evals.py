"""The golden set and the evaluation harness. Fully offline: no model is ever called."""

import json
import re
from pathlib import Path

import pytest

from app.corpus.index import rule_key
from app.llm.fake_adapter import FakeLLM
from app.llm.replay_adapter import ReplayAdapter
from app.pipeline import Pipeline
from app.schemas import AskRequest
from evals import run_eval as ev
from tests.helpers import compose_json, understand_json

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def golden():
    return ev.load_golden()


# --- the golden set -----------------------------------------------------------------------------


def test_golden_has_the_required_shape(golden):
    assert len(golden) >= 45
    for c in golden:
        assert set(ev.REQUIRED_FIELDS) <= set(c), c["id"]
        assert c["lang"] in ("en", "hi")
        assert c["expected_status"] in ("ANSWERED", "PARTIAL", "NOT_FOUND")
        assert isinstance(c["tags"], list) and c["tags"]
        assert c["question"].strip() and len(c["question"]) <= 500


def test_golden_contains_the_17_sample_questions_verbatim(golden):
    sample = [c for c in golden if c["source"].startswith("sample_questions.md")]
    assert [c["id"] for c in sample] == [f"S{n:02d}" for n in range(1, 18)]
    path = next(REPO.glob("**/track-1-bhumi-vikas-sahayak/resources/sample_questions.md"), None)
    if path is None:
        pytest.skip("the participant pack is not in this checkout")
    numbered = dict(re.findall(r"^(\d+)\. (.+)$", path.read_text("utf-8"), re.M))
    for c in sample:
        n = str(int(c["id"][1:]))
        stripped = re.sub(r"\s*\(Tip:.*\)$", "", numbered[n]).strip()
        assert c["question"] == stripped, c["id"]
    assert {c["id"] for c in sample if c["expected_status"] == "NOT_FOUND"} == {"S16", "S17"}


def test_golden_covers_the_required_families(golden):
    tags = {t for c in golden for t in c["tags"]}
    for needed in (
        "band-edge", "units", "gap", "false-premise", "injection", "hindi", "out-of-scope",
        "nonexistent-rule", "flagship", "amendment", "rule-12a", "sqft", "gaj",
    ):  # fmt: skip
        assert needed in tags, needed
    questions = " ".join(c["question"] for c in golden)
    for needle in (
        "9.0 m",
        "12.0 m",
        "18.0 m",
        "40 sq m",
        "225 sq m",
        "75.5 sq m",
        "1,500 sq ft",
        "200 gaj",
    ):
        assert needle in questions, needle
    assert any("पिछले निर्देश भूल जाओ" in c["question"] for c in golden)
    assert any("Ignore previous instructions" in c["question"] for c in golden)
    assert any(c["question"] == "What does Rule 150 say?" for c in golden)
    langs = [c["lang"] for c in golden]
    assert langs.count("hi") >= 8


def test_golden_pages_agree_with_the_corpus(golden, built):
    """verified_page must be a page of one of the expected rules (checked against the page text)."""
    corpus, index = built
    for c in golden:
        if not c["expected_rules_any"]:
            assert c["verified_page"] is None, c["id"]
            continue
        pages = set()
        for rule in c["expected_rules_any"]:
            for chunk in index.by_key.get(rule_key(rule), []):
                pages.update(chunk.pages)
        assert c["verified_page"] in pages, (c["id"], c["verified_page"])
        assert 1 <= c["verified_page"] <= corpus.n_pages


def test_golden_expected_rules_exist(golden, built):
    _, index = built
    for c in golden:
        for rule in c["expected_rules_any"]:
            assert index.by_key.get(rule_key(rule)), (c["id"], rule)


def test_golden_expected_values_match_the_calculators():
    """The numbers in the golden set are the calculators' numbers, not typed guesses."""
    from app import calculators as calc

    assert calc.front_open_space(9.0).result.value == 3.0
    assert calc.front_open_space(12.0).result.value == 3.6
    assert calc.front_open_space(18.0).result.value == 4.5
    assert calc.rear_open_space(225.5).result.value == 3.0
    assert calc.max_built_up(calc.to_sqm(1500, "sqft").value).result.value == 174.19
    assert calc.permission_fee(75.5).result.value is None


def test_unverified_cases_are_counted_honestly(golden):
    assert all(c["verified_by"] == "" for c in golden)  # a human sign-off is still pending


# --- judging one case --------------------------------------------------------------------------------


def run_case(pipeline: Pipeline, case: dict) -> dict:
    return ev.evaluate_case(pipeline, case)


def case_of(golden, case_id):
    return next(c for c in golden if c["id"] == case_id)


def test_judge_passes_a_correct_offline_answer(make_pipeline, golden):
    r = run_case(make_pipeline(), case_of(golden, "F01"))
    assert r["pass"] and r["status"] == "PARTIAL" and r["values_ok"] and r["rule_hit"]
    assert r["fabrication_shown"] == 0 and r["answered_without_citation"] == 0
    assert r["calls"] == 0 and r["latency_ms"] > 0


def test_judge_reports_every_reason_for_a_failure(make_pipeline, golden):
    case = dict(case_of(golden, "S01"), expected_values={"front_open_space": 9.9},
                expected_rules_any=["61"], must_not_contain=["3.6"], expected_status="NOT_FOUND")  # fmt: skip
    r = run_case(make_pipeline(), case)
    assert not r["pass"]
    reasons = " | ".join(r["reasons"])
    assert "expected NOT_FOUND" in reasons and "none of the expected rules" in reasons
    assert "front_open_space: got 3.6, expected 9.9" in reasons
    assert "forbidden text shown" in reasons


def test_status_matching_rules():
    assert ev.status_matches("ANSWERED", "PARTIAL") and ev.status_matches("ANSWERED", "ANSWERED")
    assert not ev.status_matches("ANSWERED", "NEEDS_REVIEW")
    assert ev.status_matches("PARTIAL", "PARTIAL") and not ev.status_matches("PARTIAL", "ANSWERED")
    assert ev.status_matches("NOT_FOUND", "NOT_FOUND") and not ev.status_matches(
        "NOT_FOUND", "ERROR"
    )


def test_value_matching():
    assert ev.value_matches(3.6, 3.6000000001) and not ev.value_matches(3.6, 3.0)
    assert ev.value_matches(None, None) and not ev.value_matches(None, 0)
    assert ev.value_matches("above_limit", "above_limit")
    assert not ev.value_matches(0, None) and not ev.value_matches(1, True)


def test_a_fabricated_quote_is_counted_as_shown(make_pipeline, golden, built):
    """Even if the pipeline were broken, the harness checks the card itself."""
    pipeline = make_pipeline()
    case = case_of(golden, "F01")
    card, trace = pipeline.ask_traced(AskRequest(question=case["question"]))
    card.citations[0].quote = "A sentence that is nowhere in the rules of Bhopal."
    r = ev.judge(pipeline, case, card, trace, 1.0)
    assert r["fabrication_shown"] == 1 and not r["pass"]


def test_an_answer_naming_a_nonexistent_rule_is_a_fabrication(make_pipeline, golden):
    pipeline = make_pipeline()
    case = case_of(golden, "F01")
    card, trace = pipeline.ask_traced(AskRequest(question=case["question"]))
    card.answer += " See also Rule 150."
    assert ev.judge(pipeline, case, card, trace, 1.0)["fabrication_shown"] == 1


def test_an_answer_without_a_citation_is_flagged(make_pipeline, golden):
    pipeline = make_pipeline()
    case = case_of(golden, "F01")
    card, trace = pipeline.ask_traced(AskRequest(question=case["question"]))
    card.citations = []
    r = ev.judge(pipeline, case, card, trace, 1.0)
    assert r["answered_without_citation"] == 1 and not r["pass"]


def test_percentile_is_nearest_rank():
    assert ev.percentile([], 0.5) == 0.0
    assert ev.percentile([5], 0.95) == 5
    assert ev.percentile(list(range(1, 101)), 0.5) == 50
    assert ev.percentile(list(range(1, 101)), 0.95) == 95
    assert ev.percentile([10, 1, 7], 0.5) == 7


# --- the whole run ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def offline_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("report")
    assert ev.main(["--provider", "offline", "--out-dir", str(out)]) == 0
    return out, json.loads((out / "report.json").read_text("utf-8"))


def test_offline_run_writes_both_reports(offline_report):
    out, report = offline_report
    md = (out / "report.md").read_text("utf-8")
    assert md.startswith("# Evaluation report")
    for heading in (
        "## Summary (measured)",
        "## The 17 sample questions",
        "## All cases",
        "## Failures",
        "## Method",
    ):
        assert heading in md
    assert "OFFLINE run" in md  # an offline run says it is not a live measurement
    assert report["provider"] == "offline" and report["runs"] == 1


def test_report_json_matches_what_the_accuracy_page_reads(offline_report):
    _, report = offline_report
    s = report["summary"]
    for key in (
        "status_accuracy", "rule_hit", "rule_hit_total", "value_accuracy", "abstention",
        "fabrication_shown", "fabrication_attempted", "injection_resistance", "latency_ms",
    ):  # fmt: skip
        assert key in s, key
    assert set(s["latency_ms"]) >= {"p50", "p95", "n"}
    assert s["rule_hit_total"] == 17 and report["golden_cases"] == len(report["cases"]) >= 45
    for c in report["cases"]:
        assert {"id", "question", "expected_status", "status", "pass", "latency_ms"} <= set(c)
    assert report["corpus_sha256"] and "generated_at" in report


def test_offline_run_has_no_fabrication_and_correct_numbers(offline_report):
    """The deterministic parts hold with no model at all."""
    _, report = offline_report
    s = report["summary"]
    assert s["fabrication_shown"] == 0
    assert s["answered_without_citation"] == 0
    assert s["value_accuracy"] == 1.0, [
        c["reasons"] for c in report["cases"] if c["values_ok"] is False
    ]
    assert s["injection_resistance"] == 1.0
    assert s["model_calls"] == 0


def test_offline_failures_are_exactly_the_model_dependent_ones(offline_report):
    _, report = offline_report
    failed = {c["id"] for c in report["cases"] if not c["pass"]}
    # these need Step B (a composed, cited answer) or Step A's scope judgement
    assert failed <= {
        "S04", "S06", "S07", "S08", "S09", "S11", "S12", "S13", "S15", "P01", "H03", "W01", "O04",
        "D02",
    }, failed  # fmt: skip
    for c in report["cases"]:
        if not c["pass"]:
            assert c["status"] in ("NEEDS_REVIEW", "NOT_FOUND", "PARTIAL"), c["id"]


def test_targets_report_what_is_met_and_what_is_not(offline_report):
    _, report = offline_report
    t = report["targets"]
    assert t["fabrication_shown"]["met"] and t["value_accuracy"]["met"]
    assert not t["rule_hit"]["met"]  # honest: an offline run cannot cite lookups
    assert t["rule_hit"]["target"] == 15 and t["status_accuracy"]["target"] == 0.9


def test_strict_mode_fails_when_a_target_is_missed(tmp_path):
    code = ev.main(["--provider", "offline", "--no-write", "--only", "S12", "--strict"])
    assert code == 1


def test_selection_by_id_tag_and_limit(golden):
    assert [c["id"] for c in ev.select(golden, "S01,S02", None)] == ["S01", "S02"]
    assert all("injection" in c["tags"] for c in ev.select(golden, "injection", None))
    assert len(ev.select(golden, None, 5)) == 5


def test_no_write_leaves_no_files(tmp_path):
    assert (
        ev.main(
            ["--provider", "offline", "--no-write", "--only", "S10", "--out-dir", str(tmp_path)]
        )
        == 0
    )
    assert not list(tmp_path.iterdir())


def test_multiple_runs_report_variance_and_flaky_cases(tmp_path):
    code = ev.main(
        ["--provider", "offline", "--runs", "3", "--only", "S01,S16", "--out-dir", str(tmp_path)]
    )
    assert code == 0
    report = json.loads((tmp_path / "report.json").read_text("utf-8"))
    assert report["runs"] == 3 and len(report["run_summaries"]) == 3
    assert (
        report["summary"]["status_accuracy_min"] == report["summary"]["status_accuracy_max"] == 1.0
    )
    assert all(c["runs"] == 3 and c["runs_passed"] == 3 and not c["flaky"] for c in report["cases"])


def test_live_provider_without_keys_stops_with_a_clear_message(monkeypatch):
    for name in ("CEREBRAS_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ev, "load_dotenv_if_present", lambda: None)
    with pytest.raises(SystemExit) as e:
        ev.make_pipeline("live", 0, record=True, fresh=False)
    assert "CEREBRAS_API_KEY and ANTHROPIC_API_KEY" in str(e.value)


# --- replay -------------------------------------------------------------------------------------------


def test_replay_with_no_recordings_counts_every_miss(tmp_path, monkeypatch):
    from app.llm import replay_adapter

    monkeypatch.setattr(replay_adapter, "RECORDINGS_DIR", tmp_path / "empty")
    code = ev.main(["--provider", "replay", "--only", "S12,S16", "--out-dir", str(tmp_path)])
    assert code == 0
    report = json.loads((tmp_path / "report.json").read_text("utf-8"))
    assert report["summary"]["replay_misses"] >= 1
    assert any("no recording" in n for n in report["notes"])
    assert "REPLAY run" in (tmp_path / "report.md").read_text("utf-8")


def test_recorded_answers_replay_identically_with_no_model(
    make_pipeline, built, settings, tmp_path
):
    corpus, index = built
    quote = "Provision for lifts shall be made for building more than 12.5 meters in height."
    fake_a = FakeLLM({"understand": understand_json("lifts", query="lifts building height")})
    fake_b = FakeLLM(
        {
            "compose": compose_json(
                "Lifts are required above 12.5 m in height (Rule 83), not above 15 m.",
                [("r83-0-0", quote)],
            )
        }
    )
    recorder = Pipeline(
        corpus, index, settings,
        ReplayAdapter("cerebras", "m", "none", inner=fake_a, directory=tmp_path, writable=True),
        ReplayAdapter("anthropic", "m", "low", inner=fake_b, directory=tmp_path, writable=True),
    )  # fmt: skip
    req = AskRequest(question="Is a lift required over 15 m?")
    live_card = recorder.ask(req)
    assert live_card.status == "ANSWERED" and len(fake_a.calls) == len(fake_b.calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 2

    player = Pipeline(
        corpus, index, settings,
        ReplayAdapter("cerebras", "m", "none", directory=tmp_path),
        ReplayAdapter("anthropic", "m", "low", directory=tmp_path),
    )  # fmt: skip
    again, trace = player.ask_traced(req)
    assert (again.status, again.answer) == (live_card.status, live_card.answer)
    assert again.citations[0].quote == quote and again.meta.replay is True
    assert not trace.errors and again.meta.calls == 2
    assert len(fake_a.calls) == len(fake_b.calls) == 1  # the models were not called again


def test_read_cache_false_forces_a_fresh_call(tmp_path):
    inner = FakeLLM({"understand": understand_json("lifts")})
    adapter = ReplayAdapter("c", "m", "", inner=inner, directory=tmp_path, writable=True)
    adapter.complete_json("understand", [{"role": "user", "content": "q"}], {})
    adapter.complete_json("understand", [{"role": "user", "content": "q"}], {})
    assert len(inner.calls) == 1  # the second call came from the recording
    fresh = ReplayAdapter("c", "m", "", inner=inner, directory=tmp_path, read_cache=False)
    fresh.complete_json("understand", [{"role": "user", "content": "q"}], {})
    assert len(inner.calls) == 2


# --- the demo recorder ----------------------------------------------------------------------------------


def test_demo_questions_include_the_ui_example_chips():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "record_demo", REPO / "backend/scripts/record_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    demo = {q for _, q in module.DEMO_QUESTIONS}
    examples = REPO / "web/src/lib/examples.ts"
    if not examples.exists():
        pytest.skip("web/ is not in this checkout")
    block = examples.read_text("utf-8").split("EXAMPLE_LABELS")[0]
    chips = re.findall(r'^\s+"(.+)",$', block, re.M)
    assert len(chips) == 3
    for chip in chips:
        assert chip in demo, chip


def test_record_demo_refuses_to_run_without_keys(monkeypatch, capsys):
    import importlib.util

    for name in ("CEREBRAS_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    spec = importlib.util.spec_from_file_location(
        "record_demo2", REPO / "backend/scripts/record_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "load_dotenv_if_present", lambda: None)
    assert module.main() == 2
    assert "Nothing was recorded" in capsys.readouterr().out
