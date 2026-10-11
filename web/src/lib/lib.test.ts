import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
import translations from "#/i18n/translation.json";
import {
  formatInr,
  formatIst,
  formatNumber,
  formatResult,
  quoteRegex,
  ruleFromChunkId,
  splitAtQuote,
} from "#/lib/format";
import { chipsFor, overrideFor } from "#/lib/chips";
import { FIXTURES, cardOf } from "#/test-utils";

const require = createRequire(import.meta.url);
const { checkTranslations, getSupportedLanguageCodes } =
  require("../../scripts/check-translation-completeness.cjs") as {
    checkTranslations: (
      j: unknown,
      langs: string[],
    ) => {
      missing: Record<string, string[]>;
      extra: Record<string, string[]>;
      untranslated: Record<string, string>;
    };
    getSupportedLanguageCodes: () => string[];
  };

describe("formatting", () => {
  it("groups rupees the Indian way", () => {
    expect(formatInr(3000)).toBe("₹3,000");
    expect(formatInr(125000)).toBe("₹1,25,000");
    expect(formatInr(10000000)).toBe("₹1,00,00,000");
    expect(formatInr(750)).toBe("₹750");
    expect(formatInr(75.5)).toBe("₹75.50");
  });
  it("trims numbers without exponents", () => {
    expect(formatNumber(250)).toBe("250");
    expect(formatNumber(1.25)).toBe("1.25");
    expect(formatNumber(139.3546)).toBe("139.3546");
  });
  it("formats calculator results", () => {
    expect(formatResult({ value: 3, unit: "m" })).toBe("3 m");
    expect(formatResult({ value: 3000, unit: "INR" })).toBe("₹3,000");
    expect(formatResult({ value: 0, unit: "m" }, "Nil")).toBe("Nil");
    expect(formatResult({ value: null, unit: "" })).toBeNull();
    expect(formatResult({ value: "above_limit", unit: "" })).toBe(
      "above_limit",
    );
  });
  it("formats time in IST whatever the PC zone is", () => {
    expect(formatIst("2026-10-11T09:30:00.000Z")).toBe("11/10/2026 15:00");
  });
  it("maps chunk ids to rule ids", () => {
    expect(ruleFromChunkId("r83-0-0")).toBe("83");
    expect(ruleFromChunkId("r12-a-0")).toBe("12-A");
    expect(ruleFromChunkId("r26-b-1-0")).toBe("26-B");
    expect(ruleFromChunkId("nonsense")).toBeNull();
  });
  it("finds a quote however the whitespace falls", () => {
    expect(quoteRegex("a  b\nc")?.test("a b   c")).toBe(true);
    expect(quoteRegex("1.25 (x)")?.test("FAR 1.25 (X) ok")).toBe(true);
    expect(quoteRegex("1.25")?.test("1x25")).toBe(false); // the dot is literal
    expect(splitAtQuote("front 3.0 meters\n rear", "3.0   meters")).toEqual([
      "front ",
      "3.0 meters",
      "\n rear",
    ]);
    expect(splitAtQuote("nothing here", "absent")).toBeNull();
    expect(splitAtQuote("x", undefined)).toBeNull();
  });
});

describe("chips", () => {
  it("reads the inputs from the calculators and flags assumptions", () => {
    const chips = Object.fromEntries(
      chipsFor(cardOf(FIXTURES.PARTIAL)).map((c) => [c.key, c]),
    );
    expect(chips.plot_area_sqm).toMatchObject({ value: 200, assumed: false });
    expect(chips.road_width_m).toMatchObject({ value: 9 });
    expect(chips.height_m).toMatchObject({ value: null, assumed: true });
    expect(chips.use).toMatchObject({ value: "residential", assumed: true });
    expect(chips.building_type).toMatchObject({ value: null });
  });
  it("has none for lookups, not-found and review cards", () => {
    for (const f of [
      FIXTURES.ANSWERED,
      FIXTURES.NOT_FOUND,
      FIXTURES.NEEDS_REVIEW,
    ]) {
      expect(chipsFor(cardOf(f))).toEqual([]);
    }
  });
  it("builds an override that keeps real values and drops assumed ones", () => {
    const card = cardOf(FIXTURES.PARTIAL);
    const o = overrideFor(card, chipsFor(card), "road_width_m", 12);
    expect(o).toEqual({
      intent: "plot_norms",
      plot_area_sqm: 200,
      road_width_m: 12,
    });
    const o2 = overrideFor(card, chipsFor(card), "building_type", "row");
    expect(o2).toMatchObject({ building_type: "row", road_width_m: 9 });
  });
});

describe("translations", () => {
  it("supports exactly English and Hindi", () => {
    expect(getSupportedLanguageCodes()).toEqual(["en", "hi"]);
  });
  it("has Hindi for every English key, with no copied English", () => {
    const r = checkTranslations(translations, ["en", "hi"]);
    expect(r.missing).toEqual({});
    expect(r.extra).toEqual({});
    expect(r.untranslated).toEqual({});
  });
  it("the check catches a key without Hindi", () => {
    const r = checkTranslations(
      { A$B: { en: "x" }, C$D: { en: "same", hi: "same" } },
      ["en", "hi"],
    );
    expect(r.missing).toEqual({ A$B: ["hi"] });
    expect(r.untranslated).toEqual({ C$D: "same" });
  });
  it("uses the same placeholders in both languages", () => {
    const names = (s: string) =>
      [...s.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort();
    for (const [key, v] of Object.entries(
      translations as Record<string, { en: string; hi: string }>,
    )) {
      expect(names(v.hi), key).toEqual(names(v.en));
    }
  });
});
