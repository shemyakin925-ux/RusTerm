# REPORT-104 — TASK-104 (P1–P7) + TASK-105 (R1–R6), round 141

Status: IN PROGRESS

## Done

### P1 — `pe`, `ps`, `fcf_yield` refuse across currencies (TASK-104)

Before: `_valuation_pass` compared currencies only where a side was a
*fact row it already labelled* (`pb`, `ev`, `div_yield`, `roic`,
`market_cap`). `pe`, `ps`, `fcf_yield` divided blindly — USD market cap
over MXN/CAD/GBP earnings produced a ratio with no currency and no
refusal.

Now (all in `rusterm/core/snapshot.py`):

* `sides_clash(*currencies)` next to `mismatch()` — same K6 format, and
  the B3 legacy rule kept: a side with no recorded currency does not
  start a dispute.
* `pe`/`ps`: window path compares `price_currency` with the currency of
  that TTM window; the annual backup path compares it with the currency
  of the annual fact itself (`_latest_annual_input` index 2).
* `fcf_yield`: numerator side is the unit already written on the `fcf`
  measure (`IssuerInputs.units`), denominator side is the price.
* Window currencies had to reach the pass: `IssuerInputs.window_units`
  (new field, filled from the `window_units` dict that `_issuer_inputs`
  already computes to drop mixed-currency windows) and `IssuerInputs.units`
  are now passed to `_valuation_pass`.
* Order of refusals follows B3/B2: no numerator → `missing_data`;
  currency dispute → `currency_mismatch` before the sign of the
  denominator (with two currencies the quotient does not exist at any
  sign); otherwise the old denominator refusal / the quotient.

Tests: `tests/test_task104_p1_price_side_vs_filing_currency.py` — 6
teeth, offline, USD price + GBP filings:

| tooth | red before | now |
|---|---|---|
| all three refuse | `pe=7.0`, `ps=0.7`, `fcf_yield=0.17142857142857143` (probe on a HEAD worktree) | `currency_mismatch: GBP, USD` ×3 |
| ratio label survives | — | `unit="ratio"` on the refused rows |
| one currency on both sides | green (control) | `7.0 / 0.7 / 0.1714` |
| currency-less denominator | green (control) | values, no refusal |
| missing market cap outweighs the dispute | green (control) | `missing_data: market_cap_total` / `market_cap` |
| annual backup path refuses too | `ps=0.7` | `ps` and `pe` → `currency_mismatch: GBP, USD` |

Two pins in `tests/test_task97_q4_ifrs_ingest.py` moved, and both move
because TASK-97 Q4 left the hole there on purpose («тест держит строку,
чтобы починивший её увидел изменение»):

* `test_pe_and_ps_on_kspi_straddle_currencies` →
  `test_pe_and_ps_on_kspi_refuse_the_off_rate_quotient` — the successor
  keeps the shape assertion (facts exactly `{KZT}`, price exactly `{USD}`)
  and adds, for both measures, `value is None` plus the exact
  `currency_mismatch: KZT, USD`. Declared in the commit message with
  `ЗАМЕНА-БУЛАВКИ` + `ПОЧЕМУ СИЛЬНЕЕ`.
* `KSPI_VALUED` — 10 measures → 8 (`pe`, `ps` left the set). The pin line
  `assert valued == KSPI_VALUED` is untouched; the expected set shrank by
  exactly the two measures the item rules on, so the count check still
  names every empty cell's reason.

Copy measurement (P7; the user's base untouched — `/tmp` copies only,
network 0). Both copies rebuilt with an explicit `--as-of 2026-09-29`:
`/tmp/rt-104-before` by a detached worktree of `ab2bb63`, `/tmp/rt-104-after`
by this working tree — all 44 instruments, one CLI run per instrument
(44 + 44 builds, 0 failures, ~14 s each pass). The diff compares the latest
snapshot per instrument, so clock drift cannot enter it:

