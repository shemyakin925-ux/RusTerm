# TASK-117 — Russian market (MOEX)

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-117.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 300 requests (ISS + e-disclosure), LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

The project is RusTerm, MOEX is absent. Free, no key: MOEX ISS
(`iss.moex.com/iss/...json`) for securities list, daily prices, dividends,
indices; e-disclosure.ru for reports (the user dataset `RU/` shows it works
— read-only reference).

## M1. Market row RU
Registry: RU, provider moex, id = SECID, IFRS/RSBU; `rusterm add --market RU`.
**Done when:** `rusterm markets` lists RU implemented; test on recorded ISS json.

## M2. Prices, dividends, index
ISS history (TQBR board), dividends endpoint, IMOEX index.
**Done when:** live on copy — SBER, GAZP, LKOH: ≥5 years of prices, dividends present.

## M3. Statements
IFRS reports: e-disclosure documents → if XBRL/structured absent, measures
from manual import (ADR-0011) path with the document as source; RSBU
optional. Deterministic rule: structured first, else import + named refusal.
**Done when:** SBER snapshot on copy with ≥10 measures or named refusals; test on a recorded document.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
