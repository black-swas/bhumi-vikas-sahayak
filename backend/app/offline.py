"""Offline understanding (SPEC §7 step 3, §18): regex parameters + keyword intent + glossary.

Used when the model is unreachable, in offline or replay mode, and for ``params_override``
re-runs. It reads only what the clerk typed; V8 still checks every number against the question.
"""

import re
from dataclasses import dataclass, field

from .corpus.index import guess_intent
from .i18n import NormalizedQuestion

_NUM = r"(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_AREA = re.compile(
    _NUM
    + r"\s*(sq\.?\s?m(?:eters?|etres?)?|sqm|m2|sq\.?\s?ft|sqft|square feet"
    + r"|sq\.?\s?yd|gaj|acres?|ha|hectares?)\b",
    re.IGNORECASE,
)
_ROAD_BEFORE = re.compile(
    _NUM + r"\s*(?:m|meters?|metres?|mtr)\s*(?:wide\s*|चौड़ी\s*|चौड़ा\s*)?(?:road|street|सड़क|सडक)",
    re.IGNORECASE,
)
_ROAD_AFTER = re.compile(
    r"(?:road|street|सड़क|सडक)[^\d]{0,25}" + _NUM + r"\s*(?:m|meters?|metres?|mtr)\b",
    re.IGNORECASE,
)
_HEIGHT_BEFORE = re.compile(
    _NUM + r"\s*(?:m|meters?|metres?)\s*(?:tall|high|height|ऊंचा|ऊँचा)", re.IGNORECASE
)
_HEIGHT_AFTER = re.compile(
    r"(?:height|ऊंचाई|ऊँचाई)[^\d]{0,15}" + _NUM + r"\s*(?:m|meters?|metres?)\b", re.IGNORECASE
)
_FRONTAGE = re.compile(
    r"frontage[^\d]{0,15}" + _NUM + r"|" + _NUM + r"\s*(?:m|meters?)\s*frontage", re.IGNORECASE
)
# A built-up area is named right next to its number: "built-up area 75.5 sq m", "250 sq m
# built-up". "maximum built-up area for a 300 sq m plot" names the plot, not the built-up area.
_BUILT_BEFORE = re.compile(
    r"built[- ]?up(?:\s+area)?(?:\s+(?:of|is|=|:))?\s*:?\s*$|निर्मित क्षेत्र(?:फल)?\s*:?\s*$"
)
_BUILT_AFTER = re.compile(r"\s*(?:of\s+)?(?:built[- ]?up|निर्मित)")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})\b")
_SEATS = re.compile(_NUM + r"\s*seats?", re.IGNORECASE)

_CATEGORIES = [
    ("sub_city_centre", ("sub-city", "sub city")),
    ("city_centre", ("city centre", "city center")),
    ("community_centre", ("community cent",)),
    ("local_shopping_centre", ("local shopping",)),
    ("convenience_shopping_centre", ("convenience shopping",)),
]


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _unit(raw: str) -> str:
    key = re.sub(r"[^a-z0-9]", "", raw.lower())
    if key.startswith(("sqm", "sqmeter", "sqmetre")) or key == "m2":
        return "sqm"
    if key in ("sqft", "squarefeet"):
        return "sqft"
    if key.startswith("sqyd") or key == "gaj":
        return "sqyd"
    if key.startswith("acre"):
        return "acre"
    return "ha"


@dataclass
class OfflineUnderstanding:
    intent: str
    search_query_en: str
    params: dict
    in_scope: bool = True
    extras: dict = field(default_factory=dict)


def extract_params(text: str) -> tuple[dict, dict]:
    """(params with the Step A names, extras such as grant_year or commercial_category)."""
    t = " " + text.lower() + " "
    params: dict = {
        "plot_area": None, "plot_area_unit": None, "road_width_m": None, "height_m": None,
        "built_up_area_sqm": None, "frontage_m": None, "use": None, "building_type": None,
        "voltage": None,
    }  # fmt: skip
    for m in _AREA.finditer(text):
        before = text[max(0, m.start() - 30) : m.start()].lower()
        after = text[m.end() : m.end() + 16].lower()  # "250 sq m built-up area"
        value, unit = _to_float(m.group(1)), _unit(m.group(2))
        if _BUILT_BEFORE.search(before) or _BUILT_AFTER.match(after):
            if params["built_up_area_sqm"] is None and unit == "sqm":
                params["built_up_area_sqm"] = value
        elif params["plot_area"] is None:
            params["plot_area"], params["plot_area_unit"] = value, unit
    for pattern, key in (
        (_ROAD_BEFORE, "road_width_m"),
        (_ROAD_AFTER, "road_width_m"),
        (_HEIGHT_BEFORE, "height_m"),
        (_HEIGHT_AFTER, "height_m"),
    ):
        m = pattern.search(text)
        if m and params[key] is None:
            params[key] = _to_float(m.group(1))
    m = _FRONTAGE.search(text)
    if m:
        params["frontage_m"] = _to_float(m.group(1) or m.group(2))

    if re.search(r"commercial|\bshop|दुकान|व्यावसायिक", t):
        params["use"] = "shop_cum_residence" if "residence" in t and "shop" in t else "commercial"
    elif re.search(r"residen|\bhouse|\bhome|घर|मकान|आवासीय", t):
        params["use"] = "residential"
    if "semi-detached" in t or "semi detached" in t:
        params["building_type"] = "semi_detached"
    elif re.search(r"\brow\b[- ]?(?:type|house|housing)?", t):
        params["building_type"] = "row"
    elif re.search(r"\bdetached", t):
        params["building_type"] = "detached"
    if re.search(r"extra[- ]high|\behv\b", t):
        params["voltage"] = "extra_high"
    elif re.search(r"high[- ]voltage|\bhigh tension|\bht line", t):
        params["voltage"] = "high_upto_33kv"
    elif re.search(r"low[- ]voltage|medium[- ]voltage|low and medium|कम वोल्टेज|\bservice line", t):
        params["voltage"] = "low_medium"

    extras: dict = {}
    low = text.lower()
    for category, words in _CATEGORIES:
        if any(w in low for w in words):
            extras["commercial_category"] = category
            break
    if (d := _DATE.search(text)) is not None:
        extras["grant_date"] = (int(d.group(3)), int(d.group(2)), int(d.group(1)))
    elif (y := _YEAR.search(text)) is not None and re.search(
        r"grant|granted|issued|sanction|permission|मिली|स्वीकृत|अनुमति", low
    ):
        extras["grant_year"] = int(y.group())
    if (s := _SEATS.search(text)) is not None:
        extras["cinema_seats"] = int(_to_float(s.group(1)))
    return params, extras


def offline_understand(nq: NormalizedQuestion) -> OfflineUnderstanding:
    params, extras = extract_params(nq.text)
    intent = guess_intent(nq.text) or "general_lookup"
    if intent == "general_lookup" and params["road_width_m"] and params["plot_area"]:
        intent = "plot_norms"
    return OfflineUnderstanding(
        intent=intent,
        search_query_en=nq.text,
        params=params,
        in_scope=intent != "out_of_scope",
        extras=extras,
    )
