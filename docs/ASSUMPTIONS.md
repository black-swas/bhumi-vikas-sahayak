# Assumptions (reversible decisions)

Log new entries at the bottom. Open questions for mentors stay in SPEC §26.

## M1: corpus and retrieval

- **COMMENTS blocks end at the first blank line** after the `COMMENTS` line (checked on all 17 rules:
  every block ends on a case citation). A page header inside a block does not end it.
- **Headers become page breaks.** A header `Rule N ... P` opens page P. Chunk pages come from the
  page file first (SPEC §8.5); the header breaks are the fallback (7 of 465 chunks use it). Exact
  quote pages come from `page_of_quote()`.
- **Sub-rule detection:** top-level `(n)` at line start with indent of 9 or less, numbered in sequence;
  `(1)` may sit on the heading line. Rule 2 definitions only need to increase (gaps exist). Rules 1,
  61 and 97 have no `(1)` marker, so they stay as preamble chunks. Rule 26 loses `(6)` (it is
  absorbed into 26(5)).
- **Inserted rules** (12-A, 17-a, 25(A), 26-A, 42-A, 93(a)) run from their marker to the end of the
  parent's text, footnotes included. IDs: `r12-a-0`, `r17-a-0`, `r25-a-0`, `r26-a-0`, `r42-a-0`,
  `r93-a-0`. `rule` holds the canonical label (`12-A`), `parent` the host rule.
- **Chunk size:** 1,800 characters (3,000 for tables); split at blank lines; parts under 300
  characters are merged into a neighbour. Three table blocks stay whole above 3,000 (21(3)(b),
  53(6), 96).
