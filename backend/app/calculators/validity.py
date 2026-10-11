"""C8 duration of a sanction: Rule 23 (p.41). Three years, then up to two one-year revalidations,
and the five-year limit is never relaxed."""

from datetime import date

from app.schemas import CalculationResult

from ._common import CalcError, format_date, load_table, result


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return date(d.year + years, 2, 28)


def permission_validity(
    grant_date: date | None = None, grant_year: int | None = None
) -> CalculationResult:
    if grant_date is not None and grant_year is not None and grant_date.year != grant_year:
        raise CalcError("grant_year does not match grant_date")
    t = load_table("23_validity")
    initial = t["initial_validity"]["years"]
    terms = t["revalidation"]["terms"]
    per_term = t["revalidation"]["years_per_term"]
    cap = t["five_year_limit"]["years"]

    details: dict = {
        "initial_years": initial,
        "revalidation_terms": terms,
        "revalidation_years_each": per_term,
        "cap_years": cap,
        "no_lapse_if_execution_begins": True,
    }
    assumptions = []
    inputs: dict = {}
    if grant_date is not None:
        inputs["grant_date"] = grant_date.isoformat()
        expiries = [_add_years(grant_date, initial + per_term * i) for i in range(terms + 1)]
        details |= {
            "grant_date_display": format_date(grant_date),
            "initial_expiry": expiries[0].isoformat(),
            "initial_expiry_display": format_date(expiries[0]),
            "final_expiry": expiries[-1].isoformat(),
            "final_expiry_display": format_date(expiries[-1]),
            "five_year_limit_display": format_date(_add_years(grant_date, cap)),
        }
    elif grant_year is not None:
        inputs["grant_year"] = grant_year
        assumptions.append("Only the year was given: exact dates need the date of grant")
    else:
        assumptions.append("No grant date was given: the terms are shown without dates")

    matched = " | ".join(
        [
            t["initial_validity"]["row_text"],
            t["revalidation"]["row_text"],
            t["five_year_limit"]["row_text"],
        ]
    )
    return result(
        calc_id="permission_validity",
        inputs=inputs,
        matched_row_text=matched,
        value=initial,
        unit="years",
        rule=t["rule"],
        sub_rule=t["sub_rule"],
        page=t["page"],
        assumptions=assumptions,
        warnings=[
            "Rule 23(1) as written covers development permission under Section 30 of the Act",
            "Rule 23(3): once execution begins within the validity, the permission does not lapse "
            "and no revalidation is required",
        ],
        details=details,
    )
