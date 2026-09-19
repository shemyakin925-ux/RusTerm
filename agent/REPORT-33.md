# REPORT-33 — TASK-33: insider_net lights up; the proxy channel is probed

Arrival state: selfcheck OK at 34d6f68 (13/13); full suite 661 passed,
1 skipped, 4 xfailed, 0 failed.

## Done

### E5 — the executor charter is back in place (DONE)

- `agent/TASK.md` restored from `origin/main` with
  `git checkout origin/main -- agent/TASK.md`;
  `git diff origin/main -- agent/TASK.md` prints nothing
  (byte-identical, verified at this commit).
- Regression commit: `e68c1b5` ("ТЗ-32 D6: period_basis ...") — my
  `git add -A` swept a stale working-tree copy of `agent/TASK.md`
  (its pre-10.09.2026 text) into an otherwise legitimate commit. That
  commit legitimately carried: migration 43 (period_basis in both
  lineage tables), the snapshot writer/`div_yield`/`ev_ebitda`/`roic`
  basis stamps, the ADR-0021 file, README §15 ADR line, the D6
  assertions in tests/test_c2_six_measures.py, and the 42 -> 43
  version-literal replacements declared under the D5 rule. Nothing
  else in the branch touched the charter.
- Guard so it cannot recur: E6 (next commit).

## Blocked

- (nothing)

## What not to trust

- Self-discipline finding: the E5 selfcheck ran RED (acceptance exit 2
  — this file lacked the required sections at that moment), but the
  `| tail -1` pipe masked the exit status and the commit slipped
  through (6c1ba21). The F7 defect, reproduced by me against my own
  guard. Repair: sections appended in the E6 commit; future selfcheck
  invocations run WITHOUT a masking pipe.

## Disputed

- (none yet)

## HANDOFF

Status:          PARTIAL - E5 done; E6 and E1..E4 ahead
Arrival state:   selfcheck OK at 34d6f68 (13/13)
Items done:      E5
Items not done:  E6, E1, E2, E3, E4
Acceptance:      was red at 6c1ba21 (missing report sections, now fixed); re-verified green in the E6 commit
Tests:           full default run 0 failed (see final HANDOFF)
Guards:          none touched in E5
Schema:          unchanged (43)
Network:         0 requests used of 40 (data.sec.gov)
Model:           0 of 0; GLM-5.3-Flash
Secrets:         0 hits
Pushed:          yes
Questions for the coordinator:
1. (none yet)

NOW: E6, step 1

## Done (continued)

### E6 — coordinator-owned files stop being reachable by a wide `git add` (DONE)

- `agent/p6_rule.sh` (called from selfcheck's new P6 block, before
  P3/P4): the staged diff must not touch agent/TASK.md, agent/TASK-*.md,
  agent/PROTOCOL.md, agent/CONTEXT.md, agent/BACKLOG.md,
  agent/LAUNCH.md, agent/acceptance.sh. Red output names the file and
  the undo command (`git restore --staged <файл> && git checkout --
  <файл>`). The executor's own files (REPORT-*, STATE.json,
  BATON.json, p1_rule.sh, selfcheck.sh, rusterm/, tests/, docs/adr/)
  are not restricted.
- `tests/test_e6_p6_rule.py` (temp git repo): staging agent/TASK.md
  -> red with the file named; staging agent/REPORT-33.md -> green;
  staging both -> red. 3 passed.
- The E5+E6 self-discipline finding (masked-pipe slip at 6c1ba21) is
  recorded in What not to trust; all further selfcheck runs capture
  the exit status before any pipe.

## Done (continued)

### E1 — insider_net lights up from stored transactions (DONE)

- Migration 44: `ownership_transaction` (document sha + tx_index as
  the idempotency key, insider, role, date, direction, shares, price,
  `tenb5_one` flag); `OwnershipRepo` (replace-for-document, for-issuer
  window reads). The ownership collector now PERSISTS the parsed
  transactions instead of only counting them.
- Parser: `tenb5_one` — a transaction whose footnoteId resolves to a
  footnote mentioning Rule 10b5-1 (measured on the AAPL payload: F1 ->
  "pursuant to a Rule 10b5-1 trading plan").
