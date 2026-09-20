# TASK-C3 — полоса C: сравнение с конкурентами

- **Status: READY**
- **Lane: C.** Ветка смены — `agent/night-13`. Отчёт — `agent/REPORT-C3.md`.
- **Protocol:** `agent/PROTOCOL.md` (§12). Состояние: `agent/CONTEXT.md`.
- **Relay:** сдать — `python3 agent/relay.py --branch agent/night-13 hand
  --to coordinator --report agent/REPORT-C3.md --note "<одна строка>"`;
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
  `agent/REPORT-C3.md`, `agent/STATE.json` этой ветки. Остальное чужое:
  нужна правка — строка в Disputed.
- **Budgets:** network 0.

## C3.1. Peer set на экране

**Done when:** для выбранной компании видно её peer set (источник —
`rusterm/core/peers.py` через существующий слой), с правилом отбора,
названным словами; компания без peer set говорит это, а не показывает
пустоту.

## C3.2. Box-plot и радар по группе

**Done when:** box-plot по мере внутри peer set и радар по мерам для
выбранной компании против медианы группы; меры без данных не
занижают медиану — они исключены, и число исключённых показано.

## C3.3. Отрасль целиком

**Done when:** экран отрасли из `industry_rows` — таблица и одна
диаграмма; сортировка по любой мере; строки с отказом не улетают
вниз молча, а помечены.
