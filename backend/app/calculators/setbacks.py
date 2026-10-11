"""C1 front open space, C2 rear open space, C3 side open space and plot-type classification.

Rule 56(1)-(3) (pp.77-78) and Rule 53(1) (p.70). Residential buildings up to 12.5 m only.
"""

from decimal import Decimal

from app.schemas import CalculationResult

from ._common import (
    HEIGHT_LIMIT_RULE_56_M,
    MissingInput,
    above_rule_56,
    find_band,
    fmt_num,
    height_assumption,
    load_table,
    positive,
    result,
)

BUILDING_TYPES = ("detached", "semi_detached", "row")


def _height(height_m) -> Decimal | None:
    return None if height_m is None else positive("height_m", height_m, 1000)


def front_open_space(road_width_m: float, height_m: float | None = None) -> CalculationResult:
    """C1: Rule 56(1)(a) front open space from the width of the street facing the plot."""
    road = positive("road_width_m", road_width_m, 500)
    h = _height(height_m)
    t = load_table("56_1_a_front_open_space")
    inputs = {"road_width_m": float(road)} | ({"height_m": float(h)} if h else {})
    if h is not None and h > Decimal(str(HEIGHT_LIMIT_RULE_56_M)):
        return above_rule_56("front_open_space", inputs, h, "56", "(1)(a)", t["page"])

    row = find_band(t["rows"], road)
    note = t["existing_street_note"]
    warnings = []
    details = {}
    if road < Decimal(str(note["road_width_lt_m"])):
        warnings.append(
            f"Rule 56(1)(b) (p.{note['page']}): in existing developed areas with a street narrower "
            f"than {fmt_num(note['road_width_lt_m'])} m, the building line is "
            f"{fmt_num(note['building_line_from_centre_m'])} m from the centre line of the street"
        )
        details["building_line_from_centre_m"] = note["building_line_from_centre_m"]
    return result(
        calc_id="front_open_space",
        inputs=inputs,
        matched_row_text=row["row_text"],
        value=row["value"],
        unit=row["unit"],
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=height_assumption(height_m),
        warnings=warnings,
        details=details,
    )


def rear_open_space(plot_area_sqm: float, height_m: float | None = None) -> CalculationResult:
    """C2: Rule 56(2)(a) rear open space from the plot area. A plot up to 40 sq m needs none."""
    area = positive("plot_area_sqm", plot_area_sqm, 1e7)
    h = _height(height_m)
    t = load_table("56_2_a_rear_open_space")
    inputs = {"plot_area_sqm": float(area)} | ({"height_m": float(h)} if h else {})
    if h is not None and h > Decimal(str(HEIGHT_LIMIT_RULE_56_M)):
        return above_rule_56("rear_open_space", inputs, h, "56", "(2)(a)", t["page"])

    row = find_band(t["rows"], area)
    return result(
        calc_id="rear_open_space",
        inputs=inputs,
        matched_row_text=row["row_text"],
        value=row["value"],
        unit=row["unit"],
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=height_assumption(height_m),
        details={"display": row.get("display", f"{fmt_num(row['value'])} m")},
    )


def side_open_space(
    building_type: str | None,
    height_m: float | None = None,
    frontage_m: float | None = None,
) -> CalculationResult:
    """C3: Rule 56(3) side open space by building type.

    ``result.value`` is the open space on the main side; ``details['sides_m']`` lists every side
    that needs space (the reduced figure included when the Rule 56(3) relaxation applies).
    """
    if building_type not in BUILDING_TYPES:
        raise MissingInput("building_type")
    t = load_table("56_3_side_open_space")
    h = _height(height_m)
    f = None if frontage_m is None else positive("frontage_m", frontage_m, 10_000)
    inputs: dict = {"building_type": building_type}
    if h is not None:
        inputs["height_m"] = float(h)
    if f is not None:
        inputs["frontage_m"] = float(f)
    if h is not None and h > Decimal(str(HEIGHT_LIMIT_RULE_56_M)):
        return above_rule_56("side_open_space", inputs, h, "56", "(3)", t["page"])

    spec = t["types"][building_type]
    sides = [spec["side_open_space_m"]] * spec["sides_required"]
    rows = [spec["row_text"]]
    warnings: list[str] = []
    relaxed = False

    rel = spec.get("relaxation")
    if rel:
        if h is None or f is None:
            missing = " and ".join(n for n, v in (("height", h), ("frontage", f)) if v is None)
            warnings.append(
                f"A reduced side open space of {fmt_num(rel['reduced_side_open_space_m'])} m "
                f"may apply under Rule 56(3) for a building up to {fmt_num(rel['height_m_max'])} m "
                f"high on a narrow plot; {missing} not given, so it is not applied"
            )
        else:
            frontage_ok = (
                f < Decimal(str(rel["frontage_m_lt"]))
                if "frontage_m_lt" in rel
                else f <= Decimal(str(rel["frontage_m_le"]))
            )
            if h <= Decimal(str(rel["height_m_max"])) and frontage_ok:
                sides[-1] = rel["reduced_side_open_space_m"]
                rows.append(rel["row_text"])
                relaxed = True

    value = float(sides[0]) if sides else 0.0
    return result(
        calc_id="side_open_space",
        inputs=inputs,
        matched_row_text=" | ".join(rows),
        value=value,
        unit="m",
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=height_assumption(height_m),
        warnings=warnings,
        details={
            "building_type": building_type,
            "sides_m": [float(s) for s in sides],
            "relaxation_applied": relaxed,
            "display": spec.get("display", ""),
        },
    )


def _fits(rng: dict, x: Decimal) -> bool:
    return (
        ("gt" not in rng or x > Decimal(str(rng["gt"])))
        and ("ge" not in rng or x >= Decimal(str(rng["ge"])))
        and ("le" not in rng or x <= Decimal(str(rng["le"])))
    )


def classify_plot_types(plot_area_sqm: float, frontage_m: float | None = None) -> CalculationResult:
    """Rule 53(1)(i): which types of development the plot size (and frontage) fits.

    Informational: it never decides the type. Frontage is checked only when given.
    """
    area = positive("plot_area_sqm", plot_area_sqm, 1e7)
    f = None if frontage_m is None else positive("frontage_m", frontage_m, 10_000)
    t = load_table("53_1_plot_types")
    fits = [
        r
        for r in t["rows"]
        if _fits(r["plot_area_sqm"], area) and (f is None or _fits(r["frontage_m"], f))
    ]
    inputs = {"plot_area_sqm": float(area)} | ({"frontage_m": float(f)} if f else {})
    return result(
        calc_id="plot_types",
        inputs=inputs,
        matched_row_text=" | ".join(r["row_text"] for r in fits),
        value=", ".join(r["type"] for r in fits) if fits else "none",
        unit="",
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=[]
        if f is not None
        else ["Frontage not given: plot types matched on size only"],
        warnings=[] if fits else ["The plot size does not fit any residential type in Rule 53(1)"],
        details={"fits": [r["type"] for r in fits], "frontage_checked": f is not None},
    )
