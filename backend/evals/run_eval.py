"""Evaluation harness (SPEC §17).

    uv --directory backend run python -m evals.run_eval --provider offline
    uv --directory backend run python -m evals.run_eval --provider live --runs 3
    uv --directory backend run python -m evals.run_eval --provider replay

Runs every case of ``golden.jsonl`` through the real pipeline and writes ``report.md`` and
``report.json`` next to this file. ``report.json`` is what ``/api/eval/latest`` serves to the
/accuracy page.

Providers:
  live     real Cerebras + Anthropic calls (keys needed). Each answer is saved to
           ``recordings/`` so the same run can be replayed later with no keys and no spend.
  replay   serves ``recordings/`` only. A call with no recording degrades to the offline path and
           is counted in the report as a miss, so a partial recording set cannot look complete.
  offline  no model at all: regex parameters, keyword intent, calculators and templates.

Every number in the report is measured on the run that produced it.
"""

import argparse
import json
import math
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings, load_dotenv_if_present
from app.corpus.index import rule_key
from app.corpus.loader import normalize
from app.pipeline import Pipeline, Trace, build_pipeline
from app.schemas import AnswerCard, AskRequest
from app.verify import rule_mentions

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN_FILE = EVALS_DIR / "golden.jsonl"
REQUIRED_FIELDS = (
    "id", "source", "lang", "question", "expected_status", "expected_rules_any",
    "expected_values", "must_not_contain", "tags", "verified_by", "verified_page",
)  # fmt: skip
ANSWERED = ("ANSWERED", "PARTIAL")
SAMPLE_SOURCE = "sample_questions.md"

# SPEC §17 targets. `min`/`max` say which way is good.
TARGETS: dict[str, tuple[str, float, str]] = {
    "status_accuracy": ("min", 0.90, "Status accuracy"),
    "rule_hit": ("min", 15, "Correct rule cited (sample questions, of 17)"),
    "value_accuracy": ("min", 1.0, "Calculated values correct"),
    "abstention": ("min", 1.0, "Out-of-scope answered NOT_FOUND"),
    "fabrication_shown": ("max", 0, "Fabricated quotes or rules shown"),
    "injection_resistance": ("min", 1.0, "Injection cases resisted"),
    "answered_without_citation": ("max", 0, "Answers shown without a verified citation"),
    "latency_p95_ms": ("max", 5000, "Warm end-to-end latency p95 (ms)"),
}


# --- golden set ----------------------------------------------------------------------------


def load_golden(path: Path = GOLDEN_FILE) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        missing = [f for f in REQUIRED_FIELDS if f not in case]
        if missing:
            raise ValueError(f"{path.name} line {n} ({case.get('id')}): missing {missing}")
        cases.append(case)
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case ids in the golden set")
    return cases


def select(cases: list[dict], only: str | None, limit: int | None) -> list[dict]:
    if only:
        wanted = {w.strip() for w in only.split(",") if w.strip()}
        cases = [c for c in cases if c["id"] in wanted or wanted & set(c["tags"])]
    return cases[:limit] if limit else cases


# --- one case --------------------------------------------------------------------------------


def status_matches(expected: str, got: str) -> bool:
    if expected == "ANSWERED":  # ANSWERED and PARTIAL both count as answered (SPEC §17)
        return got in ANSWERED
    return got == expected


def value_matches(expected: Any, got: Any) -> bool:
    if expected is None:
        return got is None
    if isinstance(expected, str):
        return got == expected
    return (
        isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - expected) < 1e-6
    )


def card_text(card: AnswerCard) -> str:
    """Everything the clerk would read on the card, except their own question echoed back."""
    parts = [card.answer, *card.missing_info]
    parts += [c.quote for c in card.citations]
    parts += [w.text for w in card.warnings]
    for calc in card.calculations:
        parts += [calc.matched_row_text, str(calc.result.value), *calc.assumptions, *calc.warnings]
    return " ".join(parts).lower()


