# REPORT-58 — TASK-58 (C4 + C1 + C2 + C3 + C5 + C6 + C7)

Round 70, executor, branch `agent/night-11`.

- Stop: дневной круг, по списку (Q1 verdict in C0 — no Y0 countdown
  for daytime relay rounds).
- Arrival: baton validated by the coordinator's acceptance (13/0) on
  `795ee48` at hand-off; every commit below runs the full selfcheck
  twice (executor + pre-commit hook) before landing.

## C4. Sign of 3.08 normalized by the map; clip() removed

Verdict Q2: the map layer fixes the sign, and clip was a defect of its
own — it INVENTED 0.0 for a negative rate. Landed:

- `cvm-dfp.v2` (`rusterm/normalize/concepts.py`): map-layer rule
  `normalize_sign_cvm` — DRE line 3.08 filed as a deduction (negative)
  is flipped to the positive expense convention at display time.
  Provenance, not a guess: the fact carries
  `concept_map_version='cvm-dfp.v2'` (WHAT normalized it) and the
  locator keeps the original SIGNED value in `raw_value` (as filed) —
  the same breed as the ESCALA_MOEDA scale normalization, which also
  never changed `basis` (the fact table CHECK pins basis to
  as_reported/restated; no migration was needed or made).
- `effective_tax` AMBEV: **0.23812270405274155** (≈23.81%), gold
  updated in `tests/data/golden_census_task57_br.json` in this same
  commit; the old invented `0.0` row is gone with an explanation in
  the test docstrings.
- `clip(..., 0, 0.5)` removed from `effective_tax_rate`
  (`rusterm/formulas.py`): a rate outside [0, 0.5] is now a REFUSAL
  `jurisdiction_rate: rate=<число>` (token from `rusterm/reasons.py`,
  assert in tests/test_task58_c4.py), not 0.0/0.5.
- Census row change count across markets, measured by the goldens:
  **exactly 1** — BR-AMBEV effective_tax. The CNQ/NGGTF census
  (ТЗ-49 gold) did not change a single row (their rates are in band;
  the golden passes untouched).
- Off-census honesty fallout, measured on the synthetic 20-issuer m3
  pass: TWO issuers (DIS −0.1190, one more −0.0354) had clip-invented
  zeros and now refuse `jurisdiction_rate` — effective_tax 18/20,
  floor 15→14; and a chain gap got a name: a NULL nopat whose
  effective_tax link refused was stored REASONLESS before ("покраснела
  молча") — the chain refusal now names the missing link
  (`missing_data: effective_tax, ...`, snapshot.py), nopat 13/20,
  floor 12 kept.
- `tests/data/formulas_baseline.sha256` updated in this commit (the
  sanctioned same-commit path of the formulas-era pin).
- Tests: tests/test_task58_c4.py 4 passed (map rule, untouched
  positives/others, band refusals, AMBEV end-to-end); Z2 provenance
  test updated to the new truth — raw signed value in the locator,
  v2 on the fact (pin replacement declared in the commit message).

## C6. CvmProvider.resolve — and no market provider without a door

- `CvmProvider.resolve` (ТЗ-58 C6): the BR add path searches the
  recorded CADASTRE by CD_CVM or by DENOM_SOCIAL substring (B3 tickers
  are not in the cadastre — «AMBEV» finds AMBEV S.A.),
  `cik` = CD_CVM; `unknown_issuer` is a value, not an exception.
  `ticker_venues()` → honest `{}`.
- The registry-wide test `test_every_market_provider_has_resolve_and_venues`
  (red for cvm and dart before the fix) caught the NEXT same-breed
  defect: `DartProvider` had no resolve either — a live
  `add --market KR` would die with AttributeError the same way. Fixed:
  dart's resolve validates the corp_code (the market identifier,
  `identifier='corp_code'`) via company.json and returns corp_name.
- The `_BR` adapter from ТЗ-56 is REMOVED — `tests/test_task56_z2.py`
  now runs add/ingest through the real `CvmProvider` on the recorded
  cadastre transport (7 passed).
- Tests: tests/test_task58_c6.py 2 passed.

## C3. Open-mode divergences fixed with the markets mechanics

- `metrics` — readonly by default (absent dir → named refusal,
  rc 1); `--record` keeps `_open` (positive control in the test).
- `doctor` — readonly default WITHOUT a refusal: the pinned contract
  (test_cli_doctor_detects_schema_gap) requires a JSON diagnosis even
  on an absent dir, so the absence itself becomes a FINDING
  (`schema_version=None`, `cadence.reason="no_data_dir"`), rc 1;
  `--fix` keeps `_open`.
- `census` — readonly; rebuild writes into the EXISTING catalog;
  absent dir → named refusal, rc 1.
