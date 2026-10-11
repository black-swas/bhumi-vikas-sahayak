"""Answer text for pure-calculation intents (SPEC §11): templates filled from calculator output.

The numbers in the text are the calculators' numbers, so no model ever writes a figure.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .calculators._common import fmt_num, format_inr
from .schemas import CalculationResult

TEMPLATES_FILE = Path(__file__).resolve().parents[1] / "data" / "templates.json"


@lru_cache(maxsize=1)
def _templates() -> dict:
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))


def message(key: str, lang: str, **fmt: str) -> str:
    return _templates()["messages"][key][lang].format(**fmt)


def missing_text(missing: list[str], lang: str) -> str:
    labels = _templates()["messages"]["missing_labels"]
    return ", ".join(labels.get(m, {}).get(lang, m) for m in missing)


def need_more_info(missing: list[str], lang: str) -> str:
    return message("need_more_info", lang, missing=missing_text(missing, lang))


def _term(name: str, lang: str) -> str:
    return _templates()["terms"].get(name, {}).get(lang, name)


def _sides_text(sides: list[float], lang: str) -> str:
    en = hi = ""
    s = [fmt_num(x) for x in sides]
    if not sides:
        return "none required (Nil)" if lang == "en" else "कोई आवश्यक नहीं (Nil)"
    if len(s) == 1:
        en, hi = f"{s[0]} m on one side", f"एक ओर {s[0]} मीटर"
    elif sides[0] == sides[1]:
        en, hi = f"{s[0]} m on both sides", f"दोनों ओर {s[0]} मीटर"
    else:
        en = f"{s[0]} m on one side and {s[1]} m on the other"
        hi = f"एक ओर {s[0]} मीटर और दूसरी ओर {s[1]} मीटर"
    return en if lang == "en" else hi


def _context(calc: CalculationResult, lang: str) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    for source in (calc.inputs, calc.details):
        for key, value in source.items():
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (int, float)):
                ctx[key] = fmt_num(value)
            elif isinstance(value, str):
                ctx[key] = value
    value = calc.result.value
    if isinstance(value, (int, float)):
        ctx["val"] = fmt_num(value)
        if calc.result.unit == "INR":
            ctx["inr"] = format_inr(value)
    ctx["unit"] = calc.result.unit
    d = calc.details
    if calc.calc_id == "rear_open_space" and "display" in d:
        nil = d["display"] == "Nil"
        ctx["display"] = d["display"]
        ctx["display_hi"] = "शून्य (Nil)" if nil else f"{fmt_num(value)} मीटर"
        if not nil:
            ctx["display"] = f"{fmt_num(value)} m"
    if calc.calc_id == "plot_types":
        ctx["fits_text"] = ", ".join(_term(t, lang) for t in d.get("fits", []))
        ctx.pop("display", None)
    if calc.calc_id == "side_open_space" and "sides_m" in d:
        ctx["sides_text"] = _sides_text(d["sides_m"], lang)
        ctx["type_text"] = _term(d["building_type"], lang)
    if calc.calc_id == "max_built_up" and "far" in d:
        ctx["far"] = fmt_num(d["far"])
    if calc.calc_id == "high_rise_norms" and d.get("table"):
        if d.get("max_height_m") is not None:
            ctx["height_text"] = f"up to {fmt_num(d['max_height_m'])} m"
            ctx["height_text_hi"] = f"{fmt_num(d['max_height_m'])} मीटर तक"
        elif d.get("height_display"):
            ctx["height_text"] = d["height_display"]
            ctx["height_text_hi"] = d["height_display"].replace("Above", "से अधिक:")
    if calc.calc_id == "farm_house" and "max_built_up_sqm" in d:
        ctx["plot_area_sqm"] = fmt_num(calc.inputs["plot_area_sqm"])
    if calc.calc_id == "instant_approval_threshold":
        ctx["threshold_sqm"] = fmt_num(d["threshold_sqm"])
    return ctx


def render_calc(calc: CalculationResult, lang: str) -> str:
    ctx = _context(calc, lang)
    key = calc.calc_id
    sentences = []
    for entry in _templates()["sections"].get(key, []):
        when = entry.get("when")
        value = calc.result.value
        if when == "none" and value is not None:
            continue
        if when not in (None, "none") and value != when:
            continue
        if when is None and value is None and key not in ("farm_house", "permission_validity"):
            continue
        if any(r not in ctx for r in entry.get("requires", [])):
            continue
        sentences.append(entry[lang].format(**ctx))
    return " ".join(sentences)


def render_answer(calcs: list[CalculationResult], lang: str) -> str:
    return "\n".join(t for t in (render_calc(c, lang) for c in calcs) if t)