def evaluate_case(pipeline: Pipeline, case: dict) -> dict:
    started = time.perf_counter()
    card, trace = pipeline.ask_traced(AskRequest(question=case["question"]))
    wall_ms = (time.perf_counter() - started) * 1000
    return judge(pipeline, case, card, trace, wall_ms)


def judge(pipeline: Pipeline, case: dict, card: AnswerCard, trace: Trace, wall_ms: float) -> dict:
    reasons: list[str] = []
    expected_rules = {rule_key(r) for r in case["expected_rules_any"]}
    cited = {rule_key(c.rule) for c in card.citations}
    seen = set(cited)
    for chunk_id in [*trace.candidates, *card.candidates]:
        chunk = pipeline.index.by_id.get(chunk_id)
        if chunk:
            seen.add(rule_key(chunk.rule))

    status_ok = status_matches(case["expected_status"], card.status)
    if not status_ok:
        reasons.append(f"status {card.status}, expected {case['expected_status']}")

    rule_hit = None
    retrieval_hit = None
    if expected_rules:
        rule_hit = bool(expected_rules & cited)
        retrieval_hit = bool(expected_rules & seen)
        if not rule_hit:
            reasons.append(f"none of the expected rules {case['expected_rules_any']} cited")

    values_ok = None
    if case["expected_values"]:
        values_ok = True
        for key, expected in case["expected_values"].items():
            calc = next((c for c in card.calculations if c.calc_id == key), None)
            if calc is None:
                values_ok = False
                reasons.append(f"no calculation '{key}'")
            elif not value_matches(expected, calc.result.value):
                values_ok = False
                reasons.append(f"{key}: got {calc.result.value}, expected {expected}")

    text = card_text(card)
    strings_ok = True
    for bad in case["must_not_contain"]:
        if bad.lower() in text:
            strings_ok = False
            reasons.append(f"forbidden text shown: {bad!r}")
    needed = case.get("must_contain_any")
    if needed and not any(s.lower() in text for s in needed):
        strings_ok = False
        reasons.append(f"none of {needed} shown")
    warnings_ok = True
    expected_warnings = case.get("expected_warnings_any")
    if expected_warnings:
        joined = " ".join(w.text for w in card.warnings).lower()
        joined += " " + " ".join(w for c in card.calculations for w in c.warnings).lower()
        if not any(s.lower() in joined for s in expected_warnings):
            warnings_ok = False
            reasons.append(f"no notice containing any of {expected_warnings}")

    lang_ok = card.lang == case["lang"]
    if not lang_ok:
        reasons.append(f"language {card.lang}, expected {case['lang']}")

    fabricated = 0
    for c in card.citations:
        chunk = pipeline.index.by_id.get(c.chunk_id)
        if chunk is None or normalize(c.quote) not in chunk.norm:
            fabricated += 1
    for key in rule_mentions(card.answer, pipeline.known_keys):
        if key not in pipeline.known_keys:
            fabricated += 1
    if fabricated:
        reasons.append(f"{fabricated} fabricated quote(s) or rule(s) shown")

    uncited = card.status in ANSWERED and not card.citations
    if uncited:
        reasons.append("answered without a verified citation")

    attempted = len(trace.verification_failures) + sum(
        1 for p in trace.problems if p.startswith(("V5", "V6"))
    )
    model_ms = sum(card.meta.model_time_s.values()) * 1000
    passed = (
        status_ok
        and rule_hit is not False
        and values_ok is not False
        and strings_ok
        and warnings_ok
        and lang_ok
        and not fabricated
        and not uncited
    )
    return {
        "id": case["id"],
        "source": case["source"],
        "question": case["question"],
        "tags": case["tags"],
        "expected_status": case["expected_status"],
        "status": card.status,
        "intent": card.intent,
        "status_ok": status_ok,
        "rule_hit": rule_hit,
        "retrieval_hit": retrieval_hit,
        "values_ok": values_ok,
        "strings_ok": strings_ok and warnings_ok,
        "lang_ok": lang_ok,
        "fabrication_shown": fabricated,
        "fabrication_attempted": attempted,
        "answered_without_citation": int(uncited),
        "pass": passed,
        "reasons": reasons,
        "latency_ms": round(wall_ms, 1),
        "model_time_ms": round(model_ms, 1),
        "calls": card.meta.calls,
        "tokens": card.meta.tokens,
        "cited_rules": sorted({c.label for c in card.citations}),
        "model_errors": list(trace.errors),
        "replay_miss": any("replay_miss" in e for e in trace.errors),
        "answer": card.answer[:400],
    }


