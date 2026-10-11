"""The question-to-card pipeline (SPEC §7, steps 1-10).

normalize -> direct lookup -> understand (Step A) -> validate (V8) -> retrieve -> calculate ->
compose (Step B) or template -> verify (V1-V7, one repair) -> decorate -> audit.

Numbers come from the calculators only. Question text is data: it is redacted, delimited, and
never obeyed. Every answer shown has a verified quote; if verification fails twice the card is
NEEDS_REVIEW and shows candidate rules instead of generated text.
"""

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date

from . import calculators as calc
from . import templates
from .amendments import (
    DP_INTENTS,
    amendment_warning,
    dp_precedence_warning,
    load_amendments,
    make_version,
    matching_amendments,
)
from .audit import AuditLog
from .calculators._common import DP_PRECEDENCE_WARNING, CalcError, MissingInput
from .config import Settings
from .corpus import build_corpus
from .corpus.chunker import Chunk
from .corpus.index import Index, guess_intent, rule_key
from .corpus.loader import Corpus, normalize
from .i18n import NormalizedQuestion, normalize_question
from .llm.anthropic_adapter import AnthropicAdapter
from .llm.cerebras_adapter import CerebrasAdapter
from .llm.port import LLMError, LLMMetrics, LLMPort
from .llm.prompts import build_compose_messages, build_understand_messages, format_facts
from .llm.replay_adapter import ReplayAdapter
from .llm.schema_json import COMPOSE_SCHEMA, UNDERSTAND_SCHEMA
from .offline import extract_params, offline_understand
from .schemas import (
    AnswerCard,
    AskRequest,
    CalculationResult,
    Citation,
    Meta,
)
from .schemas import Warning as CardWarning
from .verify import (
    check_answer,
    parse_compose,
    parse_understand,
    rule_mentions,
    validate_params,
    verify_citations,
)

log = logging.getLogger(__name__)

# intents answered from calculators and templates alone (no Step B call)
PURE_CALC = {
    "plot_norms", "front_open_space", "rear_open_space", "side_open_space", "far_built_up", "fee",
    "electric_line", "high_rise_norms", "farm_house", "permission_validity", "instant_approval",
}  # fmt: skip
OVERRIDE_KEYS = {
    "intent", "plot_area_sqm", "road_width_m", "height_m", "built_up_area_sqm", "frontage_m",
    "use", "building_type", "voltage", "commercial_category", "grant_year", "cinema_seats",
}  # fmt: skip
NUMERIC_PARAMS = ("plot_area", "road_width_m", "height_m", "built_up_area_sqm", "frontage_m")
MIN_CALC_QUOTE_CHARS = 25


class OverrideError(ValueError):
    """params_override has an unknown key or an unusable value (HTTP 422)."""


@dataclass
class Params:
    plot_area_sqm: float | None = None
    road_width_m: float | None = None
    height_m: float | None = None
    built_up_area_sqm: float | None = None
    frontage_m: float | None = None
    use: str | None = None
    building_type: str | None = None
    voltage: str | None = None
    commercial_category: str | None = None
    grant_year: int | None = None
    grant_date: date | None = None
    cinema_seats: int | None = None
    notes: list[str] = field(default_factory=list)  # unit conversions, assumed units


@dataclass
class Trace:
    """Internal record of one run, for tests, the eval harness and the audit line."""

    intent: str = ""
    understand_source: str = ""  # llm | offline | override
    in_scope: bool = True
    dropped_params: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    verification_failures: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    repairs: int = 0
    errors: list[str] = field(default_factory=list)
    path: str = ""  # not_found | template | compose | review | error
    metrics: dict[str, list[LLMMetrics]] = field(default_factory=lambda: {"A": [], "B": []})


# --- parameters ------------------------------------------------------------------------------


