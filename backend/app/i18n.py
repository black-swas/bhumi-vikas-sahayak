"""Question normalisation (SPEC §7 step 1, §14, §19): NFC, Devanagari digits, language, units, PII.

The model never sees a phone number, an Aadhaar-like number or an email address: they are
replaced before any LLM call.
"""

import re
import unicodedata
from dataclasses import dataclass

MAX_QUESTION_CHARS = 500
HINDI_SHARE = 0.4  # share of Devanagari among letters that makes a question Hindi
HINDI_ANSWER_MIN_RATIO = 0.3  # V7

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LETTER = re.compile(r"[^\W\d_]|[ऀ-ॿ]")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
REDACTED = "[REDACTED]"

# Hindi unit words -> the spelling the parsers expect. Longest first.
_UNIT_WORDS = [
    (r"वर्ग\s*मीटर|वर्ग\s*मी\.?|वर्गमीटर", "sq m"),
    (r"वर्ग\s*फुट|वर्ग\s*फीट|वर्गफुट", "sq ft"),
    (r"वर्ग\s*गज", "sq yd"),
    (r"वर्ग\s*यार्ड", "sq yd"),
    (r"हेक्टेयर|हेक्टेअर", "ha"),
    (r"एकड़|एकड", "acre"),
    (r"गज", "gaj"),
    (r"मीटर|मी\.", "m"),
    (r"फीट|फुट", "ft"),
]
_UNIT_PATTERNS = [(re.compile(p), r) for p, r in _UNIT_WORDS]


@dataclass(frozen=True)
class NormalizedQuestion:
    original: str  # as typed (NFC, trimmed, truncated); shown back to the clerk
    text: str  # digits and units normalised, PII redacted: what the pipeline and models see
    lang: str  # "en" | "hi"
    redactions: int
    truncated: bool


def to_ascii_digits(text: str) -> str:
    return text.translate(_DEVANAGARI_DIGITS)


def devanagari_ratio(text: str) -> float:
    """Share of Devanagari characters among all letters (0.0 when there are none)."""
    letters = _LETTER.findall(text)
    if not letters:
        return 0.0
    return len(_DEVANAGARI.findall(text)) / len(letters)


def detect_lang(text: str) -> str:
    """Hindi when Devanagari dominates; mixed or Hinglish counts as English (SPEC §14)."""
    return "hi" if devanagari_ratio(text) >= HINDI_SHARE else "en"


def redact_pii(text: str) -> tuple[str, int]:
    count = 0
    for pattern in (_EMAIL, _AADHAAR, _PHONE):
        text, n = pattern.subn(REDACTED, text)
        count += n
    return text, count


def normalize_units(text: str) -> str:
    for pattern, repl in _UNIT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def normalize_question(raw: str, lang: str | None = None) -> NormalizedQuestion:
    text = unicodedata.normalize("NFC", raw).strip()
    truncated = len(text) > MAX_QUESTION_CHARS
    text = text[:MAX_QUESTION_CHARS]
    text = to_ascii_digits(text)
    text, redactions = redact_pii(text)
    original, _ = redact_pii(unicodedata.normalize("NFC", raw).strip()[:MAX_QUESTION_CHARS])
    detected = lang if lang in ("en", "hi") else detect_lang(text)
    text = normalize_units(text)
    text = " ".join(text.split())
    return NormalizedQuestion(original, text, detected, redactions, truncated)
