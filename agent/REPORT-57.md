# REPORT-57 — TASK-57 (A1 + A2 + A3 + A4 + A5)

Round 68, executor, branch `agent/night-11`.

- Minutes to stop at start (Y0 command, verbatim):
  `python3 -c "from datetime import datetime,timezone,timedelta as T; n=datetime.now(timezone(T(hours=7))); s=n.replace(hour=10,minute=0,second=0,microsecond=0); print(int((s-n).total_seconds()//60))"`
  → **-93** at 11:32 Danang (NEGATIVE: the baton was handed to
  executor at 11:19 Danang, after the §10 night-shift stop of 10:00;
  see Questions 1). Decision: the hand itself is the coordinator's
  instruction to run this round now; taking A1 first (smallest,
  self-contained), the Y0 number is reprinted in every interim HANDOFF.
- Baseline selfcheck on arrival (before any commit), clean tree at
  `91e41ef`: 13/0, `SELFCHECK OK`, exit 0.

## A1. Circle-60 tail pinned by a test in both directions

Test name: `test_green_answer_survives_gray_measure_in_block`
(`tests/test_i2_does_not_know.py`), plus two neighbours pinning the
other branches: `test_guard_failure_with_known_reason_carries_data_reason`
(case б) and `test_guard_failure_without_data_reason_stays_generic`
(case в).

Commands and outputs:

- new tests on current code:
  `python3 -m pytest tests/test_i2_does_not_know.py -q` → `.......`
  (7 passed).
- redness proof: temporarily restored the pre-15c854f order (refusal
  before the guard) by hand, same command →
  `FAILED tests/test_i2_does_not_know.py::test_green_answer_survives_gray_measure_in_block`
  with `assert True is False` and result
  `{'answer': None, 'reason': 'no_data:missing_data', ..., 'rejected': True}`;
  `git checkout -- rusterm/core/chat.py`, same command → 7 passed.
  Cases (б) and (в) stay green under the old order by design — their
  outcome is identical in both orders; case (а) is the discriminating
  one, and it is the one that reddens.
- after the comment edit:
  `python3 -m pytest tests/test_i2_does_not_know.py tests/test_q_chat.py -q`
  → 17 passed.
- the chat.py comment is shortened to three short lines naming the
  test, no round numbers.

What would break without this test (two lines): a revert of 15c854f
would again let any single gray measure in a tool block cancel an
answer that was computed and cited from green measures of the same
block — the user loses real numbers to an unrelated refusal. And the
refusal path for a guard-rejected answer would drift silently: nothing
would pin `no_data:` + the dictionary token over the generic
«число не процитировано» when the data reason is known.

## A2. BR measures census — Ambev, offline, golden-pinned

Emitent: **BR-AMBEV (AMBEV S.A., CD_CVM 023264)** — the same payload
as Z2 (annual DFP 2024, recorded slices `tests/data/cvm/`). The
census runs offline through the REAL Z2 channel
(`add` → `ingest --source cvm` → `snapshot`), transport replaced by
the recorded bytes, real RequestGate counting; golden file
`tests/data/golden_census_task57_br.json`, tests
`tests/test_task57_br_census.py` (5 passed). The census covers the
ten TASK-49 measures **plus `roe_incl_nci`** (landed in ТЗ-56 Z1),
11 rows total — the ТЗ said «десять», the dictionary has grown by one
since; nothing was dropped.

Table in words (measure → value or refusal):

| measure | outcome |
|---|---|
| gross_margin | **0.5124228210563511** (computes) |
| net_margin | **0.16597550599636104** (computes) |
| roe_incl_nci | **0.16521917935689903** (computes) |
| effective_tax | **0.0** — see the candidate below; the true ratio from the payload is −4640375/19487327 = −0.2381 |
| roe | refuses `missing_data: total_equity` — CVM files capital only WITH NCI (2.03), Z1 rule holds, no substitution |
| operating_margin | refuses `missing_data: operating_income` — 3.05 is EBIT-like, deliberately unmapped (verdikt ТЗ-55) |
| ebitda | refuses `missing_data: d_and_a, operating_income` |
| nopat | refuses `missing_data: operating_income` |
| interest_coverage | refuses `missing_data: interest_expense, operating_income` |
| asset_turnover | refuses `missing_data: total_assets` — BPP slice has no asset lines |
| fcf | refuses `missing_data: capex, ocf` — no cash-flow statement in the recorded slices |

