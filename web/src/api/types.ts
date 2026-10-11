// Types come from the backend's OpenAPI document (npm run gen:api), so the UI and the API
// cannot drift apart silently.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type AnswerCard = Schemas["AnswerCard"];
export type CalculationResult = Schemas["CalculationResult"];
export type Citation = Schemas["Citation"];
export type CardWarning = Schemas["Warning"];
export type AskRequest = Schemas["AskRequest"];
export type FeedbackIn = Schemas["FeedbackIn"];
export type FeedbackAck = Schemas["FeedbackAck"];

export type Status = AnswerCard["status"];
export type Lang = AnswerCard["lang"];
export type FeedbackReason = FeedbackIn["reason"];

/** GET /api/health: only the fields the UI uses. */
export interface Health {
  status: string;
  mode: "live" | "replay" | "offline";
  prototype: boolean;
  amendments: string[];
  corpus: { sha256: string; rules: number; chunks: number; pages: number };
}

/** GET /api/rule/{id} */
export interface RuleText {
  rule: string;
  title: string;
  parent: string | null;
  part: string | null;
  page_start: number;
  page_end: number;
  text: string;
  chunks: { id: string; label: string; pages: number[] }[];
  pdf_en: string;
  pdf_hi: string;
}

/** One case of evals/report.json (written by the evaluation harness). */
export interface EvalCase {
  id: string;
  question: string;
  expected_status: string;
  status: string;
  pass: boolean;
  latency_ms?: number;
}

/** GET /api/eval/latest: the report, or `{ available: false }` before one exists. */
export type EvalReport =
  | { available: false }
  | {
      available: true;
      generated_at?: string;
      runs?: number;
      summary: {
        status_accuracy: number;
        rule_hit: number;
        rule_hit_total: number;
        value_accuracy: number;
        abstention: number;
        fabrication_shown: number;
        fabrication_attempted: number;
        injection_resistance: number;
        latency_ms: { p50: number; p95: number; n: number; cold_p95?: number };
      };
      cases: EvalCase[];
    };