# --- metrics -----------------------------------------------------------------------------------


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def ratio(num: int, den: int) -> float:
    return num / den if den else 1.0


def compute_metrics(results: list[dict]) -> dict:
    sample = [r for r in results if r["source"].startswith(SAMPLE_SOURCE)]
    sample_hits = sum(
        (r["rule_hit"] is True) if r["rule_hit"] is not None else r["status_ok"] for r in sample
    )
    with_values = [r for r in results if r["values_ok"] is not None]
    abstain = [r for r in results if r["expected_status"] == "NOT_FOUND"]
    injection = [r for r in results if "injection" in r["tags"]]
    expecting_rule = [r for r in results if r["rule_hit"] is not None]
    latencies = [r["latency_ms"] for r in results]
    model_times = [r["model_time_ms"] for r in results if r["calls"] > 0]
    return {
        "cases": len(results),
        "passed": sum(r["pass"] for r in results),
        "status_accuracy": ratio(sum(r["status_ok"] for r in results), len(results)),
        "rule_hit": sample_hits,
        "rule_hit_total": len(sample),
        "rule_hit_rate_all": ratio(
            sum(r["rule_hit"] is True for r in expecting_rule), len(expecting_rule)
        ),
        "retrieval_hit_rate": ratio(
            sum(r["retrieval_hit"] is True for r in expecting_rule), len(expecting_rule)
        ),
        "value_accuracy": ratio(sum(r["values_ok"] is True for r in with_values), len(with_values)),
        "value_cases": len(with_values),
        "abstention": ratio(sum(r["status_ok"] for r in abstain), len(abstain)),
        "abstention_cases": len(abstain),
        "fabrication_shown": sum(r["fabrication_shown"] for r in results),
        "fabrication_attempted": sum(r["fabrication_attempted"] for r in results),
        "injection_resistance": ratio(sum(r["pass"] for r in injection), len(injection)),
        "injection_cases": len(injection),
        "answered_without_citation": sum(r["answered_without_citation"] for r in results),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50), 1),
            "p95": round(percentile(latencies, 0.95), 1),
            "n": len(latencies),
        },
        "model_time_ms": {
            "p50": round(percentile(model_times, 0.50), 1),
            "p95": round(percentile(model_times, 0.95), 1),
            "n": len(model_times),
        },
        "model_calls": sum(r["calls"] for r in results),
        "calls_per_question": round(sum(r["calls"] for r in results) / max(len(results), 1), 2),
        "tokens": {
            k: sum(r["tokens"].get(k, 0) for r in results) for k in ("input", "output", "cached")
        },
        "replay_misses": sum(r["replay_miss"] for r in results),
    }


def target_status(summary: dict) -> dict[str, dict]:
    """Each SPEC §17 target with the measured value and whether it is met."""
    out = {}
    for key, (direction, target, label) in TARGETS.items():
        value = summary["latency_ms"]["p95"] if key == "latency_p95_ms" else summary[key]
        met = value >= target if direction == "min" else value <= target
        out[key] = {
            "label": label,
            "target": target,
            "direction": direction,
            "value": value,
            "met": met,
        }
    return out


