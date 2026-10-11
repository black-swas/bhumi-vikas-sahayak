import type { CalculationResult } from "#/api/types";

/** 250 -> "250", 1.25 -> "1.25": no trailing zeros, no exponent. */
export function formatNumber(value: number): string {
  return Number.isInteger(value)
    ? String(value)
    : String(Number(value.toFixed(4)));
}

/** Rupees with Indian digit grouping: 125000 -> "₹1,25,000". */
export function formatInr(value: number): string {
  const fixed = Number.isInteger(value) ? value.toString() : value.toFixed(2);
  const [whole, frac] = fixed.split(".");
  const head = whole.slice(0, -3);
  const tail = whole.slice(-3);
  const grouped = head
    ? `${head.replace(/\B(?=(\d{2})+(?!\d))/g, ",")},${tail}`
    : tail;
  return `₹${grouped}${frac ? `.${frac}` : ""}`;
}

/** The value a calculator produced, as the clerk reads it. Null when it has no number. */
export function formatResult(
  result: CalculationResult["result"],
  display?: unknown,
): string | null {
  const { value, unit } = result;
  if (typeof display === "string" && display === "Nil") return display;
  if (value === null || value === undefined) return null;
  if (typeof value === "string") return value;
  if (unit === "INR") return formatInr(value);
  return unit ? `${formatNumber(value)} ${unit}` : formatNumber(value);
}

/** DD/MM/YYYY HH:mm in Asia/Kolkata, the clerk's clock, whatever the PC's own zone is. */
export function formatIst(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")}/${get("month")}/${get("year")} ${get("hour")}:${get("minute")}`;
}

/** "r83-0-0" -> "83", "r12-a-0" -> "12-A", "r26-b-1-0" -> "26-B". */
export function ruleFromChunkId(chunkId: string): string | null {
  const m = /^r(\d+)(?:-([a-z]))?(?:-\d+)*$/.exec(chunkId);
  if (!m) return null;
  return m[2] ? `${m[1]}-${m[2].toUpperCase()}` : m[1];
}

/** A regex that finds `quote` inside `text` however the whitespace is laid out. */
export function quoteRegex(quote: string): RegExp | null {
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return new RegExp(escaped.join("\\s+"), "i");
}

/** Split `text` into [before, match, after] around the first occurrence of `quote`. */
export function splitAtQuote(
  text: string,
  quote: string | undefined,
): [string, string, string] | null {
  if (!quote) return null;
  const re = quoteRegex(quote);
  const m = re?.exec(text);
  if (!m) return null;
  return [text.slice(0, m.index), m[0], text.slice(m.index + m[0].length)];
}