| instrument | pe | ps | fcf_yield |
|---|---|---|---|
| US-AMX | `58.100937362525805` → `currency_mismatch: MXN, USD` | `31.027121205055263` unchanged — no revenue window assembles, the annual fallback is the FY2024 **USD** filing, both sides USD | `0.004681244312464769` unchanged — `fcf` is USD (FY2024 annual ocf/capex) over a USD cap |
| US-TECK | `missing_data: market_cap_total` unchanged | `missing_data: market_cap_total` unchanged | `missing_data: market_cap` unchanged |
| US-KSPI | `missing_data: price_close_stale:2026-09-18` unchanged | unchanged | unchanged |
| US-BHP | `missing_data: net_income_ttm` unchanged | `missing_data: revenue_ttm` unchanged | `missing_data: fcf` unchanged |
| US-VOD | `missing_data: net_income_ttm` unchanged | `missing_data: market_cap_total` unchanged | `missing_data: market_cap` unchanged |

1320 measure rows were compared across the 44 instruments and **exactly one
moved: `US-AMX pe`**. TECK/VOD have no numerator at all (no
`shares_outstanding` → no market cap), BHP has no flow inputs, and KSPI on
today's date is refused earlier by the price-staleness door (last close
2026-09-18 is past `_PRICE_STALE_DAYS = 7`) and its only facts in the copy
are 4 unmapped `us-gaap:OtherAssets`/`OtherLiabilities` rows in KZT — so the
only copy instrument whose currency seam actually reaches these three
divisions is AMX, and KSPI is covered by the offline teeth instead.

Rows the user's own older snapshot carries (v6/v7) differ from a fresh
same-day rebuild for reasons that are not this commit — stale prices and the
M1 shares door — listed here so nobody reads them as part of P1.

### P2 — one presentation per period, chosen deterministically (TASK-104)

Before: `_issuer_inputs` builds its candidate keys as **sets** of
`(unit, start, end)` triples and takes the newest with
`max(..., key=(end, start))`. The key never looks at `unit`, so a year
filed twice — AMX FY2024 in MXN (revenue 869 220 584 000, profit
22 902 025 000) and in USD (42 886 000 000 / 1 362 000 000) — gives two
equal keys, and `max` returns whichever the set yielded first. Set order
depends on the process hash seed: same code, same DB, same date, two
numbers (`net_margin` `0.026347771119971546` at seed 0,
`0.031758615865317356` at seed 1). Measured on a copy: rebuilding the same
44 instruments twice, differing only by `PYTHONHASHSEED`, moved
**1 of 1320 measure rows** — that AMX row.

Now:

* `choose_presentation(candidates, dominant_unit)` (`core/snapshot.py`) —
  newest period first (unchanged), then the issuer's dominant filing
  currency, then the lexicographically smallest `unit`; empty input →
  `None`, so every old `period_mismatch` / `missing_data` reason stands.
* All three sites that put `unit` in the key go through it: single-period
  annual, single-period common, two-period flow ∩ stock ends.
  `_annual_common_period` keys on `(start, end)` only — not a site, left
  alone.
* `dominant_filing_currency(conn, issuer_id)` (`store/repos.py`) — the
  `unit` with the most `status='ok'` monetary facts, tie → smallest.
  Monetary = three upper-case letters, the same predicate as
  `core.fact.currency_of_unit` (`^[A-Z]{3}$`), so `shares`, `pure` and
  `USD/shares` cannot vote. The `currency` column is not used (rows
  parsed before J1.0 leave it empty although the filing had a currency),
  and `basis` is not filtered (a comparative column is still a filing in
  that currency; a basis fix must not make the presentation jump).
* `issuer.reporting_currency` is recomputed by the same rule wherever
  facts are written and wherever old ones are re-read: inside
  `persist_ingestion_results`' transaction, for the issuers of that batch,
  and in `rebuild_companyfacts` once per issuer walked. The reparse half is
  required, not decorative: reparse calls `persist_ingestion_results` only
  when it has rows to add (reparse.py:99-106), so on a base parsed by the
  old parser the column would stay untouched for every issuer whose object
  is already complete. `_apply_reporting_currency(c, …)` takes the
  transaction cursor (`writer_transaction` raises on re-entry, db.py:879);
  `refresh_reporting_currency(conn, …)` is the public wrapper reparse uses.

