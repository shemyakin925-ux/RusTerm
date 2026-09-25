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

`agent/relay.py`, 70 insertions, 0 deletions; new `tests/test_task98_h2_hand_clock.py`
(220 lines, 5 teeth).

* `state_clock_refusal(state_file)` — parses `updated_at` the way O0 does
  (`fromisoformat` after swapping `Z` for `+00:00`, requires a tz), compares
  against `datetime.now(timezone.utc)` and returns `None` inside ±15 minutes
  (`STATE_CLOCK_TOLERANCE_MIN = 15`, the same tolerance as O0). Every refusal
  says what the stamp was, what the real clock is, the drift in minutes, the
  tolerance, «ход не передан, приёмка не запускалась» and the copy-pasteable
  fix command (`FIX_CLOCK_COMMAND`, a `python3 - <<'PY'` heredoc that rewrites
  only `updated_at`).
* Called in `cmd_hand` immediately after the pause check and **before** the
  `run_acceptance` block, so a stale clock never pays an acceptance pass.
* `agent/selfcheck.sh` was not touched — O0 stays exactly as it was, as the
  spec requires.
* Two decisions the spec left open, both pinned by a tooth:
  1. no `agent/STATE.json` in the tree → the gate is silent (relay's own unit
     sandboxes, and `hand` on a plumbing tree without STATE, must keep working);
  2. `--force` overrides the clock but prints
     `hand: --force поверх просроченных часов — …` (see Disputed 2 for why this
     is not a nicety).

**Verification** — the Done-when, run in a sandbox (bare `origin` in `tmp_path`,
no network, acceptance stubbed by a script that appends to `.acceptance-ran`):

```
$ python3 -m pytest tests/test_task98_h2_hand_clock.py -q
.....                                                                    [100%]
```

1. `updated_at` 44 min old → `hand` exits 5, `.acceptance-ran` **absent** (so
   the refusal happened before acceptance), words name the stamp, the
   tolerance and the fix command, and `origin`'s baton still reads
   holder=executor round=12.
2. fresh stamp → `hand` exits 0, the stub ran, baton on `origin` is
   holder=coordinator round=13.
3. stamp 44 min in the **future** → refused too (O0 compares `abs(drift)`).
4. `updated_at="вчера после обеда"` → refused, «не ISO-8601», acceptance not
   run; with `agent/STATE.json` deleted → hand proceeds.
5. stale + `--force` → proceeds, and the override line is in the output.

The emitted fix command was executed for real (in a temp dir, not in the
clone): rc 0, `updated_at = 2026-09-25T18:37:26Z`, and `state_clock_refusal`
then returned `None`.

The regression next to it — `python3 -m pytest tests/test_task98_h2_hand_clock.py
tests/test_task89_d2_relay_index.py -q` → 9 passed: the D2 sandboxes carry no
`agent/STATE.json`, so the new gate does not change what D2 pinned.

### H3 — verify cleans only its own trees

Not started.

### H4 — guard file stops growing

Not started.

## Blocked

None.

## What not to trust

* H2 was measured against a **stubbed** `agent/acceptance.sh` in a sandbox, as
  the spec's Done-when requires. That proves the order (clock → acceptance)
  inside `cmd_hand`; it does not prove that a real 13-check acceptance still
  passes after the change — the full chain only runs at commit time, and its
  result is recorded in the Runs table row for this commit, not here.
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

* **H2's gate lands on the coordinator's hands too, and this round's own hand
  would have been refused by it.** `cmd_hand` is one function for both roles.
  Measured at arrival: `agent/BATON.json` says `handed_at 2026-09-25T17:47:31Z`,
  and the `agent/STATE.json` that hand carried was stamped
  `2026-09-25T09:20:31Z` — 507 minutes old, 34× the tolerance. Without an
  escape, every coordinator hand becomes a `--force` hand, and a routine
  `--force` is a dead guard. Implemented the escape with a loud line
  (`hand: --force поверх просроченных часов — …`, tooth 5), which is the most
  H2 can do from the executor's side. Ask: TASK-99's item (have `hand` stamp
  `agent/STATE.json` itself) is the cure — it should also say *whose* clock
  the gate believes, e.g. apply it only when `--to coordinator`, or have `hand`
  refresh the stamp of the side that is handing.

