# Bhumi Vikas Sahayak (भूमि विकास सहायक)
This readme contains all the files created for the oct 11 buildathon hosted by cerebras and anthropic in the city of bhopal. The buildathon started from 12 pm and was concluded by 5 pm. Below are the details of the team and its members along with the project general information and how to use info.

Team name : 3 idiots
Team members : 
Rishit bhat 
Shiva trivedi 
Ritesh shaw
all 3 are 1st year students in Indian institute of Science Education and Research (IISER) bhopal.

How to run it :
1. Visit the vercel link or deploy it on system of your own choice by using the files provided in the github repo.
2. If using your own deployment , connect your cerebras and anthropic api keys in the environment variable’s.
3. Ask any question related to the rulebook and it would be answered appropriately.  

Uniqueness:
1. BM25 based rule referencing system.
2. In-build calculator for calculation of fees rather than the model doing the math for individual plot owners.
3. Direct refusal on irrelevant or confused or out of scope questions.
4. Can be used directly by the plot owner’s cutting the clerk our in most cases.
5. Data can be edited one by one rather than whole dataset change. 
6. Easy to understand and use layout and ux.

Future plans:
1. Admin console for changing the database through a login portal and also to solve queries rejected by the AI.
2. Can be used by the architect too by creating a special mode for them which suggests them all the technicalities and also help them check the changes and if they are under the rules in real like a normal llm.

3. 
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

1. Install [uv](https://docs.astral.sh/uv/) and Node 24+ or on vercel at [vercel](https://bhumi-vikas-sahayak-two.vercel.app/)
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
`THIRD_PARTY_NOTICES.md`. 
