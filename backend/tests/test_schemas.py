import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import AnswerCard, AskRequest, ComposeOutput, UnderstandOutput

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_FILES = sorted(FIXTURES.glob("answer_*.json"))


def test_all_status_fixtures_present():
    assert [p.stem for p in FIXTURE_FILES] == [
        "answer_amendment_q11",
        "answer_answered",
        "answer_error",
        "answer_flagship",
        "answer_hindi_q14",
        "answer_needs_review",
        "answer_not_found",
    ]


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_fixture_parses(path):
    card = AnswerCard.model_validate_json(path.read_text(encoding="utf-8"))
    if card.status == "ANSWERED":
        assert any(c.verified for c in card.citations)
    for c in card.citations:
        assert c.pdf_en.endswith(f"#page={c.page}")
        assert c.pdf_hi.endswith(f"#page={c.page}")


def test_flagship_shape():
    card = AnswerCard.model_validate_json((FIXTURES / "answer_flagship.json").read_text("utf-8"))
    assert card.status == "PARTIAL"
    values = {c.calc_id: c.result.value for c in card.calculations}
    assert values["front_open_space"] == 3.0
    assert values["rear_open_space"] == 2.5
    assert values["max_built_up"] == 250.0
    assert values["permission_fee"] == 3000.0
    assert values["application_fee"] == 250.0


def test_unknown_field_rejected():
    data = json.loads((FIXTURES / "answer_not_found.json").read_text("utf-8"))
    data["surprise"] = 1
    with pytest.raises(ValidationError):
        AnswerCard.model_validate(data)


def test_bad_status_rejected():
    data = json.loads((FIXTURES / "answer_not_found.json").read_text("utf-8"))
    data["status"] = "MAYBE"
    with pytest.raises(ValidationError):
        AnswerCard.model_validate(data)


def test_ask_request_limits():
    assert AskRequest(question="hi").params_override is None
    with pytest.raises(ValidationError):
        AskRequest(question="x" * 501)
    with pytest.raises(ValidationError):
        AskRequest(question="hi", lang="fr")


def test_step_schemas():
    u = UnderstandOutput.model_validate(
        {
            "in_scope": True,
            "intent": "front_open_space",
            "search_query_en": "front open space street width",
            "params": {
                "plot_area": 200,
                "plot_area_unit": "sqm",
                "road_width_m": 9,
                "height_m": -1,
                "built_up_area_sqm": -1,
                "frontage_m": -1,
                "use": "unknown",
                "building_type": "unknown",
                "voltage": "unknown",
            },
        }
    )
    assert u.params.road_width_m == 9
    c = ComposeOutput.model_validate(
        {"status": "not_found", "answer": "", "citations": [], "missing_info": []}
    )
    assert c.status == "not_found"
