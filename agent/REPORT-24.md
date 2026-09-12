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

### N10 — ADR-0015: the measured cost of adding a sector (DONE)

- `docs/adr/0015-poryadok-dobavleniya-sektora.md` — the one permitted
  docs/ change: a seven-step table measured on mining (catalogue,
  module, input mapping, units, registry line, fixtures, catalogue
  page), with mechanical-vs-judgement named per step. Judgement
  concentrates in reading the sector (step 1) and its terminology
  (step 3); everything else follows the template.

### N11 — a second sector proves the procedure (DONE, fallback path)

- `rusterm/core/industry/mining.py` — production-weighted business
  (volumes, grades, reserves, cost per unit), deliberately different
  in shape from asset-day shipping; `METHOD_VERSION = "mining.v1"`;
  10 metrics with names verbatim from its catalogue (in the module
  docstring); physical input mapping and expected units declared in
  inputs.py under "mining".
- **The catalogue-page experiment, executed as prescribed:** the file
  `docs/industry-metrics/mining.md` was added and the check-10
  pipeline measured on a throwaway commit —
  ```
  git diff --name-status origin/main HEAD -- docs/
    A  docs/industry-metrics/mining.md
  CHECK-10: red (the line does not match ^A docs/adr/)
  ```
  The file was removed with the throwaway branch; the catalogue lives
  verbatim in the module docstring. See Disputed.
- Tests: 6+ mining metrics computed from a synthetic import
  (test_n2_industry_view covers the machinery; mining computes 10
  declared metrics through the same compute_sector_metrics path).
- Acceptance green on the final state; the Disputed entry below is
  the recorded path taken.

### N12 — milestone M10, stated with its evidence

- Metrics per sector: tankers 34 known / 14 input-driven declared;
  mining 10 known, all declared. `method_version` maritime.v1 /
  mining.v1 on every row (asserted by tests).
- Mapped/unmapped physical records: mapped
  ("off hire days" -> off_hire_days), unmapped counted and kept
  ("totally unknown metric"), wrong-unit refused
  ("months" vs days -> unit_mismatch:days), unrecognized scale
  ("billionn days") -> unmapped — all asserted by tests.
- verified-but-wrong (N4): **not measurable — no model key**; 0 of 80
  model calls used. The four synthetic tables (clean two-column,
  ten-column by class, with a total row, footnote-inside-number) and
  the stage-① harness are committed; the audit runs the moment a key
  exists (RUSTERM_LLM_API_KEY set).
- Concentration per sector with currency: tankers fixture
  hhi = 0.30 (shares .4/.3/.2/.1), currency USD, n = 4; mixed
  KRW+USD refuses by name. Mining concentration computes through the
  same function.
- M10 does **not** cover, named honestly: the model-side extraction
  audit (no key); a real second-sector corpus (mining metrics are
  proven on synthetic imports, not on a real miner's annual report);
  per-vessel-class drilldown in the TUI (rows are sector-level);
  catalogue pages under docs/ (check 10) — they live in module
  docstrings until check 10 widens.

## Blocked

- N4 (real-model extraction audit) waits for RUSTERM_LLM_API_KEY;
  fixtures + harness delivered.

## What not to trust

- (updated as items land)

## Disputed

- **Check 10 blocks sector catalogue pages in docs/.** TASK-24 N11
  required `docs/industry-metrics/mining.md`; acceptance check 10
  allows only `A docs/adr/...` lines in docs/. Measured on a
  throwaway commit (branch deleted after measurement):
  ```
  git diff --name-status origin/main HEAD -- docs/
    A  docs/industry-metrics/mining.md
  grep -vE '^A[[:space:]]+docs/adr/' -> MATCH -> check 10 red
  ```
  Fallback taken as prescribed: the catalogue lives in the module
  docstring (`mining.py`), the file is not committed. Coordinator:
  widening check 10 to `docs/industry-metrics/` would let catalogue
  pages leave the code.

## HANDOFF

Status:          DONE (with N4 blocked on the model key)
Items done:      §0, N1, N2, N3, N5, N6, N7, N8, N9, N10, N11 (fallback path), N12
Items not done:  N4 — real-model audit blocked on RUSTERM_LLM_API_KEY (fixtures + harness delivered, 0 of 80 calls used); N13 — the 09:30 condition not met, the queue continues with TASK-25
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK at every green commit; the N11 catalogue-file experiment measured check 10 red on a throwaway branch, file withdrawn, Disputed carries the output
Tests:           597 passed, 3 skipped, 0 xfailed (final count at the closing commit)
Schema:          unchanged (41)
Goldens:         golden_m2.json and golden_m6_ca.json unchanged; both golden tests inside the 597
hhi:             fraction convention (0..1), unit index, hand-computed 0.38 on .5/.3/.2; 0.8 sum yields the reason; empty and single-member defined
Sectors:         tankers (maritime.v1, 34 known, 14 declared input-driven), mining (mining.v1, 10 known and declared)
Physical inputs: mapped: off_hire_days; unmapped counted: unknown metric, unrecognized scale; unit-refused: months-vs-days — all asserted
Extraction:      four synthetic tables committed (clean / ten-column / total-row / footnote-in-number); stage ① reaches all; verified-but-wrong n/a without a model key
Concentration:   tankers fixture hhi 0.30, currency USD, n 4; mixed KRW+USD refuses
docs/ path:      catalogue page in module docstring; Disputed entry with the check-10 output quoted; ADR-0015 added (the permitted docs change)
Network:         0 requests used (budget 0, actual 0)
Model:           app llm_calls 0 of 80; GLM-5.3-Flash
Pushed:          yes, every work commit pushed to origin/agent/night-6 as it landed
Questions for the coordinator:
1. Widen check 10 to allow `A docs/industry-metrics/*.md` so catalogue pages leave module docstrings?
2. N4 needs the model key — fold its audit into a later night or hand it to the coordinator's key-holding run?
3. The tools registry pin moved 4 -> 5 (get_industry_metrics) — confirm the five-tool surface is the intended model API.

NOW: N12, step 3
