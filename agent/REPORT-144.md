# REPORT-144 — «Добавить аналоги…» (done by the coordinator, 22.10)

User, 22.10: «тз 144 и финал сделай ты».

## Done
- **G1** `rusterm/core/peers_suggest.py`: `rank_candidates` (pure) +
  `suggest(provider, exclude, year)`. Source measured live 22.10: EDGAR
  atom list by SIC (100 CIK per page; names in it are broken
  «ARRAY(0x…)», so CIK only) + one `frames` request per revenue tag
  (`Revenues` first, ASC-606 fallback — Tigo Energy filed ASC-606 ×1000)
  + `company_tickers_exchange.json` (Nasdaq/NYSE only). Empty frame
  year → year − 1. Provider doors in `providers/edgar.py`: `sic_code`,
  `sic_ciks`, `revenue_frame` (404 → empty frame), `listed_companies`.
- **G2** window: button «Добавить аналоги…» on «Аналоги» when the
  company has no group; suggest and build run in worker threads
  (`_PeerSuggestWorker`, `_PeerGroupWorker`, closeEvent waits); choice
  via `QInputDialog.getText` prefilled with the tickers (one patchable
  seat — TASK-141 D4 hang). `desktop_actions.build_peer_group`: follow
  each new ticker (same door as «+ компания»), then
  `peers set sic-NNNN --origin classifier --approve --note "SEC SIC …"`;
  peers that fail to collect are left out and named. New peers join the
  current watchlist so the home table lists them.
- Bank SIC groups (`sic-6021/6022/6029/6035/6036`) are the «banks»
  sector in `core.snapshot._sector_of` — the bank rules (not-applicable
  measures, TASK-143 F1b no OI derivation, hidden card rows) hold for a
  bank added this way. `home.sector_name("sic-3674")` → «Отрасль SIC 3674».
- **G3** on a copy of the user's base (live SEC, ~110 requests):

  | ticker | group | members | build time |
  |---|---|---|---|
  | NVDA | sic-3674 | NVDA, AMD, AVGO, INTC, MU | ~60 s |
  | KO | sic-2080 | KO, PEP, KDP, STZ, PRMB | 75 s |
  | XOM | (list) | CVX, PSX, MPC, COP, PBF | not built |
  | PFE | (list) | JNJ, MRK, ABBV, BMY, LLY | not built |
  | WMT | (list) | COST, TGT, DG, BJ, DLTR | not built |

  «Аналоги» for NVDA and KO: 9 columns + median row filled
  (`desktop_peers.peer_table`). XOM/PFE/WMT: candidate lists from the
  same rule (prototype run, 32 requests for five SICs); not built to
  stay within the network budget.

## Tests
- `tests/test_task144_peers_suggest.py` (8): ranking, first tag wins,
  determinism/limit, year fallback, SIC paging, frames 404, bank SIC →
  banks, sector name, build_peer_group argv.
- `tests/test_desktop_task144_peer_button.py` (1): offscreen button →
  suggest → dialog → build with the dialog's tickers.
- B1 allowlist: `no_cik`, `no_candidates`, `no_peers_collected`, `no_sic`.
- Full suite without I5: green after one fix (W4 contract: the window no
  longer calls `data.format_value` — actions pre-format revenue).

## What not to trust
- STZ market cap «—» on the copy (other STZ measures present) — not
  investigated; candidate for the next check.
- XOM/PFE/WMT groups were not built on the copy (lists only).

## HANDOFF
Status: DONE · Guards: none touched · Schema: 48 · Network: ~140 SEC
(prototype 32 + G3 ~110) · LLM: 0.
