# TASK-114 — price chart, daily change in the list, market overview home

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-114.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 50 requests (Yahoo indices), LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

Prices are stored (years of daily rows) but no price chart; the left list
shows names only; the window opens on an empty card.

## P1. Price chart
Chart mode «Цена»: line/candles, periods 1М 6М 1Г 5Л Макс, volume bars,
crosshair with date/value. Source: `price` table.
**Done when:** offscreen test — 5 period buttons change the x-range;
candle spec has OHLC from stored rows; look.py — chart has ≥200 points for DELL on 1Г.

## P2. List with price and change
Left tree: ticker · name · last price · change % today (green/red).
**Done when:** test — change = close_t / close_t-1 − 1 from `price`.

## P3. Overview screen
Home (no paper selected): main indices (S&P 500, Nasdaq, Dow, Russell,
MOEX, KOSPI, Hang Seng — Yahoo `^` symbols, no key), list movers top/bottom
5, last refresh time.
**Done when:** offscreen test with fake index rows; look.py start shot shows the block.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
