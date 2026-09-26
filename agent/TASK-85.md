# TASK-85 — mutation testing: do the formula tests have teeth?

- **Status: READY**
- **Report:** `agent/REPORT-85.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-85.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network — `pip install mutmut` only. LLM 0.
- **How to work:** as TASK-82.
- **Taken after:** TASK-82 (its property tests count as killers).

РАЗРЕШЕНО ПРАВИТЬ: pyproject.toml
РАЗРЕШЕНО ПРАВИТЬ: .gitignore

## Where we are

`test_no_tautology_asserts` catches asserts true for any input — by
pattern. It cannot see an assert that is merely too weak. Mutation
testing measures that: change the code, count tests that notice.

## Fixed decisions

| Question | Rule |
|---|---|
| Tool | mutmut (BSD, free), version pinned and named in the report. Not a runtime or `[test]` dependency: a separate extra `mutation = ["mutmut==<ver>"]`. |
| Fallback | mutmut does not run on this layout / Python 3.14 after 30 min of trying → write `tools/mutate.py`: stdlib `ast` mutator with operators `+↔-`, `*↔/`, `<↔<=`, `>↔>=`, `==↔!=`, `and↔or`, constant `0↔1`, `return x → return None`; one mutant at a time in a temp copy. Report says which path was taken and why. |
| Where it runs | `tools/mutation.sh`: copies the repo into `$TMPDIR`, runs there, prints `module killed/survived/timeout`. The working tree stays clean (acceptance 13). |
| Targets | `rusterm/formulas.py`, `rusterm/reasons.py`, `rusterm/parsers/cvm_dfp.py`. |
| Test subset | `tests/test_formulas.py tests/test_golden_formulas.py tests/test_v4_formulas.py tests/test_b1_*.py tests/test_prop_*.py tests/test_reasons.py` + parser tests for `cvm_dfp`. |
| Equivalent mutant | listed in `tests/data/mutation/equivalent.txt`: `<file>:<line> <operator> — <one-line reason>`. No other way to excuse a survivor. |

## M1. Baseline

**Done when:** `bash tools/mutation.sh` runs to the end; report table:
target → mutants / killed / survived / timeout, and wall time.

## M2. Kill the survivors in `formulas.py`

Ordered by line. For each survivor: a new assert that kills it, **or**
an entry in `equivalent.txt`. Cap: 40 survivors per night; the rest
listed in the report by line.

**Done when:** rerun shows `formulas.py` killed ≥ 90 % of non-equivalent
mutants, or every survivor processed — whichever comes first; the
numbers before/after in the report.

## M3. Same for `reasons.py` and `cvm_dfp.py`

**Done when:** same rule, same report table.

## M4. Gate that cannot rot

`tests/test_mutation_gate.py`, marker `slow` (add the marker and
`-m "not live and not slow"` to `addopts` if absent): runs
`tools/mutation.sh` and fails if any target's killed-share is below the
figure committed in `tests/data/mutation/baseline.json`.

**Done when:** `python3 -m pytest -m slow tests/test_mutation_gate.py -q`
green; default run does not collect it; `bash agent/acceptance.sh` green.
