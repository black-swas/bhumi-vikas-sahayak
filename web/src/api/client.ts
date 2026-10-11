import type {
  AnswerCard,
  AskRequest,
  EvalReport,
  FeedbackAck,
  FeedbackIn,
  Health,
  RuleText,
} from "./types";

// Empty means same origin: the dev server proxies /api, and in production the API is served
// from the same host. Never put a secret in a VITE_ variable: it is compiled into the bundle.
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "network");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // the body was not JSON
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

const jsonPost = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  ask: (body: AskRequest) => request<AnswerCard>("/api/ask", jsonPost(body)),
  health: () => request<Health>("/api/health"),
  rule: (id: string) =>
    request<RuleText>(`/api/rule/${encodeURIComponent(id)}`),
  evalLatest: () => request<EvalReport>("/api/eval/latest"),
  feedback: (body: FeedbackIn) =>
    request<FeedbackAck>("/api/feedback", jsonPost(body)),
};
