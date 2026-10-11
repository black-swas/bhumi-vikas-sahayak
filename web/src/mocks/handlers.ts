import { http, HttpResponse } from "msw";
import type { AnswerCard, AskRequest } from "#/api/types";
import amendment from "./fixtures/answer_amendment_q11.json";
import answered from "./fixtures/answer_answered.json";
import errorCard from "./fixtures/answer_error.json";
import flagship from "./fixtures/answer_flagship.json";
import hindi from "./fixtures/answer_hindi_q14.json";
import needsReview from "./fixtures/answer_needs_review.json";
import notFound from "./fixtures/answer_not_found.json";
import evalLatest from "./fixtures/eval_latest.json";
import health from "./fixtures/health.json";
import rule56 from "./fixtures/rule_56.json";

const card = (fixture: unknown): AnswerCard =>
  structuredClone(fixture) as unknown as AnswerCard;

/** Front open space for a road width, from Rule 56(1)(a) (the mock mirrors the real table). */
function frontRow(road: number): { value: number; row: string } {
  if (road <= 9) return { value: 3.0, row: "1. Up to 9.0 meters 3.0 meters" };
  if (road <= 12)
    return {
      value: 3.6,
      row: "2. More than 9.0 meters and up to 12 meters 3.6 meters",
    };
  if (road <= 18)
    return {
      value: 4.5,
      row: "3. More than 12.0 meters and up to 18 meters 4.5 meters",
    };
  return { value: 6.0, row: "4. Above 18 meters 6.0 meters" };
}

function rearValue(plot: number): number {
  if (plot <= 40) return 0;
  if (plot <= 150) return 1.5;
  if (plot <= 225) return 2.5;
  return 3.0;
}

/** The edited-input path: the same flagship card with the calculators' numbers re-derived. */
function recompute(override: Record<string, unknown>): AnswerCard {
  const out = card(flagship);
  const road =
    typeof override.road_width_m === "number" ? override.road_width_m : 9;
  const plot =
    typeof override.plot_area_sqm === "number" ? override.plot_area_sqm : 200;
  const builtUp = Math.round(plot * 1.25 * 100) / 100;
  for (const c of out.calculations) {
    const inputs = c.inputs as Record<string, unknown>;
    if (c.calc_id === "front_open_space") {
      const row = frontRow(road);
      inputs.road_width_m = road;
      c.result.value = row.value;
      c.matched_row_text = row.row;
    } else if (c.calc_id === "rear_open_space") {
      inputs.plot_area_sqm = plot;
      c.result.value = rearValue(plot);
    } else if (c.calc_id === "max_built_up") {
      inputs.plot_area_sqm = plot;
      c.result.value = builtUp;
    } else if (
      c.calc_id === "application_fee" ||
      c.calc_id === "permission_fee"
    ) {
      inputs.built_up_area_sqm = builtUp;
      if (c.calc_id === "application_fee") c.result.value = builtUp;
    }
  }
  out.meta.calls = 0;
  out.meta.latency_ms = 4;
  out.meta.model_time_s = {};
  out.meta.providers = { A: "offline", B: "none" };
  return out;
}

const hasDevanagari = (text: string) => /[ऀ-ॿ]/.test(text);

function pickCard(question: string): AnswerCard {
  if (/property tax|market rate|aadhaar/i.test(question)) return card(notFound);
  if (/lift/i.test(question)) return card(answered);
  if (/development permission|\b300\b/i.test(question)) return card(amendment);
  if (/rule 103|development plan|review/i.test(question))
    return card(needsReview);
  if (/error-test/i.test(question)) return card(errorCard);
  if (hasDevanagari(question)) return card(hindi);
  return card(flagship);
}

export const handlers = [
  http.get("/api/health", () => HttpResponse.json(health)),

  http.post("/api/ask", async ({ request }) => {
    const body = (await request.json()) as AskRequest;
    const result = body.params_override
      ? recompute(body.params_override as Record<string, unknown>)
      : pickCard(body.question);
    result.question = body.question;
    return HttpResponse.json(result);
  }),

  http.get("/api/rule/:ruleId", ({ params }) =>
    params.ruleId === "56"
      ? HttpResponse.json(rule56)
      : HttpResponse.json({ detail: "No such rule" }, { status: 404 }),
  ),

  http.get("/api/eval/latest", () => HttpResponse.json(evalLatest)),

  http.post("/api/feedback", () =>
    HttpResponse.json({ ack_id: "mock-ack-001", stored: true }),
  ),
];
