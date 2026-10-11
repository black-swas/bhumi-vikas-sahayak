"""Shared helpers for the calculators (SPEC §10). Numbers come from data/tables/*.json only."""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Any

from app.schemas import CalculationResult, CalcValue

TABLES_DIR = Path(__file__).resolve().parents[2] / "data" / "tables"

DP_PRECEDENCE_WARNING = (
    "Rule 103: norms in the Bhopal Development Plan take precedence over these rules; "
    "Rule 61 Table 8: FAR may be adopted as provided in the Development Plan. "
    "Check the Development Plan before finalising."
)
HEIGHT_LIMIT_RULE_56_M = 12.5


class CalcError(ValueError):
    """Invalid input (non-positive, absurdly large, unknown unit or category)."""


class MissingInput(CalcError):
    """A required input was not supplied; ``missing`` names what the clerk must provide."""

    def __init__(self, *missing: str):
        super().__init__("missing input: " + ", ".join(missing))
        self.missing = list(missing)


@cache
def _load(name: str) -> str:
    return (TABLES_DIR / f"{name}.json").read_text(encoding="utf-8")


def load_table(name: str) -> dict:
    """A fresh copy of a table, so callers can never mutate the cached data."""
    return json.loads(_load(name))


def D(x: Any) -> Decimal:
    return Decimal(str(x))


def positive(name: str, x: Any, maximum: float) -> Decimal:
    try:
        d = D(x)
    except Exception as e:  # noqa: BLE001 - any parse failure is an input error
        raise CalcError(f"{name} is not a number") from e
    if not d.is_finite() or d <= 0:
        raise CalcError(f"{name} must be greater than zero")
    if d > D(maximum):
        raise CalcError(f"{name} is above the sane maximum of {maximum}")
    return d


def in_band(x: Decimal, gt: Any, le: Any) -> bool:
    return (gt is None or x > D(gt)) and (le is None or x <= D(le))


def find_band(rows: list[dict], x: Decimal) -> dict | None:
    return next((r for r in rows if in_band(x, r.get("gt"), r.get("le"))), None)


def num(d: Decimal | float | int, places: int = 2) -> float:
    q = Decimal(1).scaleb(-places)
    return float(D(d).quantize(q, rounding=ROUND_HALF_UP))


def fmt_num(x: Any) -> str:
    """250.0 -> '250', 1.25 -> '1.25' (no exponent, no trailing zeros)."""
    return format(D(x).normalize(), "f")


def format_inr(amount: Any) -> str:
    """Indian digit grouping: 125000 -> '₹1,25,000'; paise only when present."""
    d = D(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, _, frac = format(d, "f").partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while head:
        groups.insert(0, head[-2:])
        head = head[:-2]
    grouped = ",".join([*groups, tail]) if groups else tail
    return f"₹{grouped}" + (f".{frac}" if frac != "00" else "")


def format_date(d: date) -> str:
    """DD/MM/YYYY (the clerk's convention; dates are IST calendar dates)."""
    return d.strftime("%d/%m/%Y")


def result(
    *,
    calc_id: str,
    inputs: dict[str, Any],
    matched_row_text: str,
    value: float | str | None,
    unit: str,
    rule: str,
    sub_rule: str,
    page: int,
    assumptions: list[str] | None = None,
    warnings: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> CalculationResult:
    return CalculationResult(
        calc_id=calc_id,
        inputs=inputs,
        matched_row_text=matched_row_text,
        result=CalcValue(value=value, unit=unit),
        rule=rule,
        sub_rule=sub_rule,
        page=page,
        assumptions=assumptions or [],
        warnings=warnings or [],
        details=details or {},
    )


def height_assumption(height_m: Any) -> list[str]:
    if height_m is None:
        return ["Building height assumed to be 12.5 m or less (Rule 56 applies)"]
    return []


def above_rule_56(calc_id: str, inputs: dict, height_m: Decimal, rule: str, sub: str, page: int):
    """Result for a height above 12.5 m: Rule 56's tables do not apply (see Rule 42)."""
    return result(
        calc_id=calc_id,
        inputs=inputs,
        matched_row_text="",
        value=None,
        unit="",
        rule=rule,
        sub_rule=sub,
        page=page,
        warnings=[
            f"Height {fmt_num(height_m)} m is above 12.5 m: Rule 56's open-space tables do not "
            "apply; Rule 56(5) refers to Tables 4 and 5 of Rule 42 (see the high-rise norms)"
        ],
        details={"routed_to": "high_rise_norms"},
    )
