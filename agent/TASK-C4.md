# TASK-C4 — полоса C: экспорт того, что на экране

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C4.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C4.md --note "<одна строка>"`;
  затем `python3 agent/relay.py --branch agent/night-13 wait --for executor
  --timeout 3600`.
- **Как работать:** раздел «Как работать» из `agent/TASK-C1.md` действует
  целиком: вопросов не задавать, развилки закрывать правилом, спорное — в
  Disputed и дальше по списку, коммитить инкрементами, за заход делать
  максимум.
- **Решения C0 из `agent/TASK-C1.md` в силе:** PySide6 (не PyQt, не
  tkinter), Qt только в `rusterm/desktop/` (ADR-0023), ядро без Qt,
  набор зелёный без PySide6, данные из `rusterm/tui/model.py`, точка
  входа `python3 -m rusterm.desktop`, раздачи нет (ADR-0018).
- **Территория:** `rusterm/desktop/`, `tests/test_desktop_*.py`,
  `agent/REPORT-C4.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** network 0.

## C4.1. Таблица уходит в файл

**Done when:** видимая таблица экспортируется в csv и md тем же
кодом, что `rusterm export` (не своей копией); отказы в файле — теми
же словами, что на экране.

## C4.2. График уходит картинкой

**Done when:** текущий график сохраняется в png; подпись содержит
эмитента, меру, период и дату выгрузки.

## C4.3. Провенанс не теряется

**Done when:** в экспорте таблицы есть колонка источника (документ,
дата, хэш ответа); тест: ни одна строка со значением не уходит без
источника.
