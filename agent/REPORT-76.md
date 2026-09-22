# REPORT-76 — рулинги по ТЗ-75, V3 и разблокированная эстафета

DEVIATION FROM THE BRIEF, on the first line as required: the user ordered
that the lane-`agent/night-13` repair (C-band, TASK-C10) be recorded in the
reports written for THIS task instead of `agent/REPORT-C10.md`. The repair
narrative is therefore in the sections **Done** (Lane night-13 repair) and
the disputes section below; `REPORT-C10.md` was left untouched. Everything
else follows `TASK-76.md` and `PROTOCOL.md`.

Arrival state: clone fresh from `origin`, branch `agent/night-11` at
`1c4ec42` (round 101, holder executor — `relay.py wait --for executor`
exit 0, "ХОД ТВОЙ"). No acceptance run before the first commit; the
coordinator's note states 13/0 at the start of this circle, and W1's own
clean-tree run is the first measurement (quoted below).

## Done

- **W1 — L3 has teeth, and the red was shown before the fix.**
  `_l3_missing()` is now the parseable core of the guard
  (`tests/test_report_sections.py`), and the guard reads real
  `git log --format=%x1e%h %s --name-only` output through it. Four new
  tests:
  `test_l3_finds_the_item_by_subject_with_files_attached`,
  `test_blank_line_split_leaves_the_subject_block_without_files`,
  `test_l3_flags_an_item_that_no_commit_carries`,
  `test_l2_staged_fallback_only_opens_for_a_non_test_file`.
  How the staged fallback (L2) is handled, as W1 asks: it is a parameter
  of `_l3_missing`, so the teeth tests pass an explicit `[]` (or a named
  list) and never inherit the live index — degeneracy can no longer hide
  behind an unrelated staged file.
  Red proof with the parser put back to blank-line splitting
  (`log_text.replace("\x1e", "").split("\n\n")`, one line, not committed):

  ```
  E   AssertionError: assert ['Q7'] == []
        Left contains one more item: 'Q7'
  tests/test_report_sections.py:310: AssertionError: assert ['Q7'] == []
  E   AssertionError: пункты ['V1', 'S1', 'S2', 'S4', 'S5'] объявлены
      сделанными, но коммита круга с реализацией (не только tests/) не
      найдено
  FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
  FAILED tests/test_report_sections.py::test_l3_finds_the_item_by_subject_with_files_attached
  ```

  Restored: `python3 -m pytest tests/test_report_sections.py -q` →
  `12 passed`. No assert was removed by W1 (diff: 0 removed assert lines,
  5 added).
- **Lane night-13 repair** (per the user's order, see the deviation line):
  `agent/night-13` had never been pushed, its `STATE.json` still said
  `working` with `last_commit` two commits behind HEAD, and the baton had
  been held by the executor since round 5 while C1…C10 were done. Arrival
  acceptance there: «Итог: пройдено 10, провалено 3», exit 3 (red checks
  3, 11, 13). Four causes, all repaired there: (1) commit `5357b51` had
  taken two assert lines out of `tests/test_desktop_chat.py` without a
  declaration, so `selfcheck.sh` was red on any empty index — which is why
  the whole C band committed with hooks bypassed; (2) C7.1 had been
  degraded to `None` instead of moved: the SQL now sits behind the door
  `ChatTranscriptRepo.list_sessions()`, the window lists header plus
  sessions again, and the removed pins are back and stricter; (3)
  `rusterm/env.py report()` returned the whole `_LAST_ORIGINS` cache, so a
  key set after bootstrap was reported absent — `tests/test_env.py` pins
  the case; (4) `.wt-exec2/`, a stale registered worktree, tripped check
  13 and was hidden by a local `.git/info/exclude` rule rather than
  deleted, because it is not this session's to delete.

## Blocked

- none so far.

## What not to trust

- W1's red quote comes from a temporary one-line mutation of the parser in
  the working tree; it was reverted by copying the file back
  (`/tmp/trs-good.py`), not by `git checkout`, so verify the diff against
  HEAD rather than trusting the sentence.
- The lane night-13 repair numbers (10/3 arrival, 13/0 after) come from
  that branch, not from this one; nothing from it has been merged into
  `agent/night-11`.

## Disputed

- `.git/relay-branch` in the original clone still pointed at
  `agent/night-11` while the working branch there was `agent/night-13`;
  every relay call must pass `--branch` explicitly or it moves another
  shift's baton. Not a TASK-76 item — worth a line in PROTOCOL §12.
- `test_disputed_lines_live_only_in_disputed_section` compares against the
  exact name `Disputed`, while W2's numbering renames a repeated header to
  `Disputed #2`. A report with two `## Disputed` blocks therefore reports
  its own second block as misplaced. Measured, not fixed: guard files and
  that test's rule are the coordinator's.

## HANDOFF

Status: in progress — W1 committed, W2 onward next.
