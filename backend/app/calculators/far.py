"""C4 FAR and maximum built-up area: Rule 61 Table 8 (p.83), notes on p.84, Rule 103."""

from app.schemas import CalculationResult

from ._common import (
    DP_PRECEDENCE_WARNING,
    CalcError,
    D,
    MissingInput,
    fmt_num,
    load_table,
    num,
    positive,
    result,
)

USE_ALIASES = {
    "residential": "residential",
    "commercial": "commercial",
    "public": "public_semi_public",
    "semi_public": "public_semi_public",
    "public_semi_public": "public_semi_public",
    "industrial": "industrial",
}
NOT_IN_TABLE_8 = {"shop_cum_residence", "cinema", "other"}


def max_built_up(
    plot_area_sqm: float,
    use: str | None = None,
    commercial_category: str | None = None,
) -> CalculationResult:
    """Maximum built-up area = FAR x plot area.

    ``use`` None means residential (flagged as an assumption). Commercial needs the centre
    category. Industrial, shop-cum-residence, cinema and other uses are not in Table 8 as a
    number, so the result carries no value and says why.
    """
    area = positive("plot_area_sqm", plot_area_sqm, 1e7)
    t = load_table("61_far")
    assumptions: list[str] = []
    warnings = [DP_PRECEDENCE_WARNING]
    if use is None or use == "unknown":
        use = "residential"
        assumptions.append("Use assumed to be residential")
    inputs = {"plot_area_sqm": float(area), "use": use}

    group = USE_ALIASES.get(use)
    if group is None and use not in NOT_IN_TABLE_8:
        raise CalcError(f"unknown use: {use!r}")

    rows = [r for r in t["rows"] if r["use"] == group] if group else []
    row = None
    if group == "commercial":
        if commercial_category is None:
            raise MissingInput("commercial_category")
        inputs["commercial_category"] = commercial_category
        row = next((r for r in rows if r["category"] == commercial_category), None)
        if row is None:
            raise CalcError(f"unknown commercial category: {commercial_category!r}")
    elif rows:
        row = rows[0]

    far = row["value"] if row else None
    if far is None:
        reason = (
            "Table 8 gives industrial FAR as per Rule 48; not computed here"
            if group == "industrial"
            else f"Table 8 of Rule 61 gives no FAR for use '{use}'; not computed here"
        )
        return result(
            calc_id="max_built_up",
            inputs=inputs,
            matched_row_text=row["row_text"] if row else "",
            value=None,
            unit="sq m",
            rule=t["rule"],
            sub_rule=t["sub_rule"],
            page=t["page"],
            assumptions=assumptions,
            warnings=[reason, *warnings],
        )

    built_up = num(area * D(far))
    sq = t["notes"]["servant_quarter"]
    park = t["notes"]["covered_parking"]
    if float(area) >= sq["plot_area_sqm_min"]:
        quarters = (
            "one servant quarter"
            if float(area) <= sq["plot_area_sqm_max_one_quarter"]
            else "two servant quarters"
        )
        warnings.append(
            f"Rule 61 Note (3) (p.{sq['page']}): on a plot of 200 sq m or more, {quarters} "
            f"(each up to {fmt_num(sq['max_quarter_area_sqm'])} sq m) may be permitted and "
            "are not counted in the built-up area, so the buildable area can exceed this figure"
        )
    if float(area) >= park["plot_area_sqm_min"]:
        warnings.append(
            f"Rule 61 Note (4) (p.{park['page']}): covered parking with a clear height of "
            f"{fmt_num(park['clear_height_m'])} m, within the permissible ground coverage, is not "
            "counted towards FAR on plots of 200 sq m or more"
        )
    return result(
        calc_id="max_built_up",
        inputs=inputs,
        matched_row_text=row["row_text"],
        value=built_up,
        unit="sq m",
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=assumptions,
        warnings=warnings,
        details={"far": far, "plot_area_sqm": float(area), "far_page": t["page"]},
    )