- `governance.insider_net_inputs_from_store`: 365-day window over the
  stored transactions; buys/sells/net named in the lineage_ref;
  denominator = market_cap_total of the instrument's latest snapshot;
  no transactions or no denominator -> no input (the honest gray
  stays). `insider_net` gained the ruled 10b5-1 detail (BACKLOG 11):
  `tenb5_net=-2877sh (100% of net)` appended to the reason.
- Wired into the governance producer lambda in cmd_snapshot,
  cmd_refresh and cmd_industry (merged with the manual-import inputs).
- Live record for US-AAPL (the TASK-32 issuer): after
  `ingest --source ownership` + `snapshot`, the governance_assessment
  row reads `insider_net / yellow / within_pm_0.1pct; tenb5_net=-2877sh
  (100% of net)`; lineage_ref:
  `ownership:buys=0,sells=2877,net=-2877sh,window=365d,documents=2`.
  Arithmetic: 0 bought, 2877 sold (both sales under 10b5-1 plans),
  net -2877 shares over the 365-day window; against market cap
  4 884 506 779 050 USD the net ratio is ~-5.9e-10 — far inside the
  +/-0.1% yellow band.

### E2 — the DEF 14A channel is probed (DONE)

| endpoint (host) | status | bytes | format | machine-readable |
|---|---|---|---|---|
| data.sec.gov/submissions/CIK0000320193.json (filter DEF 14A) | 200 | (same cached feed) | JSON | yes — 11 DEF 14A in the recent 1000; newest filed 2026-01-08 |
| www.sec.gov/Archives/edgar/data/320193/000130817926000008/aapl014016-def14a.htm | 200 | 1 248 425 | XHTML with the iXBRL namespace (not a PDF) | partial: the inline-XBRL layer exists (cover page and compensation tags), but board-independence and related-party facts are prose in HTML tables |

The answer per the task: the proxy is NOT a PDF, but the governance
facts this module needs are not machine-readable facts — the path for
them stays manual import (P7, already built). No regex over HTML was
written. Requests: 1 data.sec.gov (submissions re-fetch in the probe
process) + 1 www.sec.gov.

### E3 — the colour is provable (DONE)

- `GovernanceRepo.record` now refuses a green/yellow/red assessment
  whose lineage_ref is empty — the guard sits at the WRITE, not only
  at the producer (`I-governance: ... без lineage не записывается`).
- `tests/test_governance.py::test_colour_without_lineage_cannot_be_written`:
  non-gray through insider_net/independent_directors with an empty
  lineage_ref raises; writing such an Assessment through record raises.

### E4 — staleness works on real dates (DONE)

- `STALENESS_DAYS` 550 -> 450 per BACKLOG ruling 10 (annual proxy plus
  late-filing grace; 550 let a two-season-old document pass).
- `tests/test_governance.py::test_staleness_450_days_on_real_filing_date`:
  asserts the ruled constant == 450; an assessment dated the real
  filing date (2026-09-10) is colored; the same input assessed on
  2027-12-15 (beyond the window) turns gray with reason
  `stale:assessed:2026-09-10`.

## HANDOFF (final, TASK-33 complete)

Status:          DONE
Arrival state:   selfcheck OK at 34d6f68 (13/13)
Items done:      E5, E6, E1, E2, E3, E4
Items not done:  none in TASK-33
Acceptance:      «Итог: пройдено 13, провалено 0», SELFCHECK OK at the E1-E4 commit (exit captured before any pipe)
Tests:           668 passed, 1 skipped, 6 deselected, 4 xfailed, 0 failed
Guards:          P6 added (coordinator-owned files protected, self-tested); GovernanceRepo.record refuses colour without lineage (stronger); STALENESS_DAYS 450 (ruled); version literals 43 -> 44 declared via the D5 rule
Schema:          43 -> 44 (ownership_transaction)
Network:         data.sec.gov 3 of 40 (D2-era submissions 2 + proxy probe 1); www.sec.gov 1 (proxy document)
Model:           0 of 0; GLM-5.3-Flash
Secrets:         0 hits
Pushed:          yes
Questions for the coordinator:
1. The insider_net numerator uses transactionShares from
   nonDerivativeTable only; derivative-table exercises are not in the
   net. Confirm or name the extension.
2. div_yield vendor-window basis stamped "ttm" — same convention
   should apply to any future rolling-window input (ADR-0021 §2).

NOW: HANDOFF, step 8
