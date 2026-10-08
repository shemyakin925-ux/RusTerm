# REPORT-131 — С1: the window opens on a table of all companies

Done by the coordinator on 08.10.2026 (executor paused by the user; the
user said: work autonomously).

## Done
- H1: tab «Все компании» first and current at start (`rusterm/desktop/home.py`,
  `window.repaint_home`). Columns: Тикер · Компания · Группа · Капитализация ·
  P/E · Чистая маржа · ROE · Цена за год · Цена. Values from the latest
  snapshot with the card's dash rules (`card.implausible`, «сейчас» not
  older than the last annual report); price change from
  `core.prices.year_change` (adjusted price, no point a year back → «—»).
  Sort by number, «—» last. Double-click → card tab. 0.5 s for 38 papers.
- H2: the sidebar search filters the home table too.
- H3: group names in Russian in the tree and the table (`home.SECTOR_RU`).
- Card dash rules widened: margins with |x| > 100 % (CHTR net margin 561 %),
  P/E or EV/EBITDA > 500 (HPE 1 488×).
## Blocked
## What not to trust
- Market cap of ADRs is wrong (AMX ×20, BHP ×2, RIO ×0.75) — TASK-138.
## Disputed
## Runs
- look.py on a copy: «Все компании» rows 38, cells «нет данных» 0/304.
- tests/test_product_home.py 6/6; desktop suite green except the known
  date-bound firsthour trio (TASK-135 A3).
## HANDOFF

```
Status:          DONE
Items done:      H1, H2, H3
Items not done:  none
Acceptance:      known reds only (I5 linked-worktree, firsthour date-bound)
Tests:           tests/test_product_home.py 6/6
Guards:          none touched
Schema:          unchanged (48)
Network:         38 requests to Yahoo (market cap check, cached)
Pushed:          yes
Questions for the coordinator:
1. none
```
