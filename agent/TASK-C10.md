# TASK-C10 — полоса C: сборка .app и запуск без терминала

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C10.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C10.md --note "<одна строка>"`;
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
  `agent/REPORT-C10.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** сеть — только установка PyInstaller.

## C10.1. Сборка

**Done when:** `.app` собирается PyInstaller по ADR-0004 §6; линковка
Qt остаётся динамической (требование LGPL, «Проверить до Фазы 1» в
ADR-0004) — проверено и названо, чем именно проверено.

## C10.2. Запуск без терминала

**Done when:** собранное приложение открывается двойным щелчком и
находит каталог данных; каталога нет — говорит словами, что сделать.

## C10.3. Честная граница

**Done when:** в отчёте сказано прямо, что подпись и нотаризация не
делались (ADR-0018, платно) и что это значит при первом запуске на
чужой машине.

## C10.4. Smoke-тест сборки

**Done when:** тест по маркеру: собранное приложение стартует и
закрывается, код возврата 0; в обычном прогоне пропускается.
