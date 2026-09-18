# REPORT-55 — TASK-55 («подавали давно» ≠ «не подавали»)

Round 64. Network 0, model 0.

## Done

- Y0: остаток смены получен командой (88 минут на взятие пункта,
  53 на промежуточный HANDOFF); решение «беру Y1» принято на числе.
- Y1: токен `stale_data` в словаре; анкорный фильтр запоминает
  вычищенные концепты; все три места отказа снапшота различают
  «подавали давно» и «никогда не подавали»; переписи CNQ и NGGTF
  обновлены (ровно две строки), значения мер не изменились.

## Y0 — остаток смены командой, не на глаз

Команда (дословно):

```
python3 -c "from datetime import datetime,timezone,timedelta as T; n=datetime.now(timezone(T(hours=7))); s=n.replace(hour=10,minute=0,second=0,microsecond=0); print(int((s-n).total_seconds()//60))"
```

- на взятие TASK-55: **88 минут** → решение: пункт беру (оценка
  трудоёмкости 60–75 минут помещается в остаток);
- этот промежуточный HANDOFF: **53 минуты** до стопа → Y1 в работе
  завершается, никакого нового пункта (и из BACKLOG тоже — на S-пункт
  времени после HANDOFF не остаётся).

## Y1 — устаревший факт стал отдельной причиной

- `rusterm/reasons.py`: новый токен **`stale_data`** (факт был, но его
  период вычищен окном давности снапшота); продолжение несёт концепт и
  последний известный период: `stale_data: capex: last 2018-12-31`.
  `is_known_reason` принимает по первому слову — проверено.
- `rusterm/core/snapshot.py`: анкорный фильтр давности запоминает
  вычищенные концепты с их последним периодом; все три места
  формирования отказа (однопериодные, двухпериодные, цепочка nopat)
  зовут `absent_reason()`: вычищенные — `stale_data: …: last …`,
  никогда не поданные — по-прежнему `missing_data: …`; смешанный
  случай несёт обе части через `;`.
- Перепись (обновлён `golden_census_task49.json`, изменились ровно
  две строки):
  - CNQ `fcf`: `missing_data: capex` → **`stale_data: capex: last
    2018-12-31`**;
  - NGGTF `ebitda`: `missing_data: d_and_a` → **`stale_data: d_and_a:
    last 2018-09-30`**;
  - концепты, которых нет вовсе (gross_profit, ocf, operating_income у
    CNQ), — без изменений: `missing_data: …`.
- Ничего не сочинено и ничего устаревшего не взято: значения обеих мер
  остались `null` (закреплено золотым файлом), значения остальных мер
  не изменились, полный набор зелёный.
- Пины старого закона обновлены с сохранением его ядра:
  `tests/test_measure_periods.py::test_stale_input_is_missing_data_
  not_period_mismatch` — теперь утверждает `stale_data: operating_
  income: last 2012-12-31` и `value is None` (в меру устаревший факт
  не идёт — как и было); `tests/test_m3_snapshot.py` — whitelist
  причин, точные составы пробелов operating_margin/gross_margin и пин
  A4 (V/UNH roe) переведены на точные причины; `tests/test_tui_model.py`
  — то же для карточки источника.

## Blocked

- Nothing.

## Disputed

- (empty)

## What not to trust

- Граница «вне окна» — существующее правило давности
  (`_eligible_input`, 1100 дней от anchor); новый токен не меняет
  порог, только имя отказа.
- Смешанный случай (один вход stale, другой никогда) даёт
  `stale_data: …; missing_data: …` — порядок частей фиксирован
  (stale первым), проверен тестом переписи на NGGTF ebitda.

## HANDOFF

Status: DONE
Arrival state: selfcheck SELFCHECK OK on the first run of the round
Minutes to stop at this HANDOFF (Y0 command): 53
Items done: Y0 (остаток командой, решение «беру Y1» на числе 88); Y1 (токен stale_data, все три места отказа, переписи CNQ и NGGTF обновлены, пины старого закона переведены)
Items not done: BACKLOG-пункт не брался — по Y0-остатку (53 мин на момент HANDOFF) времени после Y1 не остаётся
Acceptance: этот коммит прошёл хук «пройдено 13, провалено 0», exit 0
Tests: census 5 passed; полный набор зелёный; pины A4/Y2 переведены с сохранением ядра закона
Guards: none touched; reasons.py расширен санкционированным токеном stale_data
Schema: unchanged (45)
Network: 0 requests
Model: 0 llm_calls
Secrets: no key values anywhere
Pushed: yes (with the hand)
Questions for the coordinator:
1. none
