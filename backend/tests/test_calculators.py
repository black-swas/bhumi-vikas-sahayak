from datetime import date

import pytest

from app import calculators as calc
from app.calculators._common import (
    DP_PRECEDENCE_WARNING,
    CalcError,
    MissingInput,
    format_date,
    format_inr,
)
from app.schemas import AnswerCard, CalculationResult

# --- C1 front open space ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "road,expected",
    [(9.0, 3.0), (9.01, 3.6), (12.0, 3.6), (12.01, 4.5), (18.0, 4.5), (18.01, 6.0), (3, 3.0)],
)
def test_front_open_space_band_edges(road, expected):
    r = calc.front_open_space(road)
    assert r.result.value == expected and r.result.unit == "m"
    assert (r.rule, r.sub_rule, r.page) == ("56", "(1)(a)", 77)


def test_front_open_space_matched_row_and_assumption():
    r = calc.front_open_space(9)
    assert r.matched_row_text == "1. Up to 9.0 meters 3.0 meters"
    assert r.assumptions == ["Building height assumed to be 12.5 m or less (Rule 56 applies)"]
    assert calc.front_open_space(9, height_m=9).assumptions == []


def test_front_open_space_narrow_road_adds_centre_line_note():
    r = calc.front_open_space(5.9)
    assert r.result.value == 3.0
    assert any("56(1)(b)" in w and "centre line" in w for w in r.warnings)
    assert r.details["building_line_from_centre_m"] == 6.0
    assert not calc.front_open_space(6.0).warnings  # exactly 6.0 m is not "less than 6.0"


def test_front_open_space_above_12_5_m_routes_to_rule_42():
    r = calc.front_open_space(12, height_m=12.51)
    assert r.result.value is None and r.details["routed_to"] == "high_rise_norms"
    assert calc.front_open_space(12, height_m=12.5).result.value == 3.6


# --- C2 rear open space ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "plot,expected",
    [(40, 0.0), (40.01, 1.5), (150.0, 1.5), (150.01, 2.5), (225.0, 2.5), (225.01, 3.0), (10, 0.0)],
)
def test_rear_open_space_band_edges(plot, expected):
    r = calc.rear_open_space(plot)
    assert r.result.value == expected
    assert (r.rule, r.sub_rule, r.page) == ("56", "(2)(a)", 78)


def test_rear_open_space_nil_is_shown_as_nil():
    r = calc.rear_open_space(40)
    assert r.details["display"] == "Nil" and r.result.value == 0.0
    assert calc.rear_open_space(150).details["display"] == "1.5 m"


# --- C3 side open space and plot type --------------------------------------------------------


def test_side_open_space_by_type():
    d = calc.side_open_space("detached")
    assert d.result.value == 3.0 and d.details["sides_m"] == [3.0, 3.0]
    s = calc.side_open_space("semi_detached")
    assert s.result.value == 3.0 and s.details["sides_m"] == [3.0]
    r = calc.side_open_space("row")
    assert r.result.value == 0.0 and r.details["sides_m"] == [] and r.details["display"] == "Nil"


@pytest.mark.parametrize(
    "height,frontage,sides",
    [(10, 10, [2.5]), (10.01, 10, [3.0]), (10, 10.01, [3.0]), (9, 8, [2.5])],
)
def test_semi_detached_relaxation_edges(height, frontage, sides):
    r = calc.side_open_space("semi_detached", height, frontage)
    assert r.details["sides_m"] == sides
    assert r.details["relaxation_applied"] is (sides == [2.5])


@pytest.mark.parametrize(
    "height,frontage,sides",
    [(7, 11.99, [3.0, 1.5]), (7, 12, [3.0, 3.0]), (7.01, 11, [3.0, 3.0])],
)
def test_detached_relaxation_edges(height, frontage, sides):
    assert calc.side_open_space("detached", height, frontage).details["sides_m"] == sides


