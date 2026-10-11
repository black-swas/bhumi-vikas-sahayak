"""C6 Rule 42 norms for buildings above 12.5 m: Table 4 (up to 30 m, p.58) and Table 5 (high rise,
p.59). The row chosen is the highest one whose road, plot and frontage minimums are all met."""

from decimal import Decimal

from app.schemas import CalculationResult

from ._common import (
    DP_PRECEDENCE_WARNING,
    HEIGHT_LIMIT_RULE_56_M,
    D,
    fmt_num,
    load_table,
    positive,
    result,
)

HIGH_RISE_HEIGHT_M = 30.0
HIGH_RISE_STOREYS = 10


def high_rise_norms(
    road_width_m: float,
    plot_area_sqm: float,
    height_m: float,
    frontage_m: float | None = None,
    storeys: int | None = None,
) -> CalculationResult:
    road = positive("road_width_m", road_width_m, 500)
    area = positive("plot_area_sqm", plot_area_sqm, 1e7)
    h = positive("height_m", height_m, 1000)
    f = None if frontage_m is None else positive("frontage_m", frontage_m, 10_000)
    inputs = {"road_width_m": float(road), "plot_area_sqm": float(area), "height_m": float(h)}
    if f is not None:
        inputs["frontage_m"] = float(f)
    if storeys is not None:
        inputs["storeys"] = storeys

    if h <= Decimal(str(HEIGHT_LIMIT_RULE_56_M)) and not (storeys and storeys > HIGH_RISE_STOREYS):
        return result(
            calc_id="high_rise_norms",
            inputs=inputs,
            matched_row_text="",
            value=None,
            unit="FAR",
            rule="42",
            sub_rule="(1)",
            page=58,
            warnings=[
                "Rule 42 applies above 12.5 m; up to 12.5 m the Rule 56 open-space tables apply"
            ],
            details={"routed_to": "plot_norms"},
        )

    high = h > D(HIGH_RISE_HEIGHT_M) or bool(storeys and storeys > HIGH_RISE_STOREYS)
    t = load_table("42_table5" if high else "42_table4")
    table_no = 5 if high else 4
    warnings = [DP_PRECEDENCE_WARNING]
    if not high:
        note = t["column_6_deleted"]
        warnings.append(
            "Table 4 column 6 (ground coverage) and Note (1) were deleted on 06/03/2025 "
            f"(p.{note['page']})"
        )

    def meets(row: dict) -> bool:
        c = row["columns"]
        return (
            road >= D(c["road_width_min_m"])
            and area >= D(c["plot_area_min_sqm"])
            and (f is None or f >= D(c["frontage_min_m"]))
        )

    met = [r for r in t["rows"] if meets(r)]
    if not met:
        low = t["rows"][0]["columns"]
        return result(
            calc_id="high_rise_norms",
            inputs=inputs,
            matched_row_text="",
            value=None,
            unit="FAR",
            rule=t["rule"],
            sub_rule=t["sub_rule"],
            page=t["page"],
            warnings=[
                f"This plot does not meet the minimum road width, plot size and frontage of any "
                f"Table {table_no} row (the lowest row needs a road of "
                f"{fmt_num(low['road_width_min_m'])} m, "
                f"a plot of {fmt_num(low['plot_area_min_sqm'])} sq m and a frontage of "
                f"{fmt_num(low['frontage_min_m'])} m)",
                *warnings,
            ],
            details={"table": table_no, "row_no": None},
        )

    row = met[-1]
    c = row["columns"]
    if f is None:
        warnings.append(
            f"Frontage not given: Table {table_no} row {row['row_no']} also needs a frontage of at "
            f"least {fmt_num(c['frontage_min_m'])} m"
        )
    if c["max_height_m"] is not None and h > D(c["max_height_m"]):
        warnings.append(
            f"The proposed height {fmt_num(h)} m is above the {fmt_num(c['max_height_m'])} m "
            f"maximum height of Table {table_no} row {row['row_no']}"
        )
    return result(
        calc_id="high_rise_norms",
        inputs=inputs,
        matched_row_text=row["row_text"],
        value=c["far"],
        unit="FAR",
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        warnings=warnings,
        details={
            "table": table_no,
            "row_no": row["row_no"],
            "max_height_m": c["max_height_m"],
            "height_display": row.get("height_display"),
            "front_mos_m": c["front_mos_m"],
            "side_rear_mos_m": c["side_rear_mos_m"],
            "ground_coverage_pct": c.get("ground_coverage_pct"),
            "frontage_checked": f is not None,
        },
    )
