# Evaluation report

Generated 2026-10-11T10:31:49+00:00 · provider **offline** · 1 run(s) · 67 cases · corpus `148eb556793f`

Models: Step A `none (offline)`, Step B `none (offline)` (effort low, thinking default).

> OFFLINE run: no model was called. Questions that need Step B (a cited, composed answer) end as NEEDS_REVIEW here, which is the designed degraded behaviour. This is not a measurement of the live system.
> Anthropic has no seed and no temperature=0: only a replay is repeatable.
> Expected values were derived from the calculators and checked by a test against the rulebook page text; a human sign-off (verified_by) is still pending for every case.

## Summary (measured)

| Metric | Result | Target | Met |
|---|---|---|---|
| Status accuracy | 80.6% | ≥ 90.0% | **NO** |
| Correct rule cited (sample questions, of 17) | 8 | ≥ 15 | **NO** |
| Calculated values correct | 100.0% | ≥ 100.0% | yes |
| Out-of-scope answered NOT_FOUND | 91.7% | ≥ 100.0% | **NO** |
| Fabricated quotes or rules shown | 0 | ≤ 0 | yes |
| Injection cases resisted | 100.0% | ≥ 100.0% | yes |
| Answers shown without a verified citation | 0 | ≤ 0 | yes |
| Warm end-to-end latency p95 (ms) | 5.8 | ≤ 5000 | yes |

Cases passed: **54 of 67** (a case passes only if its status, rule, values, notices, language and integrity checks all pass).

Also measured: correct rule cited on 78.2% of all cases that name a rule; the expected rule was among the cited or retrieved candidates on 94.5%; fabrications caught before display: 0.

## Latency (measured)

| | p50 | p95 | n |
|---|---|---|---|
| End to end | 2.4 ms | 5.8 ms | 67 |
| Model time (Step A + B, questions that called a model) | 0 ms | 0 ms | 0 |

Model calls: 0 (0 per question) · tokens in/out/cached: 0/0/0.

## The 17 sample questions

| Case | Question | Expected | Got | Rules cited | Result |
|---|---|---|---|---|---|
| S01 | My house faces a 10 m wide street and will be 9 m tall. How much open space do I | ANSWERED | ANSWERED | 56(1) | pass |
| S02 | I want a farm house on agricultural land. What is the minimum plot size and the  | ANSWERED | ANSWERED | 17 | pass |
| S03 | My development permission was granted in 2023. How long does it stay valid, and  | ANSWERED | PARTIAL | 23(1), 23(2) | pass |
| S04 | I applied for building permission and the authority has not replied. What happen | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S05 | How far must my balcony stay from a low-voltage overhead electric line, vertical | ANSWERED | ANSWERED | 52(1) | pass |
| S06 | Who is allowed to sign and submit my building plans? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S07 | What documents go with an application for building permission? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S08 | What is the fee for building permission for a residential house? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S09 | Can I change my plan after it is sanctioned? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S10 | What is the minimum rear open space for a 150 sq m residential plot? | ANSWERED | PARTIAL | 56(2) | pass |
| S11 | Do I need separate development permission for a 300 sq m plot that matches the D | PARTIAL | NEEDS_REVIEW | - | **FAIL** |
| S12 | Which rule decides what happens when the Development Plan and these rules disagr | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S13 | What are the rules for lifts in a building taller than 15 m? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S14 | मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है। आगे कितनी जगह खाली | ANSWERED | PARTIAL | 56(1) | pass |
| S15 | बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है? | ANSWERED | NEEDS_REVIEW | - | **FAIL** |
| S16 | How do I pay my property tax online? | NOT_FOUND | NOT_FOUND | - | pass |
| S17 | What is the current market rate for land in Kolar Road, Bhopal? | NOT_FOUND | NOT_FOUND | - | pass |

## All cases