def build_params(vparams: dict, extras: dict) -> Params:
    p = Params(
        road_width_m=vparams.get("road_width_m"),
        height_m=vparams.get("height_m"),
        built_up_area_sqm=vparams.get("built_up_area_sqm"),
        frontage_m=vparams.get("frontage_m"),
        use=vparams.get("use"),
        building_type=vparams.get("building_type"),
        voltage=vparams.get("voltage"),
        commercial_category=extras.get("commercial_category"),
        grant_year=extras.get("grant_year"),
        cinema_seats=extras.get("cinema_seats"),
    )
    if vparams.get("plot_area") is not None:
        unit = vparams.get("plot_area_unit")
        conv = calc.to_sqm(vparams["plot_area"], unit or "sqm")
        p.plot_area_sqm = conv.value
        if unit is None:
            p.notes.append("Plot area taken as square metres (no unit was given)")
        elif conv.input_unit != "sqm":
            p.notes.append(f"Plot area converted: {conv.text}")
    if (g := extras.get("grant_date")) is not None:
        try:
            p.grant_date = date(*g)
        except ValueError:
            pass
    return p


def apply_override(p: Params, override: dict) -> str | None:
    """Merge a clerk's edits into the parameters. Returns an intent override, if given."""
    unknown = set(override) - OVERRIDE_KEYS
    if unknown:
        raise OverrideError(f"unknown parameter(s): {', '.join(sorted(unknown))}")
    intent = override.get("intent")
    for key, value in override.items():
        if key == "intent":
            continue
        if value is None:
            setattr(p, key, None)
            continue
        if key in ("use", "building_type", "voltage", "commercial_category"):
            if not isinstance(value, str):
                raise OverrideError(f"{key} must be text")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OverrideError(f"{key} must be a number")
        setattr(p, key, int(value) if key in ("grant_year", "cinema_seats") else value)
    return intent


# --- calculators -----------------------------------------------------------------------------


def run_calculators(intent: str, p: Params) -> tuple[list[CalculationResult], list[str]]:
    """Run the calculators for an intent. Returns (results, names of missing inputs)."""
    calcs: list[CalculationResult] = []
    missing: list[str] = []

    def attempt(fn, *args, **kwargs) -> None:
        try:
            out = fn(*args, **kwargs)
        except MissingInput as e:
            missing.extend(e.missing)
        except CalcError:
            missing.append(_invalid_name(fn))
        else:
            calcs.extend(out if isinstance(out, list) else [out])

    def need(name: str, value) -> bool:
        if value is None:
            missing.append(name)
            return False
        return True

    if intent == "plot_norms":
        if need("plot_area_sqm", p.plot_area_sqm):
            if need("road_width_m", p.road_width_m):
                attempt(calc.front_open_space, p.road_width_m, p.height_m)
            attempt(calc.rear_open_space, p.plot_area_sqm, p.height_m)
            types = None
            try:
                types = calc.classify_plot_types(p.plot_area_sqm, p.frontage_m)
                calcs.append(types)
            except CalcError:
                missing.append("plot_area_sqm")
            wanted = (
                [p.building_type] if p.building_type else (types.details["fits"] if types else [])
            )
            for bt in wanted:
                attempt(calc.side_open_space, bt, p.height_m, p.frontage_m)
            attempt(calc.max_built_up, p.plot_area_sqm, p.use, p.commercial_category)
            attempt(
                calc.fees,
                built_up_area_sqm=p.built_up_area_sqm,
                plot_area_sqm=p.plot_area_sqm,
                use=p.use,
                height_m=p.height_m,
                cinema_seats=p.cinema_seats,
                commercial_category=p.commercial_category,
            )
            if p.height_m and p.height_m > 12.5 and p.road_width_m:
                attempt(
                    calc.high_rise_norms,
                    p.road_width_m,
                    p.plot_area_sqm,
                    p.height_m,
                    p.frontage_m,
                )
            attempt(calc.instant_approval_threshold, p.plot_area_sqm, p.use)
    elif intent == "front_open_space":
        if need("road_width_m", p.road_width_m):
            attempt(calc.front_open_space, p.road_width_m, p.height_m)
    elif intent == "rear_open_space":
        if need("plot_area_sqm", p.plot_area_sqm):
            attempt(calc.rear_open_space, p.plot_area_sqm, p.height_m)
    elif intent == "side_open_space":
        if p.building_type:
            attempt(calc.side_open_space, p.building_type, p.height_m, p.frontage_m)
        elif p.plot_area_sqm:
            for bt in calc.classify_plot_types(p.plot_area_sqm, p.frontage_m).details["fits"]:
                attempt(calc.side_open_space, bt, p.height_m, p.frontage_m)
        else:
            missing.append("building_type")
    elif intent == "far_built_up":
        if need("plot_area_sqm", p.plot_area_sqm):
            attempt(calc.max_built_up, p.plot_area_sqm, p.use, p.commercial_category)
    elif intent == "fee":
        attempt(
            calc.fees,
            built_up_area_sqm=p.built_up_area_sqm,
            plot_area_sqm=p.plot_area_sqm,
            use=p.use,
            height_m=p.height_m,
            cinema_seats=p.cinema_seats,
            commercial_category=p.commercial_category,
        )
    elif intent == "electric_line":
        attempt(calc.electric_clearance, p.voltage)
    elif intent == "high_rise_norms":
        ok = need("road_width_m", p.road_width_m)
        ok &= need("plot_area_sqm", p.plot_area_sqm)
        ok &= need("height_m", p.height_m)
        if ok:
            attempt(calc.high_rise_norms, p.road_width_m, p.plot_area_sqm, p.height_m, p.frontage_m)
    elif intent == "farm_house":
        attempt(calc.farm_house, p.plot_area_sqm)
    elif intent == "permission_validity":
        attempt(calc.permission_validity, p.grant_date, p.grant_year)
    elif intent == "instant_approval":
        if need("plot_area_sqm", p.plot_area_sqm):
            attempt(calc.instant_approval_threshold, p.plot_area_sqm, p.use)

    for c in calcs:
        for note in p.notes:
            if note not in c.assumptions:
                c.assumptions.append(note)
    return calcs, list(dict.fromkeys(missing))


