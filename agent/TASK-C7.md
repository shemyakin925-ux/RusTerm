# TASK-C7 — полоса C: разговор внутри окна

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C7.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C7.md --note "<одна строка>"`;
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
  `agent/REPORT-C7.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** в тестах 0 вызовов модели; живой прогон — по маркеру.

## C7.1. История разговоров

**Done when:** прошлые разговоры видны и открываются; они переживают
перезапуск окна (та же таблица, что у CLI).

## C7.2. Счётчики на виду

**Done when:** число вызовов и стоимость показаны числами из того же
места, что `rusterm status`; ключ не показывается никогда — тест на
отсутствие ключа в тексте окна.

## C7.3. Гвард цитат в окне

**Done when:** ответ с числом без цитаты не показывается как ответ —
показывается отказ; проверено на записанном ответе, без сети.
