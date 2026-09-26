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

## Blocked

Nothing blocked. J2 is not started yet — it is the second item of this
spec and gets its own commit.

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
| `pytest -q` on the 4 relay/neighbour modules | `19 passed` (rc=0) |
| `python3 probe_j1_coordinator_shape.py` | 8 failed → 12 failed, 22 passed (Disputed 1) |
| `python3 mutate_j1.py` | base rc=0; table below |

Mutation campaign (`rt99-mut` scratch worktree, relay.py restored after
each run; the worktree is removed at the end of the shift):

| Mutation | Reddens |
|----------|---------|
| base, no mutation | nothing — rc=0, 6 passed |
| M1 `hand` does not stamp at all (`stamp=None`) | all 6 teeth, and inside tooth 1 the guard run itself: `1 failed` where `1 passed` is asserted |
| M2 plumbing takes STATE from the caller's worktree | 6 |
| M3 stamp overwrites STATE instead of merging | 2, 5, 6 |
| M4 `task`/`report` taken from arguments only, no BATON fallback | 3, 5, 6 |
| M5 own staged STATE treated as foreign again | 5 |
| M6 STATE dedup guard removed | nothing — see `## What not to trust` |

## HANDOFF

Status: PARTIAL — J1 done and committed, J2 pending in the same spec.

- Items done: J1 — this commit (relay.py plus its 6-tooth module).
- Items not done: J2 (refusal words for files left staged).
- Numbers: the J1 module green at 6 of 6; the relay neighbourhood
  regression green at 19 of 19; mutation campaign as tabled above.
- Open asks: three entries in `## Disputed` — the unborn-report shape
  needs a disposition, the H2-before-stamp order is TASK-100 K1's, and
  `handed` needs either a doc line or a different word.
- Question for the coordinator: in TASK-97 skip Q12 row 1 as ruled here,
  or keep the row and let it re-implement what J1 already shipped?
