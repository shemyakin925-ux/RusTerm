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

Why some numbers here look huge: a bare `pytest -q` without `I5_NESTED=1`
lets an i5 case spawn `selfcheck.sh` → `acceptance.sh` → another whole suite
(measured: 3 test files took 1317 s that way). The hook always sets
`I5_NESTED=1`; the 28-minute wall above is a plain suite run on this machine
(today it also carried `PYTHONHASHSEED=0`).

## HANDOFF
Status: NOT STARTED