def _invalid_name(fn) -> str:
    return "plot_area_sqm" if "plot" in getattr(fn, "__name__", "") else "road_width_m"


# --- calculator citations --------------------------------------------------------------------


def verbatim_excerpt(chunk: Chunk, limit: int = 380) -> str | None:
    """The opening of a chunk, cut at a word boundary: an exact slice of the rule text."""
    words = chunk.text.split()
    out = ""
    for word in words:
        if len(out) + len(word) + 1 > limit:
            break
        out = f"{out} {word}".strip()
    return out if len(out) >= 15 else None


def find_quote(chunk: Chunk, piece: str) -> str | None:
    """A verbatim quote from the chunk that contains ``piece`` (whitespace-tolerant).

    A short piece, such as one fee-table row, is widened with the lines before it so that the
    quote reads as text (at least 25 characters). Returns None if the piece is not in the chunk.
    """
    tokens = piece.split()
    if not tokens:
        return None
    m = re.search(r"\s+".join(re.escape(t) for t in tokens), chunk.text, re.IGNORECASE)
    if m is None:
        return None
    start = chunk.text.rfind("\n", 0, m.start()) + 1
    while len(normalize(chunk.text[start : m.end()])) < MIN_CALC_QUOTE_CHARS and start > 0:
        prev = chunk.text.rfind("\n", 0, start - 1) + 1
        if not chunk.text[prev : start - 1].strip():
            break
        start = prev
    return " ".join(chunk.text[start : m.end()].split())


# --- the pipeline ----------------------------------------------------------------------------