- **Candidate cap:** direct hits and intent pins are always kept, so a pinned set larger than 6
  (the flagship's `plot_norms` pins 10 chunks) is returned in full; BM25 hits only fill up to 6
  and 18,000 characters.
- **Glossary Hindi terms are working translations** for retrieval, not the official Kruti Dev
  terms. D must confirm them against the Hindi PDF.
- **Intent pins** use chunk references: `56(1)` = rule 56 sub-rule 1, `61` = whole rule,
  `r21-3-1` = one exact chunk. `plan_change` pins the two Rule 21(3) fee-table parts by ID; this
  breaks if the chunker's size limits change, and `test_every_intent_pin_resolves_to_chunks` will
  catch a missing ID.
- **`BM25_NOT_FOUND_THRESHOLD`** is not tuned yet (needs the golden set). `SearchResult.top_score`
  exposes the number for the gate.

## M2: tables and calculators

- **Row text is a contiguous fragment of the page.** Where the PDF interleaves two columns (fee
  items 2 and 4, Table 4/5 rows), `row_text` is the left-column text plus the first right-column
  fragment, and the rest sits in `row_text_parts`. Both are checked against the page.
- **`test_tables_match_source` also checks the numbers**: every number stored beside a `row_text`
  (bounds, values, columns) must occur in that text, unless listed in `derived_fields`
  (for example "Nil" = 0, "three years" = 3, hectares to sq m).
- **Fee bands are inclusive whole square metres.** 126-200 includes 139.35; only an area between
  two integers (75.5, 125.5) falls in a gap, and then no fee is chosen (`value` is `None`, both rows
  are shown). The application fee is exact: Rs 1.00 x area, no rounding to whole metres.
- **Industrial uses fee item 2** (shops, store house, factory, trade or any other commercial or
  industrial purpose): +50% of the slab. High rise industrial: +100% (item 2 of 21(3)(c)).
- **Nil is 0.0** in `result.value` with `details.display = "Nil"`.
- **Rule 56 applies up to 12.5 m inclusive.** Above it, C1-C3 return no value and route to Rule 42.
- **C6 picks the highest Table 4/5 row** whose road, plot and (if given) frontage minimums are met,
  and warns when the proposed height exceeds that row's maximum. Table 5 applies above 30 m or more
  than 10 storeys (Rule 2(38)); exactly 30 m is Table 4.
- **Side open space for the flagship** is computed for each type the plot size fits (semi-detached
  and row), because the question doesn't name a type.
- **Decimal arithmetic everywhere** (no float rounding): 183.7 sq m x 1.25 = 229.63 (half up).
- Rule 23's text covers development permission under Section 30; `permission_validity` says so.

## M3: LLM slice, verification, pipeline

- **Step A and Step B facts re-read on 11 Oct 2026** from the Cerebras and Anthropic docs: strict
  schemas ban pattern, format, minItems, oneOf, nullable, minLength; Anthropic structured output
  can break on `refusal` and `max_tokens`, so both are handled before any JSON is trusted.
- **Quote rule:** a quote is shown only if its whitespace-collapsed, lower-cased text is a substring
  of the chunk's `norm` and is 15-400 characters (V3). Calculator-derived citations use a verbatim
  slice of the chunk text found with a whitespace-tolerant search; short table rows are widened with
  the line(s) above so they read as text.
- **Pure-calculation intents never call Step B.** Their answer text comes from `templates.json`;
  Hindi wording there is a working draft for teammate D to check against the official terms.
- **Gaps in Step A are filled from the question's own text** (regex), and V8 still checks every
  number. A number the model reports that is not in the question is dropped.
- **Offline out-of-scope hints** (property tax, market rate, Aadhaar, ...) are a fixed phrase list in
  `corpus/index.py`; `BM25_NOT_FOUND_THRESHOLD` is still untuned.
- **Replay recordings** are keyed by provider, model, effort, prompt version, step, messages and
  schema; prompt tag ids are hashes of the content so the keys are stable.
- **Feedback is stateless:** `/api/feedback` redacts PII and writes the report to the audit sink; a
  stored queue needs the admin store (cut).
- **Calculator warnings and assumptions are English only** even on a Hindi card.

## M0b + M4: frontend

- **Whitelist import is smaller than SPEC §16.3 lists.** The shell's sidebar rail body, `utils.ts`
  and the toast handlers pull in 172 files (agent server adapter, backends, telemetry), so they were
  rewritten (rail, `cn`, toasts via `react-hot-toast`) instead of copied. `action-tooltip.tsx` is
  agent-confirmation UI and was not copied. Copied files are listed in `THIRD_PARTY_NOTICES.md`.
- **Reuse is still SPEC §26 #9, unconfirmed with the organisers.** If it is refused, delete the
  copied files listed there and rebuild those few components.
- **Themes:** light-plus (default) and one dark; the other four shell themes were dropped.
- **Styles scope attribute** is `data-bvs-ui` on `<body>` (the shell's postcss prefixer is kept so
  runtime theme overrides keep working).
- **npm uses `legacy-peer-deps`** (`web/.npmrc`): `tailwind-scrollbar` peers on `tailwindcss 4.x`,
  which the registry resolved as `undefined`; the install is otherwise pinned to the shell's versions.
- **The thread lives in `sessionStorage`** (20 turns), the panel width in `localStorage`.
- **Print slip opens in the same tab** (`/slip/:id`), because sessionStorage is not shared with a
  new tab.
- **Admin mode is not built** (SPEC §16B cut line); no `/admin` route exists.

## M7: evaluation

- **No API keys were available when M7 was built**, so nothing in `evals/recordings/` is a live
  model answer and `report.md`/`report.json` are from an **offline** run. `--provider replay` with an
  empty recordings folder degrades to the same offline path and counts every missing recording
  (`replay_misses`); it can never look complete by accident. To produce the real numbers:
  `uv --directory backend run python -m evals.run_eval --provider live` (records as it goes), then
  `--provider replay` for the repeatable run, and `scripts/record_demo.py` for the pitch backup.
- **`ANSWERED` in the golden set means ANSWERED or PARTIAL**; `PARTIAL` is exact (S11 only);
  `NOT_FOUND` is exact. A case passes only if status, cited rule, values, notices, language and
  integrity (no fabrication, no answer without a verified citation) all hold.
- **Sample score = answerable questions with the right rule among the verified citations, plus
  out-of-scope questions that returned NOT_FOUND, out of 17** (target 15).
- **`verified_by` is empty on every case.** `verified_page` is checked automatically against the
  chunks of the expected rules, and `expected_values` against the calculators; a human still has to
  read each page (teammate D).
- **BM25 cannot decide "out of scope".** Top scores: in-scope questions 6.3 to 22.3, unrelated ones
  0.0 to 18.6 ("How do I renew my driving licence?" scores 18.6 because Rule 26 mentions licences).
  `BM25_NOT_FOUND_THRESHOLD` therefore stays unset. Offline abstention is a fixed list of topic
  phrases plus the unknown-rule check; an unlisted topic ("weather") is answered NEEDS_REVIEW offline
  and relies on Step A (`in_scope=false`) when live. Golden case O04 keeps that gap visible.
- **A question naming a rule that does not exist** ("Rule 150", "Rule 12-Z") is NOT_FOUND without
  any model call. A lone lowercase letter after a space ("rule 56 a plot") is an article, not an
  inserted rule.
- **Offline extractive answer:** a question that names a rule ("What does Rule 56(2) say?") with no
  model shows the rule's own opening words as verified quotes (status PARTIAL, no summary).
- **Bugs the golden set found in the deterministic path** (all fixed, all covered by cases): a comma
  in "1,500 sq ft" was read as 500; "250 sq m built-up area" was read as a plot; "maximum built-up
  area for a 300 sq m plot" was read as a built-up area; fee questions were routed to FAR; Step B's
  FACTS and the V5 number check ignored `details`; "चौड़ी सड़क" was not parsed.
- **Road widths in feet are not supported** (Step A's schema is metres only). No golden case.
- **Latency numbers** from an offline or replay run are not model latency; only a live run reports
  Cerebras `time_info` and Anthropic wall-clock.