def test_relaxation_not_applied_without_height_and_frontage():
    r = calc.side_open_space("semi_detached")
    assert r.result.value == 3.0 and any("2.5 m" in w for w in r.warnings)


def test_side_open_space_needs_a_type():
    with pytest.raises(MissingInput) as e:
        calc.side_open_space(None)
    assert e.value.missing == ["building_type"]


def test_plot_types_by_area():
    assert calc.classify_plot_types(200).details["fits"] == ["semi_detached", "row"]
    assert calc.classify_plot_types(225).details["fits"] == ["semi_detached", "row"]
    assert calc.classify_plot_types(225.01).details["fits"] == ["detached"]
    assert calc.classify_plot_types(125).details["fits"] == ["semi_detached", "row"]
    assert calc.classify_plot_types(124.99).details["fits"] == ["row"]
    assert calc.classify_plot_types(49).details["fits"] == []


def test_plot_types_with_frontage():
    assert calc.classify_plot_types(200, 9).details["fits"] == ["semi_detached", "row"]
    assert calc.classify_plot_types(200, 7).details["fits"] == ["row"]
    assert calc.classify_plot_types(300, 12).details["fits"] == []  # detached needs above 12
    assert calc.classify_plot_types(300, 12.5).details["fits"] == ["detached"]


# --- C4 FAR ----------------------------------------------------------------------------------


def test_far_residential_200():
    r = calc.max_built_up(200)
    assert r.result.value == 250.0 and r.result.unit == "sq m"
    assert r.details["far"] == 1.25 and r.matched_row_text == "1. Resdential 1.25"
    assert r.assumptions == ["Use assumed to be residential"]
    assert (r.rule, r.sub_rule, r.page) == ("61", "Table 8", 83)


def test_far_always_carries_dp_caveat():
    for plot in (50, 199.99, 200, 600):
        assert DP_PRECEDENCE_WARNING in calc.max_built_up(plot, "residential").warnings
    assert "Rule 103" in DP_PRECEDENCE_WARNING and "Table 8" in DP_PRECEDENCE_WARNING


def test_far_notes_3_and_4_only_from_200_sq_m():
    below = calc.max_built_up(199.99, "residential")
    assert not any("Note (3)" in w or "Note (4)" in w for w in below.warnings)
    at = calc.max_built_up(200, "residential")
    assert any(
        "Note (3)" in w and "one servant quarter" in w and "25 sq m" in w for w in at.warnings
    )
    assert any("Note (4)" in w and "parking" in w for w in at.warnings)
    assert any(
        "two servant quarters" in w for w in calc.max_built_up(500.01, "residential").warnings
    )


def test_far_rounding_is_decimal_not_float():
    assert calc.max_built_up(183.7, "residential").result.value == 229.63  # 229.625 -> half up


@pytest.mark.parametrize(
    "category,far",
    [
        ("city_centre", 2.5),
        ("sub_city_centre", 2.0),
        ("community_centre", 1.75),
        ("local_shopping_centre", 1.5),
        ("convenience_shopping_centre", 1.25),
    ],
)
def test_far_commercial_categories(category, far):
    r = calc.max_built_up(100, "commercial", category)
    assert r.details["far"] == far and r.result.value == far * 100


def test_far_other_uses():
    assert calc.max_built_up(100, "public").details["far"] == 1.0
    assert calc.max_built_up(100, "industrial").result.value is None
    assert calc.max_built_up(100, "shop_cum_residence").result.value is None
    with pytest.raises(MissingInput):
        calc.max_built_up(100, "commercial")
    with pytest.raises(CalcError):
        calc.max_built_up(100, "spaceport")


# --- C5 fees ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "area,fee",
    [
        (1, 750), (75, 750), (76, 1250), (125, 1250), (126, 2000), (200, 2000), (201, 3000),
        (250, 3000), (300, 3000), (301, 4000), (400, 4000), (401, 6000), (600, 6000), (601, 7500),
        (750, 7500), (751, 10000), (1000, 10000), (1001, 12500), (1250, 12500), (1251, 15000),
        (1500, 15000), (1501, 20000), (2000, 20000), (2001, 25000), (2500, 25000),
        (2500.01, 50000), (9000, 50000),
    ],
)  # fmt: skip
def test_residential_permission_fee_bands(area, fee):
    assert calc.permission_fee(area).result.value == fee


