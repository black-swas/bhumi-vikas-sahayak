# Deploying the hosted copy on Vercel

The hosted copy is a convenience so the jury can try the tool without installing anything. The
**local run** (`.\run.ps1`) is the primary path and works with no internet and no key. A hosted copy
is online by definition, shows the PROTOTYPE banner like every other surface, and is never presented
as a BMC or MPSeDC service.

Facts below were checked against Vercel's docs on 11 Oct 2026 (`/docs/services`,
`/docs/services/routing`, `/docs/services/config-reference`, `/docs/frameworks/backend/fastapi`).
**Services is Beta**: re-read those pages before deploying.

## What gets deployed

One Git repository, one Vercel project, two services on one domain (`vercel.json` at the repo root):

| Service | Root | Receives | Notes |
|---|---|---|---|
| `web` | `web/` | everything except `/api/*` | React Router SPA (`ssr: false`), the Vercel preset in `react-router.config.ts`. `web/public/pdf/` is served from the CDN at `/pdf/rules-en.pdf` and `/pdf/rules-hi.pdf` |
| `api` | `backend/` | `/api/*` | FastAPI `app.main:app` on the Python runtime (3.12, from `.python-version`), one Vercel Function |

A service receives the **original** request path, so every FastAPI route is declared under `/api` and
nothing is rewritten. With `services` present, `functions`, `installCommand`, `buildCommand`,
`outputDirectory` and `framework` are not valid at the top level of `vercel.json`, so there are none.

## Environment variables

Set these in the Vercel project (Settings, Environment Variables) for **Production and Preview**.
Mark both keys **Sensitive** (dashboard checkbox, or `--sensitive` on `vercel env add`).

| Variable | Value | Sensitive | Why |
|---|---|:-:|---|
| `LLM_PROVIDER` | `live` | | `live`, `replay` or `offline`. With a key missing, that step degrades by itself |
| `UNDERSTAND_PROVIDER` | `cerebras` | | Step A |
| `ANSWER_PROVIDER` | `anthropic` | | Step B |
| `CEREBRAS_API_KEY` | a **dedicated** hosted-demo key | yes | Backend only. Never a `VITE_` variable |
| `ANTHROPIC_API_KEY` | a **dedicated** hosted-demo key with a monthly spend limit | yes | Backend only |
| `CEREBRAS_MODEL_UNDERSTAND` | `qwen-3.8-27b` | | Check `GET /v1/models` first |
| `ANTHROPIC_MODEL_ANSWER` | `claude-haiku-5-5` | | Exact ID, no date suffix |
| `AUDIT_SINK` | `stdout` | | One JSON line per question, no question text. Forced to `stdout` whenever Vercel sets `VERCEL`, so a stray `file` cannot break a read-only function |
| `SERVE_WEB` | `0` | | The CDN serves the web service. The backend ignores `SERVE_WEB=1` on Vercel |

Optional, same screen (defaults are in `.env.example`): `CEREBRAS_FALLBACK_MODEL_ID` (`gpt-oss-120b`),
`ANTHROPIC_EFFORT` (`low`), `ANTHROPIC_THINKING` (`default`), `MAX_TOKENS_UNDERSTAND` (300),
`MAX_TOKENS_ANSWER` (1500), `CEREBRAS_RPM_LIMIT` (4), `REQUEST_DEADLINE_S` (25; after it the answer
comes from the offline path). `DEMO_REPLAY=1` serves committed recordings with no keys (the backup).

**Never set** a `VITE_*` variable that holds a secret: Vite compiles every `VITE_*` value into the
public bundle. The web service needs no variables (`VITE_API_BASE_URL` stays empty: same origin).
Node for the web service must be 24.x (`engines` in `web/package.json`).

## Before the first deploy

```powershell
uv --directory backend run python scripts/preflight.py   # config, secrets, assets, entrypoint
uv --directory backend run pytest -q
npm run lint --prefix web ; npm test --prefix web ; npm run build --prefix web
```