| Case | Tags | Expected | Got | ms | Result |
|---|---|---|---|---|---|
| S01 | sample, calc, setback, table | ANSWERED | ANSWERED | 8.7 | pass |
| S02 | sample, calc, lookup | ANSWERED | ANSWERED | 3.3 | pass |
| S03 | sample, calc, lookup | ANSWERED | PARTIAL | 4.5 | pass |
| S04 | sample, lookup, no-invented-number | ANSWERED | NEEDS_REVIEW | 1.6 | **FAIL** |
| S05 | sample, calc, table | ANSWERED | ANSWERED | 3.5 | pass |
| S06 | sample, lookup | ANSWERED | NEEDS_REVIEW | 3 | **FAIL** |
| S07 | sample, lookup, long-answer | ANSWERED | NEEDS_REVIEW | 1.9 | **FAIL** |
| S08 | sample, lookup, fee, needs-built-up-area | ANSWERED | NEEDS_REVIEW | 2 | **FAIL** |
| S09 | sample, lookup | ANSWERED | NEEDS_REVIEW | 1.1 | **FAIL** |
| S10 | sample, calc, band-edge, table | ANSWERED | PARTIAL | 2.8 | pass |
| S11 | sample, lookup, amendment | PARTIAL | NEEDS_REVIEW | 2 | **FAIL** |
| S12 | sample, lookup | ANSWERED | NEEDS_REVIEW | 1.3 | **FAIL** |
| S13 | sample, lookup, false-premise | ANSWERED | NEEDS_REVIEW | 1.5 | **FAIL** |
| S14 | sample, calc, hindi, table | ANSWERED | PARTIAL | 3.2 | pass |
| S15 | sample, lookup, hindi, fee | ANSWERED | NEEDS_REVIEW | 1.2 | **FAIL** |
| S16 | sample, out-of-scope | NOT_FOUND | NOT_FOUND | 0.4 | pass |
| S17 | sample, out-of-scope | NOT_FOUND | NOT_FOUND | 0.4 | pass |
| F01 | flagship, calc, assumption, dp-precedence | ANSWERED | PARTIAL | 11.7 | pass |
| E01 | calc, band-edge, table | ANSWERED | PARTIAL | 4.1 | pass |
| E02 | calc, band-edge, table | ANSWERED | PARTIAL | 5 | pass |
| E03 | calc, band-edge, table | ANSWERED | PARTIAL | 2.9 | pass |
| E04 | calc, band-edge, table | ANSWERED | PARTIAL | 4.1 | pass |
| E05 | calc, band-edge, table | ANSWERED | PARTIAL | 4.6 | pass |
| E06 | calc, band-edge, table, nil | ANSWERED | PARTIAL | 2.8 | pass |
| E07 | calc, band-edge, table | ANSWERED | PARTIAL | 4.2 | pass |
| E08 | calc, band-edge, table | ANSWERED | PARTIAL | 2.3 | pass |
| E09 | calc, band-edge, table | ANSWERED | PARTIAL | 2.2 | pass |
| E10 | calc, band-edge, table | ANSWERED | PARTIAL | 3.2 | pass |
| G01 | calc, fee, gap, band-edge | ANSWERED | ANSWERED | 3.4 | pass |
| G02 | calc, fee, band-edge | ANSWERED | ANSWERED | 4 | pass |
| G03 | calc, fee, band-edge | ANSWERED | ANSWERED | 2.9 | pass |
| U01 | calc, units, sqft | ANSWERED | PARTIAL | 2.2 | pass |
| U02 | calc, units, gaj, hinglish | ANSWERED | PARTIAL | 1.5 | pass |
| U03 | calc, units, sqyd | ANSWERED | PARTIAL | 1.8 | pass |
| U04 | calc, units, sqft, far | ANSWERED | PARTIAL | 2.3 | pass |
| U05 | calc, units, gaj, hindi | ANSWERED | PARTIAL | 2.1 | pass |
| P01 | lookup, false-premise | ANSWERED | NEEDS_REVIEW | 2 | **FAIL** |
| I01 | injection, calc, fee | ANSWERED | ANSWERED | 3.6 | pass |
| I02 | injection, calc, fee, hindi | ANSWERED | ANSWERED | 3.5 | pass |
| I03 | injection, nonexistent-rule, out-of-scope | NOT_FOUND | NOT_FOUND | 0.2 | pass |
| N01 | nonexistent-rule, out-of-scope | NOT_FOUND | NOT_FOUND | 0.1 | pass |
| N02 | nonexistent-rule, out-of-scope, hindi | NOT_FOUND | NOT_FOUND | 0.1 | pass |
| N03 | nonexistent-rule, out-of-scope | NOT_FOUND | NOT_FOUND | 0.1 | pass |
| O01 | out-of-scope | NOT_FOUND | NOT_FOUND | 0.3 | pass |
| O02 | out-of-scope | NOT_FOUND | NOT_FOUND | 0.3 | pass |
| O03 | out-of-scope | NOT_FOUND | NOT_FOUND | 0.4 | pass |
| O04 | out-of-scope, unlisted-topic | NOT_FOUND | NEEDS_REVIEW | 0.7 | **FAIL** |
| OH1 | out-of-scope, hindi | NOT_FOUND | NOT_FOUND | 0.4 | pass |
| OH2 | out-of-scope, hindi | NOT_FOUND | NOT_FOUND | 0.4 | pass |
| H01 | calc, hindi, table | ANSWERED | PARTIAL | 2.2 | pass |
| H02 | calc, hindi, table | ANSWERED | ANSWERED | 2.4 | pass |
| H03 | lookup, hindi | ANSWERED | NEEDS_REVIEW | 1.4 | **FAIL** |
| R01 | calc, band-edge, rule-12a | ANSWERED | ANSWERED | 4.2 | pass |
| R02 | calc, rule-12a | ANSWERED | ANSWERED | 3 | pass |
| HR1 | calc, high-rise, table | ANSWERED | ANSWERED | 4 | pass |
| FB1 | calc, far, dp-precedence | ANSWERED | ANSWERED | 5.8 | pass |
| FE1 | calc, fee, table | ANSWERED | ANSWERED | 6.2 | pass |
| FE2 | calc, fee, surcharge | ANSWERED | ANSWERED | 4.9 | pass |
| EL2 | calc, table | ANSWERED | ANSWERED | 3.1 | pass |
| FH2 | calc, lookup | ANSWERED | ANSWERED | 3.9 | pass |
| SD1 | calc, side, table | ANSWERED | PARTIAL | 3.3 | pass |
| SD2 | calc, side, table | ANSWERED | PARTIAL | 4 | pass |
| SD3 | calc, side, table, nil | ANSWERED | PARTIAL | 3 | pass |
| D01 | lookup, direct | ANSWERED | PARTIAL | 1.6 | pass |
| D02 | lookup, direct, hindi | ANSWERED | PARTIAL | 1 | pass |
| W01 | lookup, no-outside-knowledge | ANSWERED | NEEDS_REVIEW | 1.4 | **FAIL** |
| T01 | calc, lookup | ANSWERED | PARTIAL | 2.7 | pass |

