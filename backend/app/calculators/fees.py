"""C5 application fee and permission fee: Rule 21(2)(ii) p.35, 21(3)(b) p.36, 21(3)(c) p.37.

The fee depends on the built-up area, not the plot area. When only the plot area is known the fee
is computed at the maximum built-up area (FAR x plot) and labelled as an assumption.
"""

from decimal import Decimal

from app.schemas import CalculationResult

from . import far as far_calc
from ._common import (
    CalcError,
    D,
    MissingInput,
    fmt_num,
    format_inr,
    load_table,
    num,
    positive,
    result,
)

# use -> key of the "other items" entry in the table (Rule 21(3)(b) items 2-6)
_ITEM_KEYS = {
    "commercial": "commercial_or_industrial",
    "industrial": "commercial_or_industrial",
    "shop_cum_residence": "shop_cum_residence",
    "administrative_block": "administrative_block_in_factory",
    "public": "social_and_other",
    "other": "social_and_other",
    "cinema": "cinema",
}
RESIDENTIAL_USES = {"residential"}


def is_high_rise(
    high_rise: bool | None = None, height_m: float | None = None, storeys: int | None = None
) -> bool:
    """Rule 2(38): more than ten storeys, or height above 30 m."""
    if high_rise is not None:
        return high_rise
    t = load_table("21_fees")["high_rise"]["definition"]
    return bool(
        (height_m is not None and D(height_m) > D(t["height_m_gt"]))
        or (storeys is not None and storeys > t["storeys_gt"])
    )


def application_fee(built_up_area_sqm: float) -> CalculationResult:
    """Rule 21(2)(ii): Rs 1.00 per sq m of the proposed built-up area; never refunded."""
    area = positive("built_up_area_sqm", built_up_area_sqm, 1e7)
    t = load_table("21_fees")["application_fee"]
    fee = D(t["rate_inr_per_sqm"]) * area
    return result(
        calc_id="application_fee",
        inputs={"built_up_area_sqm": float(area)},
        matched_row_text=t["row_text"],
        value=num(fee),
        unit="INR",
        rule="21",
        sub_rule=t["sub_rule"],
        page=t["page"],
        warnings=["Application fee is not refunded in any case (Rule 21(2)(iii))"],
        details={"rate_inr_per_sqm": t["rate_inr_per_sqm"], "display": format_inr(fee)},
    )


def _surcharge(use: str, high_rise: bool) -> tuple[int, str]:
    """(surcharge percent, row_text) for items 2-6 of the residential/high-rise tables."""
    t = load_table("21_fees")
    key = _ITEM_KEYS.get(use)
    if high_rise:
        if key in (None, "cinema"):
            return 0, ""
        entry = t["high_rise"][key]
        return entry["surcharge_pct"], entry["row_text"]
    if key is None:
        return 0, ""
    entry = t["permission_fee_other_items"][key]
    return entry["surcharge_pct"], entry["row_text"]


def permission_fee(
    built_up_area_sqm: float,
    use: str = "residential",
    high_rise: bool = False,
    cinema_seats: int | None = None,
) -> CalculationResult:
    area = positive("built_up_area_sqm", built_up_area_sqm, 1e7)
    if use != "residential" and use not in _ITEM_KEYS:
        raise CalcError(f"unknown use: {use!r}")
    t = load_table("21_fees")
    inputs = {"built_up_area_sqm": float(area), "use": use, "high_rise": high_rise}
    warnings: list[str] = []

    if use == "cinema":
        if cinema_seats is None:
            raise MissingInput("cinema_seats")
        item = t["permission_fee_other_items"]["cinema"]
        value = (
            item["fee_up_to_threshold_inr"]
            if cinema_seats <= item["seats_threshold"]
            else item["fee_above_threshold_inr"]
        )
        return result(
            calc_id="permission_fee",
            inputs=inputs | {"cinema_seats": cinema_seats},
            matched_row_text=" ".join([item["row_text"], *item["row_text_parts"]]),
            value=float(value),
            unit="INR",
            rule="21",
            sub_rule=item["sub_rule"],
            page=t["permission_fee_other_items"]["page"],
            details={"display": format_inr(value)},
        )

    pct, item_text = _surcharge(use, high_rise)

    if high_rise:
        base_entry = t["high_rise"]["residential"]
        base = D(base_entry["rate_inr_per_sqm"]) * area
        rows = [base_entry["row_text"]]
        sub_rule, page = t["high_rise"]["sub_rule"], t["high_rise"]["page"]
        details: dict = {"rate_inr_per_sqm": base_entry["rate_inr_per_sqm"], "high_rise": True}
    else:
        section = t["permission_fee_item1_residential"]
        sub_rule, page = section["sub_rule"], section["page"]
        slab = next((r for r in section["rows"] if _in_slab(area, r)), None)
        if slab is None:
            return _gap_result(area, inputs, section)
        base = D(slab["value"])
        rows = [slab["row_text"]]
        details = {"slab_inr": slab["value"], "high_rise": False}

    if pct:
        rows.append(item_text)
        details["surcharge_pct"] = pct
        details["surcharge_applies_to"] = "the permission fee slab only, not the application fee"
    fee = base + base * D(pct) / 100
    details["display"] = format_inr(fee)
    if use in ("commercial", "industrial") and pct:
        details["item"] = (
            "Rule 21(3) item 2: shops, store house, factory, trade, business or industrial"
        )
    return result(
        calc_id="permission_fee",
        inputs=inputs,
        matched_row_text=" | ".join(rows),
        value=num(fee),
        unit="INR",
        rule="21",
        sub_rule=sub_rule,
        page=page,
        warnings=warnings,
        details=details,
    )


