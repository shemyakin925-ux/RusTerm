# REPORT-99 — TASK-99: `hand` stamps STATE (REPORT-89 Disputed 1)

- **Branch:** `agent/night-11`, round 129, holder executor.
- **Spec:** `agent/TASK-99.md`. File scope: `agent/relay.py` only.
- **Budgets:** network 0, LLM 0 (git transport only).
- **Rulings carried in:** #1 → J1, and it **replaces TASK-97 Q12 row 1**
  (in TASK-97 skip that row and write «done in TASK-99 J1»); #2 → J2 is
  words only, a refused hand keeps `--add` files staged.

## Arrival state (measured at round 129, before the first source edit)

The coordinator's hand commit (`143a48c`) moved BATON to round 129 and
left `agent/STATE.json` naming `agent/REPORT-98.md`. Live run in the
shift clone, no edits yet:

```
$ python3 -m pytest -q tests/test_report_sections.py::test_done_items_have_code_commits_in_round
E  AssertionError: пункты ['H1', 'H2', 'H3', 'H4'] объявлены сделанными,
   но коммита круга с реализацией (не только tests/) не найдено
FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
```

`_report_text()` reads the report named by STATE, `_round_under_review()`
reads the round from BATON: STATE pointed at the previous shift, whose
H1–H4 commits sit below the `Эстафета: круг 129` boundary. Every item
this shift commits could not make the guard green — the arriving side had
to overwrite STATE by hand, i.e. prove the previous shift's work with its
own hand.

## Done

### J1 — `hand` writes `agent/STATE.json` in the same baton commit

Four fields, spec-verbatim (`agent/relay.py`):

- `_hand_state_stamp()` (relay.py:214) — `task`/`report` from the new
  BATON (so they mirror it even when `--task/--report` were not passed),
  `status: "handed"`, `updated_at = now()`;
- `_state_bytes()` (relay.py:237) — merge, not rewrite: `item`, `step`,
  `model`, the request counters of the previous shift stay. A STATE that
  does not parse as a JSON object prints a line and the stamp starts from
  an empty file;
- `_stamp_working_state()` (relay.py:257) — tree path, written before
  `git add` so the baton commit carries it;
- `push_baton(..., stamp=...)` (relay.py:266, 285–286, 294) — STATE joins
  the commit path list once (explicit `--add agent/STATE.json` does not
  duplicate it) and is no longer treated as «foreign» staged work;
- plumbing path (relay.py:341, 352) — the stamp is built from the branch
  blob (`git show <base>:agent/STATE.json`), not from the caller's
  worktree: a coordinator holding a parallel shift in another branch
  cannot have that shift's clock and report landed in this baton commit;
- `cmd_hand` (relay.py:977, 988) — passes the stamp and echoes which four
  fields went in.

**Done-when, measured.** In a scratch clone with a bare origin: red
before (`hand` without the stamp), and after `hand` —
`1 passed` from `test_done_items_have_code_commits_in_round` with no
further commit; `STATE["task"] == BATON["task"]`.

Module `tests/test_task99_j1_hand_stamps_state.py` — 6 teeth, all green
(`......  [100%]`):

| # | Tooth | Proves |
|---|-------|--------|
| 1 | Done-when gate | green right after `hand`; red again when the STATE bytes are reverted from `HEAD~1` |
| 2 | commit carries STATE once | `STATE.task == BATON.task`, `status=handed`, other fields preserved, `updated_at` within 120 s |
| 3 | mirroring | no `--task/--report` arguments → STATE still equals BATON |
| 4 | dedup | explicit `--add agent/STATE.json` does not list the path twice |
| 5 | own staged STATE | is not «чужое», its edit survives the hand |
| 6 | plumbing | stamps the branch blob, leaves the worktree byte-identical |

Regression, same run: `test_task89_d2_relay_index.py +
test_task98_h2_hand_clock.py + tests/test_task99_j1_hand_stamps_state.py
+ test_no_shared_tmp.py` → 19 passed, rc=0.

Mutation campaign (scratch worktree, `mutate_j1.py`) — see `## Runs`.

### J2 — a refused `hand` names the files it left staged

Spec, verbatim: on refusal `hand` prints
«в индексе остались: <files> — это твоя работа, не откатана» for every
`--add` file still staged. Done when: test with a rejecting pre-commit
stub — output lists both `--add` files; BATON not staged. Ruling #2 keeps
the behaviour («a refused hand leaves `--add` files staged — work is not
rolled back») and asks for words only, so `die` stays the exit for every
other path and only the shape of the message changes.

Implementation (`agent/relay.py`):