Root cause of Disputed 23 is now named in the code: `watch add` writes a
literal `"USD"` for every SEC issuer (cli/__init__.py:1573-1575) and
nothing recomputed it, so KSPI carried 568 KZT filings under a USD
registry row.

Tests: `tests/test_task104_p2_deterministic_presentation.py` — 13 teeth,
offline, real `SnapshotBuilder` and real `rebuild_companyfacts`; the
seed teeth spawn subprocesses so the seed is really the process's.

| tooth | red before (`7ec196a`) | now |
|---|---|---|
| twice-filed year presents in the dominant currency | value of whichever filing the set gave first | MXN ratio |
| same number under seeds 0/1/2 (`== repr(...)`) | seed 1 → `0.031758615865317356` | MXN ratio ×3 |
| two-period path (`roe`) presents the same way | USD numerator at seed 0 | MXN value |
| dominant unit that did not file this period invents nothing | `dominant_filing_currency` did not exist | MXN, refusal reasons intact |
| `shares` / `USD/shares` do not vote | — | `MXN` |
| tie in fact counts → smallest unit | — | TJS |
| ingest refreshes `reporting_currency` | column never moved | `KZT` |
| later ingest moves it back | column never moved | `USD` |
| no monetary facts → registry value kept | — | `USD`, nothing invented |
| reparse refreshes the column while adding nothing | `assert 'USD' == 'MXN'` | `MXN`, `added=0` |
| second reparse leaves it alone | `assert 'USD' == 'MXN'` | idempotent |

Whole file on the detached `7ec196a` worktree (with the new API stubbed to
`None` so the file imports there — recorded, not hidden): **7 of 13 failed**
at seeds 0 and 1, 6 at seed 2. On the working tree: 13 passed at seeds 0
and 1.

Copy (P7 — `/tmp` copies, `HOME=/tmp/rt-sandbox-home`,
`RUSTERM_ENV_FILE=/nonexistent/rusterm.env`, one offline `rusterm reparse`
per copy, request counter 86 → 86):

| issuer / instrument | before-tree reparse | working-tree reparse |
|---|---|---|
| `cik-1985487` US-KSPI | registry `USD`, dominant `KZT` (568 of 625 rows) | **registry `KZT`** |
| `cik-1129137` US-AMX | `USD`, dominant `MXN` (2469 vs USD 828) | `MXN` |
| `cik-886986` US-TECK | `USD`, dominant `CAD` (1949 vs USD 47) | `CAD` |
| `cik-839923` US-VOD | `USD`, dominant `EUR` (3335, GBP 34) | `EUR` |
| issuers whose column differs from the dominant unit | 4 of 44 | **0 of 44** |

Both trees' runs added the same 11 558 facts and moved the same 3 basis
rows; the registry column is the only difference in their output. KSPI's
own filing mix (KZT 568, TJS 4, USD 1, plus `shares`/`KZT/shares`/`pure`
that cannot vote) is the rule's case: minority units do not get the vote.
Why four KSPI rows carry TJS is not this item's question — it is item 26
of `## Disputed`.

Seed stability on the copy, `snapshot --as-of 2026-09-29`, 44 instruments
per build: before 1 of 1320 rows moved between seeds; after, three builds
(seeds 0/1/2) → 0 moved in all three pairwise comparisons.
Было → стало: `US-AMX net_margin` `seed-зависимый (0.0263… / 0.0317…)` →
`0.026347771119971546`.

### P3 — `invested_capital` carries the minority interest (TASK-104)

Before: the row summed `total_equity + total_debt − cash − st_investments`
inline (`core/snapshot.py:1795`) and never looked at `minority_interest`,
while `roic`'s denominator (`_capital_at` → `formulas.invested_capital`,
which does take NCI) already carried it. One build therefore held two
answers to one input. On the user's copy: SCCO `invested_capital`
`12 053 000 000` while its `roic` `0.3691530064459498` averages a
denominator that ends at `12 129 400 000` — the row was the reported NCI
(`76 400 000` at 2026-06-30) short of its own sibling.

