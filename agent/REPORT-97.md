# REPORT-97 — работа координатора переходит к тебе: отрасли, честность мер, ядро снапшота

## Done

| Item | What shipped | Proof |
|---|---|---|
| Q12-5 | Tier refusal on `/splits`/`/dividends` no longer kills the quote stage. `providers/twelvedata.py`: `PLAN_REFUSAL_REASONS` + `is_plan_refusal()` — the shape of a vendor refusal stays vendor knowledge, not CLI knowledge. `cli/_ingest_twelvedata_actions`: the two payloads are now fetched independently — a plan refusal is remembered and the loop continues, so an endpoint that answered is still parsed, written and cached; gate usage is recorded once per stage; the stage returns 0 with the note «недоступны на бесплатном тарифе Twelve Data (ADR-0018) … повтор заплатит тот же 403, поэтому он не совет». Every other reason (429, transport, 5xx, bad JSON, `BudgetExceeded`) still fails the stage exactly as before. A refused call is counted as spent in the stage's own «запросов» line, and refused payloads are never cached — so the note re-appears on the next run instead of a silent "0 written". | `tests/test_task97_q12_ca_plan_refusal.py`: 12 tests, red-before 7 failed / 3 passed, green-after. Mutations M1-M5 (Runs 4). Focused batch and whole suite: Runs 5-7. |

Three pre-existing tests encoded the overturned expectation and were
updated to the verdict, assertion by assertion — nothing was deleted, no
xfail, no marker:

| Test | Was | Now | Still asserted |
|---|---|---|---|
| `test_c3_actions.py::test_vendor_failure_leaves_actions_empty_with_named_reason` | 403 on both endpoints → `code == 1` | `code == 0` + the reason must be in the note on stdout | `corp_action.all("US-X") == []` (K7: a vendor refusal is a value, not an invention) |
| `test_task96_r3_refused_calls.py::test_refused_splits_are_still_counted` | `_ingest == 1`, transport called twice (`/dividends` never asked) | `_ingest == 0`, calls `["time_series", "/splits", "/dividends"]` | `_requests_used == len(calls)` — and it holds on the new path with 3 calls, one gate record |
| `test_task96_r3_refused_calls.py::test_refused_dividends_after_successful_splits_are_counted_once` | `_ingest == 1` | `_ingest == 0` | call list and the no-double-record sum (3 samples, not 4) |

Two teeth added on top of the verdict's minimum, because the new `continue`
path bypasses the old "record and return" line:
`test_a_refused_by_plan_call_is_still_counted` and
`test_a_hard_failure_is_counted_too` (ТЗ-96 R3's accounting invariant
re-asserted on both branches).

## Blocked
nothing.

## What not to trust
- Q12-5 was verified only offline on stubbed transports (`tests/data/edgar`,
  `tests/data/twelvedata`) with a 403 on `/splits`/`/dividends`. The shape
  of that 403 comes from the round-132 field run (REPORT-96: Runs 24/30 and
  its Disputed item 5). No live call was made this round (TASK-97 budget:
  network 0 outside Q2/Q4, and the Q12 header blocks live price runs on the
  rejected key). So "the free plan answers 403 for these two endpoints" is
  reproduced, not re-measured.
- The predicate maps *any* HTTP 403 to "this is the plan", because that is
  what the field measurement showed and what the verdict's Done-when names.
  If Twelve Data ever answers 403 for a dead key rather than 401, a key
  problem would be reported as a tier limit. Not observed this round;
  recorded here as the assumption, not as a verified fact.
- The wording of the stage note is mine; the verdict's phrase
  «недоступны на бесплатном тарифе Twelve Data (ADR-0018)» is inside it and
  is asserted by `test_the_tier_refusal_is_said_in_words`.
- No mutation proves "a refused payload must not enter `raw_object`": the
  refusal branch has no `repos.raw.put` line to flip. That test guards a
  future edit, not a present defect.

## Disputed
nothing yet.

## Runs

1. Round-135 baseline, whole suite, HEAD `1a27329`, before any edit:
   `1 failed, 1434 passed, 6 skipped, 20 deselected, 6 xfailed in 1472.52s
   (0:24:32)`. The single red is the documented I5 guard demo going red for
   the wrong reason while the new test file was still untracked; green
   after `git add`.
2. Q12-5 red-before (teeth first, no production code changed):
   `7 failed, 3 passed in 10.72s` at 18:24Z. `test_follow_finishes_the_path…`
   reproduced the field shape verbatim: `US-AAPL: 4/5 цены — отказ
   (запросов 2)`.
3. Q12-5 green-after the implementation: 10 passed at 18:31Z. Then the
   self-check found a second defect in my own first version: the stage line
   printed `запросов: 1` while two calls had been paid for — the same
   under-count ТЗ-96 R3 was written against, re-introduced by counting only
   successes. Added `requests_spent += 1` on the refusal branch plus two
   accounting tests → 12 green.
4. Mutations, each reverted and verified byte-identical to the
   pre-mutation copy (`diff` clean):
   - M1 `is_plan_refusal` accepts any `source_unreachable*` →
     `test_a_plain_failure_still_fails_the_stage` red. Leniency cannot
     swallow a real breakage.
   - M2 `is_plan_refusal` returns `False` (pre-fix behaviour) → 6 red,
     including the `follow` path and both wording tests.
   - M3 `is_plan_refusal` also accepts `vendor_rate_limited` →
     `test_a_rate_limit_is_not_called_a_plan_limit` red.
   - M4 (first attempt, no-op) the replace string spanned two f-string
     source lines and matched nothing — that run reported "2 passed" and is
     not a proof.
   - M4 (corrected) note reworded to «что-то не так» → 3 red (wording,
     second run, `follow`).
   - M5 refusal no longer added to `requests_spent` → exactly
     `test_a_refused_by_plan_call_is_still_counted` red.
5. Focused batch after the fix (`test_task97_q12_ca_plan_refusal`,
   `test_c3_actions`, `test_task96_r3_refused_calls`, `test_task96_r2_follow`,
   `test_a1_refresh`, `test_b1_reasons`, `test_market_prices`,
   `test_k1_price_schema`): `46 passed` at 18:47Z. Before the three
   pre-existing tests were updated to the verdict, the earlier version of
   this batch was red exactly on them: `3 failed`.
6. Whole suite after the fix: running since 18:52:36Z
   (`rt101-scratch/q125-final.log`); the number goes into the commit message
   and back into this row when it exits.
7. Killed three verification processes, all mine, all with no consumer left
   (honest log, not a defect claim): the 18:32 and 18:44 full-suite runs were
   interrupted because the code or tests changed under them, so their
   collected snapshot no longer matched the tree. Interrupting the 18:32 run
   orphaned the `agent/selfcheck.sh` → `agent/acceptance.sh` nested run that
   the I5 demo inside it had started (pids 4049 / 4129 / 9860) — that demo
   had left `# i5 green case: staged widening` staged in `agent/p6_rule.sh`,
   and nobody was left to unstage it. Guard restored from HEAD and verified
   identical by hash, index and worktree
   (`12f5791ae1104dc55501ecfe1f670f0eef05aa99`); the two concurrent full
   suites would also have put the time-budgeted tests under contention.

## HANDOFF
Status: NOT STARTED
