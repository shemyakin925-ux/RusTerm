# TASK-104 — honest numbers: rulings on REPORT-103 Disputed (part 1)

- **Status: READY**
- **Report:** `agent/REPORT-104.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-104.md --add agent/REPORT-104.md
  --note "<line>"`; then `wait --for executor` in a loop.
- **Budgets:** network 0, LLM 0.
- **Queue:** 104 → 105 → 92 → 93 → 87 G1 → 94 E3–E8 → 85 → 86. Do 104
  and 105 in one round, report both in `REPORT-104.md`.
- Every item: tests red before; «было → стало» on a **copy** of the
  user's base (P7).

## Where we are

Round 140 accepted: TASK-103 and TASK-97 complete — fresh clone 13/0;
23 asserts replaced under 20 declared ЗАМЕНА-БУЛАВКИ; `docs/` untouched.
KSPI 0 → 11 valued measures. Rulings (numbers = REPORT-103 Disputed):

| # | Ruling | Item |
|---|---|---|
| 2 | executor's reading of `roic` accepted | — |
| 3, 22 | extend the currency guard | P1 |
| 4 | B6 stays | — |
| 5, 23 | deterministic presentation currency | P2 |
| 6 | the row carries NCI | P3 |
| 7 | disclosed `GrossProfit` first — accepted | — |
| 8, 21 | chain `gross_margin` | P4 |
| 13 | priced measures take currency from `measure.unit` | P5 |
| 15 | dollar numerator | P6 |
| 16 | one `as_of` | P7 |
| 10, 12, 20 | accepted as built (KSPI capex ban stays) | — |

## P1. `pe`, `ps`, `fcf_yield` refuse across currencies

Same K6 rule as `pb`: sides in different currencies →
`currency_mismatch: <A>, <B>`. No FX conversion (no free source).
**Done when:** test USD price + GBP facts → refusal for all three; copy:
AMX, TECK, KSPI, BHP, VOD `pe`/`ps`/`fcf_yield` before → after.

## P2. One presentation per period, chosen deterministically

When a period is filed in two units, pick the issuer's **dominant
filing currency**: the unit with most monetary facts for that issuer;
tie → lexicographically smallest. `issuer.reporting_currency` is
refreshed from the same rule on ingest/reparse (KSPI → KZT).
**Done when:** test — the AMX shape gives the same value under
`PYTHONHASHSEED` 0, 1, 2; KSPI `reporting_currency` = KZT on the copy.

## P3. `invested_capital` row includes NCI

Row = equity + NCI + debt − cash − st_inv, the same formula `roic`
uses; golden values that move are replaced under a declared pin.
**Done when:** test — SCCO shape: row = number inside `roic`.

## P4. `gross_margin` uses the finished `gross_profit` measure

Wire through `_CHAIN_MEASURES` like `nopat ← effective_tax`.
**Done when:** test — no GrossProfit fact, revenue + cogs → margin has a
value; copy: CLF, FCX, LUMN, SCCO, STX, KSPI before → after.

## P5. Priced measures in the industry table

For estimate (priced) measures the currency is `measure.unit`; a
currency-less share-count fact does not count as `""`.
**Done when:** test — 9 USD `market_cap_total` values → aggregate
computed; copy: the five sets' `market_cap_total` row before → after.

## P6. `insider_net` in money

Numerator = Σ shares × close on the deal date (same currency as
`market_cap_total`); bump `METHOD_VERSION`.
**Done when:** test — price doubles, no deals → indicator unchanged.

## P7. `rusterm snapshot --as-of` is one date

The factory and `build()` receive the same `as_of`.
**Done when:** test — `--as-of 2026-09-12` → governance row dated 12.09.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Write to `~/EquityLab` (P7).
