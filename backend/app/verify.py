"""Verification checks V1-V8 (SPEC §12). Nothing the model wrote is shown until it passes here.

V1  parse against the schema          V5  numbers in the answer come from sources
V2  citations name real candidates    V6  rules mentioned exist and are cited
V3  quotes are exact substrings       V7  the answer is in the question's language
V4  an answer has a verified citation V8  extracted parameters occur in the question
"""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from .corpus.chunker import Chunk, page_of_quote
from .corpus.index import rule_key
from .corpus.loader import Corpus, normalize
from .i18n import HINDI_ANSWER_MIN_RATIO, devanagari_ratio, to_ascii_digits
from .schemas import Citation, ComposeOutput, UnderstandOutput

QUOTE_MIN_CHARS = 15
QUOTE_MAX_CHARS = 400
MAX_ANSWER_WORDS = 90

_NUMBER = re.compile(r"\d+(?:,\d+)*(?:\.\d+)?")
_RULE_MENTION = re.compile(
    r"(?:\brules?|नियम)\s*(?:no\.?\s*)?(?P<num>\d{1,3})(?:(?P<sep>\s?-?\s?)(?P<let>[A-Za-z])(?![A-Za-z0-9]))?",
    re.IGNORECASE,
)


# --- V1 --------------------------------------------------------------------------------------


def parse_model(model: type[BaseModel], data: dict):
    """V1: returns (object, None) or (None, short reason). No raw model text in the reason."""
    try:
        return model.model_validate(data), None
    except ValidationError as e:
        fields = sorted({".".join(str(p) for p in err["loc"]) or "root" for err in e.errors()})
        return None, f"V1: output does not match the schema ({', '.join(fields)})"


def parse_understand(data: dict):
    return parse_model(UnderstandOutput, data)


def parse_compose(data: dict):
    obj, err = parse_model(ComposeOutput, data)
    if obj is not None and len(obj.answer.split()) > MAX_ANSWER_WORDS:
        return None, f"V1: answer is longer than {MAX_ANSWER_WORDS} words"
    return obj, err


# --- V2, V3 ----------------------------------------------------------------------------------


@dataclass
class CitationCheck:
    verified: list[Citation] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)  # {"chunk_id", "check", "reason"}


def make_citation(corpus: Corpus, chunk: Chunk, quote: str) -> Citation:
    page = page_of_quote(corpus, chunk, quote)
    return Citation(
        chunk_id=chunk.id,
        rule=chunk.rule,
        label=chunk.label,
        title=chunk.title,
        page=page,
        quote=" ".join(quote.split()),
        verified=True,
        pdf_en=f"/pdf/rules-en.pdf#page={page}",
        pdf_hi=f"/pdf/rules-hi.pdf#page={page}",
    )


def verify_citations(
    raw: list[tuple[str, str]], candidates: dict[str, Chunk], corpus: Corpus
) -> CitationCheck:
    """Keep a citation only if its chunk is a candidate (V2) and its normalised quote is an
    exact substring of that chunk's normalised text, 15-400 characters long (V3)."""
    out = CitationCheck()
    seen: set[tuple[str, str]] = set()
    for chunk_id, quote in raw:
        chunk = candidates.get(chunk_id)
        if chunk is None:
            out.failures.append({"chunk_id": chunk_id, "check": "V2", "reason": "not a candidate"})
            continue
        q = normalize(quote)
        if not QUOTE_MIN_CHARS <= len(q) <= QUOTE_MAX_CHARS:
            out.failures.append({"chunk_id": chunk_id, "check": "V3", "reason": "bad length"})
            continue
        if q not in chunk.norm:
            out.failures.append(
                {"chunk_id": chunk_id, "check": "V3", "reason": "quote is not in the chunk"}
            )
            continue
        if (chunk_id, q) in seen:
            continue
        seen.add((chunk_id, q))
        out.verified.append(make_citation(corpus, chunk, quote))
    return out


# --- V5, V6, V7 ------------------------------------------------------------------------------


def numbers_in(text: str) -> set[float]:
    """Every number in a text, ASCII or Devanagari digits; 3,000 and 1,25,000 read as one number."""
    return {float(n.replace(",", "")) for n in _NUMBER.findall(to_ascii_digits(text))}


