import re

import pytest

from app.corpus import build_corpus
from app.corpus.chunker import page_of_quote
from app.corpus.loader import normalize

ID_RE = re.compile(r"r\d+(?:-[a-z])?(?:-\d+)?-\d+")
INSERTED = {
    "12-A": ("12", "r12-a-0"),
    "17-a": ("17", "r17-a-0"),
    "25-A": ("25", "r25-a-0"),
    "26-A": ("26", "r26-a-0"),
    "42-A": ("42", "r42-a-0"),
    "93-a": ("93", "r93-a-0"),
}


@pytest.fixture(scope="module")
def built():
    corpus, _ = build_corpus()
    return corpus, {c.id: c for c in corpus.chunks}


def test_ids_unique_and_well_formed(built):
    corpus, by_id = built
    assert len(by_id) == len(corpus.chunks) > 300
    for cid in by_id:
        assert ID_RE.fullmatch(cid), cid
    for cid in ("r56-1-0", "r56-2-0", "r56-3-0", "r2-38-0", "r12-a-0", "r17-a-0", "r26-b-1-0"):
        assert cid in by_id


def test_no_comments_in_chunks(built):
    corpus, _ = built
    for c in corpus.chunks:
        assert "COMMENTS" not in c.text and "comments" not in c.norm.split(), c.id
    commentary = " ".join(r.commentary for r in corpus.rules)
    assert "Kurban Hussain" in commentary
    assert not any("kurban hussain" in c.norm for c in corpus.chunks)
    assert not any("narmada tax" in c.norm for c in corpus.chunks)


def test_sub_rule_chunks(built):
    _, by_id = built
    assert by_id["r56-1-0"].label == "56(1)"
    assert by_id["r56-1-0"].text.lstrip().startswith("(1) Front open spaces")
    assert by_id["r56-2-0"].text.lstrip().startswith("(2) Rear Open Space")
    assert by_id["r56-3-0"].text.lstrip().startswith("(3) Side open space")
    assert by_id["r56-0-0"].label == "56"
    assert by_id["r56-1-0"].title == "Residential Buildings"
    # "(1)" written on the heading line still becomes its own chunk
    assert by_id["r23-1-0"].label == "23(1)"
    assert by_id["r42-1-0"].label == "42(1)" and "table no 4" in by_id["r42-1-0"].norm


def test_rule_2_definitions(built):
    corpus, by_id = built
    defs = [c for c in corpus.chunks if c.rule == "2" and c.sub != "0"]
    assert len({c.sub for c in defs}) >= 75
    hr = by_id["r2-38-0"]
    assert hr.label == "2(38)"
    assert "high rise building" in hr.title.lower()
    assert hr.pages == (8,)
    assert "far" in by_id["r2-30-0"].title.lower() or "floor area ratio" in by_id["r2-30-0"].norm


@pytest.mark.parametrize("rule", sorted(INSERTED))
def test_inserted_rules_split_out(built, rule):
    corpus, by_id = built
    parent, cid = INSERTED[rule]
    c = by_id[cid]
    assert c.rule == rule and c.parent == parent
    assert c.sub == "a"
    parent_text = " ".join(x.norm for x in corpus.chunks if x.rule == parent)
    # the inserted text appears once: in its own chunk, not in the parent's chunks
    snippet = c.norm[:50]
    assert snippet not in parent_text


def test_rule_12a_content_and_page(built):
    _, by_id = built
    c = by_id["r12-a-0"]
    assert "186 sqm" in c.text
    assert c.pages == (21,)
    assert "instant/deemed approval" in c.norm
    # footnote after the inserted rule stays with it; the parent keeps no 12-A text
    assert "186 sqm" not in " ".join(x.text for x in by_id.values() if x.rule == "12")


def test_rule_17_farm_house_separate_from_17a(built):
    _, by_id = built
    assert "minimum size of the plot shall be 0.40 hectare" in by_id["r17-0-0"].norm
    assert "agricultural tourist" not in by_id["r17-0-0"].norm
    assert "agricultural tourist" in by_id["r17-a-0"].norm


def test_26b_is_its_own_rule(built):
    _, by_id = built
    assert by_id["r26-b-0-0"].rule == "26-B"
    assert by_id["r26-b-1-0"].label == "26-B(1)"


def test_norm_is_normalised_and_matches_text(built):
    corpus, _ = built
    for c in corpus.chunks:
        assert c.norm == normalize(c.text), c.id
        assert "  " not in c.norm and c.norm == c.norm.lower()


def test_page_bounds(built):
    corpus, _ = built
    for c in corpus.chunks:
        rule = corpus.rule_by_id(c.parent or c.rule)
        assert c.pages == tuple(sorted(c.pages)) and c.pages
        assert rule.page_start <= c.pages[0], c.id
        assert c.pages[-1] <= min(rule.page_end, 108), c.id


def test_key_page_numbers(built):
    _, by_id = built
    assert by_id["r56-1-0"].pages == (77,)
    assert by_id["r56-2-0"].pages == (78,)
    assert by_id["r56-3-0"].pages == (78,)
    assert by_id["r53-1-0"].pages == (70,)
    assert by_id["r61-0-0"].pages == (83,)
    assert by_id["r21-2-0"].pages == (35,)
    assert 36 in by_id["r21-3-1"].pages
    assert by_id["r103-0-0"].pages == (107,)
    assert by_id["r83-0-0"].pages == (95,)
    assert by_id["r52-1-0"].pages == (69,)


def test_chunk_pages_come_from_page_file(built):
    corpus, _ = built
    misses = [c.id for c in corpus.chunks if c.norm[:60] not in corpus.pages[c.pages[0]]]
    assert len(misses) <= 3, misses


def test_page_of_quote(built):
    corpus, by_id = built
    assert page_of_quote(corpus, by_id["r56-1-0"], "Up to 9.0 meters 3.0 meters") == 77
    assert page_of_quote(corpus, by_id["r56-2-0"], "Above 150 and up to 225.00 2.50") == 78
    # a quote that sits on a later page of a multi-page chunk maps to that page
    ch = by_id["r56-6-0"]
    assert page_of_quote(corpus, ch, ch.norm[-40:]) == ch.pages[-1]


def test_chunk_sizes_bounded(built):
    corpus, _ = built
    assert all(len(c.text) <= 4200 for c in corpus.chunks)
    assert sum(1 for c in corpus.chunks if len(c.text) > 3000) <= 5