Now, in `_valuation_pass`:

* the row is computed by `formulas.invested_capital(equity, minority, debt,
  cash, stinv)` — literally the call `_capital_at` makes on both borders,
  so «row = the number inside roic» is structural, not two sums that happen
  to agree;
* `minority_interest` joined the row's `money_currency(...)` list: a GBP
  minority under a USD balance sheet now refuses with
  `currency_mismatch: GBP, USD` instead of being dropped silently;
* it joined `ic_missing` too, so refusals name it — `missing_data:
  minority_interest, st_investments, total_debt` (AMX), `stale_data:
  minority_interest: last 2010-07-31, …` (CRM). `roic` had already refused
  for those same inputs; after the change the two rows give one answer;
* lineage: the NCI fact id is signed in next to the other four inputs, and
  `nci_lineage` is appended, so D7's derived zero shows up as the role
  `nci_absent_in_equity_block` — a decision, not an input. Same treatment
  the `ev` block and `_capital_at` give it.
* D7 keeps its meaning: an issuer that never reported a minority line (no
  `minority_interest`, no `total_equity_incl_nci`) still gets 0.0 and the
  old number. An issuer that discloses the total *including* NCI but no
  minority line refuses with the named input — subtracting the minority out
  of equity is not this row's call, and quietly ignoring it is the bug.

Nothing else moved: `roic`, `ev`, `roe_incl_nci` and
`_DISCLOSED_AGGREGATE` were already NCI-aware and were not touched.

Tests: `tests/test_task104_p3_invested_capital_nci.py` — 10 teeth, offline,
real `SnapshotBuilder`, SCCO-shaped fixture (end border 35 + 4 + 5 − 2 − 1,
begin border 25 + 6 + 8 − 3 − 1, `nopat` 4.8).

| tooth | red at `7bb410b` | now |
|---|---|---|
| row includes the reported NCI | `37.0` vs `41.0 ± 4.1e-05` | 41.0, no null_reason |
| **row = the number inside `roic`** (Done-when) | stored `roic 0.12631578947368424` vs `4.8/((35+37)/2) = 0.1333…` | recomputed from the row equals stored `roic` |
| row is the dictionary formula, not an inline sum | `37.0` vs `invested_capital(35, 4, 5, 2, 1)` | equal |
| NCI fact signed into the row lineage | lineage = {cash, st_inv, debt, equity} | + `f-i1-minority_interest-2024-12-31` |
| never-reported issuer keeps the old number **and** the role | `{'input'}`, role absent | 37.0 + `nci_absent_in_equity_block` |
| NCI only inside `total_equity_incl_nci` → refuses | computed `37.0` | `missing_data: minority_interest` |
| NCI in another currency → refuses | computed `37.0` | `currency_mismatch: GBP, USD` |
| negative NCI is added, not absorbed | `37.0` vs `32.0 ± 3.2e-05` | 32.0 |
| `roic` does not start counting NCI twice | green already (guard tooth) | `4.8/((35+41)/2)` |
| row still computes without a price (ТЗ-91 B2) | `37.0` vs `41.0` | 41.0, unit `USD` |

Red before, captured: `9 failed, 1 passed in 1.75 s` on a detached
`7bb410b` worktree (`/tmp/p3-red-before.log`); the tenth tooth is the
no-double-count guard and is meant to be green on both sides. After:
`10 passed`.

No existing pin moved, so P3 needs no ЗАМЕНА-БУЛАВКИ: the 11 files that
reference `invested_capital` / `roic` / the census and schema-44 goldens
run unchanged — `107 passed in 8.10 s` (`test_b1_honesty`,
`test_b1_zero_vs_missing`, `test_invariants`, `test_k4_k6_valuation`,
`test_task91_b2/b3/b4/b5`, `test_v4_formulas`, `test_upgrade_path`,
`test_task49_census`). Their `invested_capital` golden rows pin
`null_reason: concept_not_mapped` (schema44:74-77) — a path that never
reaches `_valuation_pass`, so the item cannot move them. Wider NCI-related
set, `69 passed, 1 xfailed in 27.66 s` (`test_c2_six_measures`,
`test_concept_map`, `test_formulas`, `test_golden_formulas`,
`test_task56_z2`, the P3 file, `test_m3_snapshot`, `test_pipeline`). The
task's «golden values that move are replaced under a declared pin» clause is
therefore satisfied vacuously — nothing moved.

