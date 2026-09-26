# REPORT-97 — работа координатора переходит к тебе: отрасли, честность мер, ядро снапшота

## Done

| Item | What shipped | Proof |
|---|---|---|
| Q12-5 | Tier refusal on `/splits`/`/dividends` no longer kills the quote stage. `providers/twelvedata.py`: `PLAN_REFUSAL_REASONS` + `is_plan_refusal()` — the shape of a vendor refusal stays vendor knowledge, not CLI knowledge. `cli/_ingest_twelvedata_actions`: the two payloads are now fetched independently — a plan refusal is remembered and the loop continues, so an endpoint that answered is still parsed, written and cached; gate usage is recorded once per stage; the stage returns 0 with the note «недоступны на бесплатном тарифе Twelve Data (ADR-0018) … повтор заплатит тот же 403, поэтому он не совет». Every other reason (429, transport, 5xx, bad JSON, `BudgetExceeded`) still fails the stage exactly as before. A refused call is counted as spent in the stage's own «запросов» line, and refused payloads are never cached — so the note re-appears on the next run instead of a silent "0 written". | `tests/test_task97_q12_ca_plan_refusal.py`: 12 tests, red-before 7 failed / 3 passed, green-after. Mutations M1-M5 (Runs 4). Focused batch and whole suite: Runs 5-7. |
| Q12-6 | `rusterm reparse` rebuilds **facts** from stored raw payloads, not only `basis`. `store/repos.py`: `companyfacts_sources()` (an `EXISTS` filter — exactly the "raw lies, no facts" state it was meant to repair) replaced by `companyfacts_objects()` (every stored companyfacts object) plus `count_for_source()`. `core/reparse.py`: `rebasis_companyfacts` → `rebuild_companyfacts`; per object the owner is resolved instrument → issuer (never guessed), the payload is re-read and re-parsed by the current parser, and stored rows are keyed by `locator.json_pointer`. An unseen pointer means a new fact through the same doors `ingest` uses (`apply_concept_map` + `persist_ingestion_results`, one write transaction per object); a seen pointer means `basis` aligned if it differs. Rows whose locator carries no pointer are counted (`unlocatable`) and left alone rather than re-inserted; ownerless objects are counted and named. `cli/cmd_reparse` prints added / unmapped / ownerless / unlocatable and points at the snapshot rebuild. | `tests/test_task97_q12_reparse_facts.py`: 10 new tests, Runs 8-10. Mutations M1-M7 (Run 9). Copy of the user's base (Run 11): 414 facts added, refusals 8 → 2 in the newest snapshot of every paper. `tests/test_reparse_basis.py`: 6 call sites renamed, every assertion kept (Run 10). |

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
- Q12-6 on the user's base: reparse was run **only on a copy**
  (`/tmp/rt-q126/data`, `ditto` of `rusterm.db` + `raw/`), every query
  against the real catalog used `mode=ro`. The user's own base still holds
  all 54 refusals — running `rusterm reparse` there is the coordinator's
  call, not mine.
- The clone's code did the copy run, not the user's installed checkout:
  `cd <clone> && python3 -m rusterm.cli --root /tmp/rt-q126/data reparse`,
  with `import rusterm` verified to resolve to
  `…/rt-night11-exec/rusterm/__init__.py` before the run.
- "фактов добавлено: 414 (вне карты концептов: 123)" — 414 is audited
  (dei rows 2525 → 2939, exactly +414, and per object: AAPL 86, VZ 87,
  ADBE 86, MSFT 135, VALE 17, KSPI 3, TECK 0). The 123 is the number the
  CLI printed for tags the concept map refuses; I did not audit it tag by
  tag.
- Idempotence of a second reparse is proven on the fixture catalog
  (`added == 0 and changed == 0`), not on the copy — the copy was parsed
  once.
- TECK is not fixed and cannot be by this path: its stored payload carries
  no `dei` section at all (only `ifrs-full`), so reparse has nothing to
  add. Its two refusals need a concept route, not a reparse.
- The red-before run is an import error (2 collection errors, Run 8),
  which is weaker evidence than a per-test red. The behaviour-level
  red-before is mutation M2 — deleting the insert reddens exactly the
  "facts appeared" and "second run adds nothing" tests.
- The prose premise was mine-from-the-baton until it was measured: the
  test docstring, `core/reparse.py` and `store/repos.py` first repeated
  REPORT-96 Run 33's wording («six papers have no dei section at all»,
  «54 refusals spread over the six», «objects with no facts are the blind
  spot»). Measurement on the copy says otherwise — 7 of 44 objects have no
  `dei` *rows* (6 of them do carry a `dei` section in raw, TECK's payload
  does not), the 54 refusals belong to 4 papers × 2 measures × snapshot
  versions, and the base has **no** fact-less objects at all. All three
  docstrings were rewritten to the measured numbers before the commit; the
  earlier wording should not be trusted anywhere it resurfaces.

