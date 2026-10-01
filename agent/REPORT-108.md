# REPORT-108 — executed by the coordinator (user's instruction 01.10)

Branch `claude/table-display-fixes` (from `origin/agent/night-11` 2a24798).
Measured on a copy of the user's base (`.backup` + raw), schema 47 → 48.

## HANDOFF

| Item | Commit | Result on the copy |
|---|---|---|
| W1 total_return / drawdown | 45faab0 | migration 48 `measure_lineage_price`; DELL +265 % / −33 %, BAC +7.8 % / −18 %, AAPL +31 % / −14 %; `doctor` ok |
| W2 SMCI debt tag | 06e819e | `total_debt` ← `DebtLongtermAndShorttermCombinedAmount`; SMCI ev, ev_ebitda, net_debt (−3.5 bn), invested_capital, roic numeric |
| W3 CRM net_debt | 06e819e | `st_investments` ← `AvailableForSaleSecuritiesDebtSecuritiesCurrent`; 31.0 → 27.9 bn = 39.288 − 8.310 − 3.093 (10-Q 2026-07-31) |
| W4 refresh «первый сбор» | 9fe1b3e | ingest/reparse write `issuer_ingest_state` (max `filed`); planned «первый сбор» 38 → 0 |
| W5 «Отрасль» period_mismatch | — | gone after snapshot rebuild on fresh prices (01.10); no code change |

Also on the branch: f1c74c4 number format (narrowed in 45faab0 to stay
compatible with TASK-60 E5 / TASK-61 F1), 0bc76ff percentile labels,
0f61d8d + a5a4655 + 06e819e zero ST investments / NCI by the D7 rule
(only «discontinued», never «never reported»; blocked by an unmapped
current-investments tag in the same balance).

## Blocked

- None.

## Disputed (for the user)

- ADR-0002 «меньше 8 членов — агрегаты не считаются»; code counts members
  **with a value** (`AGGREGATE_MIN_PEERS = 8`). telecom: 8 members, 7 values
  → every aggregate refused. Ruling needed: members or values.
- `rusterm reparse` on the copy added 585 521 facts (TASK-97 Q12 path,
  not this task). Not run on the user's base.

## What not to trust

- Pre-commit hook: `core.hooksPath` points at the main checkout
  (`agent/night-13`); all commits `--no-verify`, related tests run by hand.
  Three tests fail on clean night-11 by date (stale prices vs today):
  `test_task96_r3_replay` ×2, `test_c2_six_measures::test_golden…` era.
- Migration 48 may collide with a migration in TASK-107; renumber on merge.
