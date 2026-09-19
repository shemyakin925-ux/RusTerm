# REPORT-B1 — TASK-B1 (lane B: formula honesty + reason dictionary)

Branch: `agent/night-12`, worktree `/tmp/rt-lane-b` (lane A's dirty
files in the main checkout untouched). Model: GLM-5.3-Flash.
Network: 0 (ТЗ budget). Baseline suite: 1 pre-existing red,
`tests/test_selfcheck_guard.py::test_selfcheck_cannot_exit_zero_with_dirty_tree`
— see Disputed; unrelated to lane B items.

## Done

### B1.1 — census "green that didn't deserve it" (commit 1)

Method: every public formula in `rusterm/formulas.py` probed with
out-of-domain inputs by a throwaway script (value / (None, reason) /
exception recorded from actual runs, not from memory); table below.
Dishonest cases found: 9 (+1 dead helper). Closed: 5 + helper removal
(ТЗ cap). Tests: `tests/test_b1_honesty.py` (14 tests, boundary inputs
per closure). Era baseline `tests/data/formulas_baseline.sha256`
updated in the same commit: `015bab5d…991de`.

| measure | out-of-domain input | before | verdict | after |
|---|---|---|---|---|
| clip | x outside band | clamps to bound | dishonest helper, 0 consumers after C4 | removed |
| effective_tax | tax/pretax None; pretax<=0; rate outside [0,0.5] | refusal with reason | honest (ТЗ-58 C4) | unchanged |
| invested_capital (dispatcher) | cash/st_investments missing | TypeError crash | dishonest | refusal `missing_data: cash, st_investments` (names concepts) |
| invested_capital (dispatcher) | any extra kwarg (period_start…) | TypeError crash | dishonest | explicit-arg call, computes |
| invested_capital (raw) | None operand | TypeError | named, precondition in docstring; dispatcher is the honest door | unchanged |
| roic / roe / roe_incl_nci / asset_turnover | avg denom =0 / <0; None inputs | refusal (dispatcher) / raw TypeError on None numerator | honest; raw crash named | unchanged |
| nopat (dispatcher) | oi present, tax_rate None | (None, None) — no value, NO reason (I4) | dishonest | refusal `missing_data` |
| gross/operating/net_margin | revenue < 0 | silent negative ratio | dishonest | refusal `negative_denominator` (same §1.4 rule as pe/pb/ps) |
| gross/operating/net_margin (raw) | numerator None | TypeError | dishonest (silent crash) | refusal `missing_data` |
| drawdown | any price <= 0 | silent 0.0 "no drawdown" | dishonest | refusal `missing_data: nonpositive_price`; rising series keeps real 0.0 |
| ebitda | oi present, d_and_a missing | returns oi as ebitda (understated, green) | dishonest | refusal `missing_data: d_and_a`; both-paths-missing names all concepts sorted |
| market_cap / market_cap_total | price or shares < 0 | silent negative cap | dishonest, NOT closed (unreachable from parsers; trivial fix) | listed |
| hhi | negative shares summing to 1 | accepted, hhi=2.5 | dishonest, NOT closed (trivial check) | listed |
| split_factor / dividend_factor | k=0 / price=0 | ZeroDivisionError; negative domain → silent nonsense factor | dishonest, NOT closed (bare-float signature; needs quotes-layer protocol change — costlier) | listed |
| price_adj | negative prices pass through | mechanical map | acceptable (validated upstream), named | unchanged |
| total_return / pe / pb / ps / ev_ebitda / div_yield / interest_coverage | zero/negative denominators, None | refusal via _divide_checked | honest | unchanged |
| cagr | v_start<=0, v_end<0, n<=0 | refusal; note: negative_denominator/denominator_zero tokens reused outside literal meaning | honest (tokens in dictionary), named | unchanged |
| ttm / fcf / market_cap_total (None) / enterprise_value | missing inputs | refusal | honest | unchanged |
| dispatcher, unknown concept | unknown name | `missing_data` (concept_not_mapped fits better) | named, NOT closed (unreachable from pipeline; trivial) | listed |

Golden files: none touched — census goldens (task49, task57_br) and
m2/m6_ca exercise none of the five closed paths (verified by reading
golden rows before the change; census suites green after).

NOW: B1.1, step 6 (committed)

## Blocked

- none.

## What not to trust

- My own first commit attempt (B1.1) was poisoned by me: I ran the full
  pytest suite in the same worktree WHILE the pre-commit selfcheck was
  running. The two selfcheck invocations collided on the single-flight
  lock; an i5 guard-source test died mid-scenario and left a debris
  line in `agent/p6_rule.sh` (restored from HEAD since). The 3 ERRORs
  in `tests/test_i5_guard_source.py` from that run are artifacts of the
  collision, not real failures. Lesson recorded: in this worktree,
  never run pytest while a commit/selfcheck is in flight.
- Baseline (before any lane-B change): 1 red,
  `tests/test_selfcheck_guard.py::test_selfcheck_cannot_exit_zero_with_dirty_tree`
  — it fails while HEAD is the coordinator's relay commit (root cause
  in the Disputed section); it heals as soon as the first executor
  commit lands.
- The 5-formula probe outputs quoted in Done were captured by a
  throwaway script (`/tmp/probe_b11.py`), not committed; the committed
  evidence is `tests/test_b1_honesty.py`.

## Disputed

- DISPUTED: `agent/p6_rule.sh` relay-branch allowlist knows only
  `TASK-[0-9]+\.md` / `REPORT-[0-9]+\.md`; lane tasks are letter-named
  (`TASK-B1.md`, `REPORT-B1.md`). Consequence: every selfcheck with an
  empty index reads the coordinator's own relay commit as a violation
  ("чужие файлы (исполнителя): agent/TASK-B1.md") — the guard fires on
  the commit the coordinator itself made. Not fixed by me (file is not
  lane-B territory; widening the regex is the coordinator's call).
  On numeric-task branches (night-11) the allowlist matched, which is
  why this never fired before lanes B/C.
- DISPUTED: same allowlist gap makes
  `test_selfcheck_cannot_exit_zero_with_dirty_tree` red on any freshly
  handed lane branch until the first executor commit lands. The test
  is correct; the allowlist is stale.

## HANDOFF

- Interim: B1.1 committed (see Done); B1.2, B1.3 in progress.
  Shift not finished; final HANDOFF appended at the end.

NOW: B1.2, step 1 (census collected)
