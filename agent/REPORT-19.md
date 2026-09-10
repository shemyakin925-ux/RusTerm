# REPORT-19 — TASK-19, Phase 0 of M8 (branch `agent/night-3`)

## Done

- Section 0: `git pull` on `agent/night-2` (already up to date), branched
  `agent/night-3`; `bash agent/acceptance.sh` → `STATUS=0`,
  `Итог: пройдено 13, провалено 0`; `_SCHEMA_VERSION` read from file: **39**
  (next free migration number 40, not assumed).
- Report journal opened and `agent/STATE.json` repointed at it (this commit).

## Blocked

- (empty)

## What not to trust

- (empty yet)

## Disputed

- (empty yet)

## HANDOFF

- (pending, end of shift)

NOW: section 0, step 4
- F1 (commit 3af771f): Market.access + KR/BR/AU rows (providers
  intentionally unresolved), per-market venue prefixes, docstring
  jurisdiction/venue ruling. tests/test_db.py synthetic 'UK'->'GB'.
  Verify: pytest tests/test_markets.py tests/test_db.py -q -> 15 passed;
  acceptance STATUS=0 13/13; grep UK in rusterm/ tests/ empty.
  P1 note: 3 removed asserts replaced by strictly stronger pins
  (ordered 6-tuple; 7-code stderr listing).
- F2 (commit 299c1c1): six reasons added with
  ADR comments; guard untouched. pytest test_repos+test_metrics+
  test_invariants -q -> 38 passed; acceptance STATUS=0 13/13.