def average_runs(per_run: list[dict]) -> dict:
    """Mean of the numeric metrics over runs, keeping min and max so variance is visible."""
    if len(per_run) == 1:
        return per_run[0]
    merged: dict = {}
    for key, first in per_run[0].items():
        if isinstance(first, dict):
            merged[key] = average_runs([r[key] for r in per_run])
        elif isinstance(first, (int, float)) and not isinstance(first, bool):
            vals = [r[key] for r in per_run]
            merged[key] = round(sum(vals) / len(vals), 4)
            merged[f"{key}_min"], merged[f"{key}_max"] = min(vals), max(vals)
        else:
            merged[key] = first
    return merged


# --- building and running ----------------------------------------------------------------------


def eval_settings(provider: str) -> Settings:
    load_dotenv_if_present()
    settings = get_settings()
    # The limiter may need to wait a long time on the free tier: do not give up at 25 s.
    return replace(settings, llm_provider=provider, request_deadline_s=900.0, audit_sink="none")


def make_pipeline(provider: str, run: int, record: bool, fresh: bool) -> Pipeline:
    settings = eval_settings(provider)
    if provider == "live":
        missing = [
            name
            for name, ok in (("CEREBRAS_API_KEY", settings.has_cerebras_key),
                             ("ANTHROPIC_API_KEY", settings.has_anthropic_key))
            if not ok
        ]  # fmt: skip
        if missing:
            raise SystemExit(
                f"--provider live needs {' and '.join(missing)} in the environment or .env. "
                "Use --provider offline to run without keys."
            )
        # Only the first run records; later runs are fresh calls so variance is real.
        return build_pipeline(
            settings, record=record and run == 0, use_recordings=not fresh and run == 0
        )
    return build_pipeline(settings)


def run_once(pipeline: Pipeline, cases: list[dict], verbose: bool) -> list[dict]:
    results = []
    for case in cases:
        result = evaluate_case(pipeline, case)
        results.append(result)
        if verbose:
            mark = "ok  " if result["pass"] else "FAIL"
            print(f"  {mark} {result['id']:<5} {result['status']:<13} {result['latency_ms']:>8.0f} ms"
                  f"  {'; '.join(result['reasons'])}")  # fmt: skip
    return results


def build_report(
    provider: str, runs: int, cases: list[dict], per_run: list[list[dict]], pipeline: Pipeline
) -> dict:
    run_summaries = [compute_metrics(r) for r in per_run]
    summary = average_runs(run_summaries)
    first = per_run[0]
    case_rows = []
    for i, row in enumerate(first):
        passes = sum(run[i]["pass"] for run in per_run)
        case_rows.append(
            {
                **row,
                "pass": passes == runs,
                "runs_passed": passes,
                "runs": runs,
                "flaky": 0 < passes < runs,
            }
        )
    settings = pipeline.settings
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider,
        "runs": runs,
        "golden_cases": len(cases),
        "unverified_cases": sum(1 for c in cases if not c["verified_by"]),
        "corpus_sha256": pipeline.corpus.sha256,
        "models": {
            "A": settings.cerebras_model if pipeline.understand else None,
            "B": settings.anthropic_model if pipeline.compose else None,
            "anthropic_effort": settings.anthropic_effort,
            "anthropic_thinking": settings.anthropic_thinking,
        },
        "summary": summary,
        "targets": target_status(run_summaries[0] if runs == 1 else summary),
        "run_summaries": run_summaries if runs > 1 else [],
        "cases": case_rows,
        "notes": notes_for(provider, summary, runs),
    }


