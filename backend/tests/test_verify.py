import pytest

from app.corpus.index import rule_key
from app.schemas import Citation
from app.verify import (
    check_answer,
    check_language,
    check_numbers,
    check_rule_mentions,
    numbers_in,
    parse_compose,
    parse_understand,
    rule_mentions,
    validate_params,
    verify_citations,
)
from tests.helpers import compose_json, understand_json

LIFT_QUOTE = "Provision for lifts shall be made for building more than 12.5 meters in height."


@pytest.fixture()
def lifts(index):
    return {c.id: c for c in index.resolve_pin("83")}


@pytest.fixture()
def known_keys(corpus):
    return {rule_key(c.rule) for c in corpus.chunks}


# --- V1 --------------------------------------------------------------------------------------


def test_v1_valid_and_invalid_outputs():
    ok, err = parse_understand(understand_json("lifts"))
    assert ok is not None and err is None and ok.intent == "lifts"
    bad, err = parse_understand({"in_scope": True, "intent": "make_coffee"})
    assert bad is None and err.startswith("V1")
    compose, err = parse_compose(compose_json("ok"))
    assert compose is not None
    extra = compose_json("ok") | {"surprise": 1}
    assert parse_compose(extra)[0] is None  # extra fields are rejected
    assert parse_compose(compose_json("word " * 91))[0] is None  # over 90 words
    assert parse_compose(compose_json("word " * 90))[0] is not None


def test_v1_error_does_not_leak_model_text():
    _, err = parse_compose({"status": "SECRET-TEXT", "answer": 1})
    assert "SECRET-TEXT" not in err


# --- V2 + V3 ---------------------------------------------------------------------------------


def test_v3_exact_quote_is_verified(corpus, lifts):
    check = verify_citations([("r83-0-0", LIFT_QUOTE)], lifts, corpus)
    assert not check.failures and len(check.verified) == 1
    c = check.verified[0]
    assert c.verified and c.page == 95 and c.rule == "83"
    assert c.pdf_en == "/pdf/rules-en.pdf#page=95" and c.pdf_hi == "/pdf/rules-hi.pdf#page=95"


def test_v3_whitespace_and_case_normalisation(corpus, lifts):
    messy = "  provision for  LIFTS shall be made\nfor building more than 12.5 meters in height. "
    assert len(verify_citations([("r83-0-0", messy)], lifts, corpus).verified) == 1
    curly = LIFT_QUOTE.replace("shall", "shall ")
    assert len(verify_citations([("r83-0-0", curly)], lifts, corpus).verified) == 1


def test_v3_fabricated_or_altered_quote_is_dropped(corpus, lifts):
    fabricated = "Lifts are required for every building above 15 meters in height."
    altered = LIFT_QUOTE.replace("12.5", "15.0")
    for q in (fabricated, altered, LIFT_QUOTE + " Always."):
        check = verify_citations([("r83-0-0", q)], lifts, corpus)
        assert not check.verified
        assert check.failures[0]["check"] == "V3"


def test_v3_length_limits(corpus, lifts):
    assert (
        verify_citations([("r83-0-0", "lifts shall")], lifts, corpus).failures[0]["check"] == "V3"
    )
    chunk = lifts["r83-0-0"]
    long_quote = chunk.text[:450] if len(chunk.text) >= 450 else chunk.text
    if len(" ".join(long_quote.split())) > 400:
        assert not verify_citations([("r83-0-0", long_quote)], lifts, corpus).verified


def test_v2_citation_must_name_a_candidate(corpus, lifts):
    check = verify_citations([("r56-1-0", "Up to 9.0 meters 3.0 meters")], lifts, corpus)
    assert check.failures == [{"chunk_id": "r56-1-0", "check": "V2", "reason": "not a candidate"}]
    assert not check.verified
    assert verify_citations([("r999-0-0", LIFT_QUOTE)], lifts, corpus).failures[0]["check"] == "V2"


def test_quote_from_the_wrong_chunk_is_dropped(corpus, index):
    both = {c.id: c for c in index.resolve_pin("83") + index.resolve_pin("56(1)")}
    # a real sentence, but not from the chunk it is attributed to
    check = verify_citations([("r56-1-0", LIFT_QUOTE)], both, corpus)
    assert not check.verified


def test_duplicate_citations_collapse(corpus, lifts):
    check = verify_citations(
        [("r83-0-0", LIFT_QUOTE), ("r83-0-0", LIFT_QUOTE.lower())], lifts, corpus
    )
    assert len(check.verified) == 1


# --- V5 numbers ------------------------------------------------------------------------------


def test_numbers_in_handles_commas_decimals_and_devanagari():
    assert numbers_in("Fee ₹3,000 and ₹1,25,000 for 12.5 m") == {3000.0, 125000.0, 12.5}
    assert numbers_in("नियम ५६ में ९.० मीटर") == {56.0, 9.0}
    assert numbers_in("no digits here") == set()


def test_v5_flags_a_number_not_in_any_source():
    assert check_numbers("Lifts above 12.5 m", ["building more than 12.5 meters"]) == []
    assert check_numbers("Lifts above 15 m", ["building more than 12.5 meters"]) == [15.0]
    assert check_numbers("fee is 0", ["Rs 3,000"]) == [0.0]
    assert (
        check_numbers("fee Rs 3,000", ["fee 3000.00"]) == []
    )  # same number, formatted differently


