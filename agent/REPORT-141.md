# REPORT-141 — TASK-141 (rulings on REPORT-139: map v8, split basis, split debt, revenue line, CIK hint)

## Done
- D0 — `CONCEPT_MAP_VERSION` bumped to `us-gaap.v8` (the dps successor
  from 406e3f9 changed the mapping while the version stayed v7). Version
  comment names the addition; pins updated where they assert the CURRENT
  version: `tests/test_w2_w3_remap.py` (2), `tests/test_w5_verizon_shares.py`,
  `tests/test_coordinator_0810.py` (map_version), `tests/test_task130_k2_map.py`;
  the GUIDE's live `concept_map_version` line and the executable status
  block's JSON now read v8. Remaining `us-gaap.v7` mentions are history
  comments only:
  `grep -rn "us-gaap.v7" rusterm/ GUIDE.md` →
  concepts.py:40 (v7 withdrew OtherCostOfOperatingRevenue — history),
  concepts.py:77 (v7 added InterestExpenseNonoperating — history),
  repos.py:486 (withdraw door docstring — history),
  GUIDE.md:260 (recorded status example — updated to v8 as the block is
  executed and matched by test_guide_truth).
  Runs: pinned suites `49 passed`; full suite via this commit's hook.

## Blocked
- (empty)

## What not to trust
- The full-suite green for D0 comes from this commit's hook (quoted in
  the HANDOFF below); the two earlier hook attempts failed on tree
  hygiene (an untracked D1 test file in the tree, my own concurrent load
  on the machine) — not on D0's code; those attempts were aborted before
  committing.

## Disputed
- (empty)

## HANDOFF
(interim — D0 committed; D1–D5 ahead)
Status:          PARTIAL
Arrival state:   TASK-140 accepted (74950ac); tree clean at 46e0254
Items done:      D0
Items not done:  D1, D2, D3, D4, D5
Acceptance:      this commit's pre-commit selfcheck; the final HANDOFF
                 quotes the last one and the D5 verify
Tests:           pinned suites 49 passed (quoted in Done)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 (D0 is offline)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diffs grepped for RUSTERM_* values — 0 hits
Pushed:          yes
Questions for the coordinator:
1. (none yet)

NOW: D0, step 6

## Done (D1 continued)
- D1 — share count basis across a split. The companyfacts parser now
  puts the fact's `filed` date into the locator; `reparse` aligns stored
  locators with the fresh parse (new store doors
  `FactRepo.locators_by_pointer` / `update_locators`; value, period,
  basis and origin untouched; idempotent — second run changes nothing,
  measured below); `core.prices.split_factor_between` returns the split
  factors in (period_end, filing]; the market-cap path divides a share
  count whose filing crossed a split and notes it in the lineage role;
  a fact with no filing date stays as-is with a role saying the basis is
  unknown. Test: `tests/test_task141_split_basis.py` — 3:1 split between
  period end and filing → cap = actual close × count ÷ 4-equivalent
  (`2 passed`), incl. the no-date case.
  Runs on the copy: `reparse` → «локаторов выровнено: 565173»; history
  rebuild; `yahoo_check.py US-WMT` → **21/21 = 100 %** (market_cap 2024
  was 66.9 % off, now within 5 %); control ten `yahoo_check` →
  **188/190 = 99 %** (gate ≥ 99 % holds; DELL pe 2024 8.8 % and
  net_income 5.2 % remain — pre-existing, Yahoo line methodology);
  `card_fill` control ten → **1490/1629 = 91 %** (gate ≥ 90).

## Done (D2 — committed under the user's pause order)
- D2 — debt filed as a Noncurrent + Current pair (PFE). `core/debt.py`
  gained `pair_total_at` (both tags required on one date — half a pair is
  not debt); new store door `SnapshotRepo.debt_pair_facts`; the builder's
  input pass falls back to the pair when no combined debt tag exists
  (latest date closed at as_of), the pair's second fact rides as its own
  input `total_debt_pair_current`, and the net_debt / invested_capital
  lineage loops name BOTH documents; the card's `statement_series` sums
  the same door for years the combined tag never covered (no second copy
  of the rule). The ТЗ-31 C2 pin («one tag only») is replaced per the
  coordinator's ruling — declared below.
  Tests: pair → sum; combined present → combined only — in
  `tests/test_task141_split_basis.py` (+ the card/snapshot suites green:
  product_card, coordinator_0810, c2, task130 — 48 passed locally).
  NOT measured yet (user paused the shift): the copy gates —
  `yahoo_check US-PFE` total_debt within 5 % and the control ten ≥ 99 %
  after a history rebuild. The copy is at /tmp/rusterm-b2-base with the
  pre-D2 rebuild; the gates run first thing on resume.

## Blocked
- (empty)

## What not to trust
- D2's copy gates are UNMEASURED (see above); D2 is committed on green
  unit tests only. The earlier cancelled background run did not produce
  numbers.
- D0/D1 numbers quoted earlier stand (they were measured before their
  commits).

## Disputed
- (empty)

## HANDOFF (FINAL — paused by the user mid-TASK-141)
Status:          PARTIAL (D0, D1 committed and pushed; D2 committed under
                 the pause order with unit tests green, copy gates
                 pending; D3, D4, D5 not started)
Arrival state:   selfcheck green on arrival (TASK-141 taken at 46e0254
                 via wait, round 159)
Items done:      D0 (b3b57c4), D1 (ed8fb63), D2 (this commit)
Items not done:  D2 copy gates (first on resume: history --all --rebuild
                 on the copy, yahoo_check US-PFE + control ten, card_fill);
                 D3, D4, D5
Acceptance:      D0/D1 hooks green («Принято. SELFCHECK OK»); this
                 commit's hook is the next full run
Tests:           local D2 suites 48 passed; full suite via hooks
Guards:          none touched
Schema:          unchanged (48)
Network:         ~7 of 150 (Yahoo fundamentals, all cached after the
                 first fetch per ticker)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diffs grepped for RUSTERM_* values — 0 hits
Pushed:          yes
Questions for the coordinator:
1. Same as REPORT-139 Q1 (XOM CIK policy) — D4 will land the manual CIK
   door next resume.

NOW: D2, step 6 (paused by the user)