So: **4 rows carry a value, 7 refuse**; every refusal token is
dictionary-checked by an assert, none is a bare `missing_data`.
`rusterm census --instrument BR-AMBEV` prints the issuer like US/CA/
OTC (asserted in test_census_command_lists_br_like_us_ca_otc; live
offline run quoted in the prep: 36 facts, 11 rows).

### Candidate (no code written, per ТЗ): CVM 3.08 sign convention

DRE line 3.08 «Imposto de Renda e Contribuição Social sobre o Lucro»
is filed as a SIGNED deduction (negative). The dictionary maps 3.08 →
`tax_expense`, and `effective_tax = clip(tax/pretax, 0, 0.5)` clamps
−0.2381 to **0.0** — a green-looking number that says AMBEV pays 0%
tax. Options for the coordinator: normalize the sign at the map layer
(cvm-dfp.v2, magnitude) or give BR its own measure; both are code, so
per A2 this is reported, pinned as-is in the golden (`"0.0"` with the
artifact documented in the test docstring), not "fixed".

## A3. B35 — read-only `markets` leaves the tree clean; CLI open-mode sweep

Test `tests/test_b35_markets_readonly.py` (3 passed): in a fresh
temp **git tree**, `markets`, `markets --json` and `--help` each exit 0
and leave `git status --porcelain` EMPTY (evidence run: the same three
commands printed `start status: ''` → `status= ''` after each;
`init` shows `?? rusterm.db`); positive control asserts `init` and
`ingest` still create the catalog (`?? rusterm.db`, file exists).
B35 is marked closed in `agent/BACKLOG.md` — but that edit could not
ride THIS commit: the committed P6 guard has no authorization path for
BACKLOG (markers exist only for PROTOCOL/CONTEXT), so the BACKLOG edit
stays in the working tree for the coordinator's relay commit (see the
question list, item 4).

Full sweep `_open` vs `_open_readonly` over every CLI command:

| command | writes/reads | opens via |
|---|---|---|
| init, demo, ingest, refresh, snapshot, export, verify, ops, industry, add, backup, restore, chat, watchlist, import | writes | `_open` |
| status, cadence, coverage, budget, markets | reads | `_open_readonly` |
| census | reads, can rebuild snapshot | `_open` |
| metrics | reads (writes only with `--record`) | `_open` |
| doctor | diagnostics (writes only with `--fix`) | `_open` |
| tui | docstring says read-only | own path: `ensure_app_dir` + `apply_migrations` in `tui/app.py run()` |

Divergences found — **not fixed** (per ТЗ), listed as candidates:

1. `metrics` — prints computed values, writes only with `--record`,
   yet opens via `_open`: on an absent data dir it creates
   `rusterm.db`. Same breed as B35.
2. `doctor` — pure diagnostics by default, opens via `_open`: creates
   the catalog just by being asked for a report.
3. `census` — `_open` is defensible (it may rebuild a snapshot), but on
   an absent dir it creates the base instead of refusing by name the
   way `status` does.
4. `tui` — documented as read-only, but `run()` creates the data dir
   and runs migrations before showing anything; the docstring and the
   behavior disagree.

## A5. Flickering tests — first cause named and fixed; three named ones pending

**Cause 1 (found and fixed this commit): nested selfcheck in
`test_selfcheck_guard.py::test_selfcheck_cannot_exit_zero_with_dirty_tree`
hits the O0 clock guard on a stale staged `STATE.json`.**

Mechanism, shown by runs: selfcheck's O0 check reads the STAGED
`agent/STATE.json` and compares its `updated_at` with the real clock
(tolerance 15 min). The dirty-tree test runs selfcheck WITHOUT
`I5_NESTED=1`, so O0 fires before P3/P4 as soon as the executor's
index has been holding a staged STATE.json for more than 15 minutes —
which is ALWAYS the case in the second full pytest pass of an
acceptance (check 11 runs ~15+ min after check 3 started).

