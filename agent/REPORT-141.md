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
