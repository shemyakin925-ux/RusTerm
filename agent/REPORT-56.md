# REPORT-56 — TASK-56 (Z1 + Z2)

Round 67, executor, branch `agent/night-11`.

- Baseline selfcheck on arrival (before any commit):
  767 passed, 1 skipped, 9 deselected, 4 xfailed, exit 0 (6:31).

## P0. Orphan change in `rusterm/core/chat.py` (pre-Z1 housekeeping)

Found in the working tree at shift start, uncommitted, unexplained.
Facts collected:
- diff: refusal `no_data:<reason>` moved to fire only after the guard
  rejects the answer; a green answer now survives gray tool results;
- comment inside cites "ТЗ-53 W3 / round 60 live run";
- last commit touching chat.py is ТЗ-42 (`290ec80`); W3 commits of
  round 60 (`5171e68`, `732ee16`, `d549f2a`) did not touch it;
- evidence run: full suite WITH the change = 767 passed (above);
  9 chat tests WITHOUT the change = 9 passed — so no existing test
  pins either behavior.

Decision: committed separately as P0 (15c854f) with this
documentation, not mixed into Z1. Coordinator decides keep-or-revert
(see Disputed).

## Done

- P0: orphan chat.py change documented and committed (15c854f);
  acceptance on that commit: 13/0, exit 0.
- Z1 (recommitted, see CORRECTION): new measure `roe_incl_nci` = net_income / avg(
  total_equity_incl_nci_begin, ..._end), unit ratio — its own
  formula `roe_incl_nci()` in
  formulas.py, dispatch in calculate_measure, two-period inputs
  ("net_income", "total_equity_incl_nci") in snapshot.py. CNQ value
  from the saved payload pinned gold: 0.25812916000667985
  (tests/data/golden_census_task49.json, census test extended with
  the row; NGGTF row pinned too: 0.01688468064145367 — it reports
  both equity tags). `roe` keeps refusing with the exact same token
  (assert: `missing_data: total_equity`), no substitution; lineage
  test proves the inputs are the facts canonicalizing to
  total_equity_incl_nci and net_income from the saved EDGAR response.
  Real `rusterm census --instrument in-CNQ` on an offline-built root
  shows both lines side by side. Formula unit rules tested
  (missing_data / denominator_zero / negative_denominator, not a
  synonym of roe on the same income). No anchor shift: verified the
  max period_end of incl_nci facts never exceeds the current
  staleness anchor for all 25 saved payloads.
  CORRECTION: the first Z1 commit (56794ef, local-only, never
  pushed) also edited docs/data-dictionary.md. The acceptance guard
  "docs/ additions only" compares origin/main..HEAD and therefore
  fires one commit late: it passed 13/0 on 56794ef itself, then
  reddened every following commit attempt — a commit fixing docs can
  never pass a guard that looks at HEAD, so the local unpushed
  history was rewritten instead (backup ref kept, nothing published).
  The rewritten Z1 commit carries no docs edit: data-dictionary.md
  stays at the origin/main state, the dictionary row lives in the
  new docs/adr/0022 (additions under docs/adr/ are the allowed
  channel); README names 0022 as the docs-truth guard requires.
  Folding ADR-0022 into docs/data-dictionary.md is the coordinator's
  move at acceptance.
- Freeze bookkeeping required by the guards, same commit:
  tests/data/formulas_baseline.sha256 replaced (new sha256 of
  formulas.py, per test_ifrs_map docstring rule); GUIDE.md demo line
  and tests/test_cli.py pin updated 27→28 measures / 23→24 empty —
  the new measure adds one snapshot row by design. First Z1 commit
  attempt was rejected by the acceptance hook because of these three
  stale pins; no test was weakened.
- For the reader: `roe` answers "profit on the owners' share of
  capital"; `roe_incl_nci` answers "profit on ALL capital including
  the minority slice" — for CNQ the denominator is bigger, so 25.8%
  is return on the whole equity base, not on the parent's share.
