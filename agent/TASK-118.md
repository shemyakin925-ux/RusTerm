# TASK-118 — Korea: DART key wired; fallback without key

- **Status: READY**
- **Report:** `agent/REPORT-118.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 200 requests, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

KR market row is «нет ключа»: the free OpenDART key is issued to the user
but never reached the program env. User 03.10: «DART выдан. Если не
работает — найти другой вариант».

## K1. Key path
Read `RUSTERM_DART_KEY` from `~/.rusterm.env` like other keys; Settings tab
shows «ключ DART: принят / отклонён (<code>)» via one test request.
**Done when:** test — env file → provider configured; status line text.

## K2. Fallback without key (deterministic)
If the key is rejected or absent: prices from Yahoo `.KS/.KQ`; filings
list + documents from dart.fss.or.kr public site (no key; method in
`/Volumes/KINGSTON/LLM adaptation/dart_annual_reports.py` — read-only
reference: detailSearch.ax → main.do → document); financial statements
from the public «재무제표» viewer HTML if parsable, else named refusal.
**Done when:** live on copy — Samsung 005930: prices + ≥1 annual report
document + measures or named refusals; test on recorded HTML.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