Copy (P7 — `/tmp` only, offline, `HOME=/tmp/rt-sandbox-home`,
`RUSTERM_ENV_FILE=/nonexistent/rusterm.env`, `bash /tmp/p3-copy-measure.sh`):
the pristine copy `/tmp/rt-104/data` (616 822 facts, 285 snapshots) is
restored before each tree, then all 44 instruments are built with
`snapshot --as-of 2026-09-29` — tree B = detached `7bb410b` worktree
(`/tmp/rt-head`), tree A = the working tree — and every measure row of each
instrument's latest snapshot is dumped `mode=ro` (1630 rows per tree; A's run
left 329 snapshots = 285 + 44, so the builds really wrote).
`B_FAILED=0`, `A_FAILED=0`, `P3COPY_RC=0`, 06:20:11 → 06:20:46Z, network 0.

22 rows differ: 16 `invested_capital`, 6 `roic`.

| kind | rows | what changed |
|---|---|---|
| value → value | 4 | see below |
| refusal name only | 18 | `minority_interest` added to `missing_data` (AMX, BHP, JPM, KSPI, RIO, STX, TECK, VOD) or to `stale_data: … last <date>` (CRM, HPQ, LUMN, NTAP); 6 of them are the matching `roic` rows, so the pair now agrees |
| value → refusal | **0** | no instrument lost a number it had |

| instrument | `invested_capital` before → after | |
|---|---|---|
| US-NEM | 31 317 000 000 → 31 488 000 000 | + 171 000 000 |
| **US-SCCO** | **12 053 000 000 → 12 129 400 000** | + 76 400 000 = the NCI row at the 2026-06-30 border |
| US-SNPS | 37 582 230 000 → 37 581 070 000 | − 1 160 000: minority with a deficit, sign kept |
| US-VALE | 98 430 000 000 → 100 065 000 000 | + 1 635 000 000 |

SCCO is the Done-when shape, checked against the copy's own facts: at the
border `12 632 200 000 (total_equity) + 76 400 000 (minority_interest)
+ 6 750 700 000 (total_debt) − 5 665 000 000 (cash) − 1 664 900 000
(st_investments) = 12 129 400 000` — the after-row; without the NCI term the
same five facts give 12 053 000 000, the before-row. `roic` for SCCO is
`0.3691530064459498` in **both** trees, which is the other half of the same
statement: `roic` was always dividing by the NCI-inclusive number, and the
row now says it too. (The begin border implied by `nopat 4 452 446 698.996212
/ roic` is `11 993 100 000`, so the average is `12 061 250 000` — derived
from stored measures, not dumped separately.)

Reconnaissance for the same file on the copy, because it decides whether P3
could have created refusals: 24 issuers report `minority_interest`; 4 report
`total_equity_incl_nci` with no minority line (AMX, RIO, TECK, JPM) and all
4 already refused `invested_capital` for another missing input before the
change, so naming one more input costs nothing.

## Blocked

## What not to trust

- P2, copy reparse: the `after` run happened while the change was still
  uncommitted, so its log line prints `7ec196a` for both trees — the trees
  differ by the working-tree diff, not by the sha. Reproduce by running
  `bash /tmp/p2-kspi-reparse.sh` after the commit (it needs one detached
  worktree of the parent at `/tmp/rt-head`).
- P2, same log: its trailing `diff` compares copies taken before and after
  each reparse, so the *fact counts* in it grow on both sides (11 558 rows
  added). Only the second field (`registry`) is this item's result.
