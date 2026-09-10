# TASK-23 — M9: котировки и валюация. Формулы наконец получают входы

- **Status: READY** — take it when `agent/TASK-22.md` is finished and
  handed over, or when its items are exhausted before 09:30.
- **Branch:** `agent/night-5` (branch it from the head of `agent/night-4`)
- **Report:** `agent/REPORT-23.md`
- **Sequential, one process.** Schema, then a provider, then the
  scheduler — each depends on the one before.
- **Depends on nothing in TASK-20…22.** Every formula this task feeds
  was written and tested in M1–M3. If the M8 nights went badly, this
  one still runs as written.
- **Goal of the night, in one sentence:** milestone M9 — the half of the
  terminal that computes market cap, enterprise value, EV/EBITDA,
  price-to-book, dividend yield and ROIC stops being formulas with no
  inputs, and the collector stops asking for data it already has.

Section 1 is the working protocol and outranks the task list.

---

## 0. Start here

```bash
git checkout agent/night-4 && git pull
git checkout -b agent/night-5
bash agent/selfcheck.sh > /tmp/sc.txt 2>&1; echo "STATUS=$?"; tail -6 /tmp/sc.txt
python3 -c "from rusterm.store.db import _SCHEMA_VERSION as v; print(v)"
printenv RUSTERM_TWELVEDATA_KEY | cut -c1-4
```

`STATUS=0` required. Read `_SCHEMA_VERSION` from the file. The last
command tells you whether tonight has a network half: **no key → do K1,
K3, K5, K6, K8 (all offline), write `TWELVEDATA_KEY UNSET` in
`## Blocked`, and skip the items that record payloads. Do not simulate a
vendor response and do not hand-write one.**

**First commit:** create `agent/REPORT-23.md` with its five section
headers and repoint `agent/STATE.json` at it in the same commit —
`tests/test_report_sections.py` reads the report `STATE.json` names.

Read, in full: `docs/adr/0014-kotirovki-twelve-data-i-kadentsiya-po-polnote.md`,
`docs/adr/0008-postavshchik-kotirovok.md`, `rusterm/formulas.py`
(**especially `price_adj`, `total_return`, `drawdown`,
`market_cap_per_class`, `market_cap_total`, `enterprise_value`,
`ev_ebitda`, `price_to_book`, `dividend_yield`, `roic` — they are
written and tested; you are feeding them, not rewriting them**),
`rusterm/providers/market.py`, `rusterm/providers/budget.py`,
`rusterm/core/refresh.py`, `rusterm/core/snapshot.py`,
`rusterm/store/db.py`, `docs/module-contracts.md` §2,
`docs/threat-model-sources.md` §2, `agent/TASK.md`.

## 0.1. What was measured before this task was written

The coordinator checked, on 10.09.2026:

| Command | Result |
|---|---|
| `grep -oE "CREATE TABLE[^(]*" rusterm/store/db.py` | 38 tables, **neither `price` nor `corporate_action` among them** |
| `grep -n "class .*Provider" rusterm/providers/market.py` | `MarketDataProvider` protocol and `SyntheticMarketProvider` — **no real vendor** |
| `grep -n "price_adj" rusterm/formulas.py tests/` | **exists and is tested** — split/dividend order independence was closed as backlog B5 in TASK-7 |

So the hard half is done. Tonight is storage, one vendor, and a
scheduler — not new financial mathematics. **If you find yourself
writing an adjustment formula, stop: it already exists.**

## 0.2. The two decisions behind this task. Not open for re-litigation

1. **Twelve Data, free tier, and it is the only vendor.** 8 req/min,
   800/day, `close` and `adjusted`, key `RUSTERM_TWELVEDATA_KEY`.
2. **Collection cadence follows completeness, not the calendar.** An
   instrument with gaps is backfilled at once, across nights if needed;
   an instrument whose history is closed is polled every 7–14 days. The
   same rule applies to disclosures: an issuer whose filings are all
   collected is checked for a new one every week or two, not nightly.

Both are the user's, recorded in ADR-0014 with the reasoning.

---

## 1. Working protocol. This outranks the task list

Identical to `agent/TASK-19.md` §1 — the cycle, the five prohibitions,
selfcheck, the stuck rule, the stop rule, commit format, R1–R4
bookkeeping, push, the 09:30 line, network rules N2–N7, money and quota.
**Read it there.** What differs tonight:

- **N3 is per host and the ceiling is the vendor's, not ours.** Twelve
  Data free tier: **8 requests per minute and 800 per day, and you must
  not exceed either.** The minute limit is the one that will bite: the
  gate sleeps, and a night spent sleeping is a night wasted — design K5
  so it does not queue work it cannot run.
