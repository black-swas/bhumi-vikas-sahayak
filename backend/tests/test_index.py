import pytest

from app.corpus import build_corpus
from app.corpus.index import HIGH_RISE_M, INTENT_PINS, guess_intent, stem, tokenize


@pytest.fixture(scope="module")
def ix():
    return build_corpus()[1]


def ids(chunks):
    return [c.id for c in chunks]


def test_front_open_space_query_ranks_56_1_in_top_3(ix):
    top = [c.id for c, _ in ix.rank("front open space street width", k=3)]
    assert "r56-1-0" in top
    assert len(top) == 3


def test_residential_far_finds_rule_61_despite_resdential_typo(ix):
    top = ix.rank("residential FAR", k=3)
    assert top[0][0].rule == "61"
    # the typo "Resdential" in Table 8 is reached through the glossary
    assert "resdential" in ix.search("residential FAR").query_tokens
    assert any(c.rule == "61" for c in ix.search("residential FAR").candidates)


def test_direct_lookup_hindi_rule(ix):
    chunks = ix.direct_lookup("नियम 56")
    assert chunks and {c.rule for c in chunks} == {"56"}
    assert "r56-1-0" in ids(chunks)
    assert ids(ix.direct_lookup("नियम ५६(१)")) == ["r56-1-0"]  # Devanagari digits


def test_direct_lookup_rule_12a(ix):
    assert ids(ix.direct_lookup("Rule 12-A")) == ["r12-a-0"]
    assert ids(ix.direct_lookup("what is rule 12A about")) == ["r12-a-0"]
    assert ids(ix.search("Rule 12-A").candidates)[0] == "r12-a-0"


def test_direct_lookup_patterns(ix):
    assert ids(ix.direct_lookup("Rule 56(1)")) == ["r56-1-0"]
    assert ids(ix.direct_lookup("what does 56(2) say")) == ["r56-2-0"]
    assert ids(ix.direct_lookup("rule 2(38)")) == ["r2-38-0"]
    assert {c.rule for c in ix.direct_lookup("Rule 26-B")} == {"26-B"}
    assert ids(ix.direct_lookup("rule 17(a)"))[0].startswith("r17-")  # lettered clause: whole rule
    # an article "a" after the number is not an inserted-rule letter
    assert {c.rule for c in ix.direct_lookup("rule 56 a plot of land")} == {"56"}
    assert ix.direct_lookup("no rule number here, 9 m road") == []
    assert ix.direct_lookup("rule 150") == []  # does not exist


def test_search_returns_at_most_six_deduplicated_without_pins(ix):
    res = ix.search("front open space street width")
    assert len(res.candidates) == 6
    assert len(set(ids(res.candidates))) == 6
    big = ix.search("नियम 56")
    assert len(big.candidates) == 6 and ids(big.candidates)[:2] == ["r56-0-0", "r56-1-0"]


def test_intent_pins_plot_norms(ix):
    res = ix.search("200 sq m plot 9 m road", intent="plot_norms")
    got = set(ids(res.candidates))
    assert {"r56-1-0", "r56-2-0", "r56-3-0", "r53-1-0", "r61-0-0", "r21-2-0"} <= got
    assert all(c in res.candidates for c in res.pins)


@pytest.mark.parametrize(
    "intent,expected",
    [
        ("front_open_space", {"r56-1-0"}),
        ("rear_open_space", {"r56-2-0"}),
        ("electric_line", {"r52-1-0"}),
        ("dp_vs_rules", {"r103-0-0"}),
        ("instant_approval", {"r12-a-0", "r23-1-0"}),
        ("farm_house", {"r17-0-0"}),
        ("lifts", {"r83-0-0"}),
        ("deemed_permission", {"r28-0-0"}),
        ("development_permission_need", {"r2-5-0", "r12-1-0"}),
        ("plan_signing", {"r18-0-0", "r26-b-1-0"}),
    ],
)
def test_pins_resolve(ix, intent, expected):
    assert expected <= set(ids(ix.pins_for(intent)))


def test_every_intent_pin_resolves_to_chunks(ix):
    for intent, refs in INTENT_PINS.items():
        for ref in refs:
            assert ix.resolve_pin(ref), (intent, ref)
    assert ix.pins_for("out_of_scope") == [] and ix.pins_for("general_lookup") == []
    assert ix.pins_for(None) == []


def test_front_open_space_above_12_5_m_pins_rule_42(ix):
    assert ids(ix.pins_for("front_open_space", height_m=HIGH_RISE_M + 5)) == ["r42-1-0"]
    assert ids(ix.pins_for("front_open_space", height_m=9)) == ["r56-1-0"]


def test_glossary_expansion(ix):
    assert {"open", "spac"} <= set(ix.search("what setback for my plot").query_tokens)
    assert {"open", "spac"} <= set(ix.search("how much gap at the front").query_tokens)
    assert "fee" in ix.search("शुल्क कितना").query_tokens
    floors = ix.search("how many floors can I build").query_tokens
    assert {"floor", "area", "ratio", "height"} <= set(floors)
    hindi = ix.search("आगे कितनी जगह छोड़नी होगी").query_tokens
    assert {"open", "spac", "front"} <= set(hindi)
    assert {"floor", "area", "ratio"} <= set(ix.search("कितनी मंजिल बन सकती है").query_tokens)


def test_hindi_question_retrieves_front_open_space(ix):
    res = ix.search("मेरा प्लॉट 200 वर्ग मीटर, 9 मीटर सड़क: आगे कितनी जगह?")
    assert "r56-1-0" in ids(res.candidates)[:3]


def test_guess_intent():
    assert guess_intent("Balcony distance from a low voltage electric line?") == "electric_line"
    assert guess_intent("front gap and fee for my plot") == "plot_norms"
    assert guess_intent("lifts needed above which height") == "lifts"
    assert guess_intent("what is the weather") is None


def test_tokenizer():
    assert tokenize("Height up to 12.5 meters") == ["height", "up", "12.5", "meter"]
    assert tokenize("Rule 56(1)(a)") == ["rule", "56", "1"]
    assert tokenize("शुल्क कितना है") == ["शुल्क"]
    assert tokenize("१२.५ मीटर") == ["12.5", "मीटर"]
    assert stem("spaces") == stem("space") == "spac"
    assert stem("approved") == stem("approve") == stem("approving")
    assert stem("fees") == "fee"


def test_commentary_never_retrieved(ix):
    res = ix.search("Narmada Tax double taxation CREDAI", k=6)
    assert all("narmada" not in c.norm for c in res.candidates)
    res = ix.search("Kurban Hussain Indore Municipal Corporation")
    assert all("kurban" not in c.norm for c in res.candidates)
