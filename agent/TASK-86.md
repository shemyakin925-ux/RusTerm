# TASK-86 — CI where the user lives: macOS, the desktop, a nightly deep run

- **Status: READY**
- **Report:** `agent/REPORT-86.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-86.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network — git push and read-only `gh run list/view`. LLM 0.
- **How to work:** as TASK-82.

РАЗРЕШЕНО ПРАВИТЬ: .github/workflows/acceptance.yml
РАЗРЕШЕНО ПРАВИТЬ: pyproject.toml

## Where we are

- `.github/workflows/acceptance.yml`: `ubuntu-latest` only, Python
  3.12/3.14, `pip install -e ".[test]"`. The user runs **macOS**.
- The desktop extra is never installed in CI → every
  `tests/test_desktop_*.py` is skipped there (`importorskip`). 21
  controls with press tests, none run by CI.
- `tests/test_j5_ci.py` needs PyYAML and **skips without it** — the
  guard of CI is itself not guaranteed to run.
- Repo `shemyakin925-ux/RusTerm` is public: macOS runners cost
  nothing (ADR-0018 holds).

## Fixed decisions

| Question | Rule |
|---|---|
| Matrix | `os: [ubuntu-latest, macos-latest]` × `python-version: ["3.12", "3.14"]`, `fail-fast: false`. Key `python-version` stays (test_j5_ci reads it). |
| Desktop job | separate job `desktop`, both OS, Python 3.12, `pip install -e ".[test,desktop]"`, `QT_QPA_PLATFORM=offscreen`; on Ubuntu the apt packages Qt needs — find the minimal set, name it. |
| No-skip guard | desktop job fails if the pytest summary for `tests/test_desktop_*.py` shows any `skipped`. |
| Deep job | `schedule` cron once a day + `workflow_dispatch`; ubuntu, 3.12; `HYPOTHESIS_PROFILE=deep python -m pytest -m slow -q`; `timeout-minutes: 90`. If TASK-82/83/85 are not done yet, the job still exists and runs whatever `slow` collects. |
| Secrets | none, as before (test_j5_ci). |
| New CI asserts | text-level (regex over the YAML file) — they must not skip without PyYAML. |

## Q1. macOS in the matrix

**Done when:** workflow has the matrix above; `bash agent/acceptance.sh`
passes on the `macos-latest` runner (BSD `sed`/`find` differences fixed
in code or tests, **not** in `acceptance.sh`).

## Q2. Desktop job

**Done when:** job exists; on both OS it runs the desktop tests with 0
skipped; the no-skip guard is demonstrated red once (temporarily
uninstall PySide6 in a throwaway branch run, or show the guard's
command red locally) — evidence in the report.

## Q3. Deep job

**Done when:** job exists; one `workflow_dispatch` run triggered and its
conclusion named.

## Q4. Guards that do not skip

`tests/test_ci_matrix.py`, no PyYAML: asserts `macos-latest`,
`ubuntu-latest`, `3.12`, `3.14`, job `desktop`, `QT_QPA_PLATFORM`,
the no-skip guard, `schedule:` present; no `secrets.`.

**Done when:** green locally and in CI.

## Q4a. pytest-qt for the desktop

pytest-qt (MIT, free) added to the `desktop` extra only; core and the
default run never import it.

**Done when:**
- `_CollectWorker` tested through `qtbot.waitSignal(finished_run,
  timeout=10000)` — the signal really arrives from the worker thread;
- window close during a running collect: `cancel_flag` set, worker
  joined, no `QThread: Destroyed while thread is still running` in
  captured stderr;
- at least 3 existing press tests switched to `qtbot.mouseClick` where
  they call handlers directly — no assert removed
  (`git diff <base>..HEAD -- tests/ | grep -c '^-.*assert'` → 0);
- green in the `desktop` CI job on both OS; without PySide6 the files
  still skip (`importorskip`), acceptance green.

## Q5. Proof, not claim

**Done when:** report quotes
`gh run list --branch agent/night-11 --workflow acceptance --limit 3
--json conclusion,url,headSha` with the head SHA of this task's last
commit and `success` for every job. `gh` unauthenticated or unavailable
→ `Blocked: gh` with the error text; the coordinator reads CI.