## Runs

| # | Command | Result |
|---|---------|--------|
| 1 | `git fetch origin agent/night-11` + `git rev-parse --short HEAD origin/agent/night-11` + `git status --porcelain` | `HEAD=93ba7bc origin=93ba7bc dirty=0`, baton holder `executor` round 127 |
| 2 | `python3 -m pytest tests/test_report_sections.py -q` (before edits) | 1 failed: `test_done_items_have_code_commits_in_round`, items `['D1', 'D2', 'D3']` |
| 3 | `grep -n 'rusterm-relay-verify\|night-10' .claude/skills/run-agent-relay/SKILL.md` (before) | 6 lines: 55, 62, 158, 170, 173, 207 |
| 4 | same grep (after the H1 edit) | no output, `rc=1` — the spec's Done when |
| 5 | `git diff --stat` | one file, `.claude/skills/run-agent-relay/SKILL.md`, 9 insertions and 7 deletions |
| 6 | `python3 -c` calling `verify_worktree(None, …)` twice + `verify_worktree('/tmp/mine', …)` | unique paths, `True`; explicit path honoured |
| 7 | H1 commit `8b4dfa9` (pre-commit → selfcheck → acceptance) | `Итог: пройдено 13, провалено 0`, `Принято.`, `SELFCHECK OK`, rc 0; 3 files, 154 insertions, 14 deletions; pushed `93ba7bc..8b4dfa9` |
| 8 | `python3 -m pytest tests/test_task98_h2_hand_clock.py -q --tb=short` (after the 4th tooth was fixed) | `.....` — 5 passed, no failures |
| 9 | `python3 -m pytest tests/test_task98_h2_hand_clock.py tests/test_task89_d2_relay_index.py -q` | 9 passed |
| 10 | `FIX_CLOCK_COMMAND` executed in a throwaway temp dir with a 2026-01-01 stamp | rc 0, `updated_at = 2026-09-25T18:37:26Z`, `state_clock_refusal` → `None`; the 44-min case prints `на +44.4 мин (допуск 15, тот же, что у O0) — ход не передан, приёмка не запускалась` + the command |
| 11 | accidental, then measured: `tests/test_i5_guard_source.py` killed mid-run (it nests a real selfcheck, ~8 min per case), then `git diff --cached -- agent/p6_rule.sh` | the guard came out modified **and staged**: `+116 lines` vs `+114` in HEAD, an extra blank + `# i5 green case: staged widening` in the index. Restored with `git restore --staged --worktree agent/p6_rule.sh`. Mechanism evidence for H4 |

## HANDOFF

Interim block, round 127, written after H1 and H2 (the final one comes at the
close of the round and is what the guard checks).

Status: PARTIAL, round in progress.
Items done: H1, H2.
Items not done: H3, H4.
Verified: the H1 grep gate is empty; the default verify path is unique per run
and an explicit path still honoured (both by calling `verify_worktree`
offline); H2's five teeth in a sandbox with the acceptance stubbed — stale
clock refuses before acceptance, fresh clock reaches it, future stamp refused,
unparsable stamp refused, missing STATE ignored, `--force` overrides loudly.
Not verified: H1/H2 were not exercised through a real `relay.py verify` or a
real network `hand`; H3 and H4 have no work and no tests yet.
Budget: network 0, LLM 0; 39 cumulative requests, unchanged since the round-125
close. The only network use is git (fetch, push).
Asks: Disputed 1 (H1's gate is wider than its body) and Disputed 2 (H2's gate
also fires on the coordinator's hands; TASK-99 should say whose clock it
believes).