- **This task's budget is 200 requests.** Count every one in
  `STATE.json` `"net_requests"`.
- **P1 applies to `golden_m2.json` and `golden_m6_ca.json`.** Feeding
  valuation measures must not move a single fundamental number. A
  changed golden value is a stop under §1.5.
- `docs/` is frozen; a new ADR is the one permitted change there.

---

## 2. The work, in priority order

### K1. Цены и корпоративные действия получают место в схеме

`rusterm/store/db.py`, `rusterm/store/repos.py`. One migration; read
`_SCHEMA_VERSION` first.

- Table `price`: instrument, date, `close`, `adjusted`, `currency`,
  volume, source, retrieved_at. **Both `close` and `adjusted` are
  stored** — `docs/module-contracts.md` §2 requires both, and the diff
  is built on `close`.
- Table `corporate_action`: instrument, ex_date, kind (`split` |
  `dividend`), factor or amount, currency, source.
- `PriceRepo` and `CorporateActionRepo` in the existing style. SQL stays
  inside `rusterm/store/` (check 7).
- A price row is unique per (instrument, date, source) — re-collecting a
  day overwrites nothing and duplicates nothing (I7).

**Done when:** the migration applied twice creates no duplicates
(asserted by row count); an existing database migrates and every
pre-existing table keeps its row count; `python3 -m pytest
tests/test_db.py tests/test_repos.py -q` green.

### K2. Провайдер Twelve Data, один и с честным лимитом

`rusterm/providers/twelvedata.py` (new), registered in the provider
registry. **Needs the key**; without it, do K3 and come back.

- `MarketDataProvider` implementation: daily `close` and `adjusted`,
  plus splits and dividends where the endpoint gives them.
- Declares host, **8/min**, **800/day** to `RequestGate`. No key →
  `ConfigError` value and the offline path (N2). The key never enters
  git, a log, a report or a test.
- Caches by content hash in the raw store (ADR-0003): asking for a day
  already held costs **zero** requests.
- 429 is a stop, not a puzzle (N4). Never raise the declared limits in
  code to go faster.
- A **trimmed recorded payload** under `tests/data/twelvedata/`, ceiling
  256 KB, and a golden test resolving each asserted price back into it.

**Done when:** `python3 -m pytest tests/test_market_prices.py -q` green
with the key unset (network tests skip cleanly, N7) and with it set; a
test asserts a second collection of the same day issues **zero**
requests; the report states requests used against the 200 budget.

### K3. Корректировка считается нашей функцией, вендорская — сверка

`rusterm/core/` — wiring only. **Do not write an adjustment formula.**

`price_adj` exists, is tested, and is order-independent across splits
and dividends (backlog B5). Its inputs are the `corporate_action` rows
from K1.

- The adjusted series the program uses is **computed by `price_adj`**
  from stored corporate actions.
- The vendor's own `adjusted` is stored beside it and used as a
  **cross-check**: where the two disagree beyond a tolerance, that is a
  finding recorded with both numbers — not a silent preference for
  either, and not a reason to delete our own.
- A disagreement is reported, never resolved by overwriting.

**Done when:** a golden test builds a series with a split and a dividend
and asserts our adjusted series matches the expected values exactly; a
test asserts a deliberate vendor/our mismatch is reported with both
numbers and neither series is modified.

### K4. Валюационные меры доезжают до снапшота

`rusterm/core/snapshot.py`, `rusterm/normalize/concepts.py`.

Six formulas have been waiting since M1: `market_cap_total`,
`enterprise_value`, `ev_ebitda`, `price_to_book`, `dividend_yield`,
`roic`. Feed them.

- `market_cap` is summed **per share class** and then across classes —
  `market_cap_per_class` and `market_cap_total` already encode this, and
  a preferred class is not a footnote.
- A missing price is `missing_data: price_close`, exactly like a missing
  fundamental. **Never carry yesterday's price forward as today's.**
- A stale price beyond a threshold is a reason, not a number.

**Done when:** the measure table `measure -> n/N + reasons` is in the
report **including the six new measures**; `golden_m2.json` and
`golden_m6_ca.json` are unchanged, asserted; a test drives the
missing-price and stale-price paths and asserts a reason, not a value.

### K5. Обход по полноте: добить неполные, полные опрашивать редко

`rusterm/core/refresh.py`, `rusterm/store/repos.py`. **This is the
item the user asked for by name, and it is what makes the free tier
sufficient.** Extend the existing refresh path; do not rewrite it.

