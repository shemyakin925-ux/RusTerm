# TASK-131 — С1: the window opens on a table of all companies

- **Status: READY**
- **Report:** `agent/REPORT-131.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С1. **Read PRODUCT.md first** — it is
  the only definition of done (user, 06.10.2026).
- **Budgets:** network 0, LLM 0.
- **Executor model:** GLM 5.3 (not Flash) from 06.10.

## Rules of the new queue (user 06.10.2026, bind TASK-130…136)

1. Every change serves a PRODUCT.md scenario. Nothing else.
2. **Frozen:** BR/KR/AU/OTC/MOEX, curses TUI, «Качество» tab, chat,
   new guards/hooks/selfcheck rules. Do not touch them.
3. Acceptance = tests + `look.py` on a copy of the user's base (P7):
   `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`.
   `report.json` is the machine check. The user's own «yes» is the final
   one — the coordinator collects it.
4. Reuse `rusterm/desktop/card.py` (coordinator, 06.10): `SECTIONS`,
   `LABELS`, `format_number`, `implausible`, `DASH`. Do not fork them.
5. Empty is «—» (never «нет данных»), names are Russian, years old→new.

## Where we are

- 06.10 coordinator rebuilt the company card (`card.py`, branch
  `claude/product-card`): sections, Russian names, 10 years old→new,
  «—», hidden empty / not-applicable rows, implausible values dashed,
  statement rows from facts. Merged into this shift branch before you start.
- Start screen today: «нет данных» in the middle, grey buttons, until the
  user clicks a company in the tree (`agent/check-2026-10-06/00-start.png`).

## H1. Home table (first)
On start and whenever no company is selected, the centre shows one table:
ticker · name · group (Russian) · капитализация · P/E · чистая маржа ·
ROE · изменение цены за 1 год · последняя цена (date in tooltip).
Values come from the latest snapshot / price table through store doors —
no new formulas in the UI (ADR-0009). Sorting by any column. Double-click
→ that company's card.
**Done when:** offscreen test on fixtures — 3 companies → 3 rows,
click-sort by «Капитализация» orders numerically, double-click loads the
card; look.py `00-start.png` + report: start table rows ≥ 38, zero cells
equal «нет данных».

## H2. Search filters the home table
The existing search field filters both the tree and the home table (ticker
or name, case-insensitive, from the first letter).
**Done when:** test — typing «del» leaves only DELL in both.

## H3. Group names in Russian
Tree and home table: `banks` → «Банки», `hardware_electronics` →
«Техника и электроника», `mining_metals` → «Металлы и добыча»,
`software` → «Софт», `telecom` → «Телеком». One dict in `rusterm/desktop/`;
unknown code shown as is.
**Done when:** test — every sector code of the user-base copy has a name;
look.py: no tree label contains `_`.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `PRODUCT.md`,
  `TASK-*.md`.
- Edit existing `docs/` files or applied migrations.
- Write to `~/EquityLab` (P7) — work on a copy.
- Paid tariffs, cards, deposits (ADR-0018).
