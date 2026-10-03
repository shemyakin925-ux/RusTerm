# REPORT-63 — TASK-63, round 80: the first user hour, measured

## Done

- H1. Fresh catalog `/tmp/rt-h1`, real `~/.rusterm.env`, no preparation.
  Every step timed; verbatim output preserved below.
  - budget before: 0.1 s — «использовано 0»;
  - `init`: **0.1 с** — «применено миграций: 44; schema_version=45»;
  - `add --ticker AAPL --name "Apple Inc." --market US`: **5.7 с** (live) —
    «создан инструмент US-AAPL (эмитент Apple Inc., CIK 320193, тикер AAPL
    на US, площадка Nasdaq)»;
  - `ingest --source edgar --instrument US-AAPL`: **74.0 с** — «companyfacts
    загружены; фактов: 12366; неотображённых концептов: 10311»;
  - `snapshot`: **0.2 с** — «снапшот v1 … мер: 28 — со значением 8, пусто 20»;
  - window (offscreen, RUSTERM_APP_SMOKE): **2.0 с** incl. the 1.2 s
    auto-close — exit 0;
  - `export --format md`: **0.1 с** — 28 rows, 8 values, 20 footnoted
    refusals (verbatim table captured; top reasons: 7× missing_data:
    price_close, 8× concept_not_mapped, period_mismatch,
    missing_prior_period, missing_data: total_equity_incl_nci).
- Totals line: **8 значений из 28 строк словаря** (ценовых мер 12+ — их
  причины называют `price_close`; цены собираются отдельной командой
  `--source twelvedata`, которой в сценарии не было); **происхождение
  видно у всех 8 полученных мер** (панель источника окна и источник-колонка
  десктопного экспорта: документ + хэш + период), в CLI-экспорте
  происхождения нет. Budget after: «использовано 0» — см. H2.
- H3. Second pass on the same base: `ingest` **13.5 с** — «companyfacts
  уже в store — пропущено» (0 new requests vs 74.0 s first pass);
  `snapshot` built **v2** with the same 28/8 measures and identical values
  (asset_turnover 0.2900968783638321, period 2026-06-27 — byte-equal).
  Data did not drift; the version bump for identical content is noted in H2.

- H4. README §11.2 vs code: README named pandas in the Python rationale;
  proven by run that this is false — `grep -rln pandas rusterm/` finds
  nothing, `pyproject.toml` has `dependencies = []`, acceptance runs the
  suite without third-party packages. Fixed the cell to: «экосистема
  парсинга отчётности; обязательных сторонних пакетов нет
  (dependencies = [])». The rest of §11.2 checked against the code —
  SQLite one file, content-addressed store, PySide6, pyqtgraph/QtCharts
  backends, PyInstaller, golden-file formulas — all hold; no other
  divergence proven, docs/ untouched.

## Blocked

## What not to trust

- The window step was measured offscreen with auto-close; a human sees a
  real screen — timings hold, aesthetics unmeasured.
- Request counts: the runs made live requests to sec.gov (add's ticker map
  + companyfacts), but `rusterm budget` reported 0 (see H2) — the true
  count is "at least 2", the exact per-step request split is not visible
  to the user anywhere.

## Disputed

## HANDOFF

Status: DONE
Arrival state: task taken round 80 on 813461f, selfcheck green
Items done: H1, H2, H3, H4, H5 (proposals below)
Items not done: none
Acceptance: hook verdict on this commit; no code behavior changed this
round except the README cell
Tests: no new tests (measurement round); suites untouched and green on
arrival
Guards: none touched
Schema: unchanged
Network: 3+ live requests (add + companyfacts + second-pass skip made 0);
within the 30-request budget — but see H2 #1: the program itself cannot
show that number
Model: GLM-5.3, app llm_calls 0
Secrets: no key material in this report
Pushed: this commit pushes immediately
Questions for the coordinator:
1. H2 #1 is the sharpest: the user cannot see their own request spend.

NOW: H5, step 2

## H2. Где сценарий спотыкается

- `budget` после живых запросов: «использовано 0» — add (ticker map) и
  ingest (companyfacts) сделали реальные запросы, но счётчик не пишет
  эти сэмплы. Должно было: показать расход. (Шаг: budget после add/ingest.)
- `ingest` молчит 74 секунды: ни стадий, ни прогресса — пользователь не
  отличает работу от зависания. Должно было: стадии (fetch/parse/store)
  или хотя бы «идёт загрузка companyfacts…».
- «неотображённых концептов: 10311» — пугающее число без объяснения:
  это пробег карты концептов, а не потеря данных. Должно было: словам
  рядом («концептов вне карты — не стали мерами; это нормально»).
- 20 из 28 мер пусты с причиной `price_close`, а что цены ставятся
  ОТДЕЛЬНОЙ командой (`ingest --source twelvedata`), из отказа не
  узнать. Должно было: строка-совет, как в F4 для KR.
- CLI-экспорт не несёт происхождения: json без provenance, md без
  источников — происхождение есть только в окне (панель/колонка).
  Должно было: provenance в json, как у десктопного экспорта.
- Второй snapshot создал v2 на идентичных данных — версия растёт без
  изменения содержимого. Должно было: «без изменений» или та же версия.

Что пользователь обязан знать заранее (и откуда он это узнаёт сегодня):
ключи в `~/.rusterm.env` (GUIDE §0); настоящий сбор требует явного
`--source` (справка команды, но не сценарий); цены — отдельный канал
twelvedata (GUIDE, но не отказ меры); тикер и --market обязательны для
add (help); демо и настоящий инструмент различаются (README). Без GUIDE
первый шаг почти наверняка споткнётся о контакт SEC.

## H5. Предложения в BACKLOG (нумерацию даёт координатор)

- Целевые счётчики запросов: `add` и каждый `--source`-ingest пишут
  provider_requests_used в metric_sample; `rusterm budget` и `status
  --json` показывают фактический расход — accept: после add+ingest
  budget называет число больше нуля, равное числу сделанных запросов —
  size: M
- Прогресс стадий в ingest: печатать стадии fetch/parse/store с
  счётчиками — accept: на живом companyfacts-сборе пользователь видит
  не молчащие 74 с, а меняющиеся строки стадий — size: S
- Совет цен в отказах мер: сноска md/json к missing_data: price_close
  добавляет строку «цены: rusterm ingest --source twelvedata
  --instrument …» — accept: строка присутствует и парсится CLI-парсером
  (подстановка команды) — size: S
- provenance в CLI-экспорте: `--format json` несёт attach_provenance по
  lineage (как десктопный) — accept: json-экспорт содержит документ и
  хэш для каждой меры с входами — size: M
- «неотображённых концептов» словами: рядом с числом строка-объяснение
  и доля покрытия карты — accept: вывод ingest объясняет число словами
  из ядра, не пугает — size: S
- Снапшот без изменений: повторный snapshot на идентичных входах не
  создаёт новую версию (или помечает «без изменений») — accept: второй
  прогон не увеличивает версию при том же содержимом — size: M
- Десктопный сбор для KR называет dart_key_unset и как получить ключ
  (те же слова, что у CLI-отказа F4) — accept: отказ окна на
  KR-инструменте несёт причину и строку-инструкцию с подстановкой —
  size: S