class Pipeline:
    def __init__(
        self,
        corpus: Corpus,
        index: Index,
        settings: Settings,
        understand: LLMPort | None = None,
        compose: LLMPort | None = None,
        amendments: list[dict] | None = None,
        audit: AuditLog | None = None,
    ):
        self.corpus = corpus
        self.index = index
        self.settings = settings
        self.understand = understand
        self.compose = compose
        self.amendments = amendments if amendments is not None else load_amendments()
        self.audit = audit
        self.known_keys = {rule_key(c.rule) for c in corpus.chunks}

    @property
    def mode(self) -> str:
        if self.understand is None and self.compose is None:
            return "offline"
        return "replay" if self.settings.llm_provider == "replay" else "live"

    # -- public --------------------------------------------------------------------------

    def ask(self, req: AskRequest, request_id: str | None = None) -> AnswerCard:
        return self.ask_traced(req, request_id)[0]

    def ask_traced(
        self, req: AskRequest, request_id: str | None = None
    ) -> tuple[AnswerCard, Trace]:
        t0 = time.perf_counter()
        rid = request_id or uuid.uuid4().hex[:8]
        trace = Trace()
        nq = normalize_question(req.question, req.lang)
        try:
            card = self._run(req, nq, rid, t0, trace)
        except OverrideError:
            raise
        except Exception as e:  # noqa: BLE001 - the last line of defence: an ERROR card, not a 500
            log.error("pipeline failure %s: %s", rid, type(e).__name__)
            trace.path = "error"
            trace.errors.append(f"exception:{type(e).__name__}")
            card = self._card(
                nq, rid, "ERROR", trace.intent or "general_lookup",
                templates.message("error", nq.lang),
                [], [], [], [], [], t0, trace,
            )  # fmt: skip
        self._audit(card, nq, trace)
        return card, trace

    # -- steps -----------------------------------------------------------------------------

    def _expired(self, t0: float) -> bool:
        return time.perf_counter() - t0 > self.settings.request_deadline_s

    def _run(self, req: AskRequest, nq: NormalizedQuestion, rid: str, t0: float, trace: Trace):
        # A question about a rule number that does not exist ("What does Rule 150 say?") is
        # answered NOT_FOUND here, without asking a model: the rulebook ends at Rule 105.
        mentioned = rule_mentions(nq.text, self.known_keys)
        if mentioned and not any(k in self.known_keys for k in mentioned):
            trace.intent, trace.path = "general_lookup", "not_found"
            return self._not_found(nq, rid, "general_lookup", t0, trace)

        # 3-4 understand + validate
        if req.params_override is not None:
            intent, query, params, in_scope = self._from_override(req, nq, trace)
        else:
            intent, query, params, in_scope = self._understand(nq, trace, t0)
        trace.intent, trace.in_scope = intent, in_scope

        # abstention gate 1: Step A (or the offline hints) say the rules do not cover it
        if not in_scope or intent == "out_of_scope":
            return self._not_found(nq, rid, intent, t0, trace)

        # 2 + 5 retrieve (direct lookup of "rule 56" is part of search)
        res = self.index.search(f"{query} {nq.text}", intent=intent, height_m=params.height_m)
        trace.candidates = [c.id for c in res.candidates]
        tau = self.settings.bm25_not_found_threshold
        if tau is not None and not res.pins and not res.direct and res.top_score < tau:
            return self._not_found(nq, rid, intent, t0, trace)  # abstention gate 2

        # 6 calculate
        calcs, missing = run_calculators(intent, params)
        missing_text = [templates.missing_text([m], nq.lang) for m in missing]

        # 7 compose or template
        if calcs and intent in PURE_CALC:
            return self._from_templates(
                nq, rid, intent, calcs, missing, missing_text, res, t0, trace
            )
        outcome = self._compose(nq, intent, res.candidates, calcs, trace, t0)
        if outcome is None:  # model unavailable, refused or failed verification twice
            if calcs:
                return self._from_templates(
                    nq, rid, intent, calcs, missing, missing_text, res, t0, trace
                )
            extract = self._extractive(nq, rid, intent, res, t0, trace)
            if extract is not None:
                return extract
            return self._needs_review(nq, rid, intent, res.candidates, calcs, t0, trace)
        obj, citations = outcome
        if obj.status == "not_found" and not calcs:
            return self._not_found(nq, rid, intent, t0, trace)
        if obj.status == "not_found":
            return self._from_templates(
                nq, rid, intent, calcs, missing, missing_text, res, t0, trace
            )
        extra_missing = list(obj.missing_info)
        status = "PARTIAL" if obj.status == "need_more_info" or extra_missing or missing else None
        trace.path = "compose"
        return self._card(
            nq, rid, status or "ANSWERED", intent, obj.answer, calcs, citations,
            [*missing_text, *extra_missing], [], res.candidates, t0, trace,
        )  # fmt: skip

    def _from_override(self, req: AskRequest, nq: NormalizedQuestion, trace: Trace):
        """Re-run the calculators on the clerk's edited parameters: no model call at all."""
        off = offline_understand(nq)
        vparams, dropped = validate_params(_ParamView(off.params), nq.text)
        trace.dropped_params = dropped
        params = build_params(vparams, off.extras)
        intent = apply_override(params, req.params_override or {}) or off.intent
        if intent == "general_lookup" and params.road_width_m and params.plot_area_sqm:
            intent = "plot_norms"
        trace.understand_source = "override"
        return intent, off.search_query_en, params, True

    def _understand(self, nq: NormalizedQuestion, trace: Trace, t0: float):
        regex_params, extras = extract_params(nq.text)
        data = None
        if self.understand is not None and not self._expired(t0):
            data = self._call_understand(nq, trace)
        if data is None:  # offline fallback
            off = offline_understand(nq)
            trace.understand_source = "offline"
            vparams, dropped = validate_params(_ParamView(off.params), nq.text)
            trace.dropped_params = dropped
            return off.intent, off.search_query_en, build_params(vparams, off.extras), off.in_scope

        trace.understand_source = "llm"
        vparams, dropped = validate_params(data.params, nq.text)
        trace.dropped_params = dropped
        # fill gaps from numbers that literally occur in the question (regex, V8-checked)
        regex_valid, _ = validate_params(_ParamView(regex_params), nq.text)
        for key, value in regex_valid.items():
            if vparams.get(key) is None and value is not None:
                vparams[key] = value
        in_scope = data.in_scope
        intent = data.intent
        if guess_intent(nq.text) == "out_of_scope":  # explicit out-of-scope topics win
            in_scope, intent = False, "out_of_scope"
        return intent, data.search_query_en, build_params(vparams, extras), in_scope

    def _call_understand(self, nq: NormalizedQuestion, trace: Trace):
        messages = build_understand_messages(nq.text)
        step = "understand"
        for attempt in (0, 1):
            try:
                raw, metrics = self.understand.complete_json(step, messages, UNDERSTAND_SCHEMA)
            except LLMError as e:
                trace.errors.append(f"A:{e.kind}")
                return None
            trace.metrics["A"].append(metrics)
            obj, err = parse_understand(raw)
            if obj is not None:
                return obj
            trace.problems.append(err or "V1")
            if attempt == 0:  # one repair call
                trace.repairs += 1
                step = "repair"
                messages = [
                    *messages[:-1],
                    {
                        "role": "user",
                        "content": f"{messages[-1]['content']}\n\n{err}. Reply again.",
                    },
                ]
        return None

    def _compose(
        self,
        nq: NormalizedQuestion,
        intent: str,
        chunks: list[Chunk],
        calcs: list[CalculationResult],
        trace: Trace,
        t0: float,
    ):
        """Step B with checks V1-V7 and one repair. Returns (ComposeOutput, citations) or None."""
        if self.compose is None or not chunks:
            return None
        candidates = {c.id: c for c in chunks}
        sources = [nq.text, format_facts(calcs)]
        problems: list[str] | None = None
        step = "compose"
        for attempt in (0, 1):
            if self._expired(t0):
                trace.errors.append("B:deadline")
                return None
            messages = build_compose_messages(nq.text, nq.lang, chunks, calcs, problems)
            try:
                raw, metrics = self.compose.complete_json(step, messages, COMPOSE_SCHEMA)
            except LLMError as e:
                trace.errors.append(f"B:{e.kind}")
                return None  # refusal, truncation, outage: never retried as an answer
            trace.metrics["B"].append(metrics)
            obj, err = parse_compose(raw)
            if obj is None:
                problems = [err or "V1: invalid output"]
            elif obj.status == "not_found":
                return obj, []
            else:
                check = verify_citations(
                    [(c.chunk_id, c.quote) for c in obj.citations], candidates, self.corpus
                )
                trace.verification_failures += check.failures
                result = check_answer(
                    answer=obj.answer,
                    lang=nq.lang,
                    citations=check.verified,
                    source_texts=sources,
                    known_keys=self.known_keys,
                )
                if result.ok:
                    return obj, check.verified
                problems = result.problems
            trace.problems += problems
            if attempt == 0:
                trace.repairs += 1
                step = "repair"
        return None

    # -- results ----------------------------------------------------------------------------

    def _calc_citations(self, calcs: list[CalculationResult]) -> list[Citation]:
        raw: list[tuple[str, str]] = []
        candidates: dict[str, Chunk] = {}
        for c in calcs:
            chunks = sorted(
                self.index.by_key.get(rule_key(c.rule), []), key=lambda ch: c.page not in ch.pages
            )
            for piece in (p.strip() for p in c.matched_row_text.split(" | ")):
                for chunk in chunks:
                    quote = find_quote(chunk, piece) if piece else None
                    if quote:
                        candidates[chunk.id] = chunk
                        raw.append((chunk.id, quote))
                        break
        return verify_citations(raw, candidates, self.corpus).verified

    def _extractive(self, nq, rid, intent, res, t0, trace):
        """A question naming a rule ("What does Rule 56(2) say?") with no model to phrase it.

        Shows the rule's own words, verbatim, as verified quotes: no summary, no generated text.
        """
        if not res.direct:
            return None
        raw, candidates = [], {}
        for chunk in res.direct[:3]:
            quote = verbatim_excerpt(chunk)
            if quote:
                raw.append((chunk.id, quote))
                candidates[chunk.id] = chunk
        check = verify_citations(raw, candidates, self.corpus)
        trace.verification_failures += check.failures
        if not check.verified:
            return None
        trace.path = "extract"
        return self._card(
            nq, rid, "PARTIAL", intent, templates.message("direct_text", nq.lang), [],
            check.verified, [], [], [], t0, trace,
        )  # fmt: skip

    def _from_templates(self, nq, rid, intent, calcs, missing, missing_text, res, t0, trace):
        answer = templates.render_answer(calcs, nq.lang)
        if missing:
            answer = f"{answer}\n{templates.need_more_info(missing, nq.lang)}".strip()
        citations = self._calc_citations(calcs)
        check = check_answer(
            answer=answer,
            lang=nq.lang,
            citations=citations,
            source_texts=[nq.text, format_facts(calcs)],
            known_keys=self.known_keys,
        )
        if not answer or not check.ok:
            trace.problems += check.problems or ["template produced no text"]
            return self._needs_review(nq, rid, intent, res.candidates, calcs, t0, trace)
        trace.path = "template"
        partial = bool(missing) or any(c.assumptions for c in calcs)
        return self._card(
            nq, rid, "PARTIAL" if partial else "ANSWERED", intent, answer, calcs, citations,
            missing_text, [], [], t0, trace,
        )  # fmt: skip

    def _not_found(self, nq, rid, intent, t0, trace):
        trace.path = "not_found"
        return self._card(
            nq, rid, "NOT_FOUND", intent, templates.message("not_found", nq.lang),
            [], [], [], [], [], t0, trace,
        )  # fmt: skip

    def _needs_review(self, nq, rid, intent, chunks, calcs, t0, trace):
        trace.path = "review"
        warnings = [
            CardWarning(type="verification_failed", text=templates.message("needs_review", nq.lang))
        ]
        return self._card(
            nq, rid, "NEEDS_REVIEW", intent, "", [], [], [], warnings, chunks, t0, trace,
        )  # fmt: skip

    def _card(
        self,
        nq: NormalizedQuestion,
        rid: str,
        status: str,
        intent: str,
        answer: str,
        calcs: list[CalculationResult],
        citations: list[Citation],
        missing_info: list[str],
        extra_warnings: list[CardWarning],
        chunks: list[Chunk],
        t0: float,
        trace: Trace,
    ) -> AnswerCard:
        shown_calcs = calcs if status in ("ANSWERED", "PARTIAL") else []
        warnings = list(extra_warnings)
        if status in ("ANSWERED", "PARTIAL"):
            warnings += self._decorate(nq, intent, shown_calcs, citations)
            if self._amendment_forces_partial(intent, citations) and status == "ANSWERED":
                status = "PARTIAL"
        amendments_in_force = self.amendments
        mt = {k: round(sum(m.model_time_s for m in v), 3) for k, v in trace.metrics.items() if v}
        all_metrics = [m for v in trace.metrics.values() for m in v]
        meta = Meta(
            providers={
                "A": self.understand.provider
                if self.understand and trace.metrics["A"]
                else "offline",
                "B": self.compose.provider if self.compose and trace.metrics["B"] else "none",
            },
            models={k: v[-1].model for k, v in trace.metrics.items() if v},
            latency_ms=int((time.perf_counter() - t0) * 1000),
            model_time_s=mt,
            calls=len(all_metrics),
            tokens={
                "input": sum(m.input_tokens for m in all_metrics),
                "output": sum(m.output_tokens for m in all_metrics),
                "cached": sum(m.cached_tokens for m in all_metrics),
            },
            replay=bool(all_metrics) and all(m.replay for m in all_metrics),
        )
        return AnswerCard(
            request_id=rid,
            question=nq.original,
            lang=nq.lang,
            status=status,
            intent=intent,
            answer=answer,
            calculations=shown_calcs,
            citations=citations,
            warnings=warnings,
            missing_info=missing_info,
            candidates=[c.id for c in chunks] if status == "NEEDS_REVIEW" else [],
            version=make_version(self.corpus.sha256, amendments_in_force, nq.lang),
            meta=meta,
        )

    def _decorate(self, nq, intent, calcs, citations) -> list[CardWarning]:
        """Step 9: Development Plan note, amendment overlay and the calculators' warnings."""
        out: list[CardWarning] = []
        calc_warnings = [w for c in calcs for w in c.warnings]
        if intent in DP_INTENTS or DP_PRECEDENCE_WARNING in calc_warnings:
            out.append(dp_precedence_warning(nq.lang))
        cited = [(c.rule, c.label) for c in citations]
        for m in matching_amendments(self.amendments, intent, cited):
            out.append(amendment_warning(m.amendment, nq.lang))
        for w in dict.fromkeys(calc_warnings):
            if w != DP_PRECEDENCE_WARNING:
                out.append(CardWarning(type="calculation", text=w))
        return out

    def _amendment_forces_partial(self, intent: str, citations: list[Citation]) -> bool:
        cited = [(c.rule, c.label) for c in citations]
        return any(m.by_intent for m in matching_amendments(self.amendments, intent, cited))

    def _audit(self, card: AnswerCard, nq: NormalizedQuestion, trace: Trace) -> None:
        if self.audit is None:
            return
        all_metrics = [m for v in trace.metrics.values() for m in v]
        self.audit.write(
            {
                "request_id": card.request_id,
                "lang": card.lang,
                "question": nq.text,
                "intent": card.intent,
                "status": card.status,
                "path": trace.path,
                "understand": trace.understand_source,
                "cited_rules": sorted({c.label for c in card.citations}),
                "calculators": [c.calc_id for c in card.calculations],
                "models": card.meta.models,
                "latency_ms": card.meta.latency_ms,
                "time_info": [m.time_info for m in all_metrics if m.time_info],
                "tokens": {
                    "input": sum(m.input_tokens for m in all_metrics),
                    "output": sum(m.output_tokens for m in all_metrics),
                    "cached": sum(m.cached_tokens for m in all_metrics),
                },
                "repairs": trace.repairs,
                "verification_failures": trace.verification_failures,
                "problems": trace.problems,
                "errors": trace.errors,
                "redactions": nq.redactions,
            }
        )