## Disputed
1. Q12-6 turned one refusal into a number that should not be trusted as
   today's capitalisation. VALE: its canonical measure inputs in the base
   stop at 2012-12-31 (76 `as_reported` facts, newest `period_end` =
   2012-12-31 — measured, `rt101-scratch/q126-anchor.py`), and the
   staleness anchor in `core/snapshot.py:571` is the newest `period_end`
   among the issuer's own inputs, not `as_of`. So the 2012 cover-page
   share count passes `_STALE_LOOKBACK_DAYS` by construction, and
   `market_cap(VALE, as_of 2026-09-24) = 14.21 × 3 256 724 482 =
   46 278 054 889.22` — this week's price times a 14-year-old share
   count. Before reparse the same cell said `missing_data`. Q12-6 does not
   authorise touching snapshot semantics, so the rule is unchanged and the
   finding is recorded here: a refusal that becomes a plausible wrong
   number is worse for a reader than the refusal. VZ and KSPI cleared on
   cover counts dated 2026-06-30 and 2025-12-31 — those two are honest.
2. The verdict's «54 отказа … было → стало» counts rows across every
   stored snapshot version, and `measure` is append-only history. After
   reparse + rebuild that total is 54 → 56 (TECK's new version adds its
   two), while the user-visible quantity — the newest snapshot of each
   paper — is 8 → 2. Making the 54 itself fall would mean deleting stored
   history, which no task in this round authorises. Both numbers are in
   Run 11; if the verdict meant the total, that needs a ruling.

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
6. Whole suite after the Q12-5 fix: the standalone run started 18:52:36Z
   (`rt101-scratch/q125-final.log`) never reached its count line — it died
   with two FAILED lines in its short summary
   (`test_i5_guard_source.py::test_i5_staged_and_authorised_widening_is_green`,
   `test_report_sections.py::test_disputed_lines_live_only_in_disputed_section`)
   under contention with the commit's own acceptance, which stages an I5
   widening in the same index and read my report while it was mid-edit.
   Durable evidence is the pre-commit acceptance of `c2b0021`:
   `P1: OK (staged)` → `Итог: пройдено 13, провалено 0` → `Принято.` →
   `SELFCHECK OK` (`rt101-scratch/q125-commit.log`); acceptance runs the
   whole suite inside itself and deletes its temp dir on success, so no
   pytest count line survives. Both tests are green on the committed tree:
   `tests/test_report_sections.py` — 33 collected, 32 passed, 1 skipped
   (the skip is the guard's own «в отчёте нет пунктов Items done», it
   wakes up when HANDOFF names items).
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
8. Q12-6 red-before, durable: the three production files this item touches
   (`core/reparse.py`, `store/repos.py`, `cli/__init__.py`) were swapped
   back to HEAD `c2b0021` content and the two test files run against them —
   `rc=2`, `ImportError: cannot import name 'rebuild_companyfacts'`,
   `Interrupted: 2 errors during collection`; all three files restored
   byte-identical (sha256 checked). A collection error is weak evidence, so
   the behaviour-level red-before is mutation M2 below
   (`rt101-scratch/q126-red-before.log`).
9. Q12-6 teeth, clean tree: `..............  [100%]` = 14 tests, rc=0 at
   19:55:11Z (10 new + 4 in `test_reparse_basis.py`). Mutations, each
   reverted and hash-verified (`rt101-scratch/q126-mutations.log`, M4
   re-run in full at `q126-m4-full.log`):
   - M1 the `EXISTS` filter returns → `test_an_object_that_contributed_no_facts_is_reparsed_too`
     and `test_an_object_without_an_owner_is_counted_not_inserted` red: the
     blind spot is the old query, not the parser.
   - M2 the insert removed → `test_the_measure_refuses_before_reparse_and_computes_after`,
     `test_a_second_reparse_adds_nothing`,
     `test_an_object_that_contributed_no_facts_is_reparsed_too` red.
   - M3 the pointer dedup removed (always insert) → `test_the_basis_fix_still_happens_in_the_same_pass`
     and `test_reparse_restores_as_reported` red: duplicates are not a
     cosmetic problem, they break the basis pass.
   - M4 the owner guard removed → `test_an_object_without_an_owner_is_counted_not_inserted`
     red with `sqlite3.IntegrityError: CHECK constraint failed: (issuer_id
     IS NOT NULL AND listing_id IS NULL) OR …` (`rusterm/store/repos.py:1470`).
   - M5 the pointer guard removed → `test_facts_without_pointers_are_not_re_inserted`
     red (`:296`).
   - M6 the concept map not applied to new facts → `test_the_added_rows_are_mapped_like_ingest_does`
     and the measure test red.
   - M7 basis alignment lost → both the new basis test and the incumbent
     `test_reparse_restores_as_reported` red.
