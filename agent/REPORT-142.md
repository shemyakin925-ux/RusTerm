# REPORT-142 — TASK-142 («Обновить» end to end, С5; peers for new companies, С4)

## Done
- E1 — one refresh pass on the copy (`/tmp/rusterm-e-base`, 49
  instruments = 44 of the user's base + NVDA KO XOM PFE WMT re-added
  through `desktop_actions.follow_instrument`; `~/EquityLab` untouched;
  XOM re-pointed to the real CIK 34088 as in REPORT-141, shell facts
  dropped). Prices were stale 12 days (user base max 2026-10-08).
  Door pressed: `desktop_actions.refresh_pass(root)` — the same body
  the window's button runs. Setup spend 52 requests (counter 238 →
  290: five follows ≈45 + XOM 7), measured pass:
  - **seconds: 185.8; requests: 49** (counter 290 → 339; 1 TwelveData
    /time_series per instrument, 0 companyfacts — no filings moved);
  - summary line verbatim: «обновлено 12:49 · 49 бумаг · 49 запросов»;
  - after the pass: 49/49 instruments' latest price date =
    2026-10-20 (the last completed US trading day; query quoted in
    What not to trust); refusals: 0 (no instrument refused);
  - `python3 tools/card_fill.py --root /tmp/rusterm-e-base` → exit 0,
    **ИТОГ 1495/1619 = 92 %** (цель 90 %); per-paper ≥ 74 %, the
    weakest (AA 74 %, waived; T 88 %, ORCL 84 %, waived) — same
    named gaps as REPORT-130 K1.

## Blocked
- (empty)

## What not to trust
- The setup adds (five follows + XOM swap) spent 52 requests per the
  counter (238 → 290), but per-ticker splits for the five are NOT
  measured: the first follow batch's log was truncated (only WMT's
  13.3 s survived). Per-ticker fills will be re-measured in E3 if
  needed; the E1 pass numbers above are complete deltas.
- The E1 price check queried `SELECT instrument_id, MAX(date) FROM
  price GROUP BY instrument_id` → 49/49 rows at 2026-10-20 (0
  laggards, 0 refusals). 2026-10-21 (today) has no close yet at the
  12:49 UTC pass time — «последний торговый день» in the Done-when
  is read as the last completed one.
- The old-format summary line is expected at this point: E2 changes
  the line; its live re-run follows the E2 commit.

## Disputed
- (empty)

## HANDOFF (interim — E1 measured; E2, E3, E4 ahead)
Status:          PARTIAL
Arrival state:   selfcheck first run was this commit's pre-commit —
                 accepted task on de65e11 (TASK-141 accepted)
Items done:      E1
Items not done:  E2, E3, E4 (not started)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes its «Итог» line
Tests:           quoted above (card_fill exit 0, 1495/1619 = 92 %)
Guards:          none touched
Schema:          unchanged (48)
Network:         101 of 400 (52 setup + 49 E1 pass)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: E1, step 6

## HANDOFF
(interim — supersedes the suffixed block above; E1 done, E2–E4 ahead)
Status:          PARTIAL
Arrival state:   accepted task on de65e11 (TASK-141 accepted); the
                 first selfcheck of the shift red only on this
                 report's skeleton (sections), fixed by this append
Items done:      E1
Items not done:  E2, E3, E4 (not started)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes its «Итог» line
Tests:           E1 quoted above (card_fill exit 0, 1495/1619 = 92 %)
Guards:          none touched
Schema:          unchanged (48)
Network:         101 of 400 (52 setup + 49 E1 pass)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: E1, step 6
