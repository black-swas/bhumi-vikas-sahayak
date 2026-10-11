import pytest

from app import templates
from app.amendments import load_amendments, matching_amendments
from app.config import get_settings
from app.i18n import (
    detect_lang,
    devanagari_ratio,
    normalize_question,
    normalize_units,
    redact_pii,
    to_ascii_digits,
)
from app.offline import extract_params, offline_understand


def test_devanagari_digits():
    assert to_ascii_digits("प्लॉट २००, सड़क ९.५ मीटर") == "प्लॉट 200, सड़क 9.5 मीटर"


def test_language_detection():
    assert detect_lang("मेरा प्लॉट 200 वर्ग मीटर का है") == "hi"
    assert detect_lang("My plot is 200 sq m") == "en"
    assert (
        detect_lang("mera plot 150 sq m hai, peeche kitni jagah chhodni hai?") == "en"
    )  # Hinglish
    assert detect_lang("plot 200 sq m सड़क 9 m road front gap kitna") == "en"  # mixed
    assert detect_lang("200 9 ?") == "en" and devanagari_ratio("123") == 0.0


@pytest.mark.parametrize(
    "src,expected",
    [
        ("200 वर्ग मीटर", "200 sq m"),
        ("1500 वर्ग फुट", "1500 sq ft"),
        ("200 वर्ग फीट", "200 sq ft"),
        ("200 गज", "200 gaj"),
        ("9 मीटर सड़क", "9 m सड़क"),
        ("30 फीट", "30 ft"),
        ("2 एकड़", "2 acre"),
        ("1 हेक्टेयर", "1 ha"),
    ],
)
def test_unit_words(src, expected):
    assert normalize_units(src) == expected


def test_pii_is_redacted():
    text, n = redact_pii(
        "call 9876543210, +91 98765 43210? mail me@example.co.in id 1234 5678 9012"
    )
    assert n == 4
    for secret in ("9876543210", "me@example.co.in", "5678", "98765 43210"):
        assert secret not in text


def test_pii_redaction_leaves_ordinary_numbers_alone():
    for s in (
        "plot 200 sq m on 9 m road",
        "area 2500.5 sq m",
        "fee 12500",
        "built up 1000000 sq m",
    ):
        assert redact_pii(s) == (s, 0)


def test_normalize_question_end_to_end():
    nq = normalize_question("  मेरा प्लॉट २०० वर्ग मीटर, फोन 9876543210  ")
    assert nq.lang == "hi" and nq.redactions == 1
    assert "200 sq m" in nq.text and "9876543210" not in nq.text and "[REDACTED]" in nq.text
    assert "9876543210" not in nq.original  # what is echoed back is redacted too
    assert (
        normalize_question("x" * 600).truncated and len(normalize_question("x" * 600).text) == 500
    )
    assert normalize_question("front gap?", lang="hi").lang == "hi"  # the clerk's toggle wins


# --- offline understanding -------------------------------------------------------------------


def test_regex_params():
    p, e = extract_params("My plot is 200 sq m on a 9 m road, 7.5 m tall, frontage 10 m, shop")
    assert (p["plot_area"], p["plot_area_unit"], p["road_width_m"]) == (200.0, "sqm", 9.0)
    assert p["height_m"] == 7.5 and p["frontage_m"] == 10.0 and p["use"] == "commercial"
    p, _ = extract_params("1,500 sq ft plot".replace(",", ""))
    assert (p["plot_area"], p["plot_area_unit"]) == (1500.0, "sqft")
    p, _ = extract_params("built up 120 sq m, plot 200 sq m")
    assert p["plot_area"] == 200.0 and p["built_up_area_sqm"] == 120.0
    p, _ = extract_params("semi-detached house, low voltage line")
    assert (p["building_type"], p["voltage"], p["use"]) == (
        "semi_detached",
        "low_medium",
        "residential",
    )
    _, e = extract_params("permission granted in 2023")
    assert e["grant_year"] == 2023
    _, e = extract_params("sanctioned on 15/06/2023")
    assert e["grant_date"] == (2023, 6, 15)


def test_offline_intents():
    def intent(q):
        return offline_understand(normalize_question(q)).intent

    assert intent("front gap and fee for my plot") == "plot_norms"
    assert intent("What is the minimum rear open space for a 150 sq m plot?") == "rear_open_space"
    assert intent("Balcony distance from a low-voltage electric line?") == "electric_line"
    assert intent("How do I pay property tax online?") == "out_of_scope"
    assert intent("Market rate of land on Kolar Road?") == "out_of_scope"
    assert not offline_understand(normalize_question("property tax")).in_scope


# --- templates and amendments ----------------------------------------------------------------


def test_template_messages_exist_in_both_languages():
    t = templates._templates()
    for key, msg in t["messages"].items():
        if key == "missing_labels":
            for label in msg.values():
                assert set(label) == {"en", "hi"}
        else:
            assert set(msg) == {"en", "hi"}, key
    for entries in t["sections"].values():
        for entry in entries:
            assert entry["en"] and entry["hi"]
    assert templates.need_more_info(["road_width_m"], "hi") == "अधिक जानकारी चाहिए: सड़क की चौड़ाई।"


def test_amendment_matching_by_label_rule_and_intent():
    am = load_amendments()
    assert matching_amendments(am, "development_permission_need", [])
    assert matching_amendments(am, "lifts", [("2", "2(5)")])  # Rule 2(5) touched
    assert matching_amendments(am, "lifts", [("12", "12(1)")])  # Rule 12 listed in affects
    assert not matching_amendments(am, "lifts", [("2", "2(38)"), ("83", "83")])
    assert not matching_amendments(am, "fee", [("56", "56(1)")])
    a = am[0]
    assert a["source_type"] == "secondary_summary" and a["verbatim_available"] is False
    assert "Gazette" in a["caveat_en"] and a["summary_hi_reviewed"] is False


def test_settings_from_env_never_hold_secrets_in_the_repr():
    s = get_settings({"CEREBRAS_API_KEY": "sk-secret", "ANTHROPIC_API_KEY": "sk-secret2"})
    assert s.has_cerebras_key and s.has_anthropic_key
    assert "sk-secret" not in repr(s)
    assert get_settings({"DEMO_REPLAY": "1"}).mode == "replay"
    assert get_settings({"LLM_PROVIDER": "offline"}).mode == "offline"
    assert get_settings({}).anthropic_model == "claude-haiku-5-5"