10. Interaction found before running, not after: the incumbent
    `tests/test_reparse_basis.py` stored its raw object without
    `instrument_id`, which the new owner resolution would (correctly) skip,
    so `res.objects == 1` would have gone red for the wrong reason. Stamped
    `instrument_id="US-ORCL"` on the `RawRepo.put` — the same stamp
    `_ingest_edgar_companyfacts` always writes — and kept every assertion.
    No assert line was removed anywhere in this item (P1: 0 removed,
    0 replaced).
11. Copy of the user's base (P7: `ditto` of `rusterm.db` + `raw/` into
    `/tmp/rt-q126/data`, 584 MB; every query against the real catalog used
    `mode=ro`; the code was the clone's, verified by `rusterm.__file__`).
    Baseline before reparse: 44 companyfacts objects, 7 of them with zero
    `dei` rows (AAPL, ADBE, KSPI, MSFT, TECK, VALE, VZ — 6 of the 7 do carry
    a `dei` section in raw; TECK's payload has none, only `ifrs-full`);
    `dei:*` rows 2525; objects with canonical `shares_outstanding` 40 of
    44; refusals `missing_data: shares_outstanding` 54 across all snapshot
    versions and 8 in the newest snapshot of a paper (KSPI, TECK, VALE, VZ
    × `market_cap`/`market_cap_total`).
    `rusterm reparse` → rc=0 in ~38 s: «объектов 44, фактов сверено
    617236, фактов добавлено: 414 (вне карты концептов: 123), basis исправлен
    у 0». Network: `metric_sample` rows for `provider_requests_used` 86 → 86
    (nothing spent). Rows added per object: MSFT 135, VZ 87, AAPL 86,
    ADBE 86, VALE 17, KSPI 3, TECK 0 — total exactly the 414, all in the
    `dei` family (2525 → 2939).
    Then `rusterm snapshot --instrument <each of 44> --as-of 2026-09-24`
    (store-only, no provider touched): refusals in the newest snapshot of
    every paper 8 → 2 (only TECK, which has nothing to add), objects with
    `shares_outstanding` 40 → 43, objects without `dei` rows 7 → 1. Values
    now computed: KSPI 18 552 930 207.96 = 97.53 × 190 227 932 (cover
    2025-12-31), VZ 199 803 139 464.18 = 48.09 × 4 154 775 202 (cover
    2026-06-30), VALE 46 278 054 889.22 = 14.21 × 3 256 724 482 — and that
    last one is the 2012 figure, see Disputed 1.
12. Self-check found the prose premise inherited from REPORT-96 rather
    than measured (see «What not to trust»), so the three docstrings were
    rewritten to Run 11's numbers — no behaviour touched. The copy's
    after-state was then re-read from disk (`mode=ro`, second
    independent query of the same catalog): refusals 56 all-versions / 2
    newest, only TECK's `as_of 2026-09-24 v7` still naming
    `missing_data: shares_outstanding`, `dei:*` rows 2939, objects without
    `dei` rows 1, objects with canonical `shares_outstanding` 43 — every
    one of them the number Run 11 records. Teeth re-run after the edits:
    `tests/test_task97_q12_reparse_facts.py`, `tests/test_reparse_basis.py`
    and `tests/test_report_sections.py` together → 47 passed, rc=0.
13. Whole suite for Q12-6: the pre-commit acceptance of this item's commit
    is the run (selfcheck → acceptance, 13 checks with the full pytest
    inside). Its `Итог:` line goes into this row as soon as the commit
    exits.

## HANDOFF
Status: PARTIAL — two of the twelve Q12 rows are committed, the rest of
TASK-97 is queued in the coordinator's order and work continues.
Items done: Q12 (rows 5 and 6) — `c2b0021` and the commit this report ships
in.
Items not done in this shift: the remaining letters of TASK-97 in the
baton order the coordinator set — Q11, Q10, Q8, Q5, Q7, Q6, Q1, Q2, Q3, Q4.
Rows 1, 2 and 7 of the Q12 verdict are outstanding too; row 1 was closed by
TASK-99.
Copy of the user's base left at `/tmp/rt-q126/data` (584 MB, mine to
delete); the real catalog was only ever opened read-only.
Questions for the coordinator: item 1 of Disputed (VALE's `market_cap`
built on a 2012 cover count — rule change, or a refusal with a named
reason?) and item 2 (does «54 → стало» mean the append-only total or the
newest snapshot per paper?).