def test_thirteen_bands_exist():
    fees = {calc.permission_fee(a).result.value for a in (1, 100, 150, 250, 350, 500, 700, 900)}
    fees |= {calc.permission_fee(a).result.value for a in (1100, 1300, 1800, 2200, 3000)}
    assert len(fees) == 13


def test_fee_gap_between_bands_is_flagged_not_rounded():
    r = calc.permission_fee(75.5)
    assert r.result.value is None
    assert any(
        "between two table rows" in w and "clerk to confirm rounding" in w for w in r.warnings
    )
    assert " | " in r.matched_row_text
    assert r.details["between_rows"][0]["fee_inr"] == 750
    assert r.details["between_rows"][1]["fee_inr"] == 1250
    assert calc.permission_fee(200.4).result.value is None


def test_application_fee_is_one_rupee_per_sq_m():
    a = calc.application_fee(250)
    assert a.result.value == 250.0 and a.details["rate_inr_per_sqm"] == 1.0
    assert calc.application_fee(75.5).result.value == 75.5  # no band, so no gap
    assert any("not refunded" in w for w in a.warnings)
    assert (a.rule, a.sub_rule, a.page) == ("21", "(2)(ii)", 35)


def test_commercial_surcharge_applies_to_slab_only():
    c = calc.permission_fee(250, "commercial")
    assert c.result.value == 4500.0 and c.details["surcharge_pct"] == 50
    assert "slab only" in c.details["surcharge_applies_to"]
    assert calc.permission_fee(250, "shop_cum_residence").result.value == 4500.0
    assert calc.permission_fee(250, "industrial").result.value == 4500.0
    assert calc.permission_fee(250, "public").result.value == 3000.0
    # the application fee is never surcharged
    commercial = calc.fees(built_up_area_sqm=250, use="commercial")
    assert [r.result.value for r in commercial] == [250.0, 4500.0]


def test_high_rise_permission_fee():
    assert calc.permission_fee(1000, "residential", high_rise=True).result.value == 10000.0
    assert calc.permission_fee(1000, "commercial", high_rise=True).result.value == 20000.0
    assert calc.permission_fee(1000, "shop_cum_residence", high_rise=True).result.value == 15000.0
    assert calc.permission_fee(1000, "public", high_rise=True).result.value == 10000.0
    r = calc.permission_fee(1000, high_rise=True)
    assert r.sub_rule == "(3)(c)" and r.page == 37


def test_is_high_rise_definition():
    assert calc.is_high_rise(height_m=30.01) and not calc.is_high_rise(height_m=30)
    assert calc.is_high_rise(storeys=11) and not calc.is_high_rise(storeys=10)
    assert not calc.is_high_rise(high_rise=False, height_m=50)


def test_cinema_fee_needs_seats():
    with pytest.raises(MissingInput):
        calc.permission_fee(500, "cinema")
    assert calc.permission_fee(500, "cinema", cinema_seats=800).result.value == 15000.0
    assert calc.permission_fee(500, "cinema", cinema_seats=801).result.value == 25000.0


def test_fees_assume_maximum_built_up_when_unspecified():
    app, perm = calc.fees(plot_area_sqm=200)
    assert (app.result.value, perm.result.value) == (250.0, 3000.0)
    for r in (app, perm):
        assert any("maximum permissible built-up area of 250 sq m" in a for a in r.assumptions)
        assert any("FAR 1.25 x plot 200 sq m" in a for a in r.assumptions)
    # a stated built-up area is used as given, with no such assumption
    app, perm = calc.fees(built_up_area_sqm=120, plot_area_sqm=200, use="residential")
    assert (app.result.value, perm.result.value) == (120.0, 1250.0)  # 76-125 band
    assert not app.assumptions and not perm.assumptions