- Z2: BR (CVM) — the market whose provider existed but had no door.
  Chosen over AU because CVM publishes machine-readable statements
  (annual DFP datasets, no key, access=auto), while the free ASX
  channel exposes header+announcements only (document bodies are
  manual-import by design, ADR-0010 §5) — an AU "channel" could not
  produce a single fact. What was built:
  - third concept map cvm-dfp.v1 (concepts.py) by live recorded
    slices: 3.01 revenue, 3.03 gross_profit, 3.07 pretax_income,
    3.08 tax_expense, 3.11 net_income (consolidated incl NCI,
    ProfitLoss analogue), 2.03 total_equity_incl_nci. DELIBERATE
    absences: 3.05 is EBIT-like and never operating_income (ТЗ-55
    verdict), 3.09 is not net_income, 2.03 is never total_equity —
    so measures that cannot be computed refuse naming the concept;
  - CvmDfpParser (parsers/cvm_dfp.py): rows -> facts, ESCALA_MOEDA
    scaling (MIL x1000, raw value kept in the locator), VERSAO
    dedupe, DRE duration / BPP instant;
  - locator kind cvm-dfp (core/fact.py): resolves the value from the
    recorded ZIP by row key — facts reproducible offline;
  - channel `rusterm ingest --source cvm` (cli _ingest_cvm_dfp):
    incremental by Last-Modified in issuer_ingest_state (unchanged
    dataset = 1 HEAD, zero GETs, asserted), sha256 dedupe, raw
    object with provider+url provenance, consolidated DRE/BPP only,
    coverage honest; gate counters go to metric_sample, so
    `rusterm budget` prints the number (fresh load = 3 requests,
    named by the command, not memory; ceiling 20 respected);
  - `rusterm markets` gained a channel column (PROVIDER_CHANNELS,
    markets.py): BR now `cvm`; AU/KR honestly `-` instead of
    provider_status=implemented hiding a dead channel; GUIDE markets
    block updated; CONTEXT.md M8 updated (allowed by the ТЗ);
  - e2e offline (tests/test_task56_z2.py, 7 tests): AMBEV add →
    ingest → snapshot → export on recorded bytes: net_margin,
    gross_margin, effective_tax, roe_incl_nci compute; roe refuses
    exactly `missing_data: total_equity`; operating_margin/ebitda/
    nopat/interest_coverage refuse naming their absent inputs;
    asset_turnover and fcf likewise; provenance + locator resolution
    asserted; second run costs one HEAD; parser + locator unit tests.
- BACKLOG B34 (S): REPORT-MARKETS now states the OTC universe-count
  tolerance band (±1% of the last recorded count, 12,867 ± ~129)
  with the dates of both live counts (12,867 on 2026-09-10; 12,794
  on 2026-09-11 = 0.57%, inside the band) and the date of the last
  live count — the drift stops being a nightly finding.
- BACKLOG B37 verified, no code needed: after six selfcheck runs
  today `ls -d "$TMPDIR"/selfcheck-guards.*` prints nothing — the
  trap required by the item already exists (ТЗ-50 T6 comment in
  agent/selfcheck.sh). Accept criterion of the item holds.

## Blocked

- none.

## Disputed

- P0: the orphan behavior change has no pinning test in either
  direction. I committed it as found (documented) because silently
  discarding someone's work is worse and the suite is green with it.
  Ask: keep (then whoever owns that behavior writes a pinning test)
  or revert 15c854f.

## What not to trust

- The P0 change itself: it is untested by construction (no test pins
  it), provenance is a comment inside the diff, nothing else.

## HANDOFF

Status: working
Minutes to stop: 501 at 02:07 Danang, Y0 command:
`python3 -c "from datetime import datetime,timezone,timedelta as T; n=datetime.now(timezone(T(hours=7))); s=n.replace(hour=10,minute=0,second=0,microsecond=0); print(int((s-n).total_seconds()//60))"`
Items done: P0 (15c854f), Z1 (a271c69), Z2 (3afd477); BACKLOG B34 + B37 verification in the next commit
Items not done: nothing from the main queue
Acceptance: 13/0 exit 0 on 15c854f, a271c69 and 3afd477
Tests: full suite via acceptance hook on each commit (arrival baseline 767 passed, 1 skipped, 4 xfailed)
