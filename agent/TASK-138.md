# TASK-138 — market cap of ADRs and dual listings (AMX ×20, BHP ×2)

- **Status: READY** — take FIRST (before TASK-132): wrong numbers on the
  home table are worse than a missing button.
- **Report:** `agent/REPORT-138.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С1/С2 + Yahoo match. Queue rules:
  `agent/TASK-131.md` «Rules of the new queue».
- **Budgets:** network ≤ 60 requests (SEC 20-F cover pages, Yahoo via the
  cache of `tools/yahoo_check.py`), LLM 0. Free sources only.

## Where we are (coordinator, 08.10)
Home table (TASK-131, done) shows our latest `market_cap_total`. Checked
against Yahoo `quarterlyMarketCap` for all 38 papers:

| paper | ours | Yahoo | ratio | likely cause |
|---|---|---|---|---|
| AMX | 1 344 bn | 66.8 bn | ×20.1 | ADS = 20 shares, price is per ADS |
| BHP | 433 bn | 224 bn | ×1.93 | ADS = 2 shares |
| RIO | 118 bn | 157 bn | ×0.75 | dual listing: plc + Ltd shares |
| VOD, TECK, CHTR, CMCSA, WDAY | — | present | — | check reason (stale price on the copy or other) |

All others within ±15 %.

**Coordinator's interim guard (08.10, `e…` see git log):** an issuer that
files mainly IFRS (`SnapshotRepo.files_mainly_ifrs`) gets market cap
refused with `adr_ratio_unknown` — AMX/BHP/RIO/VOD/KSPI/TECK show «—»
instead of ×20 / ×2. A2 lifts the guard per issuer once the ratio is a
fact; TECK and KSPI (ratio 1) should come back first.

## A1. Name the cause per paper (first, no code)
For each row above: the 20-F/40-F cover (ADS ratio, share classes), our
`market_cap_total` lineage (price fact, shares fact, class), and the fix.
**Done when:** REPORT-138 table: paper · cause · source line · proposed rule.

## A2. ADS ratio in the market cap
Store the ADS ratio as a fact with a source (20-F cover «each ADS
represents N shares»), never a hand-typed constant without a source; use
it in `market_cap_per_class` (price per ADS × shares ÷ ratio). No ratio
known → market cap «—» with reason `adr_ratio_unknown` for listings that
are ADSs (foreign issuer, price on a US venue, IFRS/20-F).
**Done when:** test on an ADS fixture (ratio 20) → cap = price × shares
÷ 20; AMX and BHP within 15 % of Yahoo on a copy.

## A3. Dual listing (RIO)
Sum both listed entities' shares if the issuer reports them, or «—» with
a reason. **Done when:** RIO within 15 % of Yahoo or «—» with the reason.

## A4. Guard
`tools/yahoo_check.py` gains `--all` (every instrument, market cap only)
so this check is one command.
**Done when:** `python3 tools/yahoo_check.py --root <copy> --all` prints
no paper outside ±15 % except ones with a named reason.

## Do not
Same list as `agent/TASK-131.md` «Do not».