- P2: no code reads `issuer.reporting_currency` today — `watch add` wrote
  it, nothing displayed it, and the snapshot path now reads the vote from
  the `fact` table instead. So the column fix is verifiable in the DB and
  in tests, but it changes no screen until something shows the registry
  currency. Not a reason to skip the item (the task asks for the column),
  but a reason not to expect a before→after row in any table.
- P3, copy measurement: tree A was the *uncommitted* working tree, so a
  reproducer must apply the P3 diff (or check the commit out) before the
  `after` build; the `before` build needs a detached worktree of `7bb410b`.
- P3, copy measurement: 44 builds per tree took 18 s and 17 s, about 0.4 s
  an instrument — far less than a `follow`. That is what this item needs
  (the facts are already in the copy, only measures are recomputed, no
  network), but it means the run exercised the build/valuation path, not the
  ingestion path, and it is not evidence about collection speed.
- P3, SCCO begin border: `11 993 100 000` is inferred from the stored
  `nopat / roic`, not read out of a `_capital_at` call. The end-border
  reconstruction (five facts → 12 129 400 000) is the measured part; the
  equality of the row with the number inside `roic` is proved in the test
  tooth, where both borders are fixture constants.
- P3, «no pin moved»: the 107-test subset is a file list chosen by
  `grep -l invested_capital tests/`, not a coverage claim. The authoritative
  whole-suite verdict is the hook's (checks 3 and 11) in the P3 commit row
  below.

## Disputed

25. **`upsert_issuer` overwrites what this rule computed.**
    `store/repos.py:67-78` ends with
    `reporting_currency=excluded.reporting_currency`, and
    `watch add` passes a literal `"USD"` for every SEC issuer
    (`cli/__init__.py:1573-1575`). Re-running `watch add US KSPI` therefore
    puts `USD` back into the column until the next ingest or reparse
    recomputes it. P2 says the column is refreshed «on ingest/reparse», so
    I left the registry write alone rather than widen the item. Ruling
    wanted: should `upsert_issuer` stop touching the column (once computed
    it is data, not registry), or should `watch add` stop guessing `USD`?
26. **Four KSPI facts carry unit `TJS` on the user's base** (after reparse:
    KZT 568, TJS 4, USD 1, plus non-monetary `shares`, `KZT/shares`,
    `pure`). P2's rule ignores them — a minority unit cannot win the vote —
    and that is the right outcome either way, so this is not a blocker. But
    «Kaspi files four TJS rows» was not asked and not answered here: if
    the payload really carries a Tajik subsidiary's figures, the question is
    whether they belong on the KSPI issuer at all.

## Runs

