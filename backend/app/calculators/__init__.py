"""Deterministic calculators C1-C10 (SPEC §10). Numbers never pass through a model."""

from app.schemas import CalculationResult

from ._common import CalcError, MissingInput
from .electric import electric_clearance
from .far import max_built_up
from .farm_house import farm_house
from .fees import application_fee, fees, is_high_rise, permission_fee
from .high_rise import high_rise_norms
from .instant_approval import instant_approval_threshold
from .setbacks import classify_plot_types, front_open_space, rear_open_space, side_open_space
from .units import to_m, to_sqm
from .validity import permission_validity

__all__ = [
    "CalcError",
    "MissingInput",
    "application_fee",
    "classify_plot_types",
    "electric_clearance",
    "farm_house",
    "fees",
    "front_open_space",
    "high_rise_norms",
    "instant_approval_threshold",
    "is_high_rise",
    "max_built_up",
    "permission_fee",
    "permission_validity",
    "plot_norms",
    "rear_open_space",
    "side_open_space",
    "to_m",
    "to_sqm",
]


def plot_norms(
    plot_area_sqm: float,
    road_width_m: float,
    height_m: float | None = None,
    frontage_m: float | None = None,
    building_type: str | None = None,
    use: str | None = None,
    built_up_area_sqm: float | None = None,
    commercial_category: str | None = None,
) -> list[CalculationResult]:
    """The combined `plot_norms` intent (the flagship question): C1-C5 and C10.

    Without a building type, side open space is computed for every type the plot size fits
    (detached excluded when it does not fit), so the clerk sees each case.
    """
    out = [
        front_open_space(road_width_m, height_m),
        rear_open_space(plot_area_sqm, height_m),
    ]
    types = classify_plot_types(plot_area_sqm, frontage_m)
    out.append(types)
    wanted = [building_type] if building_type else list(types.details["fits"])
    out.extend(side_open_space(bt, height_m, frontage_m) for bt in wanted)
    out.append(max_built_up(plot_area_sqm, use, commercial_category))
    out.extend(
        fees(
            built_up_area_sqm=built_up_area_sqm,
            plot_area_sqm=plot_area_sqm,
            use=use,
            height_m=height_m,
            commercial_category=commercial_category,
        )
    )
    out.append(instant_approval_threshold(plot_area_sqm, use))
    return out