def check_numbers(answer: str, source_texts: list[str]) -> list[float]:
    """V5: numbers in the answer that appear in none of the sources."""
    allowed: set[float] = set()
    for t in source_texts:
        allowed |= numbers_in(t)
    return sorted(n for n in numbers_in(answer) if n not in allowed)


def rule_mentions(answer: str, known_keys: set[str]) -> list[str]:
    """Rule keys named in an answer ("Rule 12-A" -> "12a", "नियम 56(1)" -> "56")."""
    keys = []
    for m in _RULE_MENTION.finditer(to_ascii_digits(answer)):
        num, let, sep = m.group("num"), m.group("let"), m.group("sep") or ""
        key = rule_key(num + (let or ""))
        # "rule 56 a plot": a lone lowercase letter after a space is an article, not an inserted
        # rule. "12-Z" is a rule number that does not exist and is reported as such.
        if let and let.islower() and sep != "" and sep.strip() == "" and key not in known_keys:
            key = rule_key(num)
        keys.append(key)
    return keys


def check_rule_mentions(answer: str, cited_keys: set[str], known_keys: set[str]) -> list[str]:
    """V6: problems for rules that do not exist or are named but not cited."""
    problems = []
    for key in dict.fromkeys(rule_mentions(answer, known_keys)):
        if key not in known_keys:
            problems.append(f"V6: Rule {key} does not exist in the rules")
        elif key not in cited_keys:
            problems.append(f"V6: Rule {key} is mentioned but not cited")
    return problems


def check_language(answer: str, lang: str) -> bool:
    """V7: Hindi needs a Devanagari ratio of at least 0.3; English must stay below it."""
    if not answer.strip():
        return True
    ratio = devanagari_ratio(answer)
    return ratio >= HINDI_ANSWER_MIN_RATIO if lang == "hi" else ratio < HINDI_ANSWER_MIN_RATIO


@dataclass
class ComposeCheck:
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check_answer(
    *,
    answer: str,
    lang: str,
    citations: list[Citation],
    source_texts: list[str],
    known_keys: set[str],
    needs_citation: bool = True,
) -> ComposeCheck:
    """V4 + V5 + V6 + V7 on a composed or templated answer."""
    check = ComposeCheck()
    if needs_citation and not citations:
        check.problems.append("V4: no citation with a verified quote")
    cited_keys = {rule_key(c.rule) for c in citations}
    # numbers allowed: sources given, plus the cited rules' labels and pages and verified quotes
    pool = [*source_texts]
    for c in citations:
        pool += [c.label, c.rule, c.quote, str(c.page)]
    bad = check_numbers(answer, pool)
    if bad:
        shown = ", ".join(f"{b:g}" for b in bad)
        check.problems.append(f"V5: number(s) not found in the sources: {shown}")
    check.problems += check_rule_mentions(answer, cited_keys, known_keys)
    if not check_language(answer, lang):
        want = "Hindi (Devanagari)" if lang == "hi" else "English"
        check.problems.append(f"V7: the answer must be written in {want}")
    return check


# --- V8 --------------------------------------------------------------------------------------

_NUMERIC_PARAMS = ("plot_area", "road_width_m", "height_m", "built_up_area_sqm", "frontage_m")
_ENUM_PARAMS = ("plot_area_unit", "use", "building_type", "voltage")


def validate_params(params, question: str) -> tuple[dict, list[str]]:
    """V8: keep a numeric parameter only if that number occurs in the question.

    Returns ({name: value or None}, [names dropped]). -1 and "unknown"/"none" mean not stated.
    """
    present = numbers_in(question)
    out: dict = {}
    dropped: list[str] = []
    for name in _NUMERIC_PARAMS:
        value = getattr(params, name)
        if value is None or value == -1:
            out[name] = None
        elif any(abs(value - p) < 1e-9 for p in present):
            out[name] = float(value)
        else:
            out[name] = None
            dropped.append(name)
    for name in _ENUM_PARAMS:
        value = getattr(params, name)
        out[name] = None if value in ("unknown", "none") else value
    if out["plot_area"] is None:
        out["plot_area_unit"] = None
    return out, dropped