`preflight.py` checks `vercel.json` against the expected services and rewrites, that `.env` is
ignored (it never opens it), that no key pattern or secret-looking `VITE_` variable is in the tree,
that the PDFs match `MANIFEST.json`, that the backend imports as `app.main:app` in hosted mode, and
that `run.ps1` parses. It cannot scan Git history: run `gitleaks detect` (or `git grep` for key
patterns across `git log -p`) before the first public push, and rotate any key that has ever been on
screen.

Also set, in the Anthropic and Cerebras consoles: a monthly spend limit on the hosted Anthropic key
and, for the retention setting, confirm the organisation setting described in SPEC §19.

## Deploy

```powershell
npm i -g vercel            # CLI 48.1.8 or newer for FastAPI
vercel link                # pick the team and project; Services must be available to it
vercel env add CEREBRAS_API_KEY production --sensitive    # repeat for each variable above
vercel deploy --prod       # or push to the connected Git branch
```

A CLI deploy uploads the working folder, so `.vercelignore` keeps `.env`, `OpenHands-main/`, the
participant pack and `node_modules/` out. A Git deploy uses `.gitignore`.

## After the deploy: the seven checks (SPEC §16A.5)

Replace `<url>` with the **Production** URL. Run them from a logged-out browser or `curl`.

1. `curl https://<url>/api/health` returns `mode`, the model IDs and the corpus hash
   (`corpus.sha256` starts `148eb556793f`), and `runtime.hosted` is `true`.
2. Ask the flagship question: `curl -X POST https://<url>/api/ask -H "Content-Type: application/json" -d "{\"question\":\"My plot is 200 sq m on a 9 m road. Front gap and fee?\"}"` answers PARTIAL with citations.
3. Open `https://<url>/accuracy` and `https://<url>/limits`, press refresh: no 404 (client-side routes).
4. `https://<url>/pdf/rules-hi.pdf#page=77` and `https://<url>/pdf/rules-en.pdf#page=77` open the pages.
5. Open the Production URL in a private window. Deployment Protection can block previews by default:
   confirm the URL the README quotes is reachable by the jury.
6. Remove `CEREBRAS_API_KEY` from a **Preview** deployment: it must answer in OFFLINE mode
   (`mode: "offline"`, the flagship still returns the calculator results).
7. Record cold (first call after idle) and warm latency for the eval report. The default region is
   `iad1`, far from Bhopal: measure, do not assume.

## What is different on the hosted copy

- **Stateless.** No runtime writes: audit goes to stdout (question text replaced by a hash and
  length), recordings are read-only, `logs/` is never created.
- **The rate limiters are per instance.** Instances do not share them, so a 429 from a shared
  Cerebras free tier can still happen; the fallbacks degrade that step. The per-IP limit (20 a
  minute) reads the client address from Vercel's own `x-vercel-forwarded-for`, trusted only when
  `VERCEL` is set.
- **Cold starts.** The first call after idle loads the corpus (about 0.2 s of work plus the
  platform's own start-up). `GET /api/health` warms an instance: call it before a demo.
- **Privacy.** Clerk questions are processed outside India by Vercel, Cerebras and Anthropic
  (SPEC §26 #10 to #12 are still open). Only public rule text and the question (after PII
  redaction) are sent. The feedback endpoint writes its redacted note to the log stream.
- **No admin mode** is built, so there is no store, no `DATABASE_URL` and no login.

## If Services will not deploy (20-minute time-box)

**Plan B: two projects from the same repository.**

1. Backend project: Root Directory `backend/`. Vercel detects `app/main.py` (also set in
   `[tool.vercel] entrypoint`). Same variables as above.
2. Web project: Root Directory `web/`, plus a `web/vercel.json` that forwards the API so the browser
   still sees one origin and CORS is not needed:

   ```json
   { "rewrites": [{ "source": "/api/:path*", "destination": "https://<api-project>.vercel.app/api/:path*" }] }
   ```

   Deploying the web project alone also needs its own `installCommand`/`buildCommand` only if the
   defaults fail; the `services`-mode restriction does not apply to a standalone project.

**Plan C:** local only. `.\run.ps1`, and the recorded video. The hosted copy is never the only path.

## After the event

Revoke both hosted keys (Cerebras and Anthropic consoles) and delete the Vercel project or its
Production environment variables.
