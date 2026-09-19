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

## Done

- C4: cvm-dfp.v2 sign normalization + clip removal + honest
  jurisdiction_rate; gold and formulas baseline updated in-commit;
  census diff = 1 row.

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
