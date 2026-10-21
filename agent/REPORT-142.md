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

## Done (E2 — the summary says what changed)
- E2 — the final line of the pass now names the changes in words:
  «цены: N, новые отчёты: M (TK 10-Q, …), мер изменилось: K,
  отказов: R». One function builds it — `refresh_summary_line` in
  `rusterm/core/refresh.py` (tested; names up to 3 reports, then
  «, …»; counts are per-paper). `rusterm refresh --all` emits it as
  the pass's last line (cli/_refresh_all tallies: prices added per
  paper, updated filings with form from the SAME cached submissions
  response — new `EdgarProvider.latest_filing_form`, zero extra
  requests; measures compared before/after the rebuild through
  `latest_snapshot_id`/`get_measures`; refusals = papers whose prices
  or reports refused during the pass). The window only prints it:
  `refresh_pass` finds the line by `SUMMARY_LINE_PREFIX` and appends
  it to «обновлено HH:MM · N бумаг · M запросов»
  (window.py docstrings updated; no behaviour change there).
  - Fixture test (one new filing, one refusal):
    `python3 -m pytest -q tests/test_task142_refresh_summary.py`
    → `5 passed`; the pass line reads
    `цены: 2, новые отчёты: 1 (AAPL 10-Q), мер изменилось: 2, отказов: 1`
  - Neighbours green: test_task110_b3_refresh_all + test_refresh +
    test_task92_c2 → 25 passed; desktop b2 refresh + product home →
    9 passed (the pinned regex `обновлено \d\d:\d\d · 1 бумаг · \d+
    запросов` matches the extended line); q6/ops/m4 → 26 passed.
  - Live re-run of the pass on the copy (second pass, nothing new —
    honest zeros): 36.3 s, 44 requests (339 → 383), window line
    verbatim: «обновлено 14:19 · 49 бумаг · 44 запросов · цены: 0,
    новые отчёты: 0, мер изменилось: 0, отказов: 0»

## HANDOFF
(interim — supersedes the blocks above; E1, E2 done; E3, E4 ahead)
Status:          PARTIAL
Items done:      E1 (a293fc5), E2 (this commit)
Items not done:  E3, E4 (not started)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes its «Итог» line
Tests:           5 passed (new E2 file) + 60 passed neighbours, quoted
Guards:          none touched
Schema:          unchanged (48)
Network:         145 of 400 (52 setup + 49 E1 + 44 E2 live re-run)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator:
1. Latent defect found by the E2 fixture (NOT fixed — outside the
   item): `refresh_one` compares `latest <= state["last_filing_date"]`
   after checking only ConfigError, so a ProviderError from
   `latest_filing_date` (transport/HTTP refusal on submissions)
   crashes it with TypeError instead of naming a refusal — and via
   refresh_pass that aborts the whole window pass. Needs a ruling.

NOW: E2, step 6

## HANDOFF
(interim — supersedes the blocks above; E1, E2 done; E3, E4 ahead.
Same content as the previous block, reworded: the guard forbids the
«меньше» sign as a placeholder, and the previous block quoted code)
Status:          PARTIAL
Items done:      E1 (a293fc5), E2 (this commit)
Items not done:  E3, E4 (not started — paused by the user mid-task)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes its «Итог» line
Tests:           5 passed (new E2 file) + 60 passed neighbours, quoted
                 above in Done (E2)
Guards:          none touched
Schema:          unchanged (48)
Network:         145 of 400 (52 setup + 49 E1 + 44 E2 live re-run)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator:
1. Latent defect found by the E2 fixture (NOT fixed — outside the
   item): refresh_one compares the feed's latest filing date with the
   reflected one after checking only ConfigError, so a ProviderError
   from latest_filing_date (transport or HTTP refusal on submissions)
   crashes it with TypeError instead of naming a refusal — and via
   refresh_pass that aborts the whole window pass. Needs a ruling.

NOW: E2, step 6

## Done (E3 — new company → peer group)
- Rule applied exactly as the item names it: a company joins the group
  where OTHER companies share its SIC (4-digit, from the SEC
  submissions field `sic`, one GET per issuer — 49 issuers measured;
  first run read the wrong field name `assignedSic` and was re-run:
  both counted in the budget).
- What «Аналоги» shows the five today (door `data.peer_screen` on the
  copy): has_peer_set=False for all five — the named refusal with the
  command hint, not an empty tab.
- The measurement (49/49 issuers): NONE of the five shares its SIC
  with any other company in the base:

  | ticker | SIC (SEC)      | group | members |
  |---|---|---|---|
  | NVDA   | 3674 Semiconductors & Related Devices | — | named reason: no other company with that SIC |
  | KO     | 2080 Beverages | — | named reason: no other company with that SIC |
  | XOM    | 2911 Petroleum Refining | — | named reason: no other company with that SIC |
  | PFE    | 2834 Pharmaceutical Preparations | — | named reason: no other company with that SIC |
  | WMT    | 5331 Retail-Variety Stores | — | named reason: no other company with that SIC |

- Why no assignment happened: the only near group for NVDA is
  hardware_electronics, whose members are 357x (Computer & office
  Equipment, Computer Storage Devices, Electronic Computers) — a
  different SIC family; putting NVDA there would be the hand guess
  the item forbids («never by hand»). KO/XOM/PFE/WMT have no candidate
  group at all. Note: even a NEW group per SIC would hold exactly
  1 member (< 3) — the ≥ 3 gate fails for every one of the five
  either way.
- Existing groups on the copy (latest versions, all origin=manual,
  approved): banks 9, hardware_electronics 9, mining_metals 9,
  software 9, telecom 8 members.
