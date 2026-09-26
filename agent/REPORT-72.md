# REPORT-72 — TASK-72, round 98

## Done

- Д1. measure_history() считает по снапшотам через
  tui_model.measure_history_by_year — извлекает значения из ВСЕХ
  снапшотов инструмента по годам (не пустой заглушка).
- Д3. format_value масштабирует: ≥1e9 → млрд, ≥1e6 → млн, ≥1e3 → тыс;
  0.0012345 → 0.0012 (4 знака); полный precision в панели/экспорте.
- test_history_honestly_absent заменён на test_history_returns_
  snapshotted_years (заглушка → реальное поведение).

## Blocked

## What not to trust

- Остальные дефекты (Д2, Д4) и пункты S1/S2/S4/S5 — в работе.

## Disputed

## HANDOFF

Status: PARTIAL
Items done: Д1, Д3
Items not done: Д2, Д4, S1, S2, S4, S5
