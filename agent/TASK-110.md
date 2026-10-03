# TASK-110 — background refresh; Yahoo is the default price source

- **Status: READY**
- **Report:** `agent/REPORT-110.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 100 requests (live check), LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

Prices go stale after 7 days and valuation measures refuse until a manual
command (01.10: 38 papers stale). Twelve Data key answers «invalid»;
splits/dividends are paid there. Yahoo (no key) is in the code since
ADR-0029 and is the method the user's own dataset used (yfinance,
`/Volumes/KINGSTON/LLM adaptation/q04_prices.py` — read-only reference).

## B0. Acceptance never sleeps (first — costs every round hours)
Round 144: the hand of TASK-109 took ~4 h — three attempts, pytest parked
in `time.sleep` for 40+ min at 0 % CPU (`sample <pid>` → `time_sleep`), and
Yahoo answered 429 from this machine. Rule: an autouse fixture in
`tests/conftest.py` (1) blocks real sockets (any connect → test error
naming the test), (2) replaces the R2 retry sleeper with a no-op recorder,
(3) fails any test whose wall time > 60 s. Tests that need the network are
marked `live` and skipped unless `RUSTERM_LIVE=1`. (4) Tests that read
`date.today()` get one frozen date per test: coordinator verify of round
145 failed `test_task102_m1_shares_freshness.py::test_boundary_of_
freshness_window_is_inclusive` only because the run crossed midnight
(edge computed on 10-03, build on 10-04); alone it passes 3/3.
**Done when:** test — a test opening a socket fails with its name; a
test calling the retry path finishes < 1 s; `pytest -q` wall time printed
in REPORT (before → after).

## B1. Yahoo by default
`RUSTERM_PRICE_SOURCE` default → `yahoo`; Twelve Data stays optional.
**Done when:** test — no env → yahoo provider chosen; `rusterm markets`
shows yahoo for prices.

## B2. Refresh on window start + every 6 h
Worker thread (same pattern as `_FollowWorker`): prices for the list
(incremental, only missing days), `refresh` for filings (only changed),
snapshot rebuild for papers that changed. Status line «обновлено HH:MM ·
N бумаг · M запросов»; never blocks the UI; cancel on close.
**Done when:** offscreen test with fake providers — start triggers one
pass, second pass after timer tick, UI responsive (event loop runs during
pass), close waits for worker.

## B3. Same pass from the OS scheduler
`rusterm refresh --all` = B2 pass headless; `rusterm schedule install`
writes a launchd plist (macOS) for daily 07:00, `schedule remove`.
**Done when:** test — plist content (path, interval) generated into
tmp_path; `--all` on a fake base updates prices + snapshots.

## B4. Stale prices are refreshed, not refused
If the price is older than the stale limit and the network is up, the
snapshot path refreshes prices first.
**Done when:** copy — count of `price_close_stale` refusals before → after
one `refresh --all` (target 0 for papers Yahoo knows).

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
