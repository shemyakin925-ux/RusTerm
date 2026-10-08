# REPORT-139 — TASK-139 (acceptance 13/0; С5 new tickers; С1 start time)

## Done
- B1 — item 11 cause found, fixed in this commit; Done-when
  (`relay.py verify` 13/0) pending, see HANDOFF.
  - Full assertion (run 3, outer suite, zstandard blocked exactly as
    acceptance item 11):
    `assert valued > 0, "снапшот пуст: ни одной меры со значением"` →
    `AssertionError: снапшот пуст: ни одной меры со значением; assert 0 > 0`
    at `tests/test_task97_q12_ca_plan_refusal.py:339`
    (`test_follow_finishes_the_path_and_builds_the_snapshot`).
  - Cause: the test picked "the latest snapshot" with
    `ORDER BY snapshot_id DESC`. snapshot_id is a random UUID, and
    `follow` leaves year snapshots of the history behind (11 snapshots in
    the failed run's DB). The DB of that run (kept under pytest-of-anton)
    shows the max-UUID snapshot = as_of 2018-09-29 with 0 valued measures,
    while the real current one (as_of 2026-10-08, version 11, 11 valued)
    sorts elsewhere: the assert is a lottery, ~1/11 per suite run. That
    matches the night's evidence: red twice via the I5 green case (nested
    acceptance check 3, selfcheck-acc files wMxl1C and sk1oiF) and once in
    the outer suite; green alone, in a fresh clone, in a clone with the
    nested environment — not clone-specific, pure order + lottery.
  - Fix: the snapshot now comes through the same door as `rusterm export`
    (`RepoRegistry.snapshot.latest_snapshot_id` — `version DESC` among
    `status='ready'`); the assert `valued > 0` stays.
  - Second witness (the coordinator's item-11 red on firsthour, assertion
    text lost): the smoke-window stage ran the start-up refresh pass, and
    YahooProvider is not covered by the test's sitecustomize stub — the
    subprocess exited to live Yahoo against the test's own «без сети»
    contract; a slow answer keeps the QThread alive at window close
    (returncode / `t_win < 60` red). Fix: `RUSTERM_NO_AUTO_REFRESH=1` in
    the test env (the ТЗ-133 R1 switch); timing limits on lines 130–131
    untouched.
  - Runs: `python3 -m pytest -q tests/test_task97_q12_ca_plan_refusal.py`
    → `12 passed`; `python3 -m pytest -q tests/test_task65_k4_firsthour.py`
    → `1 passed`, and its line now reads «запросов 6» (was 7 with the live
    refresh request) — the network door is closed.

## Blocked
- (empty)

## What not to trust
- B1's Done-when is not met yet: `python3 agent/relay.py verify` → 13/0
  has not run at the time of this commit (it runs right after the push;
  result lands in the final HANDOFF).
- The coordinator's firsthour red (their acceptance, full assertion text
  lost) is explained as the live-Yahoo refresh door, not reproduced
  verbatim: my two outer runs had firsthour green before the fix. What is
  proven: the door existed (run 2 firsthour line printed «запросов 7» =
  6 stages + 1 live refresh request inside a "hermetic" test) and is now
  closed («запросов 6»).
- Reproduction counts above come from my runs tonight on this machine;
  acceptance timing on the coordinator's side may differ.

## Disputed
- (empty)

## HANDOFF
(interim — B1 fix commit)
Status:          PARTIAL (B1 fix committed; verify pending; B2, B3 ahead)
Arrival state:   acceptance on c899dc9 reported 12/1 by the coordinator
                 (item 11, firsthour); on this tree the same red family
                 reproduced 3 times tonight (see Done), report-guard reds
                 in the runs were this report's own uncommitted skeleton
Items done:      B1
Items not done:  B2, B3 (not started)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF will quote its «Итог» line
Tests:           12 passed (q12 file), 1 passed (firsthour), 0 skipped
Guards:          none touched
Schema:          unchanged (48)
Network:         0 product requests; B1 is offline work (the one live
                 Yahoo request per firsthour run was the defect fixed)
Model:           GLM 5.3 (zai individual coding plan) via ZCode; app
                 llm_calls 0
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          yes
Questions for the coordinator:
1. The acceptance-red lottery (item 11 / nested check 3) means previous
   green acceptances this week were partly luck; worth re-running
   acceptance once after this fix lands.

NOW: B1, step 6
