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

### N2..N6, N8, N9 — the sector module is connected, physical records
### become inputs (DONE)

- **N2**: `industry/__init__.py` carries `SECTOR_MODULES`
  (sector id -> module) and `module_for_sector`; `SnapshotBuilder`
  accepts an `industry` resolver; `build()` writes the
  `industry_metrics` coverage block: ready with
  `computed X/Y method maritime.v1` when the sector has a module and
  inputs, `missing` with `industry_no_module:<sector>` (instrument in
  an unregistered sector) or `industry_no_sector`. Metrics are
  computed on read from the records (single source of truth) — no I4
  conflict, no migration.
- **N3**: `core/industry/inputs.py` — explicit per-sector
  `PHYSICAL_INPUT_MAP` (record metric name -> module input name, the
  way concepts.py maps tags); a record mapping to nothing lands in
  `unmapped` (kept and counted, never silently dropped);
  `verified=no` records never feed a metric — the metric goes grey
  with `manual_unverified`.
- **N5**: units carry scale: `parse_scaled_unit("million tons") ->
  ("tons", 1e6)`; a metric refuses inputs whose base unit differs
  (`unit_refused` -> `missing_data: unit_mismatch:<expected>`);
  an unrecognized scale word ("billionn days") is not recognised as a
  scale at all -> unmapped with the unit named.
- **N6**: grey metrics name the missing input by the module's own
  parameter name (`no off_hire_days`), asserted against the module
  signature; the block reason lists them, so `rusterm coverage`
  reads out what to import next.
- **N7** (needs N1): `sector_concentration()` — hhi over member
  revenue shares as of a date (same version machine as M7); states
  its currency; a mixed-currency sector refuses
  `currency_mismatch: KRW, USD`; recomputation as of a past date is
  immune to new data (asserted).
- **N8**: `industry_metric_rows()` in tui/model.py — physical metrics
  beside the financial aggregate, each with its method_version; grey
  rows show the missing input; manual-sourced rows carry
  `source: "manual"` for the renderer; no `import curses` in the
  model source (asserted).
- **N9**: fifth read-only tool `get_industry_metrics` — metrics with
  units, reasons and method_version; the byte-identical-database test
  passes with all five; the tools-registry pin updated 4 -> 5 names
  (P1 accounting: the removed assert line
  `assert set(tools.TOOLS) == {four names}` is replaced by the
  five-name pin — a strict superset demanded by this task).
- Tests `tests/test_n2_industry_view.py`, 9 passed. Suite: 595
  passed, 3 skipped; goldens untouched.

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
