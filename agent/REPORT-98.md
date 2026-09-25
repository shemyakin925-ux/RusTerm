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

Implementation in `agent/relay.py` (+108/−7), `import shutil` added:

* `VERIFY_TREE_PREFIX = "rusterm-relay-verify-"` and
  `VERIFY_OWNER = ".relay-verify-owner"` sit next to `verify_worktree`.
* `pid_alive(pid)` — signal 0. `PermissionError` counts as **alive**: a
  foreign process holding the pid must not let the sweep delete a tree
  somebody is using.
* `verify_owner(work)` — the stamp as a dict, or `None` when there is no
  stamp / it does not parse. No stamp = not ours = never deleted, which
  is the second half of the item ("A tree without the stamp is never
  deleted").
* `stamp_verify_tree(work)` — writes `{"pid": <os.getpid()>, "run":
  <tree name>}`. Run id = the tree's own name because that is what the
  default path already makes unique (head, UTC stamp, pid, counter).
* `remove_verify_tree(work)` — `git worktree remove --force`, then
  `shutil.rmtree` if the directory is still there, then
  `git worktree prune`.
* `sweep_stale_verify_trees(parent)` — candidates = directories under
  `parent` matching the prefix, stamped, with a dead pid. Returns what it
  removed so `cmd_verify` can name each one.
* `cmd_verify` — sweep first (default parent = `tempfile.gettempdir()`,
  the same value `verify_worktree` uses); `ours` is "the tree did not
  exist when we got here", i.e. exactly the branch that runs
  `git worktree add`; that branch also stamps. The acceptance call is
  wrapped in `try/finally`, so a green and a red run remove the tree the
  same way. A tree that already existed (explicit `--worktree`) is
  neither stamped nor removed.

Two decisions the spec left open:

* An explicit `--worktree` path that did **not** exist is also removed:
  the item's wording is "each tree it creates", and a directory verify
  created is verify's. Reusing a pre-existing explicit tree — the
  operator's own — keeps working, that is what C1's tests pin.
* The stamp lives inside the tree, so it is an untracked file. It cannot
  trip `verify_refusal`: the refusal check runs before the tree exists,
  and a swept tree is deleted without ever being inspected for trash.

Tests: new `tests/test_task98_h3_verify_trees.py`, 5 teeth, all on a
local bare "origin" in `tmp_path` with `TMPDIR` pointed at the sandbox
(the sweep therefore never touches the real temp dir) and a stub
`agent/acceptance.sh` committed **in that sandbox** — the real
acceptance script is neither copied there nor edited:

1. green run: printed default tree gone, its `worktree list` entry gone,
   the removal line printed;
2. red run (stub exits 7): rc 5, tree gone just the same;
3. stale tree, stamped, dead pid (a reaped child): swept at start and
   named in stdout, this run's own tree also gone at the end;
4. same prefix, **no** stamp: survives, its file byte-identical, not
   mentioned in stdout;
5. stamped with a **live** pid (the test process): survives, not
   mentioned.

`tests/test_relay_verify_worktree.py::test_default_worktree_path_differs_between_runs`
had to change: it planted `leftover.py` inside the first run's tree, and
under H3 that tree no longer exists after the run (`FileNotFoundError`).
Rewritten with more teeth, not fewer — the diff removes 2 `assert` lines
and adds 4: default paths still differ between two runs, **and** neither
tree survives its own run, **and** no `rusterm-relay-verify-*` is left
under the parent. The property C1 pinned ("не наследует мусор") is now
carried by removal instead of by path uniqueness.

**What the first live run caught — all teeth were green when it happened.**
`python3 agent/relay.py --branch agent/night-11 verify` on the real branch,
with two trees planted by hand under the real temp dir (one stamped with a
reaped child's pid, one unstamped): the sweep line named the stale tree, the
unstamped tree survived, this run's tree was removed at the end — and the
acceptance inside that tree came back `Итог: пройдено 10, провалено 3`. One
cause, and it is H3's own file: `?? .relay-verify-owner` tripped check 13
(«нет мусора вне git»), and both I5 cases — which run `selfcheck.sh` inside
that same linked worktree — went red through the same check 13. No sandbox
stub could see this: a stub does not implement check 13. Fix: the stamp name
goes into `.gitignore` (+5, comment included), and `untracked_files()` drops
that single name so `verify_refusal` cannot report verify's own stamp as
foreign trash on a tree whose commit predates the line. Tooth 6
(`test_the_stamp_lies_in_the_tree_and_is_not_trash`) copies the repository's
real `.gitignore` into the sandbox verbatim and asserts both halves from
inside the tree: `МЕТКА: есть`, and no stamp in the `git status --porcelain`
line the stub prints. Measured biting: with the `.gitignore` line deleted the
tooth fails on `метка видна мусором: ВНЕ-GIT: ?? .relay-verify-owner`; put
back, the module is green (9 passed with the C1 module).


### H4 — guard file stops growing

Not started.

## Blocked

None.

## What not to trust

* H3's six teeth run against a **stub** `agent/acceptance.sh`. The stub now
  reports what check 13 reports (`git status --porcelain`) and whether the
  stamp is present, which is how the collision was reproduced in the sandbox —
  but it is still not the 13-check script. The end-to-end proof is the live
  `verify` row in Runs; the row after the H3 commit is the one that says
  whether the fix holds on the real branch.
* The `.gitignore` line hides the stamp only on commits that carry the line.
  `verify` of an older commit or branch with this `relay.py` still shows
  `?? .relay-verify-owner` to check 13 and turns it red — `untracked_files()`
  cannot help, because check 13 calls `git status` itself and
  `agent/acceptance.sh` is untouchable. Reproduce: check out `964a4cf` in a
  scratch clone, run `python3 <new relay> verify` from a tree that has the
  H3 code. Not measured — the recipe is a reading of the two files.
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

* **H3 removes the thing you dig into after a red `verify`.** The item says
  "removes that tree after the run (green or red)", and it is now true for both
  colours, so the failing tree of a red acceptance no longer exists to `cd`
  into and re-run one check in. The streamed terminal output survives (that is
  what the exit line is for) and `--worktree <path>` still keeps a tree, so the
  escape hatch exists — but it is operator memory, not a documented procedure:
  `SKILL.md` says nothing either way about what is left behind. Ask: either
  record in `SKILL.md` that a red `verify` is re-runnable only with an explicit
  `--worktree`, or have `verify` print the path plus "дерево убрано, для
  разбора гони с --worktree" on the red branch.

* **H3's stamp is invisible only where `.gitignore` says so.** The item fixes
  the file and its place — `.relay-verify-owner` inside the tree — and inside
  the tree it is untracked trash to check 13 on every commit that predates the
  `.gitignore` line. The alternative was a sibling stamp next to the tree
  (`<parent>/<name>.owner`), invisible to any acceptance run and outside the
  tree's own status, but that contradicts "writes a stamp file … into each
  tree it creates". Chose the letter of the item plus one `.gitignore` line.
  Consequence for the coordinator: a round that verifies an older head with a
  new `relay.py` gets check 13 red for a reason that looks like the
  executor's mess. Ask: keep it, or move the stamp outside the tree in
  TASK-99.

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
| 12 | `python3 -m pytest tests/test_task98_h3_verify_trees.py tests/test_relay_verify_worktree.py -q --tb=line` (before the `.gitignore` fix) | 7 passed, 1 failed — `test_default_worktree_path_differs_between_runs`: `FileNotFoundError: …/rusterm-relay-verify-…-1/leftover.py`, i.e. H3 removed the tree the C1 test planted into |
| 13 | live `python3 agent/relay.py --branch agent/night-11 verify` at 19:18Z, with two hand-planted trees under the real temp dir | line 1 `verify: убрано осевшее дерево …-LIVESTALE-62414-1 — метка владельца, pid мёртв`; `…-LIVEFOREIGN-1-2` untouched and still registered; `verify: дерево … убрано после прогона`; `код возврата приёмки: 3`, `Итог: пройдено 10, провалено 3` — checks 3, 12 and 13, all on `?? .relay-verify-owner` |
| 14 | `I5_NESTED=1 python3 -m pytest tests/test_i5_guard_source.py -q` in a scratch clone of `964a4cf` | `ssss` (4 skipped), `git status --porcelain agent/p6_rule.sh` empty, staged list empty, guard still 114 lines — the commit path never touches the tracked guard; the writer is a **non-nested** run |
| 15 | tooth-biting: `.gitignore` line deleted → H3 module; line restored → H3 + C1 modules | red on `метка видна мусором: ВНЕ-GIT: ?? .relay-verify-owner` → then 9 passed |

## HANDOFF

Interim block, round 127, written after H1, H2 and H3 (the final one comes at
the close of the round and is what the guard checks).

Status: PARTIAL, round in progress.
Items done: H1, H2, H3.
Items not done: H4.
Verified: the H1 grep gate is empty; the default verify path is unique per run
and an explicit path still honoured (both by calling `verify_worktree`
offline); H2's five teeth in a sandbox with the acceptance stubbed — stale
clock refuses before acceptance, fresh clock reaches it, future stamp refused,
unparsable stamp refused, missing STATE ignored, `--force` overrides loudly;
H3's six teeth in the same kind of sandbox (own tree gone after a green and
after a red run, stale stamped tree swept, unstamped and live-pid trees left
alone, stamp present but invisible to `git status`), plus one live `verify` on
the real branch — which is what found the check-13 collision H3's stamp
caused. Housekeeping still owed by me: the hand-planted
`rusterm-relay-verify-…-LIVEFOREIGN-1-2` tree is registered in this clone and
must be removed before the round closes.
Not verified: H1/H2 were not exercised through a real network `hand`; the
post-fix live `verify` (the same command, once the fix is on the branch) had
not run yet when this block was written; H4 has no work and no tests yet.
Budget: network 0, LLM 0; 39 cumulative requests, unchanged since the round-125
close. The only network use is git (fetch, push).
Asks: the four entries of the ## Disputed section — 1: H1's gate is wider
than its body; 2: H2's gate also fires on the coordinator's hands, and TASK-99
should say whose clock it believes; 3: a red `verify` now leaves nothing to dig
into; 4: the stamp is invisible only on commits carrying the `.gitignore` line.