| what | command | result |
|---|---|---|
| P1 teeth red before | same file on a detached worktree of `ab2bb63` | 2 red: `pe=7.0`, `ps=0.7`, `fcf_yield=0.17142857142857143` |
| P1 teeth after | `pytest tests/test_task104_p1_price_side_vs_filing_currency.py` | 6 passed in 0.57 s |
| KSPI pins + i5 guard + P1 | `pytest tests/test_task97_q4_ifrs_ingest.py tests/test_i5_guard_source.py tests/test_task104_p1_….py` | **22 passed in 1317.40 s** (2026-09-29T03:38Z) |
| guard file after that run | `git diff HEAD -- agent/p6_rule.sh` | empty — the i5 fixture restored its own staged widening |
| full suite before the commit | `I5_NESTED=1 QT_QPA_PLATFORM=offscreen PYTHONHASHSEED=0 python3 -m pytest -q` | exit 0; 1676 passed, 26 skipped (the i5 cases skip under `I5_NESTED`, exactly as inside the hook), 6 xfailed; 03:49→04:17 UTC |
| copy rebuild, both trees | `python3 -m rusterm --root <copy> snapshot --instrument <id> --as-of 2026-09-29` for all 44 ids, HEAD worktree then working tree | `HEAD_REBUILD_FAILED=0`, `CHANGE_REBUILD_FAILED=0`; 1320 measure rows compared, 1 moved |
| P1 commit + push | `git commit` (hook runs acceptance) , `git push` | `7ec196a`, `Принято. / Итог: пройдено 13, провалено 0`, 5 files, 04:23:33→04:42:56Z; `origin/agent/night-11` = `7ec196a` |
| P2 teeth red before | `pytest tests/test_task104_p2_deterministic_presentation.py` on a detached `7ec196a` worktree (the new API stubbed to `None` there so the file imports) | 7 of 13 failed at `PYTHONHASHSEED` 0 and 1, 6 at seed 2; reparse pair `assert 'USD' == 'MXN'` |
| P2 teeth after | same file, working tree | 13 passed at seeds 0 and 1 |
| copy seed sweep, both trees | `bash /tmp/p2-copy-measure.sh`: 44 × `snapshot --as-of 2026-09-29` per build — before tree B0/B1 (seeds 0/1), working tree A0/A1/A2 (seeds 0/1/2), `HOME=/tmp/rt-sandbox-home`, copies under /tmp | 88 builds, 0 failures; before: 1 of 1320 rows moved between seeds (`US-AMX net_margin`); after: 0 moved in all three pairwise comparisons |
| copy reparse, both trees | `bash /tmp/p2-kspi-reparse.sh` — one offline `rusterm reparse` per copy, `issuer.reporting_currency` read back mode=ro | requests 86 → 86 both sides; `registry_differs_from_dominant` 4 → 0; US-KSPI `USD` → `KZT`, AMX → `MXN`, TECK → `CAD`, VOD → `EUR`; 05:07:49 → 05:09:38Z |
| P2 subsets | `pytest tests/test_task97_q12_reparse_facts.py tests/test_reparse_basis.py tests/test_repos.py tests/test_concurrency.py tests/test_m3_snapshot.py tests/test_pipeline.py` | 55 passed |
| P2 full suite, convenience run | `I5_NESTED=1 QT_QPA_PLATFORM=offscreen PYTHONHASHSEED=0 python3 -m pytest -q -p no:cacheprovider > /tmp/p2-fullsuite.log` (detached) | reached `[100%]`, `grep -c "FAILED\|ERROR\|failed\|error"` on the log = **0**, 05:02→05:21Z — but the run was started without capturing its exit code and the terminal's final count line never landed in the log, so this row is not the verdict. The authoritative full-suite runs are the hook's (checks 3 and 11), quoted in the P2 commit row below. |
| P2 commit, first attempt | `git commit -F /tmp/commit-p2.txt` (hook runs acceptance), detached, log `/tmp/p2-commit.log` | **rejected**, `P2COMMIT_RC=1`, 05:25:41→05:45:49Z: `Итог: пройдено 11, провалено 2` — both pytest checks failed `tests/test_report_sections.py::test_disputed_lines_live_only_in_disputed_section`, because the new P2 prose had a continuation line starting with «Disputed 26 below.» outside `## Disputed`. Nothing was committed (HEAD stayed `7ec196a`); the sentence was reworded, no test was touched. |
| P2 commit, second attempt + push | same message plus a paragraph recording the rejection, `git commit -F /tmp/commit-p2.txt`, log `/tmp/p2-commit2.log`, then `git push` | `7bb410b`, `Итог: пройдено 13, провалено 0` → `Принято.` / `SELFCHECK OK`, `P2COMMIT2_RC=0`, 6 files / 662 insertions, 05:53:00→06:13:55Z (20 m 55 s); `origin/agent/night-11` = `7bb410b` (`7ec196a..7bb410b`) |
| P3 teeth red before | `pytest tests/test_task104_p3_invested_capital_nci.py` on the detached `7bb410b` worktree `/tmp/rt-head` (the new file copied there; no API stub needed — P3 uses only existing functions), log `/tmp/p3-red-before.log` | **9 failed, 1 passed in 1.75 s**; failures are `37.0` vs `41.0 ± 4.1e-05`, `assert 0.12631578947368424 == 0.1333333333` (the Done-when tooth), `assert '37.0' is None` ×2, `assert 37.0 == 32.0 ± 3.2e-05`, `assert 'nci_absent_in_equity_block' in {'input'}`, NCI fact absent from lineage. The 1 pass is `test_roic_does_not_start_counting_nci_twice`, green by design |
| P3 teeth after | same file, working tree | 10 passed |
| P3 existing pins | `pytest` over the 11 files that name `invested_capital` / `roic` / the census and schema-44 goldens | **107 passed in 8.10 s**, no file edited → no ЗАМЕНА-БУЛАВКИ for this item |
| P3 wider NCI set | `pytest tests/test_c2_six_measures.py tests/test_concept_map.py tests/test_formulas.py tests/test_golden_formulas.py tests/test_task56_z2.py tests/test_task104_p3_….py tests/test_m3_snapshot.py tests/test_pipeline.py` | 69 passed, 1 xfailed in 27.66 s (`/tmp/p3-subset.log`) |
| report-shape guard after the P3 section | `pytest tests/test_report_sections.py` | 32 passed, 1 skipped in 0.96 s |
| copy build, both trees | `bash /tmp/p3-copy-measure.sh`: pristine copy restored before each tree, 44 × `snapshot --as-of 2026-09-29` with `/tmp/rt-head` (B) then the working tree (A), `HOME=/tmp/rt-sandbox-home`, `RUSTERM_ENV_FILE=/nonexistent/rusterm.env`, dumps via `/tmp/p3-dump.py` `mode=ro` | `B_FAILED=0`, `A_FAILED=0`, `P3COPY_RC=0`, 06:20:11→06:20:46Z; 1630 rows per dump, **22 moved** (16 `invested_capital`, 6 `roic`): 18 reason-only, 4 values (NEM, SCCO, SNPS, VALE), 0 value→refusal; A's DB holds 329 snapshots (285 + 44) |
| copy SCCO cross-check | `canonical_concept` rows of `cik-1001838` read `mode=ro` from `/tmp/rt-p3/work/data/rusterm.db` | border 2026-06-30: 12 632 200 000 + 76 400 000 + 6 750 700 000 − 5 665 000 000 − 1 664 900 000 = 12 129 400 000 (after row); without the NCI term 12 053 000 000 (before row); `roic 0.3691530064459498` identical in both dumps |