Reproduction lines (same command, same tree, minutes apart):

- check 3 (first pytest pass): `test_selfcheck_cannot_exit_zero_with_dirty_tree` PASSED;
- check 11 (second pass, 06:17Z): `FAILED tests/test_selfcheck_guard.py::test_selfcheck_cannot_exit_zero_with_dirty_tree`
  with the nested selfcheck output
  `SELFCHECK FAIL (O0): updated_at=2026-09-19T06:00:00Z расходится с реальным 2026-09-19T06:17:19Z на +17.3 мин (допуск 15)`
  — the expected `P3/P4` substring never appears (it fires after O0).
- This fired twice in a row during the A3 commit attempts of this
  shift (REPORT-57, What not to trust); the coordinator's runs on
  `fdb8070` did not see it because their index was clean — O0 is
  skipped entirely when nothing is staged.

Fix: the nested run now passes `I5_NESTED=1` (the documented
mechanism for nested acceptance runs — O0 skips it), so the test
checks what it means to check (P3/P4 ordering on junk files) and is
independent of the ambient index and wall clock. After the fix:
`python3 -m pytest tests/test_selfcheck_guard.py -q` → 3 passed.

This is NOT one of the three tests named in the ТЗ; those three are
covered below.

**The three ТЗ-named tests: not reproduced — attempts counted.**

Reproduction attempts on `6fd5996` (this machine, clean index, after
the A1–A4 landings):

1. Exact check-11 command standalone:
   `PYTHONPATH=/tmp/block57 python3 -m pytest -q` (block dir with a
   raising `zstandard.py`, same wording as acceptance) → all green,
   exit 0.
2. The coordinator's exact sequence, back-to-back:
   `python3 -m pytest -q` (check 3) followed immediately by the
   blocked-PYTHONPATH full run (check 11) → both all green,
   chain exit 0.
3. Incidental coverage: every selfcheck of this shift runs the suite
   TWICE (executor + pre-commit hook) — 8 full pytest passes across
   A1–A4, all green, including both passes on the A5.1 commit itself.

Measured statements (not guesses): the failure is not a missing
gzip-fallback (confirmed by the coordinator), and it did not reproduce
on this machine under the two documented conditions. It fired once in
the coordinator's attached tree on `fdb8070` and not in their second
run — the remaining variables are that tree/commit, their concurrent
workload, and the pre-A1 code state. Verdict: question 7 below, with
these attempts named; per ТЗ the item is not silently closed.

## A4. AU: the last market without a door — announcements channel, Z2 shape

`rusterm add --ticker CBA --market AU` → `ingest --instrument AU-CBA
--source asx` → `snapshot` now runs end-to-end OFFLINE on the
recorded ASX bodies (`tests/data/asx/header_CBA.json`,
`announcements_CBA.json`, live crawl of 11.09), through the REAL
`AsxProvider` — no adapter this time (Z2's BR test needed one because
its provider lacked `resolve`; see the defect note below).

Code: `AsxProvider.resolve` (header → name; code = ASX ticker, the
market identifier is `asx_code`), `ticker_venues()` (honest `{}` — no
exchange file), `announcements_raw` (raw bytes for provenance);
`_ingest_asx_announcements` in cli (raw store by canonical URL, cache:
unchanged list — 0 requests); `PROVIDER_CHANNELS["asx"] = "asx"`.

Tests `tests/test_task57_au_channel.py` (5 passed): full path; raw
object provenance (`provider='asx'`, URL `.../CBA/announcements`,
block `disclosures`) and cache rerun with 0 requests; no measure from
thin air (EVERY snapshot measure of AU-CBA refuses, all reason tokens
dictionary-checked, all 11 census measures present as refusals);
markets names the AU channel `asx` (the Z2 honesty test updated to the
new truth — KR stays honestly `None`); budget named by number from
`rusterm budget` (fresh ingest = 1 request, cached rerun = 0).

