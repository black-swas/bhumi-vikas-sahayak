import type { AnswerCard, CalculationResult } from "#/api/types";

export type ChipKey =
  | "plot_area_sqm"
  | "road_width_m"
  | "height_m"
  | "building_type"
  | "use";

export interface ChipValue {
  key: ChipKey;
  /** The value the calculators used, or null when the clerk has not given one. */
  value: string | number | null;
  /** True when the calculators fell back to a default (height up to 12.5 m, residential use). */
  assumed: boolean;
}

const ORDER: ChipKey[] = [
  "plot_area_sqm",
  "road_width_m",
  "height_m",
  "building_type",
  "use",
];

/** Intents for which the editable inputs make sense (the ones the calculators answer). */
const CHIP_INTENTS = new Set([
  "plot_norms",
  "front_open_space",
  "rear_open_space",
  "side_open_space",
  "far_built_up",
  "fee",
  "high_rise_norms",
  "instant_approval",
]);

function firstInput(calcs: CalculationResult[], key: string): unknown {
  for (const c of calcs) {
    const v = (c.inputs as Record<string, unknown>)[key];
    if (v !== undefined && v !== null) return v;
  }
  return null;
}

/** The inputs behind an answer, read from the calculators' own `inputs`, never re-derived. */
export function chipsFor(card: AnswerCard): ChipValue[] {
  if (!CHIP_INTENTS.has(card.intent) || card.calculations.length === 0)
    return [];
  const calcs = card.calculations;
  const assumedText = calcs.flatMap((c) => c.assumptions).join(" ");
  const sideTypes = calcs
    .filter((c) => c.calc_id === "side_open_space")
    .map((c) => (c.inputs as Record<string, unknown>).building_type)
    .filter((v): v is string => typeof v === "string");

  const values: Record<ChipKey, ChipValue> = {
    plot_area_sqm: chip(
      "plot_area_sqm",
      firstInput(calcs, "plot_area_sqm"),
      false,
    ),
    road_width_m: chip(
      "road_width_m",
      firstInput(calcs, "road_width_m"),
      false,
    ),
    height_m: chip(
      "height_m",
      firstInput(calcs, "height_m"),
      firstInput(calcs, "height_m") === null &&
        /height assumed/i.test(assumedText),
    ),
    // Several side-space results mean the clerk has not chosen a type: leave the chip empty.
    building_type: chip(
      "building_type",
      sideTypes.length === 1 ? sideTypes[0] : null,
      false,
    ),
    use: chip(
      "use",
      firstInput(calcs, "use"),
      /use assumed/i.test(assumedText),
    ),
  };
  return ORDER.map((k) => values[k]);
}

function chip(key: ChipKey, value: unknown, assumed: boolean): ChipValue {
  const ok = typeof value === "string" || typeof value === "number";
  return { key, value: ok ? value : null, assumed };
}

/** The override that re-runs the calculators with one chip changed and the rest kept. */
export function overrideFor(
  card: AnswerCard,
  chips: ChipValue[],
  key: ChipKey,
  value: string | number | null,
): Record<string, unknown> {
  const out: Record<string, unknown> = { intent: card.intent };
  for (const c of chips) {
    if (c.value !== null && !(c.assumed && c.key !== key)) out[c.key] = c.value;
  }
  // A built-up area the calculators assumed (the FAR maximum) must follow the plot, so it is
  // only carried over when it came from the question.
  const assumedBuiltUp = card.calculations.some((c) =>
    c.assumptions.some((a) => /actual built-up area was not given/i.test(a)),
  );
  const builtUp = firstInput(card.calculations, "built_up_area_sqm");
  if (typeof builtUp === "number" && !assumedBuiltUp)
    out.built_up_area_sqm = builtUp;
  out[key] = value;
  return out;
}
