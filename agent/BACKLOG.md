# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file. The executor never edits
this file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

Два пространства имён, чтобы параллельные правки не сталкивались
на общей последовательности номеров: **B** — пункты координатора,
**R** — дефекты, найденные сторонними рецензиями и перепроверенные
запуском. Номера внутри своего пространства не переиспользуются.

## Queue

- [ ] B9 — `doctor` does not check the raw store against the database:
  assert every `raw_object` row has its file on disk and every file under
  `raw/` has a row, and report drift in both directions with counts —
  accept: new test seeding one orphan row and one orphan file, `doctor`
  exits 1 naming both — size: M
- [ ] B10 — `watchlist show` cannot read a historical version from the
  CLI although `WatchlistRepo.members(version=…)` supports it: add
  `--version N` and make it print the version's action and members —
  accept: test asserting v1 members after a rollback created v3 — size: S
- [ ] B11 — CLI output ignores `NO_COLOR` and non-tty: if colour is ever
  added, gate it on both; until then add the test that asserts output is
  plain when stdout is a pipe — accept: subprocess test comparing piped
  output byte-for-byte with the expected plain text — size: S
- [ ] B12 — the audit JSONL has no failure path of its own: if
  `logs/audit.jsonl` cannot be written (read-only dir, full disk), the
  operation currently raises through. Return an error value and still
  attempt the DB write, so one destination's loss does not take the
  other — accept: test with a read-only log dir asserting the DB row
  exists and the failure is reported, not raised — size: M
- [ ] B13 — `export --format md`: a snapshot as a Markdown table for
  reading in a terminal or pasting into notes, null values as `—` with
  the reason in a footnote — accept: test asserting every null carries
  its reason and no number appears without a period — size: M

### Дефекты из рецензий

- [ ] R1 — `effective_tax_rate` считает ставку при убытке: docstring
  требует «pretax_income <= 0 → ставка юрисдикции», код проверяет только
  `== 0`. `(-100, -1000)` даёт `0.1`, а `(100, -1000)` даёт ровно `0.0`,
  потому что `clip` обрезает снизу нулём — нулевая ставка выглядит
  правдоподобно и не вызовет подозрений. Ставка идёт в NOPAT, NOPAT —
  в ROIC — accept: обе пары дают `null` с причиной, тест в
  `tests/test_formulas.py` green — size: S
- [ ] R2 — Маржи принимают отрицательный знаменатель: `gross_margin`,
  `operating_margin`, `net_margin` проверяют `revenue == 0`, тогда как
  data dictionary требует `null` при знаменателе `<= 0`.
  `gross_margin(10, -100)` = `-0.1`, при том что соседний
  `roic(10, -1, -1)` в том же модуле возвращает
  `(None, 'negative_denominator')` — accept: три маржи дают
  `negative_denominator`, тест green — size: S
- [ ] R3 — `calculate_measure("invested_capital")` бросает `TypeError`
  на неполных данных: ветка допускает вызов при заполненных
  `total_equity`, `minority_interest`, `total_debt`, а сама функция
  требует пять обязательных аргументов. Контракт движка
  (`docs/module-contracts.md`) запрещает исключения — только `null`
  с причиной; отсутствие cash в отчётности обычно — accept: вызов без
  `cash`/`st_investments` даёт `null` с `missing_data`, тест green — size: S
- [ ] R4 — EBITDA молча равна operating income при нераскрытой D&A:
  при `operating_income is not None` и `d_and_a is None` значение
  остаётся равным operating income с пустым `null_reason`. EBITDA —
  база для EV/EBITDA и net debt / EBITDA. Вдобавок возвращается
  `Measure` с непустым `value` и пустым `lineage`, что запрещено
  инвариантом I4 — accept: даёт `null` с `missing_data`, I4 это ловит,
  тест green — size: S
- [ ] R5 — `Fact` объявлен неизменяемым, но изменяем: шесть классов
  локаторов — `@dataclass(frozen=True)`, сам `Fact` (`fact.py:141`) —
  обычный `@dataclass`, `f.value = "2"` проходит. Инвариант I2 этого
  не ловит, потому что проверяет текст `repos.py` через
  `inspect.getsource`, а не поведение — accept: `frozen=True`,
  `superseded_by` меняется через `dataclasses.replace`, I2 дополнен
  проверкой `FrozenInstanceError` — size: M
- [ ] R6 — Миграция не снимает резервную копию базы вопреки
  `docs/data-model.md` §8 п.4 и собственному docstring `db.py`:
  в коде нет ни `shutil.copy`, ни временного файла. Пока миграции
  только создавали таблицы, цена была нулевой; теперь есть процедурные
  миграции с переносом данных. Копию снимать через `conn.backup(dst)`,
  а не `shutil.copy`: база в режиме WAL, часть данных в `-wal`-файле —
  accept: копия создаётся до миграций и удаляется после успеха, тест
  на то, что при сбое она остаётся, green — size: M
- [ ] R7 — Запись в content-addressed store не атомарна:
  `raw_store.py:148,152` пишут через `target.write_bytes(...)` без
  временного файла и `os.replace`. Падение оставит обрезанный объект,
  который `has_object` сочтёт существующим. Store — единственный архив
  первоисточников, повреждённый объект ломает lineage и
  `resolve(locator)` — accept: запись идёт во временный файл рядом
  и переносится `os.replace`, тест green — size: M
- [ ] R8 — Сбой в `RawRepo.put` оставляет сирот: объект пишется
  на диск, строка дописывается в манифест, и только потом идёт `INSERT`.
  Исключение на вставке оставляет файл и манифест без строки в базе
  (воспроизведено: диск `True`, манифест 1, БД 0). Повторный `put`
  строку чинит, но дописывает в append-only манифест второй экземпляр
  той же записи (манифест 2), что исказит восстановление индекса —
  accept: либо вставка в БД идёт до манифеста, либо сбой откатывает
  обе записи; тест на обе ветки green — size: M
- [ ] R9 — Записанный `checksum` миграции никогда не сверяется:
  `apply_migrations` пишет checksum в `schema_version`, но при старте
  не сравнивает его с текущим SQL. Правку уже применённой миграции —
  ту, что породила дефект Д1, — движок не заметил бы даже теоретически
  — accept: расхождение checksum применённой версии даёт внятную
  ошибку при старте, тест green — size: M

## Done

- [x] B1 — invariant numbering contiguity guard — TASK-7, verified 08.09
- [x] B2 — fixtures are synthetic, as a test — TASK-7, verified 08.09
- [x] B3 — job-queue idempotency on a second run — TASK-7, verified 08.09
- [x] B4 — second golden issuer with preferred class — TASK-7, verified 08.09
- [x] B5 — `price_adj` split/dividend order independence — TASK-7,
  verified 08.09 (first commit was red, fixed in the next one)
- [x] B6 — `doctor` reports schema drift, test added — TASK-7, verified 08.09
- [x] B7 — coverage blocks doc/code drift guard — TASK-7, verified 08.09
- [x] B8 — zstd branch covered by a fake module — TASK-7, verified 08.09

- [x] R0 — фабрика соединения с обязательными PRAGMA. Закрыто
  в `9155908`: `db.open_connection(paths)` выставляет WAL
  и `foreign_keys=ON`. Найдено сторонней рецензией как латентный
  дефект, исправлено до того, как появился вызывающий код.