The channel's refusal point, named precisely: **the document BODIES**
— a two-step PDF chain «не проверена нами живьём» (ADR-0010 §5). It is
NOT a key and NOT a paid tariff: header/announcements are open and
free, and the channel is honest about every filing
(`manual_import_required:asxdoc:<ключ>`, count printed per ingest).
Whether to probe the PDF chain live is a network-budget question for
the coordinator (Disputed Q5).

**Defect found on the way (candidate, not fixed):** `CvmProvider` has
no `resolve` — a REAL `rusterm add --ticker X --market BR` would die
with AttributeError; the Z2 tests masked this with a `_BR` adapter
supplying resolve/can_auto_ingest/ticker_venues. ASX got its resolve
in this task; BR's is a two-line candidate for the next task.

## Done

- A1: circle-60 tail pinned in both directions
  (test_green_answer_survives_gray_measure_in_block red on the
  reverted order, green after restore; cases б/в pinned on exact
  texts); chat.py comment names the test instead of the round.
- A2: BR census offline golden-pinned (4 values / 7 named refusals,
  dictionary-checked), candidate 3.08-sign reported without code.
- A3: B35 closed — markets/--json/--help leave a clean tree clean
  (test in a temp git tree, git status asserted), init/ingest positive
  control; full CLI sweep table + 4 unfixed divergences (metrics,
  doctor, census, tui) reported. BACKLOG edit is in the working tree
  for the coordinator's relay commit (question 4). NOTE: the A3 test
  and report sections landed inside commit ffeb518 together with the
  A5.1 fix — the A3 files were still staged in the index when the
  A5.1 commit was made; disclosed here, no content was lost.
- A5.1: first flicker cause named and fixed
  (test_selfcheck_cannot_exit_zero_with_dirty_tree now runs the
  nested selfcheck with I5_NESTED=1; repro in the A5 section).
- A4: AU announcements channel landed (add/ingest/snapshot offline on
  recorded ASX bodies, honest manual_import_required per filing, zero
  facts, markets channel named, budget by number); BR add-resolve
  defect reported as a candidate.
- A5: three named tests — 2 targeted reproduction attempts + 8
  incidental full passes, all green on `6fd5996`; moved to question 7
  with the attempts counted, not silently closed.
- Backlog item NOT taken, with the reason: the only open S/M items are
  B36 (size M, needs live model calls — a fresh multi-commit item,
  not a tail-of-shift item) and B38 (touches PROTOCOL.md —
  coordinator-owned, P6-blocked for this executor); B34/B37 are
  already closed per the round-68 baton note. Per the ТЗ rule
  «ничего, на что не хватает времени» — skipped, named here.

## Blocked

- (empty so far)

## What not to trust

- The first A1 commit attempt was RED and not committed: the report
  you are reading did not yet carry the five required sections, which
  reds test_report_sections and, through the nested selfcheck, the i5
  guard-source test (cascade, same root). Fixed in this commit; the
  red run's pytest line: 11 passed checks / 2 failed checks (check 3
  and check 11, same three FAILED tests).
- The user's pause killed a selfcheck mid-run; the I5 test module had
  STAGED the widened `agent/p6_rule.sh` (+2 duplicated comment lines)
  and was killed before its restore. Found by index plumbing
  (`git diff --cached` showed the +2 lines) BEFORE the final commit,
  unstaged and restored byte-exact; no commit carried it, CONTEXT.md
  verified clean. Lesson recorded: kill nothing while an I5 test is
  mid-module.

## Disputed

- Q1: §10 says the shift ends 10:00 Danang, but the round-68 baton
  was handed at 11:19 Danang with TASK-57 READY. Treated the hand as
  the instruction to run a daytime round; the Y0 line is negative.
  Confirm the stop-time convention for daytime relay rounds.
- Q2 (A2 candidate, no code written per ТЗ): CVM DRE line 3.08 is
  filed as a SIGNED deduction; `effective_tax = clip(tax/pretax, 0,
  0.5)` turns AMBEV's −0.2381 into a green 0.0 (true rate ≈ 23.8%).
  Decide: sign normalization at the map layer (cvm-dfp.v2) or a
  separate measure.
