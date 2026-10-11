"""C9 farm house norms: Rule 17(a)-(f) (p.34). Rule 17-a (agricultural tourist facility) is a
different rule with a 1.00 ha minimum and is not computed here."""

from app.schemas import CalculationResult

from ._common import D, fmt_num, load_table, num, positive, result


def farm_house(plot_area_sqm: float | None = None) -> CalculationResult:
    t = load_table("17_farm_house")
    min_plot = D(t["min_plot"]["sqm"])
    far = D(t["max_far"]["value"])
    details = {
        "min_plot_sqm": t["min_plot"]["sqm"],
        "min_plot_hectares": t["min_plot"]["hectares"],
        "max_far": t["max_far"]["value"],
        "max_height_m": t["max_height"]["value_m"],
        "min_live_trees_per_hectare": t["live_trees"]["per_hectare"],
        "min_road_width_m": t["road_access"]["min_width_m"],
        "min_open_space_all_sides_m": t["open_space"]["mos_m"],
    }
    rows = [t["min_plot"]["row_text"], t["max_far"]["row_text"]]
    inputs: dict = {}
    warnings: list[str] = []
    value, unit = t["max_far"]["value"], "FAR"

    if plot_area_sqm is not None:
        area = positive("plot_area_sqm", plot_area_sqm, 1e9)
        inputs["plot_area_sqm"] = float(area)
        meets = area >= min_plot
        details["meets_min_plot"] = meets
        details["max_built_up_sqm"] = num(area * far)
        value, unit = num(area * far), "sq m"
        if not meets:
            warnings.append(
                f"The plot of {fmt_num(area)} sq m is below the {fmt_num(min_plot)} sq m "
                f"({fmt_num(t['min_plot']['hectares'])} ha) minimum for a farm house in Rule 17(a)"
            )
    return result(
        calc_id="farm_house",
        inputs=inputs,
        matched_row_text=" | ".join(rows),
        value=value,
        unit=unit,
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        warnings=warnings,
        details=details,
    )
