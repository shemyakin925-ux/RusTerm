# TASK-C6 — полоса C: панель источника целиком

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C6.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C6.md --note "<одна строка>"`;
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
  `agent/REPORT-C6.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** network 0.

## C6.1. Панель по клику

**Done when:** клик по ячейке открывает панель: документ, дата
подачи, концепт, единица, хэш сохранённого ответа, путь к сырью;
источник — `source_panel`, ничего не досчитано на месте.

## C6.2. Открыть сохранённый ответ

**Done when:** из панели открывается сам сохранённый документ
средствами системы; файла нет — сказано словами, без падения.

## C6.3. Отказ объясняется здесь

**Done when:** для ячейки «нет данных» панель называет, какой концепт
не подан и почему это не подстановка; тест на CNQ `roe`.
