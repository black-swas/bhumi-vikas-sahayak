"""C10 Rule 12-A instant/deemed approval: the plot-area threshold only (p.21).

This states a fact about the area limit. It never says a citizen "qualifies": the other conditions
(individual plot holder, approved layout, affidavit, plan per the rules) are the clerk's to check.
Rule 12-A is not Rule 28 (deemed sanction after the authority's silence).
"""

from app.schemas import CalculationResult

from ._common import D, fmt_num, load_table, positive, result


def instant_approval_threshold(plot_area_sqm: float, use: str | None = None) -> CalculationResult:
    area = positive("plot_area_sqm", plot_area_sqm, 1e7)
    t = load_table("12_a_instant_approval")
    limit = D(t["threshold"]["plot_area_sqm_le"])
    assumptions = []
    if use is None or use == "unknown":
        use = "residential"
        assumptions.append("Use assumed to be residential")
    inputs = {"plot_area_sqm": float(area), "use": use}

    if use != "residential":
        value = "not_applicable"
        statement = "Rule 12-A covers residential plots only"
    elif area <= limit:
        value = "within_limit"
        statement = (
            f"A plot of {fmt_num(area)} sq m is within the Rule 12-A area limit "
            f"of {fmt_num(limit)} sq m"
        )
    else:
        value = "above_limit"
        statement = (
            f"A plot of {fmt_num(area)} sq m is above the {fmt_num(limit)} sq m limit of Rule 12-A"
        )
    return result(
        calc_id="instant_approval_threshold",
        inputs=inputs,
        matched_row_text=t["threshold"]["row_text"],
        value=value,
        unit="",
        rule="12-A",
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=assumptions,
        warnings=[
            "This is the area limit only, not a decision: Rule 12-A has further conditions "
            "(individual plot holder, layout approved by Town & Country Planning, affidavit, plan "
            "as per the rules) for the clerk to check",
            "The limit is as in the text consolidated to 06/03/2025 and may have changed since",
        ],
        details={
            "threshold_sqm": float(limit),
            "statement": statement,
            "conditions": [c["row_text"] for c in t["conditions"]],
        },
    )
