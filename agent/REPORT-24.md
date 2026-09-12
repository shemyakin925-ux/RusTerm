# REPORT-24 — TASK-24: M10 Industry View (offline)

## Done

- §0: branch `agent/night-6` cut from `agent/night-5` head (be74125);
  selfcheck STATUS=0; `_SCHEMA_VERSION` read from the file: 41;
  `maritime_tanker.py` carries 33 public functions.
- **RUSTERM_LLM_API_KEY UNSET** (printenv exit 1) → N4's real-model
  half is blocked; its fixtures and harness are delivered, the
  verified-but-wrong table is not measurable without a model (0 of 80
  calls used).

### N1 — hhi stops being a name without an implementation (DONE)

- `formulas.py`: `hhi(shares)` — Herfindahl–Hirschman over FRACTIONS
  (0..1), unit string "index" attached via `measure_unit("hhi")`;
  the percent convention (0..10000) is explicitly rejected in the
  docstring. Shares not summing to 1.0 within 1e-6 yield
  `missing_data: shares_sum:<sum>` — never a silent renormalisation.
  Empty set -> `missing_data: shares_empty`; a single member with
  share 1.0 is the valid monopoly edge -> 1.0. Registered in
  `calculate_measure` (unit set through kwargs, the wrapper's single
  construction point).
- Tests (tests/test_formulas.py, -k hhi): hand-computed
  [0.5, 0.3, 0.2] -> 0.38 with unit index; 0.8 total yields the
  reason; empty and single-member edges defined and asserted.
- **P1 accounting**: the obsolete era pin
  `tests/test_ifrs_map.py::test_formulas_py_is_byte_identical_to_task_start`
  (byte-freeze against TASK-18's 23737a7) died with that task's
  boundary — N1 mandates editing formulas.py. Replaced with
  `test_formulas_py_matches_era_baseline`: sha256 of formulas.py
  pinned by `tests/data/formulas_baseline.sha256`, updatable only by
  the task that edits the file, with this report as the ledger. Same
  freeze semantics, movable baseline.

## Blocked

- N4 (real-model extraction audit) waits for RUSTERM_LLM_API_KEY;
  fixtures + harness delivered.

## What not to trust

- (updated as items land)

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL
Items done:      §0
Items not done:  N1..N12 pending
Acceptance:      STATUS=0 at branch cut
Tests:           not counted yet this shift
Schema:          41 (unchanged so far)
Pushed:          with this commit
Questions for the coordinator:
1. (none yet)

NOW: N1, step 1