class _ParamView:
    """Adapts a plain dict of Step A-style parameters for validate_params."""

    def __init__(self, params: dict):
        self._p = params

    def __getattr__(self, name: str):
        return self._p.get(name)


def build_pipeline(
    settings: Settings,
    audit: AuditLog | None = None,
    *,
    record: bool = False,
    use_recordings: bool = True,
) -> Pipeline:
    """Wire the corpus, the calculators and the providers for the configured mode."""
    corpus, index = build_corpus()
    understand: LLMPort | None = None
    compose: LLMPort | None = None
    if settings.llm_provider == "replay":
        understand = ReplayAdapter("cerebras", settings.cerebras_model, "none")
        compose = ReplayAdapter("anthropic", settings.anthropic_model, settings.anthropic_effort)
    elif settings.llm_provider != "offline":
        if settings.has_cerebras_key:
            understand = CerebrasAdapter(settings)
        if settings.has_anthropic_key:
            compose = AnthropicAdapter(settings)
        if record:  # local scripts only: save each live answer so DEMO_REPLAY can serve it
            if understand is not None:
                understand = ReplayAdapter(
                    "cerebras", settings.cerebras_model, "none", inner=understand,
                    writable=True, read_cache=use_recordings,
                )  # fmt: skip
            if compose is not None:
                compose = ReplayAdapter(
                    "anthropic", settings.anthropic_model, settings.anthropic_effort,
                    inner=compose, writable=True, read_cache=use_recordings,
                )  # fmt: skip
    return Pipeline(corpus, index, settings, understand, compose, audit=audit)


__all__ = ["OverrideError", "Params", "Pipeline", "Trace", "build_pipeline"]
