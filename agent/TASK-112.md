# TASK-112 — automatic data check block

- **Status: READY**
- **Report:** `agent/REPORT-112.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network ≤ 200 requests/night (Yahoo + SEC frames), LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

Errors were found by hand: CRM net_debt 3× (wrong tag), VOD market cap
471 bn vs ~25 bn real, BAC «2026» = one quarter. User 03.10: «сделай блок
автоматической проверки».

## C1. Reference checks
`rusterm check` compares per paper: market cap, price, revenue (FY),
net income (FY), shares, net debt against free references — Yahoo
quote/summary (no key), SEC `frames`/companyconcept. Tolerance per field
(price 2 %, market cap 5 %, statements 1 %). Result table
`data_check(instrument, field, ours, ref, source, diff, status, checked_at)`
(new migration).
**Done when:** test with fake references — mismatch flagged, within
tolerance ok, missing ref = «нет эталона», not error.

## C2. Internal consistency
Rules without network: margin in [-5, 1], P/E sign = net income sign,
market cap = price × shares ±1 %, a year column only from an annual
period, history jump > 5× vs neighbours flagged.
**Done when:** test per rule on crafted facts; copy — list of findings.

## C3. Visible to the user
Window: tab «Проверка» (or section in «Качество»): red/yellow/green per
paper, click → field, ours vs reference, source link. Runs inside the
TASK-110 background pass, once a day.
**Done when:** offscreen test; look.py on the copy — tab present, ≥1 row
per paper.

## C4. Night report for the coordinator
`agent/CHECK-<date>.md` written by `rusterm check --report`: counts and the
top-20 mismatches.
**Done when:** file generated on the copy; numbers equal the table.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
