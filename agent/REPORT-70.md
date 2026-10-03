# REPORT-70 — TASK-70, round 94: анализ и план

## Done

- Q2 (анализ восьми пустых). Классификация после N1 (20 из 28):
  - (а) чинится расчётом из существующих тегов: **invested_capital**
    (total_equity + total_debt − cash − st_inv — все четыре входа
    смаплены и имеют значения в AAPL). roic при этом тоже оживёт
    (nopat уже считается в проходе 1). **Одна правка закрывает две
    меры.**
  - (б) чинится расчётом — но нужен prior period: **roe** (missing_
    prior_period — нужен total_equity за предыдущий год; в payload
    есть, но окно _issuer_inputs выбирает один год).
  - (в) честно невозможно на этом источнике: **drawdown,
    price_adj, total_return** (нужен ряд price_adj, а не одна
    закрытая цена); **hhi** (нужны пиры отрасли); **roe_incl_nci**
    (AAPL не подаёт NCI — подтверждено N3).
- Q1 (анализ двух путей): pe уже сверяется (P3 из ТЗ-69). Второй
  путь есть у market_cap (price×shares против суммы по классам —
  класс один, сверка тривиальна) и net_income_ttm (годовой факт
  против суммы квартальных — но квартальных в payload мало). Для
  остальных (net_debt, ebitda, fcf, ps) второй путь из одних данных
  не виден — записано без выдумывания.
- Q4. В main должно попасть всё содержательное этой ветки: пять мер
  по словарю, учащие отказы, счётчик запросов, степени каналов,
  страж P7, firsthour-тест. Не пускать: временные стабы в тестах
  (venue_stub, firsthour_stub) — они нужны только для тестов.
- Принято: K0-причина из ТЗ-65 процитирована координатором как
  образец; N1 возвращён и закрыт расширенно.

## Blocked

- Q1/Q2 implementation: контекст смены исчерпан на середине круга.
  Конкретный план реализации invested_capital + roic:
  1. Убрать invested_capital из _UNMAPPED_FORMULAS
     (core/snapshot.py:67);
  2. В _valuation_pass добавить блок: invested_capital =
     total_equity + total_debt − cash − st_investments (все через
     inputs.get, null при отсутствии любого);
  3. roic уже вычисляется в проходе (строка ~1167) — оживёт сам;
  4. roe: окно _issuer_inputs выбирает один год; для avg(equity_
     begin, equity_end) нужен prior period — отдельный пункт;
  5. Тест: golden для invested_capital и roic на AAPL-фактах.

## What not to trust

- Q2 классификация — анализ без прогона; invested_capital может
  выявить скрытые зависимости при реализации.

## Disputed

## HANDOFF (FINAL)

Status: PARTIAL
Arrival state: task taken round 94 on 3849e95, selfcheck green
Items done: Q1/Q2/Q4 анализ, Q3 не начат
Items not done: Q1 реализация сверок, Q2 invested_capital + roic,
Q3 второй эмитент
Acceptance: hook verdict on this commit
Tests: unaffected
Guards: none touched
Schema: unchanged
Network: 0
Model: GLM-5.3, app llm_calls 0
Secrets: нет ключевого материала
Pushed: this commit pushes immediately
Questions for the coordinator:
1. invested_capital: словарное определение включает minority_interest
   (= 0 для AAPL) — вычитать st_investments дважды (уже в cash
   частично)? Словарь говорит да, но это нюанс.
2. Q3 (второй эмитент): предпочтительный сектор для проверки
   разнородности?
3. Что взял бы следующим: invested_capital + roic (закрывает две
   меры одним движением), затем Q3 (второй эмитент).

NOW: Q2 analysis, step 1 — handing back with plan

## HANDOFF

Дополнение: контекст смены исчерпан на анализе Q2. План реализации
invested_capital + roic — в Blocked выше; детали в todo.
