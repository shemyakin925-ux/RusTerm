# TASK-132 — С4: peers as a table, one readable chart

- **Status: ACCEPTED (08.10, done by the coordinator) — G1–G4.**
- **Report:** `agent/REPORT-132.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С4. Queue rules: `agent/TASK-131.md`
  «Rules of the new queue» (bind this task).
- **Budgets:** network 0, LLM 0.

## Where we are

Tab «Отрасль» (`agent/check-2026-10-06/dell-industry.png`): a p25/median/
p75 table of 6 measures, a box-plot drawn as one white rectangle, a radar
in cartesian axes with negative values, a header in developer jargon
(«peer set … v2 · single-market · дрейф состава больше 20 % —
подозрение»). Banks: net_margin median refused `peer_set_too_small` with
8 banks in the group.

## G1. Rename and rebuild the tab (first)
Tab name «Аналоги». Table: rows = companies of the group, columns =
Капитализация · P/E · P/S · EV/EBITDA · Валовая маржа · Чистая маржа ·
ROE · Чистый долг/EBITDA · Доходность FCF · Рост выручки за год
(only columns applicable to the group — banks get no EV/EBITDA). Last
row «Медиана группы». The selected company's row is bold. Values: latest
snapshot; formatting and dashes via `card.format_number` / `card.implausible`.
**Done when:** offscreen test on fixtures (4 companies) — 5 rows, median
row equals `statistics.median` of shown values, selected row bold;
look.py on DELL: ≥ 8 rows, no cell «нет данных».

## G2. One chart: company vs median
Replace box-plot and radar with horizontal bars: for each column of G1 —
company value vs group median, same unit, labels in Russian.
**Done when:** test — chart spec has one pair per shown column; look.py
screenshot reviewed by the coordinator (no automated taste check).

## G3. Header in words
One line: «Группа: Техника и электроника · 9 компаний · медиана по
последнему году». No version numbers, rules, drift or «manual».
**Done when:** look.py report: peer header contains no `v[0-9]`,
`single-market`, `manual`, `дрейф`.

## G4. Why banks' median was refused
Find why `peer_set_too_small` fires for net_margin with 8 banks (likely
period alignment). Fix so the median uses each company's latest annual
value. If a value is genuinely missing, the cell is «—» and the median
uses the rest (n shown in tooltip).
**Done when:** test on a bank fixture group of 5 → median present;
look.py on JPM: net_margin median not «—».

## Do not
Same list as `agent/TASK-131.md` «Do not».