- **Completeness is computed, never a hand-set flag.** An instrument is
  complete when its stored history is closed to the last trading day
  with no interior gaps. Recompute it on every pass — a flag someone
  can forget to clear is the same defect as a report without a run.
- **Incomplete → backfill now, and keep going across nights.** The work
  is resumable through the existing job queue: a night that ends
  mid-backfill loses nothing.
- **Complete → poll every 7–14 days**, not nightly.
- **Backfill takes the budget first**; polling gets the remainder. When
  the daily ceiling is reached, the pass stops cleanly and records where
  it stopped — it does not sleep against the minute limit hoping for
  more.
- The same rule extends to disclosures: an issuer whose filings are all
  collected is checked for a new one on the same 7–14 day cadence
  (ADR-0014 §2), not every night.

**Done when:** a test with a fake clock proves a complete instrument is
skipped on day 3 and collected on day 10; a test proves an incomplete
instrument is backfilled ahead of a complete one when the budget is too
small for both; a test proves a pass interrupted at the ceiling resumes
from where it stopped and issues no duplicate request; the report shows
a simulated 30-day run with the request count per day, all under 800.

### K6. Цена в своей валюте, и валюационные меры это знают

**Needs:** the currency rule from TASK-21 H3 / TASK-22 J1.

A Korean issuer's price is in won and its market cap is in won. Prices
must not become the back door around the currency rule.

- A price row carries its currency; `market_cap`, `enterprise_value` and
  `price_to_book` are stated in it.
- A peer set spanning currencies yields `currency_mismatch` for these
  exactly as it does for revenue — **no conversion, no FX provider**
  (ADR-0014 §4).
- `ev_ebitda`, `dividend_yield` and `roic` are ratios and stay
  comparable across markets, provided numerator and denominator are in
  the **same** currency. Assert that they are.

**Done when:** a test asserts a mixed-currency peer set returns
`currency_mismatch` for the absolute valuation measures and real numbers
for the ratio ones; a test asserts a ratio built from two different
currencies is refused rather than computed.

### K7. Один вендор — известная дыра, а не забытая

**Needs:** K2. Report and a new ADR only.

`docs/threat-model-sources.md` §2 class B requires **two** configured
price providers: a single source is a guaranteed point of failure. The
user chose one. That gap is deliberate (ADR-0014 §3) and must be
visible, not buried.

- Twelve Data unreachable → `source_unreachable`, the price path stops,
  and **the fundamental half of the product keeps working**. Prove it
  with a test: with the price provider failing, a snapshot still builds
  and its fundamental measures are unchanged.
- Valuation measures in that state return a reason. **Never a stale
  number presented as current.**
- `doctor` reports how old the newest price is, per instrument.

**Done when:** the degradation test passes; `doctor` shows price age on
a database with deliberately old prices; the report states plainly that
the two-provider requirement is unmet by decision, citing ADR-0014 §3.

### K8. Веха M9, со своими доказательствами

Append to the report, each claim beside the command that proves it:

- which instruments have prices, and how deep the history goes;
- the measure table including the six valuation measures;
- our adjusted series against the vendor's: agreements and disagreements
  with counts;
- the simulated 30-day cadence: requests per day, backfills completed,
  polls performed;
- what M9 does **not** cover, named honestly.

**Done when:** `bash agent/selfcheck.sh` exits 0; every claim has its
command and real output beside it; `agent/STATE.json` is set to
`"status": "awaiting_review"`.

### K9. Backlog

`agent/BACKLOG.md`, top-down, only if K1–K8 are done before 09:30.

---

## 3. Closing the shift

```
Status:          DONE | PARTIAL | BLOCKED
Items done:      K1, K2, …
Items not done:  … and why
Acceptance:      the "Итог" line and the captured exit status
Tests:           N passed, N skipped, N xfailed
Schema:          _SCHEMA_VERSION <old> -> <new>, migration <number>
Golden:          golden_m2.json and golden_m6_ca.json — unchanged? assert output
Prices:          instruments covered, history depth, currencies seen
Adjusted:        our series vs vendor — agreements / disagreements
Valuation:       the six measures, n/N and reasons
Cadence:         30-day simulation — requests per day, max, all under 800
Degradation:     snapshot result with the price provider failing
Two providers:   unmet by decision (ADR-0014 §3) — confirm it is stated
Network:         requests used of the 200 budget
Model:           app llm_calls N; your own model id
Pushed:          yes/no
Questions for the coordinator:
1. …
```
