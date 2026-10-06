# TASK-135 — acceptance that finishes and never touches the real index

- **Status: READY**
- **Report:** `agent/REPORT-135.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Why it is in a frozen-guards queue:** PRODUCT.md allows fixing a
  guard that breaks work. This one does: round 147 verify ran 12/1 with
  the I5 test > 30 min and staged guard edits in the real index.
- **Budgets:** network 0, LLM 0.

## A1. I5 residue (U0 `f511665` moved I5 to a local clone)
Acceptance still shows `ERROR tests/test_i5_guard_source.py::
test_no_test_stages_the_real_repo_root` (coordinator selfcheck 06.10).
Coordinator's run in a linked worktree (06.10): three I5 tests fail with
`NotADirectoryError: '.git/COMMIT_EDITMSG'` — the U0 test writes the
literal path; in a linked worktree `.git` is a file. Use
`git rev-parse --git-path COMMIT_EDITMSG` (rule I6). Failing:
`test_i5_working_tree_widening_is_red_and_named`,
`test_i5_staged_and_authorised_widening_is_green`,
`test_i5z_demonstration_ran.py::test_i5_demonstration_ran_or_legitimately_nested`.
Find the fixture error too and fix it; the tests must pass inside
`agent/acceptance.sh` in a linked worktree and in the main checkout.
**Done when:** `bash agent/acceptance.sh` in a fresh linked worktree —
pytest item green, no ERROR line for I5.

## A2. Full suite under 15 minutes
Measure `python3 -m pytest -q` wall time on this machine; mark live/slow
tests `@pytest.mark.slow` (skipped by default, run by `--runslow`) until
the default run is < 15 min. Do not delete or weaken any assert.
**Done when:** report lists before/after wall time; default run < 900 s;
`git diff -- tests/ | grep '^-.*assert'` is empty.

## Do not
Same list as `agent/TASK-131.md` «Do not». This task may edit tests and
`pyproject.toml`/`conftest.py` only — not the guard scripts.
