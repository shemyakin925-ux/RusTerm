# TASK-103 — two small fixes from REPORT-102 Disputed; then resume TASK-97

- **Status: ACCEPTED** (round 140, 29.09)
- **Report:** `agent/REPORT-103.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-103.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** now; then resume TASK-97 at Q5 (→ Q7 → Q6 → Q1 → Q2 → Q3 →
  Q4 → Q12 (2, 7)) **in the same round** — hand only after TASK-97 is
  finished or you stop; report both in `REPORT-103.md`.

РАЗРЕШЕНО ПРАВИТЬ: agent/check_mention.sh

## Where we are

TASK-102 accepted (round 138, fresh clone 13/0, 0 asserts removed).
Copy: valued measures 528 → 607, `period_mismatch` 95 → 12, industry
cells with a value 4 → 8 of 20. Rulings on REPORT-102 Disputed:

| # | Ruling | Item |
|---|---|---|
| 1 | `div_yield` stays as built (no share input; dps has its own 550-day rule). No work | — |
| 2 | right — a bug | N2 |
| 3 | right, option (a): subject line only | N1 |

## N1. check_mention reads the subject line only

The barrier matches guard file names in the commit **subject** (first
line) only; the body is a citation.
**Done when:** tests — body cites `agent/p1_rule.sh`, file unchanged →
green; subject names `p6_rule.sh`, file unchanged → red; `git revert`
subject of a guard commit → still covered.

## N2. Aggregate currency comes from members with a value

`core/industry/aggregate.py`: the currency check reads only members that
carry a value; zero valued members → `peer_set_too_small` with the M4
phrase, never `currency_mismatch`.
**Done when:** test — absolute measure, 9 members, 0 values, mixed
lineage currencies → `peer_set_too_small`, phrase «значение меры есть у
0»; copy of the user's base: `currency_mismatch` cells before → after.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` (P7).
