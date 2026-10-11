"""Split rules into citable chunks with exact PDF pages (SPEC §8 steps 3-5).

Chunk ID: ``r{rule}-{sub}-{n}``: the rule slug, the sub-rule (``0`` = text before the first
sub-rule, ``a`` = an inserted rule), and the part number when a long chunk is split.
"""

import re
from dataclasses import dataclass

from .loader import Corpus, Rule, normalize

MAX_CHARS = 1800
MAX_TABLE_CHARS = 3000
MIN_PART = 300
MAX_SUB_INDENT = 9  # top-level "(n)" starts sit at indent 0-8; deeper ones are table rows
SNIPPET = 60

# Sub-rule starts: "(3) text" at the start of a line. Rule 2 numbers its definitions "(1)"-"(81)"
# and some are written "[(30)" or "1[(40)".
_SUB_START = re.compile(r"^(?P<indent> *)(?:\d?\[)?\((?P<n>\d+)\)[ \t]+(?!\()\S", re.M)
_TABLE_LINE = re.compile(r"\S {4,}\S")
_QUOTED_TERM = re.compile(r"[\"“]([^\"”\n]{2,80})[\"”]")

# Rules inserted inside a parent rule's text (SPEC §4.3): parent -> [(canonical rule, label, regex)]
INSERTED = {
    "12": [("12-A", "12-A", r"^[ \t]*\[?[ \t]*12 ?A\.")],
    "17": [("17-a", "17-a", r"^[ \t]*\[?[ \t]*17-a\.")],
    "25": [("25-A", "25(A)", r"^[ \t]*\[?[ \t]*25\(A\)\.")],
    "26": [("26-A", "26-A", r"^[ \t]*\[?[ \t]*26\.A\.")],
    "42": [("42-A", "42-A", r"^[ \t]*\[?[ \t]*42A\.")],
    "93": [("93-a", "93(a)", r'^[ \t]*\[?[ \t]*"?93\(a\)')],
}


@dataclass(frozen=True)
class Chunk:
    id: str
    rule: str  # "56", "26-B", or an inserted rule such as "12-A"
    label: str  # display label: "56", "56(1)", "2(38)", "12-A"
    title: str
    parent: str | None  # parent rule for inserted rules
    sub: str  # "0" preamble, "1".."n", or "a" for an inserted rule
    pages: tuple[int, ...]
    text: str  # display text
    norm: str  # normalised text for substring matching and V3


