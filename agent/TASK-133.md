# TASK-133 — С5: «Обновить» and «Добавить компанию» without the terminal

- **Status: READY**
- **Report:** `agent/REPORT-133.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С5. Queue rules: `agent/TASK-131.md`.
- **Budgets:** network ≤ 150 requests (live check on a copy), LLM 0.
  Free sources only (SEC, Yahoo) — ADR-0018.

## R1. No silent network on window start (first)
Today the window starts a refresh pass on open (TASK-110 B2): the
coordinator's offscreen look.py runs made 3–8 real requests each and wrote
to the user's base. Start refresh only if the last refresh is older than
6 h **and** the window is shown on screen (not offscreen /
`QT_QPA_PLATFORM=offscreen`). look.py must never hit the network.
Note (coordinator 08.10): `tests/test_desktop_task110_b2_refresh.py`
expects a refresh on start offscreen with fake providers — keep it: add an
explicit switch (`RUSTERM_NO_AUTO_REFRESH=1`, set by look.py and by tests
that do not test refresh) instead of sniffing the Qt platform.
**Done when:** test — offscreen build makes 0 provider calls (counted via
the request gate); look.py run → «запросов сегодня» unchanged.

## R2. One «Обновить» button
Top bar button «Обновить»: prices for all companies + new filings (SEC)
+ snapshot rebuild, in the existing worker with progress «цены 12/38 ·
отчёты 3/38 · пересчёт». At the end one line: «обновлено: 38 цен, 2 новых
отчёта (DELL 10-Q, HPQ 10-K), пересчитано 2 карточки» — or the reason in
words if offline.
**Done when:** offscreen test with fake providers — progress signals in
order, final line names counts; cancel leaves no half snapshot (existing
rule).

## R3. «Добавить компанию» by ticker
Dialog: ticker (US). Runs the same core path as `rusterm add` + ingest +
snapshot (ADR-0027 door), then selects the company. Unknown ticker →
«тикер не найден в SEC», nothing written.
**Done when:** offscreen test with fake providers — new company appears
in tree and home table with a card that has ≥ 1 statement row; unknown
ticker writes nothing (row counts unchanged).

## R4. No terminal commands shown to the user
(was TASK-111 U3) Any user-visible text that tells the user to type
`rusterm …` becomes a button or disappears. Source panel may still show
the command as information.
**Done when:** grep test over `rusterm/desktop/` user-visible strings: no
«rusterm » outside the source panel.

## Do not
Same list as `agent/TASK-131.md` «Do not».
