"""Contracts: AnswerCard (SPEC §15) and the LLM step schemas (SPEC §11)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Lang = Literal["en", "hi"]
Status = Literal["ANSWERED", "PARTIAL", "NOT_FOUND", "NEEDS_REVIEW", "ERROR"]

Intent = Literal[
    "plot_norms",
    "front_open_space",
    "rear_open_space",
    "side_open_space",
    "far_built_up",
    "fee",
    "electric_line",
    "high_rise_norms",
    "farm_house",
    "permission_validity",
    "deemed_permission",
    "instant_approval",
    "water_body_site",
    "plan_signing",
    "application_documents",
    "plan_change",
    "development_permission_need",
    "dp_vs_rules",
    "lifts",
    "general_lookup",
    "out_of_scope",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- API -------------------------------------------------------------------------------------


class AskRequest(Strict):
    question: str = Field(max_length=500)
    lang: Lang | None = None
    params_override: dict[str, Any] | None = None


class CalcValue(Strict):
    value: float | str | None
    unit: str = ""


class CalculationResult(Strict):
    calc_id: str
    inputs: dict[str, Any]
    matched_row_text: str
    result: CalcValue
    rule: str
    sub_rule: str
    page: int
    assumptions: list[str] = []
    warnings: list[str] = []
    # extra computed figures (both sides of a setback, band edges, matched rows); optional
    details: dict[str, Any] = {}


class Citation(Strict):
    chunk_id: str
    rule: str
    label: str
    title: str
    page: int
    quote: str
    verified: bool
    pdf_en: str
    pdf_hi: str


class Warning(Strict):  # noqa: A001 - name fixed by SPEC §15
    type: str
    text: str
    id: str | None = None


class Version(Strict):
    label: str
    corpus_sha256: str
    amendments: list[str] = []


class Meta(Strict):
    providers: dict[str, str] = {}
    models: dict[str, str] = {}
    runtime_config_version: int | None = None
    latency_ms: int | None = None
    model_time_s: dict[str, float] = {}
    tokens: dict[str, int] = {}  # input / output / cached, summed over the model calls
    calls: int = 0
    replay: bool = False


class AnswerCard(Strict):
    request_id: str
    question: str
    lang: Lang
    status: Status
    intent: str
    answer: str
    calculations: list[CalculationResult] = []
    citations: list[Citation] = []
    warnings: list[Warning] = []
    missing_info: list[str] = []
    candidates: list[str] = []
    version: Version
    meta: Meta


# --- Step A (Cerebras): SPEC §11 -------------------------------------------------------------

PlotAreaUnit = Literal["sqm", "sqft", "sqyd", "acre", "ha", "none"]
Use = Literal[
    "residential",
    "commercial",
    "shop_cum_residence",
    "industrial",
    "public",
    "cinema",
    "other",
    "unknown",
]
BuildingType = Literal["detached", "semi_detached", "row", "unknown"]
Voltage = Literal["low_medium", "high_upto_33kv", "extra_high", "unknown"]


class UnderstandParams(Strict):
    """Unknown numbers are -1; code turns them into None and drops any not in the question."""

    plot_area: float
    plot_area_unit: PlotAreaUnit
    road_width_m: float
    height_m: float
    built_up_area_sqm: float
    frontage_m: float
    use: Use
    building_type: BuildingType
    voltage: Voltage


class UnderstandOutput(Strict):
    in_scope: bool
    intent: Intent
    search_query_en: str
    params: UnderstandParams


# --- Step B (Anthropic): SPEC §11 ------------------------------------------------------------


class ComposeCitation(Strict):
    chunk_id: str
    quote: str


class ComposeOutput(Strict):
    status: Literal["answered", "not_found", "need_more_info"]
    answer: str  # <= 90 words, checked after parsing
    citations: list[ComposeCitation]
    missing_info: list[str]
