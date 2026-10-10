# TASK-100 — relay follow-ups from REPORT-98 Disputed

- **Status: ACCEPTED** (round 132, 26.09)
- **Report:** `agent/REPORT-100.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-100.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** right after TASK-99, before TASK-97. One commit per item.

РАЗРЕШЕНО ПРАВИТЬ: agent/relay.py

## Where we are

TASK-98 accepted (round 128, fresh clone 13/0; 2 asserts replaced under
a declared ЗАМЕНА-БУЛАВКИ, 4→6 in the module — stronger). Rulings:

| # | Ruling |
|---|---|
| 1 | right. Standing rule (in CONTEXT): **the Done-when gate governs**; if it is wider than the body, satisfy the gate |
| 2 | right → K1 |
| 3 | right → K2 |
| 4 | right → K3 (stamp outside the tree) |
| 5 | right — H4 as built is accepted; M1 keeps proving staged work survives. No work |

## K1. Whose clock the H2 gate believes

With TASK-99 J1 `hand` stamps `agent/STATE.json` itself. Order inside
`hand`: stamp first, then the H2 check sees a fresh clock — so H2 guards
only a STATE that `hand` could not stamp (malformed/missing): refuse
with words. `--force` over a stale clock is no longer a routine path.
**Done when:** test — STATE 500 min old, plain `hand` (no `--force`)
proceeds and the committed STATE carries a fresh `updated_at`; malformed
STATE → refused with words.

## K2. A red verify keeps its tree

Green → tree removed (as now). Red → tree **kept**, and the last line is
`дерево оставлено для разбора: <path> — удалит следующий verify`.
The next run removes stale stamped trees as H3 does.
**Done when:** tests — red run leaves the tree and prints the path; next
run removes it.

## K3. Stamp outside the tree

Stamp moves to `<parent>/<tree-name>.owner` (sibling); nothing is
written inside the tree; drop the `.gitignore` line added for it.
**Done when:** test — after verify, `git status --porcelain` inside the
tree is empty and the sibling stamp exists (red case) / is gone (green).

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, rule scripts, `githooks/`,
  `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` or create anything in `~` (P7).
