"""Load the rules JSONL and the page file (SPEC §8 steps 1, 2, 5, 6).

- Running headers are removed from the display text; each one is recorded as a page break.
- ``COMMENTS`` blocks (the compiler's case-law notes) are cut into ``commentary`` and never indexed.
- Rule 105's ``page_end`` (109) is clamped to the number of pages in the PDF (108).
- Every path resolves from ``__file__``, never from the working directory.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = BACKEND_DIR / "data" / "source"
RULES_FILE = "bhumi_vikas_rules.jsonl"
PAGES_FILE = "bhumi_vikas_rules_fulltext_by_page.txt"

HEADER_RE = re.compile(
    r"^\s*Rules?\s+[\w().\-–&]+(\s*-\s*[\w()]+)?\s{2,}M\.P\. Bhumi Vikas Rules, 2012\s+\d+\s*$"
)
PAGE_MARK_RE = re.compile(r"^===== PDF page (\d+) =====\s*$", re.M)
COMMENTS_LINE = "COMMENTS"

_PUNCT_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
        "​": "",
    }
)


def normalize(text: str) -> str:
    """Whitespace-collapsed, lowercase, punctuation-unified text for substring matching."""
    return " ".join(text.translate(_PUNCT_MAP).lower().split())


@dataclass
class Rule:
    rule: str
    title: str
    part: str | None
    page_start: int
    page_end: int
    text: str  # display text: headers stripped, COMMENTS cut out
    commentary: str  # the cut COMMENTS blocks; never indexed
    # (offset into ``text``, page that starts there), ascending
    page_breaks: list[tuple[int, int]] = field(default_factory=list)

    def page_at(self, offset: int) -> int:
        page = self.page_start
        for off, pg in self.page_breaks:
            if off > offset:
                break
            page = pg
        return min(max(page, self.page_start), self.page_end)


@dataclass
class Corpus:
    rules: list[Rule]
    sha256: str
    pages: dict[int, str]  # PDF page -> headers-stripped, normalised text
    chunks: list = field(default_factory=list)  # list[Chunk], filled by chunker.build_chunks

    @property
    def n_pages(self) -> int:
        return max(self.pages)

    def rule_by_id(self, rule_id: str) -> Rule | None:
        return next((r for r in self.rules if r.rule == rule_id), None)


def clean_rule_text(raw: str) -> tuple[str, str, list[tuple[int, int]]]:
    """Return (display_text, commentary, page_breaks) for one rule's raw text."""
    out: list[str] = []
    out_len = 0
    comments: list[str] = []
    breaks: list[tuple[int, int]] = []
    in_comments = False
    blank_run = 0

    for line in raw.split("\n"):
        if HEADER_RE.match(line):
            breaks.append((out_len, int(line.split()[-1])))
            continue
        if in_comments:
            if line.strip():
                comments.append(line)
                continue
            in_comments = False  # the blank line ends the block
        elif line.strip() == COMMENTS_LINE:
            in_comments = True
            comments.append(line)
            continue

        if line.strip():
            blank_run = 0
        else:
            blank_run += 1
            if blank_run > 1:
                continue
        out.append(line)
        out_len += len(line) + 1  # +1 for the joining newline

    text = "\n".join(out).strip("\n")
    # strip("\n") may have removed leading characters; page breaks keep their relative order
    # and are only used with page_at(), so a small shift at the very start is harmless.
    return text, "\n".join(comments), breaks


def load_pages(source_dir: Path) -> dict[int, str]:
    raw = (source_dir / PAGES_FILE).read_text(encoding="utf-8")
    parts = PAGE_MARK_RE.split(raw)
    pages: dict[int, str] = {}
    for i in range(1, len(parts), 2):
        lines = [ln for ln in parts[i + 1].split("\n") if not HEADER_RE.match(ln)]
        pages[int(parts[i])] = normalize("\n".join(lines))
    return pages


def _part_for_display(rule_id: str, part: str | None) -> str | None:
    # `part` labels are corrupt from rule 91 onwards (SPEC §4.3); show the title instead.
    m = re.match(r"\d+", rule_id)
    if m and int(m.group()) >= 91:
        return None
    return part


def load_corpus(source_dir: Path | None = None) -> Corpus:
    source_dir = Path(source_dir) if source_dir else DEFAULT_SOURCE_DIR
    rules_path = source_dir / RULES_FILE
    sha = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    pages = load_pages(source_dir)
    last_page = max(pages)

    rules: list[Rule] = []
    for line in rules_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        page_end = d["page_end"]
        if page_end > last_page:
            log.warning("rule %s page_end %s clamped to %s", d["rule"], page_end, last_page)
            page_end = last_page
        text, commentary, breaks = clean_rule_text(d["text"])
        rules.append(
            Rule(
                rule=d["rule"],
                title=d["title"],
                part=_part_for_display(d["rule"], d.get("part")),
                page_start=d["page_start"],
                page_end=page_end,
                text=text,
                commentary=commentary,
                page_breaks=breaks,
            )
        )
    return Corpus(rules=rules, sha256=sha, pages=pages)