- Q3 (A3 sweep): `metrics`, `doctor` (both read-only by default) and
  borderline `census` open via `_open` and create a data dir on an
  absent root; `tui` is documented read-only but creates the dir and
  migrates in `run()`. Same breed as B35 — next-task material, not
  fixed per ТЗ.
- Q4 (BACKLOG vs P6): ТЗ-57 says «РАЗРЕШЕНО ПРАВИТЬ:
  agent/BACKLOG.md» and A3 says «B35 помечена закрытой в
  agent/BACKLOG.md», but the committed P6 guard has no authorization
  path for BACKLOG at all (markers cover only PROTOCOL/CONTEXT; the
  only legal BACKLOG commits in history are «Эстафета» relay
  commits). Followed the guard, not the ТЗ line: the B35 closure text
  sits in the working tree and rides your relay commit. The ТЗ line
  and the guard disagree — the guard wins until you rule.
- Q5 (A4): the AU channel stops at the document BODIES (two-step PDF
  chain, «не проверена живьём», ADR-0010 §5) — not a key, not a paid
  tariff. Spend a few live requests probing that chain? If free and
  open, AU graduates from announcements-only to real documents; if
  not, the refusal stands named. Network-budget call, yours.
- Q6 (A4 side-finding): CvmProvider lacks `resolve` — a real
  `add --market BR` dies with AttributeError today (Z2's adapter
  masked it). Candidate two-liner for the next task.
- Q7 (A5): the three named flickering tests (export-transcript,
  tui-grep, venue-404) did not reproduce in 2 targeted attempts +
  8 incidental passes on this machine and commit (evidence in the A5
  section). The one reproduced flicker of this shift (dirty-tree/O0)
  is fixed (ffeb518). Rule: accept A5 as PARTIAL with the counted
  attempts, or name the coordinator-side conditions (their tree,
  workload, fdb8070) for one more targeted attempt.

## HANDOFF

Interim value kept for the record: the shift is closed, see the FINAL
block below — it supersedes this section.

## HANDOFF (FINAL — supersedes the interim values above)

Status:          DONE (A5 partial for the three named tests — Q7)
Arrival state:   selfcheck STATUS=OK on clean tree at 91e41ef, exit 0
Items done:      A1 (920d299), A2 (5271ff8), A3+A5.1 (ffeb518),
                 A4 (6fd5996), final report (this commit) — all pushed
Items not done:  A5 for the three ТЗ-named tests — not reproduced in
                 2 attempts (question 7); backlog item skipped with
                 the reason named in Done
Acceptance:      every landed commit ran acceptance twice (executor +
                 pre-commit hook), all 13/0, «Принято», exit 0:
                 920d299, 5271ff8, ffeb518, 6fd5996
Tests:           final suite 13/0 twice; new tests this shift:
                 test_i2 3, test_task57_br_census 5,
                 test_b35_markets_readonly 3, test_task57_au_channel 5,
                 test_task56_z2 updated to the new channel truth
Guards:          none weakened; test_selfcheck_guard now independent
                 of the ambient index (I5_NESTED=1, A5.1); P1 pin
                 declaration carried in the A4 commit message
Schema:          unchanged (44→45 done in ТЗ-56; no new migration)
Network:         0 requests of the A2/A3 budgets; A4 offline on
                 recorded ASX bodies; 0 live calls all shift
Model:           app llm_calls 0; runner model GLM-5.3-Flash
Secrets:         grepped new tests, GUIDE.md and this report for
                 RUSTERM keys — hits 0 (only the FAKE-KEY fixture in
                 pre-existing tests)
Pushed:          yes (6fd5996 and this commit right after selfcheck)
Questions for the coordinator: see Disputed Q1 and Q7, plus numbered
1–6 above (Y0 stop-time convention; CVM 3.08 sign candidate; A3
open-mode divergences; BACKLOG/P6 ruling; AU PDF-chain live probe;
CvmProvider.resolve defect).