def test_fees_need_some_area():
    with pytest.raises(MissingInput):
        calc.fees()
    with pytest.raises(MissingInput):
        calc.fees(plot_area_sqm=100, use="industrial")  # no numeric FAR in Table 8


# --- C6 high-rise norms ----------------------------------------------------------------------


def test_table_4_row_1():
    r = calc.high_rise_norms(road_width_m=12, plot_area_sqm=1000, height_m=18, frontage_m=18)
    assert r.result.value == 1.5 and r.details["row_no"] == 1 and r.details["table"] == 4
    assert r.details["max_height_m"] == 18 and r.details["front_mos_m"] == 7.5
    assert r.details["side_rear_mos_m"] == 6.0
    assert (r.rule, r.page) == ("42", 58)
    assert any("column 6" in w for w in r.warnings)


def test_table_4_picks_highest_row_met():
    r = calc.high_rise_norms(24, 2000, 28, frontage_m=30)
    assert r.details["row_no"] == 3 and r.result.value == 2.0
    # road and plot meet row 3 but the frontage only meets row 2
    r = calc.high_rise_norms(24, 2000, 28, frontage_m=21)
    assert r.details["row_no"] == 2


def test_table_4_height_over_row_maximum_is_warned():
    r = calc.high_rise_norms(12, 1000, 20, frontage_m=18)
    assert r.details["row_no"] == 1
    assert any("above the 18 m maximum height" in w for w in r.warnings)


def test_table_4_no_row_met_states_a_fact():
    r = calc.high_rise_norms(road_width_m=9, plot_area_sqm=200, height_m=15, frontage_m=10)
    assert r.result.value is None and r.matched_row_text == ""
    assert any("does not meet the minimum" in w and "Table 4" in w for w in r.warnings)
    assert calc.high_rise_norms(12, 999.9, 15, 18).result.value is None
    assert calc.high_rise_norms(12, 1000, 15, 17.9).result.value is None


def test_table_4_unknown_frontage_is_flagged():
    r = calc.high_rise_norms(12, 1000, 15)
    assert r.details["row_no"] == 1 and any("Frontage not given" in w for w in r.warnings)


def test_high_rise_uses_table_5():
    r = calc.high_rise_norms(30, 2500, 45, frontage_m=30)
    assert r.details["table"] == 5 and r.details["row_no"] == 1 and r.result.value == 2.25
    assert r.page == 59
    r = calc.high_rise_norms(75, 4500, 120, frontage_m=60)
    assert r.details["row_no"] == 5 and r.details["height_display"] == "Above 90 meters"
    assert calc.high_rise_norms(20, 1000, 20, storeys=11, frontage_m=30).details["table"] == 5
    assert calc.high_rise_norms(20, 1000, 30, frontage_m=30).details["table"] == 4  # 30 m exactly


def test_below_12_5_m_is_not_rule_42():
    r = calc.high_rise_norms(12, 1000, 12.5, 18)
    assert r.result.value is None and r.details["routed_to"] == "plot_norms"


# --- C7 electric lines -----------------------------------------------------------------------


def test_electric_low_medium_voltage():
    r = calc.electric_clearance("low_medium")
    assert r.details["vertical_m"] == 2.5 and r.details["horizontal_m"] == 1.2
    assert (r.rule, r.sub_rule, r.page) == ("52", "(1)(a)", 69)
    assert any("whichever is more" in w for w in r.warnings)


def test_electric_high_and_extra_high():
    h = calc.electric_clearance("high_upto_33kv")
    assert (h.details["vertical_m"], h.details["horizontal_m"]) == (3.7, 1.2)
    x = calc.electric_clearance("extra_high")
    assert x.details["corridor_m"] == 15.0 and x.details["each_side_of_centre_line_m"] == 7.5
    assert any("whichever is more" in w for w in x.warnings)