def _in_slab(area: Decimal, row: dict) -> bool:
    if "gt" in row:
        return area > D(row["gt"])
    return D(row["from"]) <= area <= D(row["to"])


def _gap_result(area: Decimal, inputs: dict, section: dict) -> CalculationResult:
    """An area between two bands (for example 75.5): show both rows, pick neither."""
    below = max((r for r in section["rows"] if "to" in r and r["to"] and D(r["to"]) < area),
                key=lambda r: r["to"])  # fmt: skip
    above = min((r for r in section["rows"] if "from" in r and D(r["from"]) > area),
                key=lambda r: r["from"])  # fmt: skip
    return result(
        calc_id="permission_fee",
        inputs=inputs,
        matched_row_text=f"{below['row_text']} | {above['row_text']}",
        value=None,
        unit="INR",
        rule="21",
        sub_rule=section["sub_rule"],
        page=section["page"],
        warnings=[
            f"Built-up area {fmt_num(area)} sq m falls between two table rows "
            f"({below['from']}-{below['to']} sq m: {format_inr(below['value'])}; "
            f"{above['from']}-{above['to']} sq m: {format_inr(above['value'])}): "
            "clerk to confirm rounding"
        ],
        details={
            "between_rows": [
                {"from": below["from"], "to": below["to"], "fee_inr": below["value"]},
                {"from": above["from"], "to": above["to"], "fee_inr": above["value"]},
            ]
        },
    )


def fees(
    built_up_area_sqm: float | None = None,
    plot_area_sqm: float | None = None,
    use: str | None = None,
    high_rise: bool | None = None,
    height_m: float | None = None,
    storeys: int | None = None,
    cinema_seats: int | None = None,
    commercial_category: str | None = None,
) -> list[CalculationResult]:
    """[application fee, permission fee] for a building permission.

    Without a built-up area the maximum (FAR x plot area) is used and flagged as an assumption.
    """
    assumptions: list[str] = []
    if use is None or use == "unknown":
        use = "residential"
        assumptions.append("Use assumed to be residential")
    hr = is_high_rise(high_rise, height_m, storeys)

    if built_up_area_sqm is None:
        if plot_area_sqm is None:
            raise MissingInput("built_up_area_sqm")
        far_use = {"shop_cum_residence": "commercial"}.get(use, use)
        far_result = far_calc.max_built_up(plot_area_sqm, far_use, commercial_category)
        if far_result.result.value is None:
            raise MissingInput("built_up_area_sqm")
        built_up_area_sqm = far_result.result.value
        far_val = far_result.details["far"]
        assumptions.append(
            "Fee computed at the maximum permissible built-up area of "
            f"{fmt_num(built_up_area_sqm)} sq m "
            f"(FAR {fmt_num(far_val)} x plot {fmt_num(plot_area_sqm)} sq m, Rule 61 Table 8); "
            "the actual built-up area was not given. The Development Plan may allow a different FAR"
        )

    app = application_fee(built_up_area_sqm)
    perm = permission_fee(built_up_area_sqm, use, hr, cinema_seats)
    for r in (app, perm):
        r.assumptions = [*assumptions, *r.assumptions]
    return [app, perm]
