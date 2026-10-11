"""Version stamp, amendment overlay and the Development Plan note (SPEC §13).

The committed ``data/amendments.json`` is the baseline. An amendment is only ever shown as a
warning with its source type, never as a verified quote, and a question that only the amendment
answers stays PARTIAL.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .calculators._common import DP_PRECEDENCE_WARNING
from .schemas import Version
from .schemas import Warning as CardWarning

AMENDMENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "amendments.json"
VERSION_LABEL = {"en": "consolidated to 06/03/2025", "hi": "06/03/2025 तक समेकित"}
DP_PRECEDENCE_HI = (
    "नियम 103: भोपाल विकास योजना के मानदंड इन नियमों पर प्राथमिक होंगे; नियम 61 तालिका 8: FAR विकास "
    "योजना के अनुसार अपनाया जा सकता है। अंतिम रूप देने से पहले विकास योजना देख लें।"
)
# intents whose answers rest on FAR or setbacks: they always carry the Development Plan note
DP_INTENTS = {
    "plot_norms",
    "front_open_space",
    "rear_open_space",
    "side_open_space",
    "far_built_up",
    "high_rise_norms",
    "fee",
}


def load_amendments(path: Path = AMENDMENTS_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class AmendmentMatch:
    amendment: dict
    by_intent: bool


def matching_amendments(
    amendments: list[dict], intent: str | None, cited: list[tuple[str, str]]
) -> list[AmendmentMatch]:
    """Amendments touched by this answer.

    ``cited`` is a list of (rule, label) pairs of the chunks shown on the card. An ``affects``
    entry with a bracket ("2(5)") matches a chunk label; one without ("12") matches the rule.
    """
    out = []
    for a in amendments:
        by_intent = intent is not None and intent in a.get("intents", [])
        by_rule = any(
            (label == aff or label.startswith(aff + "(")) if "(" in aff else rule == aff
            for aff in a.get("affects", [])
            for rule, label in cited
        )
        if by_intent or by_rule:
            out.append(AmendmentMatch(a, by_intent))
    return out


def amendment_warning(a: dict, lang: str) -> CardWarning:
    summary = a["summary_hi"] if lang == "hi" and a.get("summary_hi") else a["summary_en"]
    caveat = a["caveat_hi"] if lang == "hi" and a.get("caveat_hi") else a["caveat_en"]
    return CardWarning(type="amendment", id=a["id"], text=f"{a['date']}: {summary} {caveat}")


def dp_precedence_warning(lang: str) -> CardWarning:
    return CardWarning(
        type="dp_precedence", text=DP_PRECEDENCE_HI if lang == "hi" else DP_PRECEDENCE_WARNING
    )


def make_version(corpus_sha256: str, amendments: list[dict], lang: str) -> Version:
    return Version(
        label=VERSION_LABEL[lang],
        corpus_sha256=corpus_sha256,
        amendments=[a["id"] for a in amendments],
    )
