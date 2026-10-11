import hashlib
import json
import re

import pytest

from app.corpus.loader import HEADER_RE, load_corpus, normalize

COMMENT_RULES = {
    "2", "4", "12", "13", "16", "19", "21", "24", "26", "28", "55", "57", "60", "61", "81",
    "103", "105",
}  # fmt: skip


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_all_106_rules_load(corpus):
    ids = [r.rule for r in corpus.rules]
    assert len(ids) == 106
    assert ids[0] == "1" and ids[-1] == "105"
    assert "26-B" in ids
    assert len(set(ids)) == 106


def test_sha256_fingerprint(corpus):
    from app.corpus.loader import DEFAULT_SOURCE_DIR

    assert re.fullmatch(r"[0-9a-f]{64}", corpus.sha256)
    expected = hashlib.sha256((DEFAULT_SOURCE_DIR / "bhumi_vikas_rules.jsonl").read_bytes())
    assert corpus.sha256 == expected.hexdigest()
    manifest = json.loads((DEFAULT_SOURCE_DIR / "MANIFEST.json").read_text("utf-8"))
    assert corpus.sha256 == manifest["bhumi_vikas_rules.jsonl"]


def test_rule_105_page_end_clamped(corpus):
    assert corpus.n_pages == 108
    assert corpus.rule_by_id("105").page_end == 108
    assert all(1 <= r.page_start <= r.page_end <= 108 for r in corpus.rules)


def test_headers_stripped_but_kept_as_page_breaks(corpus):
    for r in corpus.rules:
        assert not any(HEADER_RE.match(ln) for ln in r.text.split("\n")), r.rule
        assert "M.P. Bhumi Vikas Rules, 2012" not in r.text, r.rule
    rule56 = corpus.rule_by_id("56")
    assert rule56.page_breaks and rule56.page_breaks[0][1] == 78
    assert rule56.page_at(0) == 77
    assert rule56.page_at(len(rule56.text) - 1) >= 78


def test_comments_cut_into_commentary(corpus):
    with_comments = {r.rule for r in corpus.rules if r.commentary}
    assert with_comments == COMMENT_RULES
    for r in corpus.rules:
        assert "COMMENTS" not in r.text, r.rule
        if r.commentary:
            assert r.commentary.lstrip().startswith("COMMENTS")
    # case-law text is gone from the rule text but kept as commentary
    assert "Kurban Hussain" not in corpus.rule_by_id("4").text
    assert "Kurban Hussain" in corpus.rule_by_id("4").commentary


def test_rule_text_after_comments_is_kept(corpus):
    # Rule 12's COMMENTS sit before the inserted Rule 12-A on the same page
    assert "instant/deemed approval" in corpus.rule_by_id("12").text
    # Rule 2's COMMENTS sit in the middle of the definitions
    assert '"occupancy or use group"' in corpus.rule_by_id("2").text


def test_parts_hidden_from_rule_91(corpus):
    assert corpus.rule_by_id("90").part is not None
    assert all(corpus.rule_by_id(str(n)).part is None for n in range(91, 106))


def test_normalize():
    assert normalize("  A’s “X” –  B\n\tC ") == 'a\'s "x" - b c'