- `tui` — documented read-only, now honest: absent dir → named
  refusal, rc 1, nothing created (was: silent ensure_app_dir).
- Tests: tests/test_task58_c3.py 5 passed (each named command leaves
  `git status --porcelain` empty from a clean git tree; writing modes
  still create — asserted). The tui fix also needed the cadence
  section of the doctor report to survive conn=None (measured crash,
  fixed; the log-path crash in the generic handler is pre-existing
  behavior for genuinely unexpected errors).
- NOTE: C6 and C3 land in one commit — the C3 code was in the working
  tree when the C6 acceptance ran, so the validated state is the
  union; both items are complete and their tests are green together.

## Done

- C4: cvm-dfp.v2 sign normalization + clip removal + honest
  jurisdiction_rate; gold and formulas baseline updated in-commit;
  census diff = 1 row (commit 35d9d62).
- C6: resolve/ticker_venues for every market provider (cvm by
  cadastre, dart by corp_code), registry-wide guard test, Z2 adapter
  removed.
- C3: metrics/doctor/census/tui readonly defaults fixed (B35
  mechanics); writing modes unchanged; doctor keeps its JSON
  diagnosis contract on absent dirs.

## Blocked

- (empty so far)

## What not to trust

- (to fill at hand-off)

## Disputed

- (empty so far)

## HANDOFF

Status:          working (interim)
Arrival state:   coordinator's 13/0 on 795ee48 at hand-off
Items done:      C4 (staged in this commit)
Items not done:  C1, C2, C3, C5, C6, C7, backlog item
Acceptance:      this commit runs the full selfcheck (twice) before
                 landing
Tests:           test_task58_c4.py 4 passed (new)
Guards:          none touched (formulas-era baseline updated per its
                 own rule)
Schema:          unchanged
Network:         0 requests used
Model:           app llm_calls 0; runner model GLM-5.3-Flash
Secrets:         no key material in new tests or the report
Pushed:          this commit — yes, right after selfcheck passes
Questions for the coordinator:
(none so far)

## Done (C7) — the A5.1 cause confirmed by run, the three-test red does not reproduce

Reproduction of the red run (measured, both commands with output):

1. RED: a cooled staged `agent/STATE.json` (updated_at set 20 minutes
   back, `git add`) + nested selfcheck WITHOUT `I5_NESTED`:

   `bash agent/selfcheck.sh` → rc=1, output (3 lines total):
   `I5: p1_rule.sh исполняется из HEAD` / `I5: p6_rule.sh исполняется из HEAD` /
   `SELFCHECK FAIL (O0): updated_at=2026-09-19T17:57:36Z расходится с реальным 2026-09-19T18:17:56Z на +20.3 мин (допуск 15)`

   The expected `P3/P4` substring NEVER appears (grep over the full
   log: no match) — O0 kills the run before the P3/P4 check, exactly
   the mechanism ffeb518 named for the flicker.

2. GREEN, same scenario after ffeb518: the nested run inside
   `test_selfcheck_cannot_exit_zero_with_dirty_tree` carries
   `I5_NESTED=1` (O0 skipped), so
   `python3 -m pytest tests/test_selfcheck_guard.py -q` → 3 passed.

The three ТЗ-named tests — NOT reproduced, measured both ways:

- plain run (check-3 equivalent):
  `pytest tests/test_transcripts.py::test_export_chat_writes_transcript_json tests/test_tui_model.py::test_tui_has_no_sql_no_http tests/test_venue_filings.py::test_g2_g5_venue_from_exchange_file_and_404_is_an_answer`
  → 3 passed;
- blocked-zstd run (check-11 equivalent,
  `PYTHONPATH=/tmp/block58` with a raising `zstandard.py`):
  → 3 passed.

Per the C7 rule («если картина не сходится — значит причина другая,
и это пишется прямо»): the check-11 red with exactly these three
tests did not reproduce under the O0 recipe or the blocked-zstd
command on this machine and commit (6ce61d4) — the O0 mechanism is
confirmed as cause 1 (the dirty-tree flicker), but the original
three-test red had a DIFFERENT or additional cause (the coordinator's
fdb8070 tree, their concurrent workload, the pre-A1 code state — as
REPORT-57 A5 already narrowed). Item goes to Disputed with these
measurements; nothing was weakened anywhere.

NOW: C7, step 4 (measured and written)

## B36 закрыта коммитом eaa91d7

Live run measured: 3 model calls (budget 40), five outcomes recorded
above in this file's C2 run — full net_margin answered with the
census-golden value 0.2791393632939477 and citations; both gray
questions (roe, fcf) rejected by the guard
(guard_rejected_uncited_number); the empty issuer answered with an
honest resolve_ticker not_found refusal.
