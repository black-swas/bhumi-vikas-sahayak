# Bhumi Vikas Sahayak (भूमि विकास सहायक)

**Prototype, not legal advice.** A tool for a Bhopal Municipal Corporation building-permission clerk at the
counter. The clerk asks a question in English or Hindi and gets a short answer in the same language with
the rule number, the **exact rule text** and its **PDF page** (links open the official English and Hindi
PDFs at that page). Setbacks, FAR and fees are computed by code from tables that are tested against the
rulebook text, never by a model. When the rules are silent it says **NOT FOUND**.

Built for Claude Impact Lab × Cerebras Café Compute, Bhopal, 11 October 2026 (Track 1).
User: the building-permission clerk. The tool points to the rule; the clerk decides.

- Rules: MP Bhumi Vikas Rules, 2012, consolidated to 06/03/2025 (English PDF, Town & Country Planning Dept).
- Known later amendment (28/08/2026, Rule 2(5)(c)) is shown as a warning from a secondary summary, never as a quote.
- Bhopal Development Plan norms are **not** encoded (Rule 103 says they take precedence).

## Run it on a counter PC (Windows, no internet needed)

1. Install [uv](https://docs.astral.sh/uv/) and Node 24+.
2. Clone this repository.
3. Optional: put `CEREBRAS_API_KEY` and `ANTHROPIC_API_KEY` in `.env` (created from `.env.example` on first run).
   Without them the app runs in **OFFLINE** mode: calculators, templates and keyword search, no model.
4. Run `.\run.ps1` (installs, builds the web app, starts one process).
5. Open http://127.0.0.1:8000.

## How it works

`question → normalise (PII redacted) → understand (Cerebras) → retrieve (BM25) → calculate (code) →
compose (Claude Haiku 5.5) or template → verify (V1–V8) → card`. Every quote shown is an exact substring
of the rule text; if verification fails twice the card says NEEDS REVIEW and shows candidate rules, never
generated text. Details: `SPEC.md`. Decisions and open questions: `docs/ASSUMPTIONS.md`.

## Layout

| Folder | What |
|---|---|
| `backend/` | FastAPI app (`app/`), data and tables (`data/`), golden set and eval harness (`evals/`), tests, scripts |
| `web/` | React single-page app (React Router, Tailwind, HeroUI), English and Hindi |
| `docs/` | `DEPLOY.md` (Vercel), `ASSUMPTIONS.md`, `PLAYBOOK.md` |

## Checks

```
uv --directory backend run pytest -q
uv --directory backend run ruff check . ; uv --directory backend run ruff format --check .
uv --directory backend run python scripts/preflight.py       # deploy and secret checks
uv --directory backend run python -m evals.run_eval --provider offline
npm ci --prefix web ; npm run lint --prefix web ; npm test --prefix web ; npm run build --prefix web
```

## Deploy

See `docs/DEPLOY.md` (Vercel Services: `web/` and `backend/` in one project) for the environment variables.

## Honest limits

See the in-app **Limits** page and `docs/ASSUMPTIONS.md`. In short: not legal advice; no Development Plan
norms; amendments after 06/03/2025 only as listed; the golden-set results in `backend/evals/report.md`
come from an **offline** run until a live run with API keys is recorded; Hindi UI and template wording
needs a native review against the official Hindi PDF.

## Credits and licence

MIT (`LICENSE`). Parts of `web/` are adapted from OpenHands Agent Canvas (MIT): see
`THIRD_PARTY_NOTICES.md`. Built with AI assistance (Claude Code); humans reviewed the tables and labels.
