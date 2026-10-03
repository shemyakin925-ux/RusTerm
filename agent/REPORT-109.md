# REPORT-109 — collection never dies on one stage; retries; offline shows what is there

Task: `agent/TASK-109.md` · Branch `agent/night-11` · Round 144.
Budgets: network ≤ 30 requests (live check), LLM 0. Network used: 0
(all Done-when checks are offline on recorded fixtures; live check not
run — P5).

## Done

(items appended below after each commit, with the command and its output)

## Blocked

(nothing yet)

## What not to trust

(see HANDOFF)

## Disputed

1. Arrival state, measured before any commit: the working tree was
   clean, and two tests red on the untouched HEAD `bd3be41` when run
   individually — `tests/test_task96_r3_replay.py::test_dei_input_
   survives_the_trim` (expects `stale_data: st_investments: last
   2015-12-31, total_debt: …`, gets the note without `st_investments`)
   and `tests/test_guide_truth.py::test_guide_blocks_run_and_match`
   (GUIDE says `concept_map_version: us-gaap.v4`, the code answers
   `us-gaap.v5`). Neither is touched by this task; both look
   date/content-drift against HEAD, not my regressions. A clean
   fresh-clone `acceptance.sh` at HEAD was started to record the
   arrival verdict — result recorded in HANDOFF when it finished.

## HANDOFF

Status: PARTIAL — items implemented, commit sequence in progress.
NOW: R4, step 6 (commit pending fresh-clone arrival verdict)

## Done (measured, pre-commit)

- **Arrival (repair carried by the round's first commit).** Fresh clone
  of `bd3be41` (the coordinator's hand), `/tmp/acceptance-fresh-clone.log`:
  acceptance falls at «3. pytest целиком» —
  `test_report_sections.py::test_w3_is_not_closed_by_a_foreign_round_on_
  the_real_branch` (probe W3 legitimately closed in round 144 by
  TASK-108's own `84ada2c`; relay marker 144 absent from history, so the
  window can never shrink past it), `test_task96_r3_replay.py::
  test_dei_input_survives_the_trim` (round-144 D7 rule `25fece2` made
  discontinued st_investments a zero contribution — it left the refusal
  string; total_debt stays named with its period), `test_w4_window_data_
  contract.py::test_pin_table_covers_every_window_call` (window calls
  `data.parse_add_request` since `5706572` unpinned). Repairs: probe
  W3→W1 (measured: W1 in history, absent from the round-144 window),
  refusal string → `stale_data: total_debt: last 2013-12-31`, pins added
  for `parse_add_request` + `last_snapshot_date`.
- **R1** ownership/prices transport error → `follow` exit 0, snapshot
  exists, output names stage + reason + parseable retry command;
  required-stage failure still non-zero.
  `python3 -m pytest tests/test_task109_follow_stages.py -q` → `5 passed`.
- **R2** `budget.retry_transport`: URLError/timeout raised twice then OK →
  success, `gate.calls_made == 3`, sleeps `[1.0, 4.0]`; always-429 → 4
  attempts, sleeps `[1.0, 4.0, 15.0]`; 403/404 → 1 request, no sleeps;
  yahoo/twelvedata returned-status transients behave the same.
  `python3 -m pytest tests/test_task109_retry.py -q` → `16 passed`.
- **R3** run 1 skips prices (coverage `prices=missing`), run 2 makes
  price requests only (edgar transport call counter unchanged), prints
  «повтор: цены»; fully-collected paper re-runs at 0 requests.
  (same file, tests `test_resume_*`) → green in the 5 above.
- **R4** offscreen window, prices transport always raising → window
  built, `offline_notice` visible with «нет сети — данные от <as_of>»,
  collect status says the same, no traceback (worker reached the final
  word); total outage → «нет сети — данных пока нет».
  `python3 -m pytest tests/test_task109_offline_window.py -q` → `4 passed`.
- **look.py on a COPY of the user's base** (`/tmp/rusterm-base-copy`,
  44 instruments, copied read-only; `~/EquityLab` untouched):
  `python3 .claude/skills/rusterm-check/look.py --code . --root
  /tmp/rusterm-base-copy --out /tmp/look-109 --companies 40` → exit 0,
  report.json: 38 companies clicked, 153 shots, `errors: []`.
- **Network budget: 0 of 30 used** (every Done-when is offline on
  recorded fixtures; the live check named in Budgets was not run).
  LLM calls: 0.

## What not to trust

- The live-transport retry delays (1 s / 4 s / 15 s) are pinned by an
  injected sleeper, never by wall-clock waiting — real-world timing is
  not measured (no live requests made).
- `look.py` exercised the window on the user's base copy but could not
  exercise the offline banner there (no failing collect in that walk);
  the banner's teeth live in the offscreen test only.
- The relay-marker hole (round-144 hand left no «Эстафета: круг 144»
  commit, so L3's round window is permanently stretched) is recorded,
  not fixed — `relay.py` is the transport both sides ride on; a repair
  wants the coordinator's ruling.
- test_state_report_tracked green only after this commit lands (STATE
  names REPORT-109.md, created by this same commit).
- **Arrival acceptance final verdict** (fresh clone at `bd3be41`, job
  finished): «Итог: пройдено 11, провалено 2», exit 2 — checks 3 and 11
  (both full pytest runs) red with the same three tests named above;
  all other checks green. All three are repaired by this round's first
  commit (probe W1, D7 refusal string, window pins).

## Done (committed)

- **89ac5ed** «ТЗ-109 R1-R4: …» — landed through the pre-commit hook
  (selfcheck + acceptance): «Итог: пройдено 13, провалено 0»,
  `SELFCHECK OK` (/tmp/commit-109b.log). Carries the arrival repairs
  (Y1 probe W3→W1, VZ refusal string per D7, window pins, GUIDE
  us-gaap.v4→v5 measured), R1–R4, the three new test files (25 tests;
  the offscreen window test lives at
  `tests/test_desktop_task109_offline.py` per acceptance check 6),
  conftest RETRY_SLEEP no-op, STATE.json, this report.
  Two assert lines replaced across two files under declared
  ЗАМЕНА-БУЛАВКИ blocks in the message (probe re-measure; 5xx retry
  count), no assert removed net.

## Disputed (continued)

2. **The first `hand` landed on the wrong branch.** `.git/relay-branch`
   held a stale `agent/night-13` from the September C-lane, and relay
   resolves the branch from that cache before anything else — my
   shift-start `wait` («круг 5 … ТЗ-C1») was reading night-13's stale
   baton all along, and the first hand moved THAT baton: commit
   `3cab826` on `origin/agent/night-13` («Эстафета: круг 6, ход у
   coordinator — agent/TASK-C1.md») carries my note, the report delta
   (+9 lines) and a STATE stamp. Night-13 is a dormant merged C-lane
   branch, so I left the published history alone (no rewrite) and
   re-pointed the cache with `--branch agent/night-11`; the real hand
   follows this entry. Coordinator: night-13 carries one stray baton
   commit (`3cab826`) — cleanup is yours (CLEANUP.md).
