# TASK-107 — the window shows years: history, yearly chart, honest source panel (user's screenshot 30.09)

- **Status: READY**
- **Report:** `agent/REPORT-107.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-107.md --add agent/REPORT-107.md
  --note "<line>"`; then `wait --for executor` in a loop.
- **Budgets:** network ≤ 20 SEC requests (V3 only), LLM 0.
- **Queue:** FIRST; then TASK-106; then 93 → 87 G1 → 94 E3–E8 → 85 → 86.
- Measure on a **copy** of the user's base (P7). Offscreen Qt tests for
  every window change.

## Where we are

Round 142 accepted (TASK-92, TASK-104 P7, TASK-105; fresh clone 13/0;
`docs/` diff = new ADRs 0024–0027 only). The user opened the window on
their base (screenshot 30.09, BAC) and saw:
- the table has only «сейчас» and 2026 — no past years;
- the chart's X axis reads 2026.088608 … 2026.088616 with one point;
- the source panel says «api: e7d84368… сырья нет в хранилище» three times;
- `ebitda`, `ev`, `ev_ebitda`, `fcf`, `fcf_yield` say «нет данных» for a bank.

## V1. Measure history by fiscal year (backfill)

A command (e.g. `rusterm history --instrument X` and `--all`) builds one
snapshot per **fiscal year end** for the last 10 years from facts already
in the base (no network): `as_of` = FY end + the filing lag actually
observed (the fact's `filed` date), so each year sees only what was filed
by then. Idempotent; `follow` and «Собрать» run it after the snapshot.
The table shows one column per fiscal year (newest first) plus «сейчас».
**Done when:** test — fixture with 3 fiscal years → 3 year columns with
different values; rerun adds no rows; copy: BAC, AAPL, KSPI year columns
before → after (count of years with a value per measure).

## V2. Chart: integer years, one point per fiscal year

X axis = fiscal year as an integer label (2016 … 2025, plus «сейчас» only
if the user picks it); Y = the annual value. No quarters, no fractional
dates. Fewer than 2 points → a sentence «одна точка — нужна история:
rusterm history …» instead of an empty plot.
**Done when:** offscreen test — 3 annual values → 3 ticks labelled
`2023 2024 2025`, no tick label contains «.»; 1 value → the sentence.

## V3. «сырья нет в хранилище»

Find why lineage points at a raw object absent from `raw/store` on the
user's base (copy): count such lineage rows per source. Fix the cause;
re-fetch missing SEC payloads within budget (free, UA key); anything not
re-fetchable is labelled with the reason in words, not a bare hash.
**Done when:** copy: missing-raw lineage rows before → after; test — a
lineage row with a missing raw object renders a worded reason.

## V4. «не применимо» for banks

Measures undefined for a sector (banks: `ebitda`, `ev`, `ev_ebitda`,
`fcf`, `fcf_yield`, `gross_margin`, …) refuse with
`not_applicable: <sector>` and the window prints «не применимо к банкам»,
not «нет данных». One table in the measure dictionary code, cited in a new
ADR (no edits to existing docs).
**Done when:** test — bank instrument → those measures `not_applicable`;
non-bank unchanged; copy: BAC before → after.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files — only new ADRs.
- Write to `~/EquityLab` (P7) or create anything in `~`.
