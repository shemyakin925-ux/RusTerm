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

### L4. Бэклог: B34 и B35

B33 was closed by TASK-27 N6 and re-verified on 13.09.2026 — do not
take it again. B35 in particular: a read-only command must not create a
data directory in the current working directory.

**Done when:** from a clean tree, `markets`, `markets --json` and
`--help` leave `git status --porcelain` empty, asserted by a test, while
`init` and `ingest` still create the directory.

### L5. Красная приёмка называет провалившуюся проверку

Question 1 of `agent/REPORT-29.md`, ruled: **fix it.** `selfcheck.sh`
keeps only the tail of a failed acceptance log, so the 12/1 flake of
13.09.2026 could not be attributed to a check at all. A guard whose
failure cannot be read teaches people to re-run it instead of reading
it.

**Done when:** on a red acceptance run `selfcheck.sh` prints every
`ПРОВАЛ` line (and, for check 3, the `FAILED` lines of pytest) — shown
on a deliberately reddened scratch copy, output pasted, copy reverted;
on a green run the output is unchanged from today's.

### L6. Тест масштаба перестаёт зависеть от нагрузки машины

Question 3 of `agent/REPORT-30.md`, ruled: **make it load-tolerant.**
`test_m4_scale::test_c2_hundred_issuer_build_shape_stays_linear` flaked
twice on 13.09 under load and passed in isolation every time. A test
that is red for a reason unrelated to the code is a test people learn
to ignore.

**Done when:** the test asserts the **shape** (ratio between the 10x
and 100x passes, with a stated tolerance), not a wall-clock budget; the
report states the measured ratio on three consecutive runs; the
assertion is not deleted and the new form is named as stricter or
equal in what it actually guarantees.

### L7. Пины реестра выводятся из реестра, а не из памяти

Ruling on question 1 of `agent/REPORT-28.md`: the replacements were
right, and the rule is now general. `test_available_lists_all_eight_names`
hand-typed the number 8 and the rate pin enumerated six names, so
registering a legitimate seventh channel broke two tests that guard
nothing about behaviour.

**Done when:** every pin over the provider registry is derived from the
registry itself — the count from `available()`, the rate/ceiling checks
as **properties** («every network name declares a tier from the closed
set», «every network name has a `HostLimit` with a positive rate»,
«no name is `paid`») — and adding a new free channel requires **no**
test edit. Show it: add a scratch channel, run the suite green, revert.
