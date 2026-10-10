# TASK-101 — hand never names an unborn report (REPORT-99 Disputed)

- **Status: ACCEPTED** (round 134, 26.09)
- **Report:** `agent/REPORT-101.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-101.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** right after TASK-100, before TASK-97. One item.

РАЗРЕШЕНО ПРАВИТЬ: agent/relay.py

## Where we are

TASK-99 accepted (round 130, fresh clone 13/0; one assert replaced under
a declared ЗАМЕНА-БУЛАВКИ, stronger). Rulings:

| # | Ruling |
|---|---|
| 1 | right → L1 (variant d: hand creates the skeleton) |
| 2 | right — owned by TASK-100 K1, unchanged |
| 3 | right — coordinator added `handed` to `AGENTS.md`. No work |

## L1. hand creates a missing report skeleton

If the `--report` file is absent from the tree, `hand` writes a skeleton
and puts it into the same baton commit:

```
# REPORT-N — <task title line>

## Done
## Blocked
## What not to trust
## Disputed
## Runs
## HANDOFF
Status: NOT STARTED
```

An existing report is never overwritten.
**Done when:** test in a scratch clone — `hand --report agent/REPORT-X.md`
with no such file → baton commit contains it, the whole
`tests/test_report_sections.py` + `tests/test_state_report_tracked.py`
are green right after the hand; existing report byte-identical after a
hand that names it.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, rule scripts, `githooks/`,
  `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` or create anything in `~` (P7).
