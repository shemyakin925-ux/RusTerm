# TASK-102 — rulings on REPORT-97 Disputed (round 136); do before resuming TASK-97

- **Status: ACCEPTED** (round 138, 27.09)
- **Report:** `agent/REPORT-102.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-102.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** now; then resume TASK-97 at Q5 (→ Q7 → Q6 → Q1 → Q2 → Q3 →
  Q4 → Q12 (2, 7)). One commit per item.

РАЗРЕШЕНО ПРАВИТЬ: agent/check_mention.sh
РАЗРЕШЕНО ПРАВИТЬ: docs/adr/0025-ttm-dlya-vseh-potokovyh-vhodov.md

## Where we are

Round 136 accepted as a partial TASK-97: Q12 (5), Q12 (6), Q11, Q10, Q8 —
fresh clone 13/0; declared pin replacements only; `docs/` touched only by
the allowed ADR-0025. Rulings on REPORT-97 Disputed:

| # | Ruling | Item |
|---|---|---|
| 1 | right — a price × 14-year-old share count is worse than a refusal | M1 |
| 2 | the user-visible number is the newest snapshot per paper: 8 → 2. Accepted, no work | — |
| 3 | right, option (a) | M2 |
| 4 | option (c) accepted as built | — |
| 5 | option (a): same-date balance may come from `restated` | M3 |
| 6 | keep `AGGREGATE_MIN_PEERS`; option (b) — say the gap in words. A 267-day spread is acceptable (user allowed up to 2 years) | M4 |
| 7 | 143 was the coordinator's earlier count by another slice; accept 129 → 170. No work | — |

## M1. Price-based measures need a fresh share count

For measures that multiply a price by shares (market_cap, pe, ps,
dividend yield, EV and anything built on them), the share count must end
no earlier than `as_of − 550 days` (same constant as
`_DPS_ANNUAL_STALE_DAYS`); the anchor is `as_of`, not the issuer's newest
fact. Older → refusal `stale_input: shares_outstanding (<date>)`.
**Done when:** test — VALE-shaped fixture (shares 2012-12-31, price
2026-09-24) → refusal naming the date; shares 2026-06-30 → value. On a
**copy** of the user's base: market_cap refusals/values before → after.

## M2. check_mention matches guard file names only

`agent/check_mention.sh`: match `p1_rule.sh` / `p6_rule.sh` (file names),
not the bare tokens `p1` / `p6`.
**Done when:** test — HEAD message «(P1: удалённых 0)» with no guard file
changed → green; message naming `p6_rule.sh` with the file unchanged →
red as today.

## M3. Balance at a window border may come from a restated filing

Stock lookup at an exact border date: `as_reported` first; if none for
that exact date, the `restated` fact for the **same date** is accepted
and marked in lineage (`basis: restated`, filing named). No other date is
ever substituted. Amend ADR-0025 clause 5 accordingly.
**Done when:** tests — only `restated` at the border → value, lineage
says `restated`; nothing at that date → `period_mismatch` as now. On a
copy: ORCL, AAPL, JPM `roe`/`asset_turnover` before → after; the 20
industry cells computed before → after.

## M4. Industry row says how many members carry a value

When `peer_set_too_small` is caused by missing values (not by members),
the line reads «участников N, значение меры есть у K» in `rusterm
industry`, TUI and the Industry tab.
**Done when:** test — 8 members, value on 1 → the phrase with 8 and 1.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Change `AGGREGATE_MIN_PEERS` or the 730-day window.
- Write to `~/EquityLab` (P7): measure on a copy.
