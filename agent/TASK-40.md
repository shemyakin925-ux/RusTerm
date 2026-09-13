# TASK-40 — N5, масштаб, и три стража, которые нельзя оставить как есть

- **Status: READY**
- **Report:** `agent/REPORT-40.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **40 requests** across hosts; model 0.
- **Goal in one sentence:** TASK-27 N5 (measured scale) plus the three
  guard defects the coordinator found while reviewing TASK-22…27.

## Items

### L1. Масштаб, измеренный, а не спроецированный (N5)

**Scope is the text of TASK-27 N5.**

**Done when:** the report states the real number of instruments reached,
wall-clock seconds per issuer and requests per host. A projection is not
a measurement and is not accepted; if the budget stops the pass, the
number reached is the number reported.

### L2. Заморозка формул перестаёт быть самоподстраиваемой

`tests/test_ifrs_map.py::test_formulas_py_matches_era_baseline` compares
`rusterm/formulas.py` against `tests/data/formulas_baseline.sha256` — a
file the same commit may rewrite. The guard cannot be weaker than the
thing it guards.

**Done when:** the baseline can only move together with a named task
item — e.g. the file carries the task id that authorised the current
hash and the test asserts that id is the task being worked on, or the
hash is pinned to a commit the test resolves. Whichever you choose, show
the guard red when `formulas.py` changes without the authorisation, then
green with it.

### L3. Словарь причин сравнивается так же, как его сравнивает код

`tests/test_v4_formulas.py` was widened with
`or m[10].startswith("missing_data: price_close")` instead of comparing
the first token, which is how `rusterm/reasons.py:is_known_reason` does
it.

**Done when:** the test compares by first token (reusing
`is_known_reason` or the same split), the ad hoc `or` is gone, and the
test is shown red against a reason genuinely outside the vocabulary.

### L4. Бэклог: B33, B34, B35

Take them from `agent/BACKLOG.md` in that order; each gets its verify
line in the report. B35 in particular: a read-only command must not
create a data directory in the current working directory.

**Done when:** from a clean tree, `markets`, `markets --json` and
`--help` leave `git status --porcelain` empty, asserted by a test, while
`init` and `ingest` still create the directory.
