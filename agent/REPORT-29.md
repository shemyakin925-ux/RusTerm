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

### A3 — the V7 tripwire stops falling from a key's presence (DONE)

- Resolution chosen: option 2 — the test keeps its contract (an
  explicit `-m live` run with a key still fails while the live M5 path
  is unimplemented) and skips by default behind the `live` marker.
  Reason: this task's budget is model 0; implementing the live path
  here would need real calls, and the path itself is TASK-35/B36
  territory. The debt is written into `agent/BACKLOG.md` by name as
  **B36** with the TASK-7 T16 contract quoted (≤ 2 calls, citations,
  mass op executes nothing, accept command given, size M).
- Docstring updated to state the resolution and point at B36.
- Verification, both runs quoted:
  - default run, key PRESENT (real `~/.rusterm.env` in place):
    `python3 -m pytest tests/test_llm_real.py -q` -> EXIT=0 (deselected);
  - default run, key ABSENT (`RUSTERM_ENV_FILE=/nonexistent/…`):
    EXIT=0 (deselected);
  - explicit `python3 -m pytest -m live tests/test_llm_real.py -q`
    without a key -> «s», clean skip, EXIT=0.
  Neither a present nor an absent key makes a default run red.

### A4 — the key value never reaches the output (DONE)

- `LlmApiClient.__repr__` and `DartProvider.__repr__` (the only two
  dataclasses carrying `api_key`) print a fixed mask
  (`api_key='sk-or-***'` / `'***'`) regardless of the stored value —
  reprs land in assertion messages and logs, a key value has no
  business there.
- `tests/test_secrets_absent.py::test_client_repr_masks_the_key`:
  builds both clients with a fake key, asserts the fake value AND its
  four-character-prefix tail are absent from `repr()`, from a
  formatted assertion message, and from every `audit_log` row written
  by an in-process `ops` run with the key in the environment (model
  unset -> rule fallback, the same door N1 built).
- Verification: full default run EXIT=0;
  `python3 -m pytest -q 2>&1 | grep -c "sk-or-v1-TESTONLY"` -> 0
  (grep found no match). The fake key lives in the test source only;
  the secrets shape guard passes (the fake does not match a real key
  shape, which is exactly why the task chose that literal).

### A5 — acceptance with the keys in place (DONE)

- Real key file in place (~/.rusterm.env, 1031 bytes):
  `bash agent/acceptance.sh` -> ACC_EXIT=0 (captured before any pipe),
  «Итог: пройдено 13, провалено 0 — Принято».
- The suite is green on the machine that has the keys; the arrival
  red (three tests, one live model call, a key prefix in pytest
  output) is closed at all three causes: isolation (A1), marker
  (A2/A3), masking (A4).

## What not to trust

- `test_m4_scale::test_c2_hundred_issuer_build_shape_stays_linear`
  failed ONCE in one full run during A1 verification and passed in
  isolation and in every subsequent full run (four more since). Timing
  sensitivity under load, offline test, untouched by this task.
- The `live`-marked tests were never run with real network access in
  this shift: `python3 -m pytest -m live` was executed only without a
  key (clean skip proof). The five live tests' own assertions are
  exactly as they were on main.

### A5 follow-up — one unexplained flake, recorded honestly

- During A5 staging, one `bash agent/selfcheck.sh` run recorded
  «Итог: пройдено 12, провалено 1», exit 1. selfcheck keeps only the
  tail of the acceptance log, so the failing CHECK could not be named
  from that run. Three immediate acceptance/selfcheck re-runs were all
  13/0 (ACC_EXIT=0 twice, SELFCHECK OK once).
- Suspected (not proven): the `test_m4_scale` timing flake inside the
  suite check — the only offline timing-sensitive test, already flaked
  once during A1 under load; its FAILED lines would have fallen above
  selfcheck's tail window. No assertion touched, nothing changed to
  chase it.

## Disputed

- (empty by design — the flake above is recorded under A5 as an
  observation with a named suspect, not a dispute about a task item)

## HANDOFF (mid-shift, TASK-29 complete except final bookkeeping)

Status:          PARTIAL — TASK-29 items A1-A5 all done; final HANDOFF at shift end
Arrival state:   selfcheck STATUS=1; acceptance «пройдено 11, провалено 2», exit 2
Items done:      A1, A2, A3, A4, A5
Items not done:  none in TASK-29; the m4_scale flake and the selfcheck tail-window
                 blindness are observations, not items
Acceptance:      «Итог: пройдено 13, провалено 0 — Принято», ACC_EXIT=0, real key
                 file in place (1031 bytes)
Tests:           625 collected; default run green; 5 live-marked deselected by
                 default, listed exactly by -m live --collect-only
Guards:          conftest env isolation + urlopen network guard (new);
                 test_secrets_absent extended with repr/audit masking case;
                 no existing assertion weakened (selfcheck P1 green on every commit)
Schema:          unchanged (41)
Network:         0 requests of 0 budget (live tests not exercised)
Model:           0 calls of 0 budget; GLM-5.3-Flash
Secrets:         default-run output grepped for the fake key literal — 0 hits;
                 the secrets shape guard caught one key-shaped line I had
                 written into this report during A2 — removed before commit
Pushed:          through A4 yes; this commit next
Questions for the coordinator:
1. selfcheck prints only tail -4 of a failed acceptance run — the 12/1
   flake above could not be attributed to a check. Dump the full
   acceptance output (or its FAILED lines) when red? Backlog-sized S.
2. The leaked key prefix from the arrival red (coordinator's note):
   user should re-issue that OpenRouter key; nothing in the repo or
   this shift's output carries it.
