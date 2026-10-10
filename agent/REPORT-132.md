# REPORT-132 — С4: peers as a table, one readable chart

Done by the coordinator on 08.10.2026 (user: «продолжай ты»).

## Done
- G1: tab renamed «Аналоги»; `rusterm/desktop/peers.py` builds the group
  table — members of the peer set, Капитализация · P/E · P/S · EV/EBITDA ·
  Валовая маржа · Чистая маржа · ROE · Чистый долг/EBITDA · Доходность
  FCF from the latest snapshot with the card's dash rules; a column is
  shown only with ≥ 3 numbers; last row «Медиана группы»; own row bold.
- G2: one chart — the company's place in the group per measure (share of
  the others it beats, 0–100, median = 50). Percent-to-median was tried
  and dropped: with a median near zero it explodes (DELL net debt/EBITDA
  2.05 vs 0.14 → «+1 364 %»).
- G3: header in words («Группа: Банки · 9 компаний · медиана по последним
  значениям»); peer-set version, scope and rule moved to the tooltip.
- G4: banks get a median — the table takes each company's latest value;
  the period-aligned aggregate stays under «Подробно» unchanged.
- The old p25/median/p75 table, box-plot and radar are kept in a
  collapsed «Подробно: распределение по отрасли».
## Blocked
## What not to trust
- Caps of DELL, JPM, T, ORCL show «—» on the copy only because prices are
  a week old there.
## Disputed
## Runs
- look.py on the copy: «Аналоги» 12/12 companies render; screenshot
  `agent/check-2026-10-08/peers-jpm.png`.
- tests: tests/test_product_peers.py 3/3, test_desktop_window peers 1/1.
## HANDOFF

```
Status:          DONE
Items done:      G1, G2, G3, G4
Items not done:  none
Acceptance:      known reds only (I5 linked-worktree, firsthour date-bound)
Tests:           tests/test_product_peers.py 3/3
Guards:          none touched
Schema:          unchanged (48)
Network:         0
Pushed:          yes
Questions for the coordinator:
1. none
```