- `die_kept(message, extra)` (relay.py:122) — one refusal exit for the
  whole `hand` path. Prints the refusal, then names the leftovers.
  **Names are taken from the index at the moment of refusal
  (`git diff --cached --name-only`), not from the arguments** — the
  push-rejection path runs `reset --mixed` before it refuses, after which
  the argument list would name files that are no longer staged. Mutation
  N3 (argument-derived names) reddens tooth 7, which is exactly that
  lie;
- `cmd_hand` (relay.py:987) — `add` hoisted once, and all nine refusals
  routed through `die_kept(..., add)`: `--to` roles (994), stop file
  (996), H2 clock (1005), red acceptance (1016), no BATON on the remote
  (1020), not the holder (1024), push rejections inside `push_baton`, and
  the post-push origin verification (1051). The early ones matter: a
  caller whose files are already staged is refused before `push_baton`
  ever runs, and would otherwise get a bare error and no names;
- `push_baton` (relay.py:317) — the foreign-index refusal (356), the
  failed commit (374) and both push rejections (tree 393, plumbing 427)
  refuse through `die_kept`, each with the same `extra` list;
- `for rel in add: print("  вложено:", rel)` (relay.py:1060) on success,
  so the symmetric case says where those files went;
- `_baton_back_to_head()` unchanged — D2's rule (BATON back to HEAD,
  foreign staged work untouched) still holds. J2 only reports it.

**Declared repair of J1, not a silent one.** Tooth 1 failed on its first
run: after a commit rejected by the stub the index held
`['agent/STATE.json', 'docs/a.md', 'docs/b.md']`. J1's own stamp survived
the refused hand — a `status: "handed"` line about a transfer that never
happened, riding into the caller's next commit. That is `hand`'s residue,
not the caller's work, so ruling #2 does not cover it, and the D2 rule
that pulls BATON back to HEAD had no equal for STATE. Fixed in this
commit:

- stamping moved **after** the foreign-index check (relay.py:360–362) — a
  refusal that happens before any write cannot leave a stamp behind at
  all;
- `_state_backup()` (relay.py:288) / `_state_restore()` (relay.py:302) —
  the file bytes *and* its index blob are remembered before stamping, and
  restored on every later refusal (commit failure, both push
  rejections). Restoring the blob with `update-index --cacheinfo` rather
  than `reset` is what lets tooth 3 pass: the caller's own staged STATE
  edit has to survive the refusal as *its own* edit, not be wiped to HEAD
  together with the stamp.

Teeth 2 and 3 are the two halves of this repair; both are red without it
(measured — N1 and N4 below).

Module `tests/test_task99_j2_refusal_names_staged.py` — 8 teeth, all
green (`........  [100%]`, rc=0):

| # | Tooth | Proves |
|---|-------|--------|
| 1 | Done-when | rejecting `.git/hooks/pre-commit` stub → stderr names **both** `--add` files; `agent/BATON.json` not in `git diff --cached`; origin BATON still `executor`, round 21 |
| 2 | own stamp rolled back | after a refused hand the worktree STATE equals the pre-hand bytes, its index entry equals the pre-hand blob — no `status: "handed"` survives |
| 3 | caller's own staged STATE | staged edit survives the refusal, unchanged, and is not reported as foreign |
| 4 | foreign-index refusal | names own `--add`, leaves `tools/foreign.py` staged untouched, BATON unstaged, worktree STATE untouched (no stamp written at all) |
| 5 | early refusal | stop-file refusal (before any `git add` inside `hand`) still names the caller's staged work |
| 6 | no `--add` | refusal prints no leftovers line — the words appear only where there is something to name |
| 7 | `--add` not staged | file present in the worktree but absent from the index → no line (names come from the index) |
| 8 | successful hand | commits both files and prints no leftovers line |

Sandbox is a bare origin + clone on `agent/night-j2` (network 0; git
transport only), with `TMPDIR` inside the sandbox and `HOME` left alone
for the reason recorded above. The stub `agent/acceptance.sh` exits 0 —
a clone of a bare origin carries no `core.hooksPath`, so the only hook
the teeth install is the rejecting `pre-commit` of tooth 1.

Regression, this run: `test_task89_d2_relay_index.py +
test_task98_h2_hand_clock.py + test_task99_j1_hand_stamps_state.py +
test_task99_j2_refusal_names_staged.py + test_no_shared_tmp.py` →
27 tests, no failures.

Mutation campaign (`mutate_j2.py`, scratch worktree, relay.py restored
after each run) — see `## Runs`.

## Blocked

Nothing blocked. Both items of this spec are implemented; J2 lands in its
own commit.

## What not to trust

- **The teeth do not run real hooks.** A `git clone` of a bare origin
  carries no `core.hooksPath`, so sandbox commits skip `acceptance.sh`.
  The stub `agent/acceptance.sh` in the fixture exits 0 and only makes the
  commit path reachable. The guard in tooth 1 is the real
  `tests/test_report_sections.py`, byte-copied into the sandbox.