Why some numbers here look huge: a bare `pytest -q` without `I5_NESTED=1`
lets an i5 case spawn `selfcheck.sh` → `acceptance.sh` → another whole suite
(measured: 3 test files took 1317 s that way). The hook always sets
`I5_NESTED=1`; the 28-minute wall above is a plain suite run on this machine
(today it also carried `PYTHONHASHSEED=0`).

## HANDOFF
Status: PARTIAL — round 141 is still running; this section is rewritten at
each fold, so read it together with the commit rows of `## Runs`.

Delivered and pushed: P1 (`7ec196a`), P2 (`7bb410b`), P3 (its commit sha and
the hook verdict are recorded in `## Runs` as soon as it lands).

Remaining in TASK-104:
- P4 — `gross_margin` through the finished `gross_profit` measure. Expected
  to need a declared pin replacement: several tests and goldens pin the
  refusal `missing_data: gross_profit` today.
- P5 — priced measures take their currency from the measure unit, so a
  share-count fact without a currency stops poisoning `market_cap_total`.
- P6 — `insider_net` in money (shares times the close on the deal date) and
  a `METHOD_VERSION` bump.
- P7 — `snapshot --as-of` must hand the same date to the factory and to
  `build()`; today the governance rows of an explicit `--as-of` build are
  dated by the machine clock.

Then TASK-105 R1–R6, reported in this file.

Questions for the coordinator:
- items 25 and 26 of `## Disputed` (the registry write that undoes P2's
  computed column; four KSPI rows carrying `TJS`);
- for P4: when the margin comes from revenue minus cost of goods sold rather
  than a disclosed gross profit row, should the screen mark it as derived,
  or is the number enough?

Budget: TASK-104 items run with network 0 and LLM calls 0 — the counters in
`agent/STATE.json` are the record; the copy work reads only `/tmp` copies.
