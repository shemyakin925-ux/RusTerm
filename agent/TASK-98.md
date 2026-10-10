# TASK-98 — relay hygiene from REPORT-88 Disputed

- **Status: ACCEPTED** (round 128, 26.09)
- **Report:** `agent/REPORT-98.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-98.md --note "<line>"`;
  then immediately `wait --for executor --timeout 3600`.
- **Budgets:** network 0, LLM 0.
- **Queue:** after TASK-89, before TASK-97. Small; one commit per item.

РАЗРЕШЕНО ПРАВИТЬ: agent/relay.py
РАЗРЕШЕНО ПРАВИТЬ: agent/p6_rule.sh
РАЗРЕШЕНО ПРАВИТЬ: agent/selfcheck.sh

The skill file (H1) is not a guarded path — no authorization line needed.
`selfcheck.sh` and `p6_rule.sh` are opened **only** for H4 below.
Any other line changed in them = rejected round.

## Where we are

TASK-88 accepted (round 124, fresh clone 13/0). Its five Disputed
entries are all upheld:

| # | Ruling | Item |
|---|---|---|
| 1 | right | H1 |
| 2 | right — O0 never fires on commit | H2 |
| 3 | right — verify trees pile up | H3 |
| 4 | right — guard file grows | H4 |
| 5 | right — no work: the hand verdict is recorded by the coordinator in `CONTEXT.md`; the report's close-out row says «hand verdict: recorded by coordinator», no placeholder number | — |

## H1. Skill text names the new verify default

`.claude/skills/run-agent-relay/SKILL.md`: the `verify --worktree
/tmp/rusterm-relay-verify` line → the C1 default (no `--worktree`), branch
`agent/night-11`.
**Done when:** `grep -n 'rusterm-relay-verify\|night-10' .claude/skills/run-agent-relay/SKILL.md` is empty.

## H2. Stale `updated_at` cannot be handed

`relay.py hand` refuses (rc≠0, words + the fix command) when
`agent/STATE.json` `updated_at` differs from real UTC by > 15 min — the
same tolerance as O0. Do not change O0 in `selfcheck.sh`.
**Done when:** test — STATE 44 min old → `hand` refuses before running
acceptance; fresh → proceeds (acceptance stubbed).

## H3. verify cleans only its own trees

`cmd_verify` writes a stamp file (`.relay-verify-owner`, pid + run id)
into each tree it creates; after the run (green or red) it removes that
tree; at start it removes stale trees under its default parent that carry
**its** stamp and whose pid is dead. A tree without the stamp is never
deleted.
**Done when:** tests — own tree removed after run; stale stamped tree
removed; unstamped tree left intact.

## H4. Guard file stops growing

- `agent/p6_rule.sh`: drop the trailing `# i5 green case: staged widening`
  line(s) after `exit 0`.
- the I5 demonstration in `selfcheck.sh` writes to a temp copy of the
  guard, never to the tracked `agent/p6_rule.sh`.
**Done when:** test — run `selfcheck.sh` standalone twice in a scratch
clone → `git status --porcelain agent/p6_rule.sh` empty; `tail -1
agent/p6_rule.sh` is `exit 0`; acceptance 13/0.

## Do not

- Touch `acceptance.sh`, `p1_rule.sh`, `githooks/`, `PROTOCOL.md`,
  `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` or create anything in `~` (P7).