- **`HOME` must not be overridden in the sandbox env.** Measured: with
  `HOME` pointed at the sandbox, a subprocess `python3 -m pytest` loses
  the user-site path and dies with `ModuleNotFoundError: pygments`. The
  fixture sets `TMPDIR` inside the sandbox (that part is deliberate —
  `tests/test_no_shared_tmp.py`) and leaves `HOME` alone; the module
  docstring records this.
- **Tooth 4 is a lock, not a red-before witness.** Mutation M6 (dropping
  the STATE dedup guard) reddens nothing — the `git add --` path is
  tolerant of a repeated pathspec. The dedup exists so the commit's file
  list stays honest; do not read tooth 4 as proof of a fixed bug.
- **`status: "handed"` is a new value this tool writes.** No guard
  validates the STATE `status` enum, so nothing reddens — but AGENTS.md
  documents only `working` / `awaiting_review`. See `## Disputed` 3.
- **The plumbing refusal at relay.py:427 has no tooth of its own.** Every
  J2 tooth refuses in the tree path or before `push_baton`; the plumbing
  branch is only reachable when the shift branch is checked out in
  another worktree *and* the push races. The shared helper `die_kept` is
  covered (N1 reddens four teeth through it), that one call site is not.
- **The leftovers line names only what is both `--add` and staged.**
  Foreign index files are listed by the separate «в индексе лежит чужое»
  message (relay.py:356), not by this line — two refusals, two lists, by
  design: ruling #2 distinguishes «моя работа» from «чужое».
- **Tooth 2 and 3 assert bytes and index blobs, not intent.** They catch
  a stamp that survived a refusal and a caller's edit that got wiped; they
  do not check that the restored blob is the *right* pre-hand edit in
  some third scenario. The N2/N4 mutation rows are what make those two
  teeth mean something.
- The J1 tests never ran the full `agent/selfcheck.sh`; the numbers above
  are module-level runs plus the commit path that acceptance will re-run.

## Disputed

1. **A stamp of a report that does not exist yet is worse than no stamp.**
   Shape: the coordinator calls `hand --report agent/REPORT-100.md` for
   the *next* shift, whose file is not on the branch. Measured in a
   scratch clone (`probe_j1_coordinator_shape.py`, log
   `/tmp/rt99-probe.log`) with the real guard copies:
   - before the hand (STATE names the previous, existing report):
     `8 failed, 26 passed` — the arrival redness J1 exists to fix;
   - after the hand (STATE names the unborn report):
     `12 failed, 22 passed`, all 11 of `test_report_sections.py` except
     one, plus `test_state_report_tracked.py`. `_report_text()` raises
     `FileNotFoundError` for a missing file, so every guard that reads the
     report dies at once — and it dies in the *coordinator's own*
     pre-commit hook, i.e. the coordinator that runs this `hand` cannot
     commit its own next worktree change.
   J1 is implemented literally, per the spec text («`task`, `report`
   (from its arguments)»), because inventing a refusal or a fallback
   policy here would be work not in the TASK. Candidate dispositions:
   (a) `hand` refuses when the named report is absent from the branch and
   offers `--allow-unborn-report`; (b) `hand` stamps the report path only
   when the file exists, keeping the previous one otherwise; (c) the
   coordinator always commits `REPORT-N.md` before calling `hand` — a
   protocol rule, no code. Say which and I will build it.
2. **The H2 clock gate still runs before the stamp.** `state_clock_refusal`
   is checked at the top of `cmd_hand`, so a stale clock refuses the hand
   even though this hand is the thing that would refresh it. TASK-100 K1
   owns the reordering («stamp first, then the H2 check sees a fresh
   clock»); the J1 fixture keeps `updated_at` 3 minutes fresh to stay off
   that gate, with a comment naming K1 as the owner.
3. **AGENTS.md does not know `handed`.** The spec requires the literal
   value `status: "handed"`, so it is written; the file that tells agents
   which values exist lists two. Either the doc gains the third value or
   the spec changes the word — the doc is out of my file scope.

## Runs

| Command | Result |
|---------|--------|
| `pytest -q tests/test_report_sections.py::test_done_items_have_code_commits_in_round` (shift clone, before any edit) | FAILED, `['H1','H2','H3','H4']` |
| `pytest -q tests/test_task99_j1_hand_stamps_state.py` | `6 passed` (rc=0) |
| `pytest -q` on the 4 relay/neighbour modules (J1) | `19 passed` (rc=0) |
| `python3 probe_j1_coordinator_shape.py` | 8 failed → 12 failed, 22 passed (Disputed 1) |
| `python3 mutate_j1.py` | base rc=0; M-table below |
| first run of J2 tooth 1 | FAILED — index after the refused commit held `['agent/STATE.json', 'docs/a.md', 'docs/b.md']` → the J1 repair above |
| `pytest -q tests/test_task99_j2_refusal_names_staged.py` | 8 of 8, rc=0 (`/tmp/rt99-j2.log`) |
| `pytest -q` on the 5 relay/neighbour modules (J1+J2) | 27 tests, all green, rc=0 (`/tmp/rt99-reg5.log` holds `…[100%]` + rc; with `-q` and no `-r` the count line did not reach it, so the number is the dots row) |
| `python3 mutate_j2.py` | base rc=0; N-table below |

