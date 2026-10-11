"""BM25 retrieval, direct rule lookup, glossary expansion and intent pins (SPEC §9).

Pure Python, no dependencies. The index is built once from the chunks and kept in memory.
"""

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .chunker import Chunk
from .loader import BACKEND_DIR

GLOSSARY_FILE = BACKEND_DIR / "data" / "glossary.json"

K1 = 1.5
B = 0.75
TITLE_WEIGHT = 2  # title tokens count double
MAX_CANDIDATES = 6
MAX_CHARS = 18_000  # soft cap on the characters added by BM25 hits

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|[^\s\d!-/:-@\[-`{-~“”‘’–—…।॥|]+")
_STOPWORDS = frozenset(
    """a an and are as at be been but by can do does for from has have how i if in into is it its
    me my no not of on or our shall should so such than that the their then there these this to
    was we what when where which who will with would you your may must any all each per
    के का की को में से है हैं पर और या कि क्या कितना कितनी कितने मेरा मेरी""".split()
)


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def _fold(text: str) -> str:
    """Lowercase, NFC, ASCII digits, nukta removed (so ज़ and ज match)."""
    text = unicodedata.normalize("NFC", to_ascii_digits(text)).lower()
    return text.replace("़", "")


def stem(tok: str) -> str:
    if len(tok) < 4 or not tok.isascii() or not tok.isalpha():
        return tok
    if tok.endswith("ies") and len(tok) > 4:
        tok = tok[:-3] + "y"
    elif tok.endswith("sses"):
        tok = tok[:-2]
    elif tok.endswith("s") and not tok.endswith("ss"):
        tok = tok[:-1]
    for suffix in ("ing", "ed"):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 3:
            tok = tok[: -len(suffix)]
            break
    if len(tok) > 4 and tok.endswith("e"):
        tok = tok[:-1]
    return tok


def tokenize(text: str) -> list[str]:
    out = []
    for tok in _TOKEN_RE.findall(_fold(text)):
        if tok in _STOPWORDS:
            continue
        out.append(stem(tok))
    return out


# --- BM25 ------------------------------------------------------------------------------------


class BM25:
    def __init__(self, docs: list[list[str]]):
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / max(len(docs), 1)
        df: Counter = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = [0.0] * len(self.tf)
        for t in set(query_tokens):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    out[i] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * self.len[i] / self.avg))
        return out


# --- glossary --------------------------------------------------------------------------------


def load_glossary(path: Path = GLOSSARY_FILE) -> list[tuple[list[str], list[str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [([_fold(t) for t in e["terms"]], e["expand"]) for e in data["entries"]]


def expand_query(query: str, glossary: list[tuple[list[str], list[str]]]) -> list[str]:
    """Extra query words contributed by glossary entries whose terms occur in the query."""
    folded = _fold(query)
    padded = " " + " ".join(_TOKEN_RE.findall(folded)) + " "
    extra: list[str] = []
    for terms, expand in glossary:
        for term in terms:
            hit = (f" {term} " in padded) if term.isascii() else (term in folded)
            if hit:
                extra.extend(expand)
                break
    return extra


# --- direct lookup ---------------------------------------------------------------------------

_RULE_WORD = r"(?:\brules?|नियम)\s*(?:no\.?|number|नं\.?|संख्या)?\s*"
_RULE_NUM = r"(?P<num>\d{1,3})(?:(?P<sep>\s?-?\s?)(?P<let>[a-z])(?![a-z0-9]))?"
_SUBS = r"(?P<subs>(?:\s*\(\s*\w+\s*\))*)"
_DIRECT_WORD = re.compile(_RULE_WORD + _RULE_NUM + _SUBS)
_DIRECT_BARE = re.compile(r"(?<![\w.])" + _RULE_NUM + r"(?P<subs>(?:\s*\(\s*\w+\s*\))+)")
_SUB_GROUP = re.compile(r"\(\s*(\w+)\s*\)")


def rule_key(rule: str) -> str:
    return re.sub(r"[^a-z0-9]", "", rule.lower())


# Intent -> chunk references to pin. "56(1)" = rule 56, sub-rule 1 (all parts); "61" = the whole
# rule; "12-A" = the inserted rule; "r21-3-1" = one exact chunk. SPEC §9 table.
INTENT_PINS: dict[str, list[str]] = {
    "plot_norms": ["56(1)", "56(2)", "56(3)", "53(1)", "61", "21(2)", "21(3)"],
    "front_open_space": ["56(1)"],
    "rear_open_space": ["56(2)"],
    "side_open_space": ["56(3)", "53(1)"],
    "far_built_up": ["61", "103"],
    "fee": ["21(2)", "21(3)"],
    "electric_line": ["52"],
    "high_rise_norms": ["42", "65"],
    "farm_house": ["17"],
    "permission_validity": ["23"],
    "deemed_permission": ["28"],
    "instant_approval": ["12-A", "23", "31(2)"],
    "water_body_site": ["50", "24(1)"],
    "plan_signing": ["18", "26", "26-B"],
    "application_documents": ["14", "16"],
    "plan_change": ["24", "r21-3-1", "r21-3-2"],
    "development_permission_need": ["2(5)", "12"],
    "dp_vs_rules": ["103"],
    "lifts": ["83"],
    "general_lookup": [],
    "out_of_scope": [],
}
HIGH_RISE_M = 12.5  # Rule 56 covers buildings up to 12.5 m; above that Rule 42 applies

_INTENT_HINTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "out_of_scope",
        (
            " property tax",
            " house tax",
            " market rate",
            " land rate",
            " guideline rate",
            " circle rate",
            " aadhaar",
            " aadhar",
            " electricity bill",
            " water bill",
            " contractor rate",
            " stamp duty",
            " registry fee",
            " ration card",
            " passport",
            "संपत्ति कर",
            "सम्पत्ति कर",
            "बाजार दर",
            "बाजार भाव",
            "बाज़ार भाव",
            "बाज़ार दर",
            "आधार",
            "बिजली का बिल",
        ),
    ),  # fmt: skip
    ("instant_approval", ("instant approval", "deemed approval", "12-a", "186")),
    ("deemed_permission", ("deemed", "authority did not reply", "no reply", "does not reply")),
    ("permission_validity", ("valid", "renew", "revalidat", "वैधता")),
    ("electric_line", ("electric", "voltage", "power line", "बिजली")),
    ("lifts", ("lift", "escalator", "लिफ्ट")),
    ("farm_house", ("farm house", "farmhouse", "फार्म हाउस")),
    ("plan_signing", ("sign the plan", "who may sign", "who can sign", "sign and submit")),
    ("application_documents", ("documents", "document", "दस्तावेज")),
    ("plan_change", ("change plan", "change the plan", "deviation", "after sanction")),
    ("dp_vs_rules", ("development plan",)),
    ("high_rise_norms", ("high rise", "high-rise", "tall building", "above 12.5", "उच्च भवन")),
    ("rear_open_space", ("rear", "पीछे", "peeche", "pichhe")),
    ("side_open_space", ("side open", "side space", "बगल")),
    ("front_open_space", ("front", "आगे", "सामने", "aage", "saamne", "setback", "set back")),
    ("fee", ("fee", "fees", "charge", "शुल्क", "फीस")),
    ("far_built_up", ("floor area ratio", "far ", "built up area", "built-up area")),
]


def guess_intent(query: str) -> str | None:
    """Conservative keyword intent for the offline path. None when unsure."""
    q = " " + _fold(query) + " "
    hits = [intent for intent, words in _INTENT_HINTS if any(_fold(w) in q for w in words)]
    if len(hits) >= 2 and {"front_open_space", "fee"} <= set(hits):
        return "plot_norms"
    return hits[0] if hits else None


# --- the index -------------------------------------------------------------------------------


@dataclass
class SearchResult:
    candidates: list[Chunk]
    pins: list[Chunk] = field(default_factory=list)
    direct: list[Chunk] = field(default_factory=list)
    bm25: list[tuple[Chunk, float]] = field(default_factory=list)
    top_score: float = 0.0
    query_tokens: list[str] = field(default_factory=list)


class Index:
    def __init__(self, chunks: list[Chunk], glossary: list | None = None):
        self.chunks = chunks
        self.by_id = {c.id: c for c in chunks}
        self.glossary = glossary if glossary is not None else load_glossary()
        self.by_key: dict[str, list[Chunk]] = {}
        for c in chunks:
            self.by_key.setdefault(rule_key(c.rule), []).append(c)
        docs = []
        for c in chunks:
            body = tokenize(c.text)
            docs.append(body + tokenize(c.title) * TITLE_WEIGHT)
        self.bm25 = BM25(docs)

    # -- lookups ------------------------------------------------------------

    def lookup(self, rule: str, sub: str | None = None) -> list[Chunk]:
        """Chunks of a rule (optionally one sub-rule). A sub-rule that is not a chunk, such as a
        lettered clause, falls back to the whole rule."""
        chunks = self.by_key.get(rule_key(rule), [])
        if sub is not None:
            exact = [c for c in chunks if c.sub == sub.lower() and c.sub not in ("0", "a")]
            if exact:
                return exact
        return list(chunks)

    def direct_lookup(self, query: str) -> list[Chunk]:
        """Resolve "rule 56", "Rule 56(1)", "नियम 56", "56(2)", "Rule 12-A" to exact chunks."""
        folded = _fold(query)
        found: list[Chunk] = []
        seen: set[str] = set()
        spans: list[tuple[int, int]] = []
        for pattern in (_DIRECT_WORD, _DIRECT_BARE):
            for m in pattern.finditer(folded):
                if any(s <= m.start() < e for s, e in spans):
                    continue
                spans.append((m.start(), m.end()))
                num, let, sep = m.group("num"), m.group("let"), m.group("sep") or ""
                subs = _SUB_GROUP.findall(m.group("subs") or "")
                sub = subs[0] if subs else None
                # "rule 56 a plot": a lone lowercase letter after a space is an article, not an
                # inserted rule. "12-a" and "12a" are inserted rules, and never fall back to "12".
                article = bool(let) and sep != "" and sep.strip() == ""
                if let and not article:
                    chunks = self.lookup(num + let, sub)
                else:
                    chunks = self.lookup(num, sub)
                for c in chunks:
                    if c.id not in seen:
                        seen.add(c.id)
                        found.append(c)
        return found

    def resolve_pin(self, ref: str) -> list[Chunk]:
        if ref in self.by_id:
            return [self.by_id[ref]]
        m = re.fullmatch(r"(\d+(?:-[A-Za-z])?)(?:\((\w+)\))?", ref)
        if not m:
            return []
        rule, sub = m.groups()
        chunks = self.by_key.get(rule_key(rule), [])
        if sub:
            return [c for c in chunks if c.sub == sub.lower()]
        return list(chunks)

    def pins_for(self, intent: str | None, height_m: float | None = None) -> list[Chunk]:
        refs = list(INTENT_PINS.get(intent or "", []))
        if intent == "front_open_space" and height_m is not None and height_m > HIGH_RISE_M:
            refs = ["42(1)"]
        out: list[Chunk] = []
        for ref in refs:
            for c in self.resolve_pin(ref):
                if c not in out:
                    out.append(c)
        return out

    # -- ranking --------------------------------------------------------------

    def rank(self, query: str, k: int = MAX_CANDIDATES) -> list[tuple[Chunk, float]]:
        """Pure BM25 ranking with glossary expansion: no pins, no direct lookup."""
        tokens = self._query_tokens(query)
        scores = self.bm25.scores(tokens)
        order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [(self.chunks[i], scores[i]) for i in order if scores[i] > 0]

    def _query_tokens(self, query: str) -> list[str]:
        extra = " ".join(expand_query(query, self.glossary))
        return tokenize(query) + tokenize(extra)

    def search(
        self,
        query: str,
        intent: str | None = None,
        height_m: float | None = None,
        k: int = MAX_CANDIDATES,
    ) -> SearchResult:
        """Candidates = direct hits + intent pins + BM25 top hits, deduplicated.

        Direct hits and pins are always kept (so a pinned set larger than ``k`` is returned in
        full); BM25 hits fill the remaining slots up to ``k`` and ``MAX_CHARS``.
        """
        direct = self.direct_lookup(query)
        pins = self.pins_for(intent, height_m)
        ranked = self.rank(query, k=k + len(direct) + len(pins))

        candidates: list[Chunk] = []
        for c in direct[:k] + pins:
            if c not in candidates:
                candidates.append(c)
        chars = 0
        for c, _score in ranked:
            if len(candidates) >= k:
                break
            if c in candidates:
                continue
            if chars + len(c.text) > MAX_CHARS:
                continue
            candidates.append(c)
            chars += len(c.text)
        return SearchResult(
            candidates=candidates,
            pins=pins,
            direct=direct,
            bm25=ranked,
            top_score=ranked[0][1] if ranked else 0.0,
            query_tokens=self._query_tokens(query),
        )
