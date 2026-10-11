"""Unit conversion to square metres and metres (SPEC §10). Every conversion explains itself."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ._common import CalcError, fmt_num, positive

# unit -> (factor, label)
AREA_UNITS = {
    "sqm": ("1", "sq m"),
    "sqft": ("0.09290304", "sq ft"),
    "sqyd": ("0.83612736", "sq yd"),
    "acre": ("4046.8564224", "acre"),
    "ha": ("10000", "ha"),
}
LENGTH_UNITS = {
    "m": ("1", "m"),
    "ft": ("0.3048", "ft"),
}
_AREA_ALIASES = {
    "sqm": "sqm", "sq m": "sqm", "sq.m": "sqm", "sq.m.": "sqm", "m2": "sqm", "square meter": "sqm",
    "square metre": "sqm", "square meters": "sqm", "square metres": "sqm",
    "sqft": "sqft", "sq ft": "sqft", "sq.ft": "sqft", "sq.ft.": "sqft", "square feet": "sqft",
    "sqyd": "sqyd", "sq yd": "sqyd", "sq.yd": "sqyd", "gaj": "sqyd", "square yard": "sqyd",
    "square yards": "sqyd",
    "acre": "acre", "acres": "acre",
    "ha": "ha", "hectare": "ha", "hectares": "ha",
}  # fmt: skip
_LENGTH_ALIASES = {
    "m": "m", "meter": "m", "metre": "m", "meters": "m", "metres": "m", "mtr": "m",
    "ft": "ft", "feet": "ft", "foot": "ft",
}  # fmt: skip


@dataclass(frozen=True)
class Conversion:
    input_value: float
    input_unit: str  # canonical code
    factor: str
    value: float  # in sq m, or in m
    unit: str  # "sq m" or "m"
    text: str  # "1,500 sq ft × 0.09290304 = 139.3546 sq m"


def _convert(value, unit: str, table: dict, aliases: dict, target: str, name: str, maximum: float):
    code = aliases.get(str(unit).strip().lower())
    if code is None:
        raise CalcError(f"unknown {name} unit: {unit!r}")
    factor, label = table[code]
    d = positive(name, value, maximum)
    out = (d * Decimal(factor)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if code in ("sqm", "m"):
        text = f"{fmt_num(d)} {target}"
    else:
        text = f"{fmt_num(d)} {label} × {factor} = {fmt_num(out)} {target}"
    return Conversion(float(d), code, factor, float(out), target, text)


def to_sqm(value, unit: str = "sqm") -> Conversion:
    return _convert(value, unit, AREA_UNITS, _AREA_ALIASES, "sq m", "area", 1e9)


def to_m(value, unit: str = "m") -> Conversion:
    return _convert(value, unit, LENGTH_UNITS, _LENGTH_ALIASES, "m", "length", 1e6)