## Failures (13)

- **S04** I applied for building permission and the authority has not replied. What happens if they miss the d
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['28'] cited
- **S06** Who is allowed to sign and submit my building plans?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['18', '26', '26-B'] cited
- **S07** What documents go with an application for building permission?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['14', '16'] cited
- **S08** What is the fee for building permission for a residential house?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['21'] cited
- **S09** Can I change my plan after it is sanctioned?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['24', '21'] cited
- **S11** Do I need separate development permission for a 300 sq m plot that matches the Development Plan?
  - status NEEDS_REVIEW, expected PARTIAL
  - none of the expected rules ['2'] cited
  - no notice containing any of ['28/08/2026']
- **S12** Which rule decides what happens when the Development Plan and these rules disagree?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['103'] cited
- **S13** What are the rules for lifts in a building taller than 15 m?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['83'] cited
  - none of ['12.5'] shown
- **S15** बिल्डिंग परमिशन की फीस कितनी है और किस नियम में लिखी है?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['21'] cited
- **P01** Lifts are required only for buildings above 15 m, right? What does the rule say?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['83'] cited
  - none of ['12.5'] shown
- **O04** What is the weather in Bhopal today?
  - status NEEDS_REVIEW, expected NOT_FOUND
- **H03** लिफ्ट कितनी ऊँचाई की इमारत में जरूरी है?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['83'] cited
  - none of ['12.5'] shown
- **W01** How close to a lake can I build?
  - status NEEDS_REVIEW, expected ANSWERED
  - none of the expected rules ['50', '24'] cited

## Method

- Cases are in `evals/golden.jsonl`. `ANSWERED` matches ANSWERED or PARTIAL; `PARTIAL` must be PARTIAL; `NOT_FOUND` must be NOT_FOUND.
- Rule hit: an expected rule is among the **verified citations**. Retrieval hit also accepts the candidate rules shown on a NEEDS_REVIEW card.
- Sample-question score = answerable questions with the right rule cited + out-of-scope questions that returned NOT_FOUND, out of 17.
- Fabrication (shown): a displayed quote that is not a substring of its rule text, or an answer naming a rule that does not exist. Fabrication (attempted): quotes and numbers the verifier dropped before display.
- Latency is wall-clock for one question through the pipeline on this machine.
