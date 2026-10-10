# REPORT-138 — market cap of ADRs and dual listings

Done by the coordinator on 08.10.2026 (user: «продолжай ты»).

## Done
- A1 (causes): AMX — price per ADS × 60.3 bn ordinary shares, ADS = 20
  B shares; BHP — ADS = 2 shares; VOD — ADS = 10 shares; KSPI and RIO —
  ADS = 1 share (RIO additionally dual-listed, A3); TECK — 40-F, Class B
  shares trade on NYSE directly, no ADS.
- A2: `rusterm ads-ratio [--all | --ticker]` reads the latest 20-F/40-F
  cover via the EDGAR provider (`core/ads.parse_ads_ratio`) and stores
  `rusterm:AdsRatio` / canonical `ads_ratio` as a fact with the raw
  document and the quote in the locator. The snapshot divides ordinary
  shares by the ratio for IFRS filers (`latest_ads_ratio`) and keeps the
  ratio fact in the market-cap lineage; no ratio → `adr_ratio_unknown`.
  Copy: AMX 67.2 bn vs Yahoo 66.8; BHP 216 vs 224.
- A4: `tools/yahoo_check.py --all` — market cap of every instrument vs
  Yahoo, ±15 %. On the copy: 1 outside (ADBE 22 %, BACKLOG P8).
## Blocked
## What not to trust
- VOD, KSPI, RIO caps not verified: prices on the copy are stale.
## Disputed
## Runs
- `rusterm ads-ratio --all` on the copy: 5 ratios (AMX 20, BHP 2, VOD 10,
  KSPI 1, RIO 1), TECK none; 12 SEC requests.
- tests: tests/test_coordinator_0810.py green (ADS parser on four real
  cover phrases, door, IFRS guard).
## HANDOFF

```
Status:          DONE
Items done:      A1, A2, A4
Items not done:  A3 -> BACKLOG P6
Acceptance:      known reds only (I5 linked-worktree, firsthour date-bound)
Tests:           tests/test_coordinator_0810.py green
Guards:          none touched
Schema:          unchanged (48)
Network:         12 SEC requests, 44 Yahoo (cached)
Pushed:          yes
Questions for the coordinator:
1. none
```
