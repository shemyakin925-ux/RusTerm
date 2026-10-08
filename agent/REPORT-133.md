# REPORT-133 — С5: «Обновить» and «Добавить компанию» without the terminal

Done by the coordinator on 08.10.2026 (user: «продолжай ты»).

## Done
- R1: `RUSTERM_NO_AUTO_REFRESH=1` turns off the refresh pass at window
  start; look.py sets it. Checked on a copy: price rows unchanged after
  a look.py run. The TASK-110 test (refresh on start offscreen with fake
  providers) still green — the switch is explicit, not platform sniffing.
- R2: button «Обновить» in the top row runs the same pass as the
  background one (`desktop_actions.refresh_pass` = `rusterm refresh
  --all`), disabled while running; progress and the final line go to the
  status label next to it.
- R3: «+ компания» (was «+ бумага») asks for a US ticker; the existing
  follow path collects it; `follow` now also builds the year history
  (offline) so the card has 10 years at once; the new company opens.
## Blocked
## What not to trust
- R3 not run live in this round (network); covered by the existing
  follow tests with fake providers.
## Disputed
- R4 moved to TASK-134 W5: the q1 tab-hint guard requires executable
  command hints, so replacing them with buttons needs that guard changed
  in the same task.
## Runs
- tests/test_product_home.py 7/7 (incl. the switch and the button),
  test_desktop_task110_b2_refresh green.
## HANDOFF

```
Status:          DONE
Items done:      R1, R2, R3
Items not done:  R4 -> TASK-134 W5
Acceptance:      known reds only (I5 linked-worktree, firsthour date-bound)
Tests:           tests/test_product_home.py 7/7
Guards:          none touched
Schema:          unchanged (48)
Network:         0
Pushed:          yes
Questions for the coordinator:
1. none
```