# --- V6 rule mentions ------------------------------------------------------------------------


def test_rule_mentions_parse(known_keys):
    assert rule_mentions("see Rule 56(1) and नियम ६१", known_keys) == ["56", "61"]
    assert rule_mentions("Rule 12-A applies", known_keys) == ["12a"]
    assert rule_mentions("rule 56 a plot of land", known_keys) == ["56"]  # "a" is an article
    assert rule_mentions("sub-rule (9) of rule 2", known_keys) == ["2"]


def test_v6_nonexistent_and_uncited_rules(known_keys):
    problems = check_rule_mentions("Rule 150 says so", {"83"}, known_keys)
    assert problems == ["V6: Rule 150 does not exist in the rules"]
    problems = check_rule_mentions("Rule 83 and Rule 56", {"83"}, known_keys)
    assert problems == ["V6: Rule 56 is mentioned but not cited"]
    assert check_rule_mentions("Rule 83", {"83"}, known_keys) == []
    assert check_rule_mentions("Rule 12-A", {"12a"}, known_keys) == []
    assert check_rule_mentions("Rule 12-A", {"12"}, known_keys)  # Rule 12 does not cite 12-A


# --- V7 language -----------------------------------------------------------------------------


def test_v7_language():
    assert check_language("Lifts are required above 12.5 m.", "en")
    assert not check_language("Lifts are required above 12.5 m.", "hi")
    assert check_language("12.5 मीटर से ऊँची इमारत में लिफ्ट आवश्यक है।", "hi")
    assert not check_language("12.5 मीटर से ऊँची इमारत में लिफ्ट आवश्यक है।", "en")
    assert check_language("A lift (लिफ्ट) is needed in Rule 83 buildings above 12.5 m", "en")


# --- V4..V7 together, which is what triggers a repair ----------------------------------------


def _citation(rule="83", label="83", quote=LIFT_QUOTE, page=95) -> Citation:
    return Citation(
        chunk_id="r83-0-0", rule=rule, label=label, title="Lifts", page=page, quote=quote,
        verified=True, pdf_en="/pdf/rules-en.pdf#page=95", pdf_hi="/pdf/rules-hi.pdf#page=95",
    )  # fmt: skip


def test_check_answer_passes_a_clean_answer(known_keys):
    r = check_answer(
        answer="Lifts are needed for a building above 12.5 m (Rule 83).",
        lang="en",
        citations=[_citation()],
        source_texts=["Lifts in a building over 15 m?"],
        known_keys=known_keys,
    )
    assert r.ok, r.problems


@pytest.mark.parametrize(
    "answer,citations,code",
    [
        ("Lifts are needed above 12.5 m.", [], "V4"),  # no verified citation
        ("Lifts are needed above 15 m.", [_citation()], "V5"),  # 15 is in the question, not here
        ("Lifts are needed above 12.5 m (Rule 150).", [_citation()], "V6"),
        ("Lifts are needed above 12.5 m (Rule 56).", [_citation()], "V6"),
        ("लिफ्ट 12.5 मीटर से ऊपर आवश्यक है (नियम 83)।", [_citation()], None),
    ],
)
def test_check_answer_triggers(known_keys, answer, citations, code):
    r = check_answer(
        answer=answer, lang="en", citations=citations, source_texts=[], known_keys=known_keys
    )
    if code is None:
        assert any(p.startswith("V7") for p in r.problems)  # Hindi text for an English question
    else:
        assert any(p.startswith(code) for p in r.problems), r.problems
    assert not r.ok


def test_question_numbers_are_allowed_sources(known_keys):
    r = check_answer(
        answer="A 15 m building needs a lift because the limit is 12.5 m (Rule 83).",
        lang="en",
        citations=[_citation()],
        source_texts=["Lifts in a building over 15 m?"],
        known_keys=known_keys,
    )
    assert r.ok, r.problems


# --- V8 --------------------------------------------------------------------------------------


def test_v8_keeps_only_numbers_that_occur_in_the_question():
    u, _ = parse_understand(understand_json(plot_area=200, plot_area_unit="sqm", road_width_m=12))
    params, dropped = validate_params(u.params, "my plot is 200 sq m on a 9 m road")
    assert params["plot_area"] == 200.0 and params["plot_area_unit"] == "sqm"
    assert params["road_width_m"] is None and dropped == ["road_width_m"]


def test_v8_devanagari_and_comma_numbers():
    u, _ = parse_understand(understand_json(plot_area=1500, plot_area_unit="sqft", road_width_m=9))
    params, dropped = validate_params(u.params, "1,500 sq ft ka plot, 9 m sadak")
    assert params["plot_area"] == 1500.0 and params["road_width_m"] == 9.0 and not dropped


def test_v8_unknowns_become_none_and_dropped_area_loses_its_unit():
    u, _ = parse_understand(understand_json(plot_area=77, plot_area_unit="sqm", use="unknown"))
    params, dropped = validate_params(u.params, "what is the front gap")
    assert params["plot_area"] is None and params["plot_area_unit"] is None
    assert params["use"] is None and params["building_type"] is None
    assert dropped == ["plot_area"]
