"""C7 clearance from overhead electric lines: Rule 52(1) (p.69)."""

from app.schemas import CalculationResult

from ._common import MissingInput, load_table, result

VOLTAGES = ("low_medium", "high_upto_33kv", "extra_high")
_SUB_RULES = {"low_medium": "(1)(a)", "high_upto_33kv": "(1)(b)", "extra_high": "(1)(c)"}


def electric_clearance(voltage: str | None) -> CalculationResult:
    if voltage not in VOLTAGES:
        raise MissingInput("voltage")
    t = load_table("52_electric")
    row = next(r for r in t["rows"] if r["voltage"] == voltage)
    more = t["whichever_is_more"]["row_text"]
    warnings = [
        "Or the clearance in the applicable Electricity Rules, whichever is more (Rule 52(1))"
    ]
    rows = [row["row_text"]]
    if voltage == "extra_high":
        note = t["extra_high_note"]
        rows.append(note["row_text"])
        value, details = (
            note["corridor_m"],
            {
                "corridor_m": note["corridor_m"],
                "each_side_of_centre_line_m": note["each_side_of_centre_line_m"],
                "vertical_m": None,
                "horizontal_m": None,
            },
        )
    else:
        value, details = (
            row["vertical_m"],
            {
                "vertical_m": row["vertical_m"],
                "horizontal_m": row["horizontal_m"],
            },
        )
    details["rule_text"] = more
    return result(
        calc_id="electric_line_clearance",
        inputs={"voltage": voltage},
        matched_row_text=" | ".join(rows),
        value=value,
        unit="m",
        rule=t["rule"],
        sub_rule=_SUB_RULES[voltage],
        page=t["page"],
        warnings=warnings,
        details=details,
    )
