# REPORT-29 — TASK-29: keys in the environment, acceptance green again

## Done

### Arrival state (before any commit, recorded per PROTOCOL §10)

- Branch `agent/night-10` cut from `main` (f0f79d8). Real key file
  `~/.rusterm.env` present (1031 bytes); no key variables in the
  process environment.
- `bash agent/selfcheck.sh` -> SELFCHECK_EXIT=1; acceptance inside:
  «Итог: пройдено 11, провалено 2», exit 2.
- `bash agent/acceptance.sh` -> ACC_EXIT=2, failing tests:
  - `tests/test_llm_api.py::test_build_without_key_is_config_error`
  - `tests/test_llm_real.py::test_m5_real_model_skips_without_key`
  - `tests/test_ops.py::test_d7_d8_ops_command_audit_rows_confirm_and_json_keys`
  Same three the coordinator measured on 616173c (TASK-29 §0).

### A1 — no test reads the real ~/.rusterm.env (DONE)

- `tests/conftest.py` (new): autouse fixture points `RUSTERM_ENV_FILE`
  at an empty 0600 file in `tmp_path` and clears every `env.ENV_NAMES`
  name from `os.environ`; monkeypatch restores both. A test that wants
  a value sets it itself. The restoring fixture in `tests/test_env.py`
  stays as required; it is covered by the global one.
- The 0600 is load-bearing: a 0644 fixture file made doctor flag
  «env-файл читается группой/остальными» and four doctor/cli tests go
  red (`test_h6_doctor` ×2, `test_doctor`, `test_cli` full cycle) —
  they had been silently saved by the very `load_env()` leak this task
  fixes. With 0600 the fixture file matches the real file's mode.
- Verification (real key file present, 1031 bytes):
  `python3 -m pytest -q --tb=short` -> EXIT=0, no FAILED lines.
  The three arrival failures pass:
  `python3 -m pytest tests/test_env.py tests/test_llm_api.py
  tests/test_llm_real.py tests/test_ops.py -q`
  -> «........................s......  [100%]».
- With `RUSTERM_ENV_FILE=/tmp/fake_rusterm.env` (fake key + fake UA,
  0600): EXIT=0, 0 FAILED lines.
- `tests/test_env.py` still proves the contract: 5 passed, including
  `test_values_picked_up_from_env_file` asserting
  `os.environ["RUSTERM_SEC_UA"] == "Synthetic Test synthetic.invalid"`.
- Observation, not hidden: `test_m4_scale` failed once in one full run
  and passed in isolation and in the two subsequent full runs (timing
  sensitivity under load, unrelated to env). Watched, not touched.

## Blocked

- (nothing yet)

## What not to trust

- `test_m4_scale::test_c2_hundred_issuer_build_shape_stays_linear`
  failed once in one full run, passed in isolation and in the two
  subsequent full runs. Timing sensitivity under load; untouched.

## Disputed

- (empty by design)

## HANDOFF

Status:          PARTIAL — shift in progress
Arrival state:   selfcheck STATUS=1; acceptance «Итог: пройдено 11, провалено 2», exit 2
Items done:      A1
Items not done:  A2, A3, A4, A5 — in progress, in numeric order
Acceptance:      «Итог: пройдено 11, провалено 2» at arrival; report-section guards
                 red until this report carried all five sections (mid-shift is
                 expected red for them)
Tests:           617 passed, 6 skipped on the tree of A1 (real key file present);
                 0 failed outside the report-section guards
Guards:          tests/conftest.py added (isolation), no assertions touched
Schema:          unchanged (41)
Network:         0 requests used of 0 budget
Model:           0 calls of 0 budget; GLM-5.3-Flash
Secrets:         nothing reprinted; arrival pytest output had printed the real
                 key prefix before this task (the defect A4 closes)
Pushed:          not yet (mid-shift; updated at HANDOFF)
Questions for the coordinator:
1. (none yet)

### A2 — network in the suite only behind the live marker (DONE)

- `pyproject.toml`: `live` marker registered; `addopts` now
  `-q --strict-markers -m "not live"` — a default run collects no test
  that can reach the network or the model.
- Five tests carry `live`: `test_edgar.py::test_live_edgar_probe…`,
  `test_refresh_live.py::test_c6_live…`, `test_llm_real.py::test_m5…`,
  `test_market_kr.py::test_live_company_json_answers`,
  `test_n4_extraction_fixtures.py::test_n4_model_audit_table`
  (the two "successors" found by survey, both key-gated).
  `python3 -m pytest -m live --collect-only -q` lists exactly these
  five files, one test each.
- Machine proof of zero requests: `tests/conftest.py` gains an autouse
  fixture that replaces `urllib.request.urlopen` with a raising guard
  for every test without the `live` marker (all five `_default_transport`
  implementations go through `urllib.request.urlopen`; subprocesses are
  covered separately by self-built environments and A1 inheritance).
- `tests/test_ops.py` subprocess env is now built by the test itself:
  every inherited `RUSTERM_*` name is stripped, then only
  `RUSTERM_SEC_UA` and a nonexistent `RUSTERM_ENV_FILE` are set; an
  assert pins the resulting name set. With a key in the parent
  environment the CLI subprocess can no longer take the API path —
  the live-call hole from arrival is closed at the source.
- Verification: default run with all four keys EXPORTED into the shell
  environment: all four names set to fake values whose shape was kept
  out of this report on purpose (the secrets guard scans tracked
  files for key shapes) -> EXIT=0, 0 failures — a request would have
  raised through the guard.
