import type { ColorThemeDefinition, ColorThemeKey } from "../types";
import { lightPlus } from "./light-plus";
import { neutralDark } from "./neutral-dark";

/**
 * The theme registry. A counter PC sits under office lights, so the default is light.
 *
 * To add a theme: create a sibling module exporting a `ColorThemeDefinition`,
 * add its key to `ColorThemeKey` in `../types.ts`, and register it below.
 */
export const COLOR_THEMES: Record<ColorThemeKey, ColorThemeDefinition> = {
  "light-plus": lightPlus,
  "neutral-dark": neutralDark,
};

export const DEFAULT_COLOR_THEME: ColorThemeKey = "light-plus";

export const AVAILABLE_COLOR_THEMES = Object.entries(COLOR_THEMES).map(
  ([key, def]) => ({ key: key as ColorThemeKey, label: def.label }),
);
