# TASK-99 — hand starts the next round green (REPORT-89 Disputed)

- **Status: READY**
- **Report:** `agent/REPORT-99.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-99.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** after TASK-98, before TASK-97. One commit per item.

РАЗРЕШЕНО ПРАВИТЬ: agent/relay.py

## Where we are

TASK-89 accepted (round 126, fresh clone 13/0; 6 asserts replaced under
a declared ЗАМЕНА-БУЛАВКИ with 12 added — stronger). Disputed rulings:

| # | Ruling |
|---|---|
| 1 | right — J1 below. This **replaces TASK-97 Q12 row 1**; in TASK-97 skip it and write «done in TASK-99 J1» |
| 2 | keep as is: a refused hand leaves `--add` files staged (work is not rolled back). J2: say so in words |

## J1. `hand` stamps STATE

`relay.py hand` writes into `agent/STATE.json`, in the same baton commit:
`task`, `report` (from its arguments), `status: "handed"`, fresh
`updated_at`. The receiving side starts with the L3 guard green.
**Done when:** test — after `hand` in a scratch clone,
`test_done_items_have_code_commits_in_round` is green with no further
commit; STATE `task` equals BATON `task`.

## J2. Refused hand names what stays staged

On refusal `hand` prints «в индексе остались: <files> — это твоя работа,
не откатана» for every `--add` file still staged.
**Done when:** test with a rejecting pre-commit stub — output lists both
`--add` files; BATON not staged.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, rule scripts, `githooks/`,
  `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` or create anything in `~` (P7).
