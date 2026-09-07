# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file. The executor never edits
this file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

## Queue

- [ ] B1 — Guard the invariant-numbering gap that hid I16: add a test
  asserting the `test_iNN_` functions in `tests/test_invariants.py` run
  contiguously from 01 with no missing number — accept:
  `python3 -m pytest tests/test_invariants.py -q -k numbering` green, and
  it fails if any `test_iNN_` is deleted — size: S
- [ ] B2 — Fixture discipline as a test, not only a convention: assert
  every file under `fixtures/` has `synthetic` in its name and in its
  body — accept: `python3 -m pytest -q -k fixtures_are_synthetic` green;
  add a temp non-synthetic file and see it go red — size: S
- [ ] B3 — Pipeline idempotency is proven for the raw store and for
  facts, but not for the job queue: assert a second `ingest` run creates
  no new `job` rows — accept: new test in `tests/test_pipeline.py`,
  `python3 -m pytest tests/test_pipeline.py -q` green — size: S
- [ ] B4 — Second golden-file issuer: a multi-class synthetic emitter
  exercising `market_cap_total` and the preferred-stock rule in `ev`,
  with a hand-computed reference — accept:
  `python3 -m pytest tests/test_golden_formulas.py -q` green with two
  issuers — size: M
- [ ] B5 — `price_adj` order-independence: applying a split and a
  dividend on disjoint dates in either order yields the same adjusted
  series — accept: new test in `tests/test_formulas.py` green — size: S
- [ ] B6 — `doctor` should report schema drift: if
  `current_schema_version(conn) != _SCHEMA_VERSION`, say so with both
  numbers. Check first whether it already does; if it does, add the
  missing test instead — accept: `rusterm doctor` on a schema-32
  database prints the drift, covered by a test — size: S
- [ ] B7 — Docs/code drift guard for coverage blocks: assert every block
  name in the `docs/watchlist-and-llm.md` §1.3 table exists in the code's
  block list, and vice versa — accept: new test green; renaming a block
  in code turns it red — size: M

- [ ] B8 — `effective_tax_rate` считает ставку при убытке: docstring
  требует «pretax_income <= 0 → ставка юрисдикции», код проверяет только
  `== 0`. `(-100, -1000)` даёт `0.1`, а `(100, -1000)` даёт ровно `0.0`,
  потому что `clip` обрезает снизу нулём — нулевая ставка выглядит
  правдоподобно и не вызовет подозрений. Ставка идёт в NOPAT, NOPAT —
  в ROIC — accept: обе пары дают `null` с причиной, тест в
  `tests/test_formulas.py` green — size: S
- [ ] B9 — Маржи принимают отрицательный знаменатель: `gross_margin`,
  `operating_margin`, `net_margin` проверяют `revenue == 0`, тогда как
  data dictionary требует `null` при знаменателе `<= 0`.
  `gross_margin(10, -100)` = `-0.1`, при том что соседний
  `roic(10, -1, -1)` в том же модуле возвращает
  `(None, 'negative_denominator')` — accept: три маржи дают
  `negative_denominator`, тест green — size: S
- [ ] B10 — `calculate_measure("invested_capital")` бросает `TypeError`
  на неполных данных: ветка допускает вызов при заполненных
  `total_equity`, `minority_interest`, `total_debt`, а сама функция
  требует пять обязательных аргументов. Контракт движка
  (`docs/module-contracts.md`) запрещает исключения — только `null`
  с причиной; отсутствие cash в отчётности обычно — accept: вызов без
  `cash`/`st_investments` даёт `null` с `missing_data`, тест green — size: S
- [ ] B11 — EBITDA молча равна operating income при нераскрытой D&A:
  при `operating_income is not None` и `d_and_a is None` значение
  остаётся равным operating income с пустым `null_reason`. EBITDA —
  база для EV/EBITDA и net debt / EBITDA. Вдобавок возвращается
  `Measure` с непустым `value` и пустым `lineage`, что запрещено
  инвариантом I4 — accept: даёт `null` с `missing_data`, I4 это ловит,
  тест green — size: S
- [ ] B12 — `Fact` объявлен неизменяемым, но изменяем: шесть классов
  локаторов — `@dataclass(frozen=True)`, сам `Fact` (`fact.py:141`) —
  обычный `@dataclass`, `f.value = "2"` проходит. Инвариант I2 этого
  не ловит, потому что проверяет текст `repos.py` через
  `inspect.getsource`, а не поведение — accept: `frozen=True`,
  `superseded_by` меняется через `dataclasses.replace`, I2 дополнен
  проверкой `FrozenInstanceError` — size: M
- [ ] B13 — Миграция не снимает резервную копию базы вопреки
  `docs/data-model.md` §8 п.4 и собственному docstring `db.py`:
  в коде нет ни `shutil.copy`, ни временного файла. Пока миграции
  только создавали таблицы, цена была нулевой; теперь есть процедурные
  миграции с переносом данных. Копию снимать через `conn.backup(dst)`,
  а не `shutil.copy`: база в режиме WAL, часть данных в `-wal`-файле —
  accept: копия создаётся до миграций и удаляется после успеха, тест
  на то, что при сбое она остаётся, green — size: M
- [ ] B14 — Запись в content-addressed store не атомарна:
  `raw_store.py:148,152` пишут через `target.write_bytes(...)` без
  временного файла и `os.replace`. Падение оставит обрезанный объект,
  который `has_object` сочтёт существующим. Store — единственный архив
  первоисточников, повреждённый объект ломает lineage и
  `resolve(locator)` — accept: запись идёт во временный файл рядом
  и переносится `os.replace`, тест green — size: M
- [ ] B15 — Сбой в `RawRepo.put` оставляет сирот: объект пишется
  на диск, строка дописывается в манифест, и только потом идёт `INSERT`.
  Исключение на вставке оставляет файл и манифест без строки в базе
  (воспроизведено: диск `True`, манифест 1, БД 0). Повторный `put`
  строку чинит, но дописывает в append-only манифест второй экземпляр
  той же записи (манифест 2), что исказит восстановление индекса —
  accept: либо вставка в БД идёт до манифеста, либо сбой откатывает
  обе записи; тест на обе ветки green — size: M
- [ ] B16 — Записанный `checksum` миграции никогда не сверяется:
  `apply_migrations` пишет checksum в `schema_version`, но при старте
  не сравнивает его с текущим SQL. Правку уже применённой миграции —
  ту, что породила дефект Д1, — движок не заметил бы даже теоретически
  — accept: расхождение checksum применённой версии даёт внятную
  ошибку при старте, тест green — size: M

## Done

- B-ранее — Фабрика соединения с обязательными PRAGMA. Закрыто
  в `9155908`: `db.open_connection(paths)` выставляет WAL и
  `foreign_keys=ON`. Найдено сторонней рецензией как латентный дефект,
  исправлено до того, как появился вызывающий код.
