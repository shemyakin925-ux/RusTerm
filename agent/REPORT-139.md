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

## Done (B2, B3 — continued after the B1 commit 46ca7a1)
- B2 — five new tickers added through the window door
  (`desktop_actions.follow_instrument`, the «+ компания» path) on a COPY
  of the user's base (`/tmp/rusterm-b2-base`, schema 48, five tickers
  absent beforehand; `~/EquityLab` untouched):
  `python3 /tmp/rt-b2/follow5.py /tmp/rusterm-b2-base NVDA KO XOM PFE WMT`.

  | ticker | seconds | requests | fill | Yahoo |
  |---|---|---|---|---|
  | NVDA | 13.1 | 11 | 175/180 = 97 % | 19/21 = 90 % |
  | KO | 14.1 | 11 | 182/185 = 98 % (was 96 %) | 20/20 = 100 % |
  | XOM | 2.4 | 5 | 0/0 = 0 % | 0/0 — nothing to compare |
  | PFE | 13.2 | 9 | 126/180 = 70 % | 17/18 = 94 % |
  | WMT | 11.8 | 9 | 185/185 = 100 % | 19/21 = 90 % |

  All five ≤ 90 s ✓ (gate); snapshot v11 with 10 year columns each (XOM
  v1 — see below). Code fix: one (dps, below); the rest are named gaps.
  - Fixed (map tag): `dps` gained the ranked successor
    `CommonStockDividendsPerShareCashPaid` — KO files
    `…PerShareDeclared` only up to 2018-09-28, the paid series runs to
    today (2025 = 2.04 USD), and the card's dps row was empty the whole
    period. Rank below Declared: BAC-style filers keep the declared
    value. Tests: `tests/test_task139_dps_paid.py` (map pin + rank order;
    declared wins when both filed; paid fills when declared stopped) —
    `3 passed`. Applied to the copy with `rusterm --root <copy> reparse`
    (3283 facts re-canonized): KO 96 % → 98 %, the «пусто весь период:
    dps» line is gone.
  - Named gap XOM (not a code defect on our side): EDGAR's
    company_tickers.json maps XOM to CIK 2115436 "ExxonMobil Holdings
    Corp" (measured: the ONLY XOM row in the feed; classic CIK 34088 is
    absent from the feed entirely). The registrant's companyfacts is
    84 KB with no annual reports → 269 facts, 0 year columns, card 0/0.
    The resolution policy ("last feed row wins", pinned by B17 and the
    resolve docstring) is a coordinator decision, not mine.
  - Named gap PFE 70 % (< 80 gate): two causes. (1) Pfizer's XBRL has NO
    `OperatingIncomeLoss` fact at all (measured: 0 facts) — the whole
    chain operating_income/ebitda/operating_margin/roic/nopat/ev_ebitda/
    interest_coverage is non-derivable from the feed; the card shows «—»
    with reasons (P8 holds). (2) `total_debt` is pinned by ТЗ-31 C2 to a
    single tag ("не сумма двух тегов"); PFE stopped filing the combined
    `LongTermDebt` after 2017 and now files `LongTermDebtNoncurrent`
    (60.5 bn) + `LongTermDebtCurrent` (2.6 bn) separately — the pin vs
    the feed is a coordinator call.
  - Named miss WMT market_cap_total/pe 2024 (×3 vs Yahoo, 66.9 %):
    measured lineage — cap = actual pre-split close 165.25 ×
    `WeightedAverageNumberOfDilutedSharesOutstanding` 8.108 bn from the
    FY2024 10-K FILED AFTER the 2024-02-26 3:1 split (shares restated to
    the post-split base). P4's price factor and the K2 "restated wins"
    share pick mix bases when a filing crosses a split. Coordinator's
    08.10 code — recorded as a question, not rewritten.
  - Methodology (not defects): NVDA market_cap 2025 ours 3.49 трлн =
    actual close × actual shares at fiscal year end; Yahoo's 2.94 трлн
    is a different date's cap (their row timing). PFE revenue 2023: the
    map's rank 0 is the ASC-606 line (50.91 bn); Pfizer's income
    statement leads with the wider "Revenues" (59.55 bn restated — the
    fact IS in our DB), a rank-policy question for the coordinator.
- B3 — window start measured 5× on the copy (process start → home table
  filled; driver mirrors `window.run()` up to `show()`;
  `RUSTERM_NO_AUTO_REFRESH=1`, the look.py mode — the background refresh
  is not the subject, the table is):
  1.51 / 1.20 / 1.19 / 1.19 / 1.19 s → **median 1.20 s ≤ 5 s (С1)**,
  home table 38 rows every run. Gate met without profiling — no fix
  needed.

## What not to trust (B2/B3 additions)
- The dps fix is applied to the COPY (reparse done there). The user's
  real base needs the same one-off `rusterm reparse` after this lands
  (same class as the 07.10 reparse; no history rebuild needed for the
  card rows — they read facts live).
- B2 timings are one run per ticker on an idle machine, warm process
  (the window scenario); a cold first add pays the imports.
- PFE/XOM verdicts rest on today's EDGAR feed and XBRL contents; the
  feed can change under them.