Mutation campaigns (`rt99-mut` scratch worktree, detached at `143a48c`,
relay.py restored and byte-checked after each run; the worktree is
removed at the end of the shift). Tooth numbers refer to the module's own
order.

J1, `mutate_j1.py` against `tests/test_task99_j1_hand_stamps_state.py`:

| Mutation | Reddens |
|----------|---------|
| base, no mutation | nothing — rc=0, 6 passed |
| M1 `hand` does not stamp at all (`stamp=None`) | all 6 teeth, and inside tooth 1 the guard run itself: `1 failed` where `1 passed` is asserted |
| M2 plumbing takes STATE from the caller's worktree | 6 |
| M3 stamp overwrites STATE instead of merging | 2, 5, 6 |
| M4 `task`/`report` taken from arguments only, no BATON fallback | 3, 5, 6 |
| M5 own staged STATE treated as foreign again | 5 |
| M6 STATE dedup guard removed | nothing — see `## What not to trust` |

J2, `mutate_j2.py` against `tests/test_task99_j2_refusal_names_staged.py`
(`/tmp/rt99-mut-j2.log`):

| Mutation | Reddens |
|----------|---------|
| base, no mutation | nothing — rc=0 (8 teeth, all dots; `mutate_j2.py` greps for the count line and it did not reach the log, so the number is from the dots row) |
| N1 refusal does not name the leftovers (line silenced) | 1, 2, 4, 5 |
| N2 refusal does not roll back its own STATE stamp | 1, 2, 3 |
| N3 leftovers taken from the arguments, not the index | 7 |
| N4 stamp applied before the foreign-index check | 1, 2, 3, 4 |
| N5 only the first leftover named instead of all | 1, 2, 4 |

Every mutation reddened at least one tooth, and no anchor in the script
missed its target (`сбоев якорей/мутаций: 0`), so the campaign ran against
the file that is in this commit.

## HANDOFF

Status: PARTIAL — J1 and J2 done; J2 lands in this commit, the close-out
hand follows.

- Items done: J1 (previous commit `0902a22`), J2 (this commit: relay.py
  plus `tests/test_task99_j2_refusal_names_staged.py`, and the declared
  J1 repair for the stamp left behind by a refused hand).
- Numbers: J2 module 8 of 8 green; relay neighbourhood 27 of 27;
  mutations N1–N5 each reddening at least one tooth.
- Open asks: three entries in `## Disputed` — the unborn-report shape
  needs a disposition, the H2-before-stamp order is TASK-100 K1's, and
  `handed` needs either a doc line or a different word.
- Question for the coordinator: in TASK-97 skip Q12 row 1 as ruled here,
  or keep the row and let it re-implement what J1 already shipped?

## HANDOFF (FINAL — supersedes the interim values above)

Status: DONE

- Items done: J1 `0902a22`, J2 `1c5e473` — one commit per item, each
  subject naming its item. The J2 commit also carries the declared repair
  of J1 (a refused hand left its own `status: "handed"` stamp behind;
  teeth 2–3 of the J2 module pin both halves).
- Items not done: none from this spec.
- Numbers: J1 module 6 of 6, J2 module 8 of 8, relay neighbourhood 27 of
  27, campaigns M1–M6 and N1–N5 as tabled (each mutation but M6 reddens
  at least one tooth, and M6 is declared a lock in
  `## What not to trust`). Every commit passed acceptance with
  «Итог: пройдено 13, провалено 0» and `SELFCHECK OK`.
- Budgets held: network 0, LLM 0 — git transport (fetch/push) only.
- Scratch cleanup: mutation worktree `rt99-mut` removed at the end of the
  shift; the campaign scripts live outside the repo
  (`../rt99-scratch/`) and the logs in `/tmp/rt99-*.log`, so nothing of
  them rides in a commit.
- Asks for the coordinator, all in `## Disputed`: (1) the unborn-report
  shape needs a disposition — variants (a) refuse with an opt-out flag,
  (b) stamp only an existing report, (c) protocol rule, no code; (2) the
  H2 clock gate runs before the stamp, which TASK-100 K1 owns; (3)
  `status: "handed"` is written by relay but documented nowhere — AGENTS.md
  lists two values and the file is out of this spec's scope.
- TASK-97 Q12 row 1: ruling #1 says J1 replaces it. If the row is kept,
  the next shift re-implements `0902a22`.