def slug(rule: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", rule.lower()).strip("-")


def _is_table(text: str) -> bool:
    return sum(1 for ln in text.split("\n") if _TABLE_LINE.search(ln)) >= 3


def _split_long(text: str) -> list[tuple[int, str]]:
    """Pack paragraphs (split at blank lines) into parts under the limit: (offset, part)."""
    limit = MAX_TABLE_CHARS if _is_table(text) else MAX_CHARS
    if len(text) <= limit:
        return [(0, text)]
    paras: list[tuple[int, int]] = []  # (start, end) of each paragraph
    pos = 0
    for m in re.finditer(r"\n[ \t]*\n", text):
        paras.append((pos, m.start()))
        pos = m.end()
    paras.append((pos, len(text)))

    parts: list[tuple[int, str]] = []
    cur_start, cur_end = paras[0]
    for start, end in paras[1:]:
        # close the current part only when it is big enough to stand alone
        if end - cur_start > limit and cur_end - cur_start >= MIN_PART:
            parts.append((cur_start, text[cur_start:cur_end]))
            cur_start = start
        cur_end = end
    tail = text[cur_start:cur_end]
    if parts and len(tail) < MIN_PART:  # a tiny final part (often a footnote) joins the last one
        off = parts[-1][0]
        parts[-1] = (off, text[off:cur_end])
    else:
        parts.append((cur_start, tail))
    return [(o, p.strip("\n")) for o, p in parts if p.strip()]


def _find_sub_starts(text: str, is_definitions: bool) -> list[tuple[int, str]]:
    """Offsets of top-level sub-rule starts, with their numbers, in order.

    Sub-rule (1) often sits on the heading line itself ("23. Duration.- (1) In case ..."), so
    the first line is searched for an inline "(1)" too.
    """
    candidates: list[tuple[int, int, int]] = []  # (offset, number, indent)
    first_line_end = text.find("\n") if "\n" in text else len(text)
    inline = re.search(r"(?<=[-\s\[])\(1\)", text[:first_line_end])
    if inline:
        candidates.append((inline.start(), 1, 0))
    for m in _SUB_START.finditer(text):
        candidates.append((m.start(), int(m.group("n")), len(m.group("indent"))))

    found: list[tuple[int, str]] = []
    prev = 0
    for off, n, indent in sorted(candidates):
        if found and off <= found[-1][0]:
            continue
        if not is_definitions and indent > MAX_SUB_INDENT:
            continue  # a numbered row inside a table or a nested list
        if not (n > prev if is_definitions else n == prev + 1):
            continue
        found.append((off, str(n)))
        prev = n
    return found


def _split_inserted(rule: Rule) -> tuple[str, list[tuple[str, str, int, str]]]:
    """Cut inserted rules out of a parent. Returns (parent text, [(rule, label, offset, text)])."""
    specs = INSERTED.get(rule.rule)
    if not specs:
        return rule.text, []
    text = rule.text
    cuts: list[tuple[int, str, str]] = []
    for canon, label, pattern in specs:
        m = re.search(pattern, text, re.M)
        if m:
            cuts.append((m.start(), canon, label))
    cuts.sort()
    if not cuts:
        return text, []
    parent = text[: cuts[0][0]]
    # drop the lone footnote-marker line ("1") that precedes an inserted rule
    parent = re.sub(r"\n[ \t]*\d[ \t]*\n?\Z", "\n", parent).rstrip("\n")
    inserted = []
    for i, (off, canon, label) in enumerate(cuts):
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(text)
        inserted.append((canon, label, off, text[off:end].strip("\n")))
    return parent, inserted


def _page_by_page_file(corpus: Corpus, norm: str, lo: int, hi: int, start: int) -> int | None:
    for pg in range(max(lo, start), hi + 1):
        if norm in corpus.pages.get(pg, ""):
            return pg
    return None


def _map_pages(corpus: Corpus, rule: Rule, text: str, offset: int, norm: str) -> tuple[int, ...]:
    """Pages a chunk spans: the page file first (SPEC §8.5), the header breaks as fallback."""
    lo, hi = rule.page_start, rule.page_end
    first = _page_by_page_file(corpus, norm[:SNIPPET], lo, hi, lo)
    last = None
    if first is not None:
        last = _page_by_page_file(corpus, norm[-SNIPPET:], lo, hi, first)
    if first is None:
        first = rule.page_at(offset)
    if last is None:
        last = max(first, rule.page_at(offset + max(len(text) - 1, 0)))
    return tuple(range(first, max(first, last) + 1))


def _definition_title(rule: Rule, seg_text: str) -> str:
    m = _QUOTED_TERM.search(seg_text.split("\n", 1)[0] + " " + seg_text[:200])
    return f"{rule.title}: {m.group(1).strip()}" if m else rule.title


def _emit(
    corpus: Corpus,
    rule: Rule,
    *,
    rule_id: str,
    label: str,
    title: str,
    parent: str | None,
    sub: str,
    seg_text: str,
    seg_offset: int,
    out: list[Chunk],
) -> None:
    for n, (part_off, part) in enumerate(_split_long(seg_text)):
        norm = normalize(part)
        if not norm:
            continue
        out.append(
            Chunk(
                id=f"r{slug(rule_id)}-{n}" if sub == "a" else f"r{slug(rule_id)}-{sub}-{n}",
                rule=rule_id,
                label=label,
                title=title,
                parent=parent,
                sub=sub,
                pages=_map_pages(corpus, rule, part, seg_offset + part_off, norm),
                text=part,
                norm=norm,
            )
        )


def chunk_rule(corpus: Corpus, rule: Rule) -> list[Chunk]:
    out: list[Chunk] = []
    parent_text, inserted = _split_inserted(rule)
    is_defs = rule.rule == "2"
    starts = _find_sub_starts(parent_text, is_defs)

    bounds = [0] + [s for s, _ in starts] + [len(parent_text)]
    # preamble
    pre = parent_text[: bounds[1]].strip("\n")
    if pre.strip():
        _emit(
            corpus, rule, rule_id=rule.rule, label=rule.rule, title=rule.title, parent=None,
            sub="0", seg_text=pre, seg_offset=0, out=out,
        )  # fmt: skip
    for i, (off, num) in enumerate(starts):
        seg = parent_text[off : bounds[i + 2]].strip("\n")
        title = _definition_title(rule, seg) if is_defs else rule.title
        _emit(
            corpus, rule, rule_id=rule.rule, label=f"{rule.rule}({num})", title=title,
            parent=None, sub=num, seg_text=seg, seg_offset=off, out=out,
        )  # fmt: skip
    for canon, label, off, seg in inserted:
        _emit(
            corpus, rule, rule_id=canon, label=label,
            title=f"{rule.title} (inserted rule {label})", parent=rule.rule,
            sub="a", seg_text=seg, seg_offset=off, out=out,
        )  # fmt: skip
    return out


def page_of_quote(corpus: Corpus, chunk: Chunk, quote: str) -> int:
    """PDF page where a (normalised) quote occurs, searched within the chunk's pages."""
    needle = normalize(quote)
    for pg in chunk.pages:
        if needle in corpus.pages.get(pg, ""):
            return pg
    return chunk.pages[0]


def build_chunks(corpus: Corpus) -> list[Chunk]:
    chunks: list[Chunk] = []
    for rule in corpus.rules:
        chunks.extend(chunk_rule(corpus, rule))
    ids = [c.id for c in chunks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate chunk ids: {sorted(dupes)}")
    corpus.chunks = chunks
    return chunks
