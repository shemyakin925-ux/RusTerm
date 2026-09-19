# TASK-C9 — полоса C: настройки, ключи и лимиты

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C9.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C9.md --note "<одна строка>"`;
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
  `agent/REPORT-C9.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** network 0.

## C9.1. Где лежат ключи

**Done when:** окно показывает, какие ключи найдены и откуда
(окружение, файл), **не показывая значений**; отсутствующий ключ
назван вместе с тем, что из-за него недоступно.

## C9.2. Лимиты хостов

**Done when:** потолки по хостам видны и совпадают с реестром; правка
идёт в тот же конфиг, что читает ядро.

## C9.3. Каталог данных

**Done when:** видно, где лежит база, сколько занимает, когда
обновлялась; смена каталога не создаёт его молча, а спрашивает.