def test_electric_needs_voltage():
    with pytest.raises(MissingInput):
        calc.electric_clearance(None)
    with pytest.raises(MissingInput):
        calc.electric_clearance("unknown")


# --- C8 validity -----------------------------------------------------------------------------


def test_validity_with_a_date():
    r = calc.permission_validity(date(2023, 6, 15))
    assert r.result.value == 3 and r.result.unit == "years"
    assert r.details["initial_expiry_display"] == "15/06/2026"
    assert r.details["final_expiry_display"] == "15/06/2028"
    assert r.details["revalidation_terms"] == 2 and r.details["revalidation_years_each"] == 1
    assert r.details["five_year_limit_display"] == "15/06/2028"
    assert r.details["cap_years"] == 5 and r.details["no_lapse_if_execution_begins"]


def test_validity_year_only_gives_no_dates():
    r = calc.permission_validity(grant_year=2023)
    assert "initial_expiry" not in r.details and r.assumptions
    assert r.details["initial_years"] == 3 and r.details["cap_years"] == 5


def test_validity_leap_day_and_errors():
    assert calc.permission_validity(date(2024, 2, 29)).details["initial_expiry"] == "2027-02-28"
    r = calc.permission_validity()  # no date: the terms without dates
    assert r.result.value == 3 and "initial_expiry" not in r.details and r.assumptions
    with pytest.raises(CalcError):
        calc.permission_validity(date(2023, 1, 1), grant_year=2022)


# --- C9 farm house ---------------------------------------------------------------------------


def test_farm_house_norms():
    r = calc.farm_house()
    assert r.result.value == 0.1 and r.result.unit == "FAR"
    assert r.details["min_plot_sqm"] == 4000 and r.details["min_plot_hectares"] == 0.4
    assert (r.rule, r.page) == ("17", 34)


def test_farm_house_with_plot():
    ok = calc.farm_house(4000)
    assert ok.details["meets_min_plot"] and ok.result.value == 400.0 and not ok.warnings
    small = calc.farm_house(3999.99)
    assert not small.details["meets_min_plot"] and small.warnings


# --- C10 instant approval --------------------------------------------------------------------


@pytest.mark.parametrize(
    "area,value",
    [
        (186, "within_limit"),
        (185.99, "within_limit"),
        (186.01, "above_limit"),
        (200, "above_limit"),
    ],
)
def test_instant_approval_threshold(area, value):
    r = calc.instant_approval_threshold(area)
    assert r.result.value == value
    assert (r.rule, r.page) == ("12-A", 21)


def test_instant_approval_never_says_qualifies():
    for area in (100, 186, 200):
        r = calc.instant_approval_threshold(area)
        text = " ".join([r.details["statement"], *r.warnings, *r.assumptions]).lower()
        assert "qualif" not in text and "eligible" not in text.replace(
            "eligible for application", ""
        )
        assert any("not a decision" in w for w in r.warnings)
    assert "above the 186 sq m limit" in calc.instant_approval_threshold(200).details["statement"]
    assert calc.instant_approval_threshold(100, "commercial").result.value == "not_applicable"


# --- units -----------------------------------------------------------------------------------


def test_unit_conversions_and_explanations():
    c = calc.to_sqm(1500, "sqft")
    assert c.value == 139.3546 and c.text == "1500 sq ft × 0.09290304 = 139.3546 sq m"
    assert calc.to_sqm(200, "gaj").value == 167.2255  # 200 x 0.83612736 = 167.225472
    assert calc.to_sqm(1, "acre").value == 4046.8564
    assert calc.to_sqm(0.4, "ha").value == 4000.0
    assert calc.to_sqm(200).value == 200.0 and calc.to_sqm(200).text == "200 sq m"
    assert calc.to_m(30, "ft").value == 9.144 and calc.to_m(9).value == 9.0
    assert calc.to_sqm(10, "Sq Ft").input_unit == "sqft"
    with pytest.raises(CalcError):
        calc.to_sqm(10, "bigha")
    with pytest.raises(CalcError):
        calc.to_sqm(-1, "sqm")