def notes_for(provider: str, summary: dict, runs: int) -> list[str]:
    notes = []
    if provider == "offline":
        notes.append(
            "OFFLINE run: no model was called. Questions that need Step B (a cited, composed "
            "answer) end as NEEDS_REVIEW here, which is the designed degraded behaviour. This is "
            "not a measurement of the live system."
        )
    if provider == "replay":
        notes.append(
            "REPLAY run: answers come from evals/recordings/. Latency is the replayed pipeline "
            "time, not the original model time."
        )
        if summary.get("replay_misses"):
            notes.append(
                f"{summary['replay_misses']} case(s) had a model call with no recording and fell "
                "back to the offline path; record them with --provider live."
            )
    if provider == "live" and runs > 1:
        notes.append("Runs after the first are fresh model calls (no cache), so variance is real.")
    if provider != "live":
        notes.append("Anthropic has no seed and no temperature=0: only a replay is repeatable.")
    notes.append(
        "Expected values were derived from the calculators and checked by a test against the "
        "rulebook page text; a human sign-off (verified_by) is still pending for every case."
    )
    return notes


# --- markdown ------------------------------------------------------------------------------------


def cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def pct(x: float) -> str:
    return f"{round(x * 100, 1)}%"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Evaluation report",
        "",
        f"Generated {report['generated_at']} · provider **{report['provider']}** · "
        f"{report['runs']} run(s) · {report['golden_cases']} cases · corpus "
        f"`{report['corpus_sha256'][:12]}`",
        "",
    ]
    models = report["models"]
    lines.append(
        f"Models: Step A `{models['A'] or 'none (offline)'}`, Step B "
        f"`{models['B'] or 'none (offline)'}` (effort {models['anthropic_effort']}, "
        f"thinking {models['anthropic_thinking']})."
    )
    lines += ["", *[f"> {n}" for n in report["notes"]], "", "## Summary (measured)", ""]
    lines += ["| Metric | Result | Target | Met |", "|---|---|---|---|"]
    ratio_keys = ("status_accuracy", "value_accuracy", "abstention", "injection_resistance")
    for key, t in report["targets"].items():
        fmt = pct if key in ratio_keys else (lambda v: f"{v:g}")
        sign = "≥" if t["direction"] == "min" else "≤"
        met = "yes" if t["met"] else "**NO**"
        lines.append(
            f"| {cell(t['label'])} | {fmt(t['value'])} | {sign} {fmt(t['target'])} | {met} |"
        )
    lines += [
        "",
        f"Cases passed: **{round(s['passed'])} of {s['cases']}** (a case passes only if its status, "
        "rule, values, notices, language and integrity checks all pass).",
        "",
        f"Also measured: correct rule cited on {pct(s['rule_hit_rate_all'])} of all cases that name a "
        f"rule; the expected rule was among the cited or retrieved candidates on "
        f"{pct(s['retrieval_hit_rate'])}; fabrications caught before display: "
        f"{s['fabrication_attempted']:g}.",
        "",
        "## Latency (measured)",
        "",
        "| | p50 | p95 | n |",
        "|---|---|---|---|",
        f"| End to end | {s['latency_ms']['p50']:g} ms | {s['latency_ms']['p95']:g} ms | {s['latency_ms']['n']:g} |",
        f"| Model time (Step A + B, questions that called a model) | {s['model_time_ms']['p50']:g} ms | "
        f"{s['model_time_ms']['p95']:g} ms | {s['model_time_ms']['n']:g} |",
        "",
        f"Model calls: {s['model_calls']:g} ({s['calls_per_question']:g} per question) · tokens in/out/cached: "
        f"{s['tokens']['input']:g}/{s['tokens']['output']:g}/{s['tokens']['cached']:g}.",
        "",
    ]
    rows = report["cases"]
    sample = [r for r in rows if r["source"].startswith(SAMPLE_SOURCE)]
    lines += [
        "## The 17 sample questions",
        "",
        "| Case | Question | Expected | Got | Rules cited | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in sample:
        lines.append(
            f"| {r['id']} | {cell(r['question'][:80])} | {r['expected_status']} | {r['status']} | "
            f"{cell(', '.join(r['cited_rules']) or '-')} | {'pass' if r['pass'] else '**FAIL**'} |"
        )
    lines += [
        "",
        "## All cases",
        "",
        "| Case | Tags | Expected | Got | ms | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        result = "pass" if r["pass"] else "**FAIL**"
        if r["flaky"]:
            result = f"flaky ({r['runs_passed']}/{r['runs']})"
        lines.append(
            f"| {r['id']} | {cell(', '.join(r['tags']))} | {r['expected_status']} | {r['status']} | "
            f"{r['latency_ms']:g} | {result} |"
        )
    failed = [r for r in rows if not r["pass"]]
    lines += ["", f"## Failures ({len(failed)})", ""]
    if not failed:
        lines.append("None.")
    for r in failed:
        lines.append(f"- **{r['id']}** {cell(r['question'][:100])}")
        for reason in r["reasons"]:
            lines.append(f"  - {cell(reason)}")
    lines += [
        "",
        "## Method",
        "",
        "- Cases are in `evals/golden.jsonl`. `ANSWERED` matches ANSWERED or PARTIAL; `PARTIAL` "
        "must be PARTIAL; `NOT_FOUND` must be NOT_FOUND.",
        "- Rule hit: an expected rule is among the **verified citations**. Retrieval hit also "
        "accepts the candidate rules shown on a NEEDS_REVIEW card.",
        "- Sample-question score = answerable questions with the right rule cited + out-of-scope "
        "questions that returned NOT_FOUND, out of 17.",
        "- Fabrication (shown): a displayed quote that is not a substring of its rule text, or an "
        "answer naming a rule that does not exist. Fabrication (attempted): quotes and numbers the "
        "verifier dropped before display.",
        "- Latency is wall-clock for one question through the pipeline on this machine.",
        "",
    ]
    return "\n".join(lines)


# --- entry point ----------------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m evals.run_eval", description=__doc__.split("\n\n")[0]
    )
    p.add_argument("--runs", type=int, choices=(1, 2, 3), default=1)
    p.add_argument("--provider", choices=("live", "replay", "offline"), default="offline")
    p.add_argument("--golden", type=Path, default=GOLDEN_FILE)
    p.add_argument("--only", help="comma-separated case ids or tags")
    p.add_argument("--limit", type=int, help="run only the first N selected cases")
    p.add_argument("--out-dir", type=Path, default=EVALS_DIR)
    p.add_argument("--no-write", action="store_true", help="print the summary, write no files")
    p.add_argument("--no-record", action="store_true", help="live: do not save recordings")
    p.add_argument("--fresh", action="store_true", help="live: ignore existing recordings")
    p.add_argument("--strict", action="store_true", help="exit 1 if any SPEC §17 target is missed")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = select(load_golden(args.golden), args.only, args.limit)
    if not cases:
        print("no cases selected", file=sys.stderr)
        return 2

    per_run: list[list[dict]] = []
    pipeline: Pipeline | None = None
    for run in range(args.runs):
        pipeline = make_pipeline(args.provider, run, not args.no_record, args.fresh)
        print(f"run {run + 1}/{args.runs}: {len(cases)} cases, provider {args.provider}")
        per_run.append(run_once(pipeline, cases, args.verbose))
    assert pipeline is not None

    report = build_report(args.provider, args.runs, cases, per_run, pipeline)
    s = report["summary"]
    print(
        f"passed {s['passed']:g}/{s['cases']} · status {pct(s['status_accuracy'])} · "
        f"rule hit {s['rule_hit']:g}/{s['rule_hit_total']} · values {pct(s['value_accuracy'])} · "
        f"abstention {pct(s['abstention'])} · fabrications shown {s['fabrication_shown']:g} · "
        f"injection {pct(s['injection_resistance'])} · p50 {s['latency_ms']['p50']:g} ms · "
        f"p95 {s['latency_ms']['p95']:g} ms"
    )
    if not args.no_write:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (args.out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {args.out_dir / 'report.md'} and report.json")
    missed = [k for k, t in report["targets"].items() if not t["met"]]
    if missed:
        print("targets not met: " + ", ".join(missed))
    return 1 if (args.strict and missed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
