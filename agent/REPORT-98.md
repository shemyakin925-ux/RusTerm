# REPORT-98 — TASK-98: relay hygiene from REPORT-88 Disputed

Round 127, branch `agent/night-11`, spec `agent/TASK-98.md`. Budgets: network 0,
LLM 0 — honoured: no data API request and no live LLM call in this round; the
only network use is `git` (fetch + push), which the relay protocol requires.

## Arrival state (measured at round 127, before the first source edit)

* `git fetch origin agent/night-11` → `HEAD=93ba7bc origin=93ba7bc dirty=0`.
  `agent/BATON.json` on the branch head: holder `executor`, round 127, task
  `agent/TASK-98.md`, report `agent/REPORT-98.md`.
* The spec was amended after it was written: `df691f7` dropped the
  `РАЗРЕШЕНО ПРАВИТЬ: .claude/skills/run-agent-relay/SKILL.md` line and states
  the skill file is not a guarded path. Re-read `agent/TASK-98.md` from the
  branch head (72 lines) rather than from the copy in the earlier hand note.
* Arrival is red, as protocol predicts, on exactly one check —
  `python3 -m pytest tests/test_report_sections.py -q` →
  `FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round`,
  `AssertionError: пункты ['D1', 'D2', 'D3'] объявлены сделанными, но коммита
  круга с реализацией (не только tests/) не найдено`. `agent/STATE.json` still
  named `agent/REPORT-89.md`, whose `Items done: D1, D2, D3` now fall outside
  the round-127 window. Fixed by the first item commit, which stamps STATE and
  creates `agent/REPORT-98.md`.
* H1 gate before the edit — `grep -n 'rusterm-relay-verify\|night-10'
  .claude/skills/run-agent-relay/SKILL.md` → 6 lines: 55, 62, 158, 170, 173,
  207. The spec body names only the `verify --worktree` line (62); the other
  five are `agent/night-10` / `night-10` mentions in prose. See Disputed 1.
* H4 residue measured: `agent/p6_rule.sh` is 114 lines, `grep -c "i5 green
  case"` → 1, and the last line of the file is `# i5 green case: staged
  widening`, i.e. after `exit 0`.

## Done

### H1 — skill text names the new verify default

`.claude/skills/run-agent-relay/SKILL.md`, 6 lines changed (9 insertions, 7
deletions), one file:

* Step 2 command (was line 55): `--branch agent/night-10` → `agent/night-11`.
* Step 3 command (was line 62): `verify --worktree /tmp/rusterm-relay-verify`
  → `python3 agent/relay.py --branch agent/night-11 verify`, plus one prose
  sentence naming the reason: the default path is unique per run (TASK-88 C1),
  and one shared path handed a run's junk to the next run.
* Lines 158, 170, 173, 207 (prose about the merged shift branch and the real
  `verify` run that gave «пройдено 12, провалено 1»): the branch token was
  replaced with a branch-neutral description («влитые ветки смены», «прежняя
  (уже влитая) ветка смены», «настоящей (не тестовой) веткой смены»). The
  claims are kept as they were measured; only the branch name that the gate
  forbids is dropped. `docs/adr/0019-net-vendorskogo-adjusted.md` and
  `REPORT-30.md` are still named, so the evidence is still checkable.

**Verification.** `grep -n 'rusterm-relay-verify\|night-10'
.claude/skills/run-agent-relay/SKILL.md` → no output, `rc=1` (the spec's Done
when). The documented default was checked against the code it documents,
offline, no network:

```
default  : /var/folders/…/T/rusterm-relay-verify-abcdef1-20260925T181555Z-45738-1
unique   : True
no --worktree needed: path_arg=None ok
explicit : /tmp/mine
```

— `verify_worktree(None, head)` and `verify_worktree('/tmp/mine', head)` both
return, two consecutive default calls differ, an explicit path is still honoured
verbatim. Not run: `relay.py verify` itself (it would pay a full acceptance
pass, ~8 min, for a doc-only change).

### H2 — stale `updated_at` cannot be handed

Not started.

### H3 — verify cleans only its own trees

Not started.

### H4 — guard file stops growing

Not started.

## Blocked

None.

## What not to trust

* The report is a live document; only sections above claim to be verified at
  the moment they were written. Sections marked "Not started" have had no work
  and no test.
* H1 changes documentation only. Nothing in `agent/relay.py` moved, so the
  sentence "the default path is unique per run" describes TASK-88 C1 as already
  shipped — verified by reading and calling `verify_worktree`, not by a full
  `verify` run.
* The numbers in "Arrival state" were measured in the shift clone at
  `/Users/anton/Documents/Qoder/2026-09-22/c597aa77/rt-night11-exec`. Line
  numbers quoted from `agent/relay.py` (531 `verify_worktree`, 573 `cmd_verify`,
  850 `--worktree` default) drift: re-measure before relying on them in H2/H3.
* No data API and no LLM was called, so nothing in this round can be taken as
  evidence about prices, quotes or chat.

## Disputed

* **H1's "Done when" is wider than H1's body.** The body names one line (the
  `verify --worktree /tmp/rusterm-relay-verify` command); the gate —
  `grep -n 'rusterm-relay-verify\|night-10' …` empty — matched 6, five of them
  prose about events measured on the `agent/night-10` branch. Satisfied the
  gate by rewriting all six: the command lines now say `agent/night-11`, the
  prose kept every measured fact and lost only the forbidden branch token,
  because relabelling those lines as `night-11` would have asserted runs that
  never happened there. Ask: when a gate is wider than the body, say so in the
  body — otherwise the executor has to guess whether prose is in scope.

## Runs

| # | Command | Result |
|---|---------|--------|
| 1 | `git fetch origin agent/night-11` + `git rev-parse --short HEAD origin/agent/night-11` + `git status --porcelain` | `HEAD=93ba7bc origin=93ba7bc dirty=0`, baton holder `executor` round 127 |
| 2 | `python3 -m pytest tests/test_report_sections.py -q` (before edits) | 1 failed: `test_done_items_have_code_commits_in_round`, items `['D1', 'D2', 'D3']` |
| 3 | `grep -n 'rusterm-relay-verify\|night-10' .claude/skills/run-agent-relay/SKILL.md` (before) | 6 lines: 55, 62, 158, 170, 173, 207 |
| 4 | same grep (after the H1 edit) | no output, `rc=1` — the spec's Done when |
| 5 | `git diff --stat` | one file, `.claude/skills/run-agent-relay/SKILL.md`, 9 insertions and 7 deletions |
| 6 | `python3 -c` calling `verify_worktree(None, …)` twice + `verify_worktree('/tmp/mine', …)` | unique paths, `True`; explicit path honoured |

## HANDOFF

Status: PARTIAL — round 127 in progress.
Items done: H1.
Items not done: H2, H3, H4.
Verified: the H1 grep gate is empty; the default verify path is unique per run
and an explicit path is still honoured, both checked by calling
`verify_worktree` offline.
Not verified: nothing beyond H1 has been started; the arrival-red check
`test_done_items_have_code_commits_in_round` is expected to be repaired by this
commit (STATE names this report, this report's `Items done` names H1, and H1's
commit touches a non-`tests/` file).
Budget: network 0 and LLM 0 so far; 39 cumulative requests, unchanged from the
round-125 close.
Ask: Disputed 1 above.