def test_converted_area_feeds_calculators():
    area = calc.to_sqm(1500, "sqft").value  # 139.3546 sq m
    assert calc.rear_open_space(area).result.value == 1.5
    assert calc.permission_fee(area).result.value == 2000.0  # inside the 126-200 band
    assert calc.permission_fee(125.5).result.value is None  # between the 76-125 and 126-200 rows


# --- input validation and formatting ---------------------------------------------------------


@pytest.mark.parametrize("bad", [0, -5, float("nan"), float("inf"), "abc", None])
def test_rejects_bad_numbers(bad):
    with pytest.raises(CalcError):
        calc.front_open_space(bad)
    with pytest.raises(CalcError):
        calc.rear_open_space(bad)


def test_rejects_absurd_numbers():
    with pytest.raises(CalcError):
        calc.front_open_space(100_000)
    with pytest.raises(CalcError):
        calc.max_built_up(1e12)


def test_inr_and_date_formatting():
    assert format_inr(3000) == "₹3,000"
    assert format_inr(125000) == "₹1,25,000"
    assert format_inr(50000) == "₹50,000"
    assert format_inr(750) == "₹750"
    assert format_inr(10000000) == "₹1,00,00,000"
    assert format_inr(75.5) == "₹75.50"
    assert format_date(date(2026, 3, 6)) == "06/03/2026"


# --- the flagship question -------------------------------------------------------------------


def test_flagship_200_sq_m_on_9_m_road():
    results = calc.plot_norms(plot_area_sqm=200, road_width_m=9)
    by_id: dict[str, list[CalculationResult]] = {}
    for r in results:
        by_id.setdefault(r.calc_id, []).append(r)

    assert by_id["front_open_space"][0].result.value == 3.0
    assert by_id["rear_open_space"][0].result.value == 2.5
    assert by_id["plot_types"][0].details["fits"] == ["semi_detached", "row"]

    sides = {r.details["building_type"]: r for r in by_id["side_open_space"]}
    assert set(sides) == {"semi_detached", "row"}  # not detached: needs above 225 sq m
    assert sides["semi_detached"].result.value == 3.0
    assert sides["semi_detached"].details["sides_m"] == [3.0]
    assert sides["row"].details["display"] == "Nil"

    far = by_id["max_built_up"][0]
    assert far.details["far"] == 1.25 and far.result.value == 250.0
    assert DP_PRECEDENCE_WARNING in far.warnings
    assert any("servant quarter" in w for w in far.warnings)
    assert any("parking" in w for w in far.warnings)

    assert by_id["permission_fee"][0].result.value == 3000.0
    assert by_id["application_fee"][0].result.value == 250.0
    assert any(
        "maximum permissible built-up area" in a for a in by_id["permission_fee"][0].assumptions
    )

    inst = by_id["instant_approval_threshold"][0]
    assert inst.result.value == "above_limit" and "186" in inst.details["statement"]


def test_flagship_results_are_valid_answer_card_calculations():
    results = calc.plot_norms(200, 9)
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "answer_flagship.json").read_text("utf-8")
    )
    fixture["calculations"] = [r.model_dump() for r in results]
    card = AnswerCard.model_validate(fixture)
    assert len(card.calculations) == len(results)


def test_flagship_matches_the_fixture_numbers():
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "answer_flagship.json").read_text("utf-8")
    )
    expected = {c["calc_id"]: c["result"]["value"] for c in fixture["calculations"]}
    got = {r.calc_id: r.result.value for r in calc.plot_norms(200, 9)}
    for calc_id, value in expected.items():
        assert got[calc_id] == value, calc_id


def test_flagship_hindi_plot_in_gaj():
    # 200 gaj = 167.2255 sq m: a different plot, so a different rear space and fee
    area = calc.to_sqm(200, "gaj").value
    assert calc.rear_open_space(area).result.value == 2.5
    assert calc.max_built_up(area).result.value == 209.03
