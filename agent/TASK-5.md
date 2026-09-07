# ТЗ. Ветка `agent/night-2`

**Репозиторий сейчас не собирается.** Первая задача — починить это.
Всё остальное после.

Задач десять: T0-T9. Идут по порядку. Следующая не начинается, пока предыдущая
не закоммичена и не проверена.

---

## ПРАВИЛА. Читай до задач, они короткие

### Ворота перед каждым коммитом

Три команды. Все три обязаны быть чистыми. Без них не коммить.

```bash
python3 -c "import rusterm.store.db"      # 1. модуль импортируется
python3 -m pytest -q | tail -2            # 2. код возврата 0
git status --porcelain | grep '^??'       # 3. пусто
```

Команда 2 вернула код 2 — это не «тесты упали», это **сборка сломана**,
тесты даже не собрались. Немедленно откатись:

```bash
git checkout -- <файл>
```

### Пять запретов

1. **Комментарий вместо кода — не реализация.** Удалить строку и написать
   на её месте `# здесь будет то-то` — значит сломать программу. Именно
   так репозиторий сломали в прошлый заход.
2. **Не удаляй `assert`.** Проверка: `git diff --cached | grep '^-.*assert'`
   должно быть пусто.
3. **Не правь существующие миграции.** Меняешь схему — добавляй новую
   с новым номером.
4. **Никаких `.bak`, `.SAVE`, `.orig`, `.xxx` и прочих копий.** Для этого
   есть git. В прошлый заход их накопилось семь штук.
5. **Не пиши «сделано» без вывода команды.**

### Цикл

Одна задача → правка → три команды ворот → коммит → строка в отчёте.
Коммить сразу, не в конце. Две ночные работы уже едва не пропали
из-за того, что лежали незакоммиченными.

Застрял на одном месте после трёх **разных** попыток — пометь тест
`@pytest.mark.xfail(strict=True, reason="…")`, запиши в отчёт и иди
дальше. Это нормальный итог.

---

## T0. Почини сборку

В `rusterm/store/db.py`, в функции `apply_migrations`, строка
`conn.execute(create_sql)` была удалена и заменена комментарием.
Получился `try:` с пустым телом — синтаксическая ошибка, не
импортируется ничего.

Сейчас там:

```python
        try:
            # Многооператорная поддержка: если SQL содержит ; — используется executescript, иначе execute
        except sqlite3.OperationalError as e:
```

Должно стать:

```python
        try:
            if create_sql.strip().rstrip(";").count(";") > 0:
                conn.executescript(create_sql)
            else:
                conn.execute(create_sql)
        except sqlite3.OperationalError as e:
```

Это же закрывает шаг «научить движок многооператорным миграциям»:
`conn.execute` умеет ровно один SQL-оператор, а пересборка таблицы
в T1 — четыре.

**Готово:** `python3 -m pytest -q` даёт `84 passed, 5 xfailed`.

---

## T1. Миграция 33

Схему нельзя менять правкой уже применённой миграции: на существующей
базе `apply_migrations` пропустит её версию, и изменение не доедет.
Проверено — было именно так.

`raw_store.py` умеет писать `compression="gzip"`, а ограничение в базе
разрешает только `('none','zstd')`. Нужна новая миграция.

**Шаг 1.** В конец списка `_MIGRATIONS` добавь запись:

```python
    ("""PRAGMA foreign_keys=OFF;
CREATE TABLE raw_object_new (
    sha256 TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    url TEXT,
    fetched_at REAL NOT NULL,
    bytes INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    compression TEXT NOT NULL CHECK (compression IN ('none','zstd','gzip')),
    instrument_id TEXT,
    block TEXT,
    http_status INTEGER,
    etag TEXT);
INSERT INTO raw_object_new SELECT * FROM raw_object;
DROP TABLE raw_object;
ALTER TABLE raw_object_new RENAME TO raw_object;
PRAGMA foreign_keys=ON;""", "raw_object"),
```

`PRAGMA foreign_keys=OFF` обязателен: на `raw_object(sha256)` ссылается
`fact.source_ref`, иначе `DROP TABLE` уронит связь.

**Шаг 2.** Подними `_SCHEMA_VERSION` с 32 до 33 и поправь комментарий
рядом: там написано «количество таблиц», должно быть «количество
миграций».

**Готово:** эта команда печатает `applied= [33]`, `version= 33`,
`строк уцелело: 1` и `запись gzip: ok`.

```bash
python3 - <<'EOF'
import sqlite3, sys, tempfile, pathlib
sys.path.insert(0, ".")
from rusterm.store import db as m
p = pathlib.Path(tempfile.mkdtemp()) / "old.db"
c = sqlite3.connect(str(p), isolation_level=None)
saved, sv = m._MIGRATIONS, m._SCHEMA_VERSION
m._MIGRATIONS, m._SCHEMA_VERSION = saved[:32], 32     # база по схеме 32
m.apply_migrations(c)
m._MIGRATIONS, m._SCHEMA_VERSION = saved, sv
c.execute("INSERT INTO raw_object(sha256,provider,fetched_at,bytes,content_type,compression)"
          " VALUES ('a'*64,'t',0,1,'text/plain','none')")
print("applied=", m.apply_migrations(c))
print("version=", c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0])
print("строк уцелело:", c.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0])
try:
    c.execute("INSERT INTO raw_object(sha256,provider,fetched_at,bytes,content_type,compression)"
              " VALUES ('b'*64,'t',0,1,'text/plain','gzip')")
    print("запись gzip: ok")
except Exception as e:
    print("запись gzip:", type(e).__name__, e)
EOF
```

`строк уцелело: 0` означает, что миграция потеряла данные. Это хуже,
чем несделанная миграция.

---

## T2. Пять инвариантов — пустышки, почини их

У пяти из пятнадцати инвариантов тело состоит из одной строки:

```python
def test_i04_measure_without_lineage_rejected():
    """Обе ветки: value задан и value IS NULL."""
    pytest.fail("I4 не реализован на этом этапе — причина в декораторе")
```

Это I4, I5, I6, I13, I15. Проверок в них нет ни одной. Следствия два,
и второе хуже первого:

1. Треть надзорного набора ничего не сторожит.
2. `xfail(strict=True)` **не снимет их сам**, когда код появится:
   `pytest.fail` падает всегда, поэтому тест навсегда останется
   «ожидаемо падающим», и никто не заметит, что правило давно
   реализовано. Прежние задания утверждали обратное — это ошибка
   автора заданий, не твоя.

Показательный случай — I15: он требует, чтобы знаменатель `<= 0` давал
`null`, и `formulas.py` это уже умеет,
`roic(10, -1, -1)` возвращает `(None, 'negative_denominator')`.
Тест об этом молчит.

**Что сделать.** В каждом из пяти напиши настоящую проверку того, что
описано в его docstring. Если нужного кода ещё нет — тест обязан падать
**из-за отсутствия кода**, а не из-за `pytest.fail`; `xfail(strict=True)`
на них оставь.

Для I15 код уже есть: перепиши на реальную проверку `roic`, `roe`,
`asset_turnover` и маржей на нулевом и отрицательном знаменателе,
и **сними** с него `xfail`. Маржи при этом упадут — это дефект Д8,
он чинится в T9; до тех пор вынеси проверку маржей в отдельный тест
с `xfail(strict=True, reason="Д8, чинится в T9")`.

**Готово:** `bash agent/acceptance.sh`, проверка 2 зелёная — она теперь
отличает настоящий тест от `pytest.fail`.

---

## T3. Верни три утерянных утверждения

В `tests/test_raw_store.py` их удалили при правке, поданной как усиление.

1. В `test_put_object_at_threshold_compresses` переменные `exists_zst`
   и `exists_gz` вычисляются и никуда не идут. Добавь после них:
   `assert exists_zst or exists_gz`.
2. Там же добавь `assert not plain.exists()` — несжатой копии рядом
   со сжатой быть не должно.
3. В `test_put_object_above_threshold_compresses` добавь
   `assert obj.compression in ("zstd", "gzip")`.

**Готово:** `python3 -m pytest tests/test_raw_store.py -q` зелёный.

---

## T4. Инвариант I16

Ни один из пятнадцати инвариантов не проверяет, что новая миграция
доезжает до **уже существующей** базы. Эта дыра и пропустила дефект,
который чинится в T1.

Добавь в `tests/test_invariants.py` функцию с именем ровно
`test_i16_schema_change_reaches_existing_db`:

1. создать базу по схеме 32 и положить в неё строку;
2. применить актуальные миграции;
3. проверить: `schema_version` вырос, строка на месте, запись
   с `compression='gzip'` проходит.

Пятнадцать существующих не трогай, `xfail` с них не снимай.

**Готово:** `python3 -m pytest tests/test_invariants.py -q` даёт
`11 passed, 5 xfailed`.

---

## T5. `Fact` объявлен неизменяемым, но изменяем

`rusterm/core/fact.py`: шесть классов локаторов объявлены
`@dataclass(frozen=True)`, а сам `Fact` на строке 120 — просто
`@dataclass`, при том что комментарий над ним говорит «неизменяемая
после создания». Проверено:

```
f.value = "2"   → проходит без ошибки
```

Инвариант I2 этого не ловит: он проверяет **текст** исходника
`repos.py` через `inspect.getsource` на отсутствие `UPDATE fact SET
value`, а не поведение объекта.

**Что сделать.** Поставить `frozen=True` на `Fact`. Поле
`superseded_by` по спецификации меняется — переведи его изменение
на создание нового объекта через `dataclasses.replace`, как и требует
модель факта. Затем допиши в I2 проверку поведения: попытка
`f.value = …` обязана поднимать `FrozenInstanceError`. Текстовую
проверку `repos.py` не удаляй, она ловит другое.

**Готово:** `python3 -m pytest tests/test_invariants.py -q` зелёный,
попытка мутации падает.

---

## T6. Перепиши ADR-0007

`docs/adr/0007-zstd-gzip-fallback.md`:

1. В разделе «Контекст» удали абзац, начинающийся со слов
   «Согласно `TASK-3.md` §3» — цитата выдумана, такого текста там нет.
2. Раздел «Решение», пункт 1, описывает правку CHECK на месте. Замени
   его описанием миграции 33 из T1: почему нельзя править применённую
   миграцию, как таблица пересобирается, почему нужен
   `PRAGMA foreign_keys=OFF`.

Статус оставь «принято агентом, требует подтверждения».

**Готово:** `grep -c "TASK-3" docs/adr/0007-*.md` даёт `0`.

---

## T7. Убери мусор

```bash
rm -f rusterm/store/db.py.bak rusterm/store/db.py.SAVE \
      rusterm/store/db.py.SAVE2 rusterm/store/db.py.backup2 \
      rusterm/store/db.py.bak3 rusterm/store/db.py.xxx \
      tests/test_repos.py.bak tests/test_repos.py.orig \
      docs/adr/0007-zstd-gzip-fallback.md.bak
printf '*.bak\n*.orig\n*.SAVE*\n*.backup*\n' >> .gitignore
```

**Готово:** `git status --porcelain` пуст.

---

## T8. Этап B

Берётся только после T0-T7. Три инкремента, каждый со своими тестами
до кода, каждый отдельным коммитом.

- **И6. Провайдеры.** Протоколы `MarketDataProvider` и
  `DisclosuresProvider` по `docs/module-contracts.md` §2-3. Пиши через
  `typing.Protocol`, **не** классом с `raise NotImplementedError`
  в теле — десять таких заглушек держат проверку 5 приёмки красной.
  Фейковый провайдер на фикстурах в `fixtures/`; каталога нет, создай.
  Каждый файл фикстуры обязан иметь `synthetic` в имени и внутри.
  Рынок РФ из проекта убран — `MOEX` в допустимых значениях быть
  не должно, список в `docs/data-model.md` §1.
- **И7. Парсер.** Синтетический XBRL-подобный JSON в факты с локаторами
  `kind=xbrl` и `kind=table`, по `docs/module-contracts.md` §4.
  В `rusterm/parsers/` не должно быть импортов HTTP-библиотек.
- **И8. Конвейер.** Девять узлов процесса 1 из `docs/processes.md`
  §46-123, очередь заданий с ключом идемпотентности, ветки ошибок
  E1-E5. Двойной прогон не создаёт ни нового объекта в store,
  ни новых фактов.

**Готово:** `bash agent/acceptance.sh` даёт 13 из 13.

---

## T9. Только после T8: И9, формульный движок

`rusterm/formulas.py` написан первым исполнителем, тестов на него нет
ни одного, и в нём уже найдено четыре дефекта. Точечно их не чинь —
модуль переписывается целиком в инкременте И9 по
`docs/data-dictionary.md` §2-3: концепты, формулы `method_version` v1,
TTM, правила `null`.

Эталон golden-file выписывается **до** кода. Иначе он зафиксирует
не правильный ответ, а получившийся.

Четыре случая ниже — приёмочные критерии И9. Сейчас каждый ведёт себя
неверно; после переписывания каждый обязан вести себя как в колонке
«должно быть».

| Вход | Сейчас | Должно быть |
|---|---|---|
| `effective_tax_rate(tax=-100, pretax=-1000)` | `(0.1, None)` | `null`, причина по правилу «pretax_income <= 0» |
| `effective_tax_rate(tax=100, pretax=-1000)` | `(0.0, None)` | то же |
| `calculate_measure("invested_capital", te=100, mi=0, td=50)` | `TypeError` | `null` с причиной `missing_data` |
| `calculate_measure("ebitda", operating_income=100, d_and_a=None)` | `value=100` | `null` с причиной `missing_data` |
| `gross_margin(gross_profit=10, revenue=-100)` | `(-0.1, None)` | `null` с причиной `negative_denominator` |

Последняя строка: `roic` в том же модуле уже возвращает
`negative_denominator` при отрицательном знаменателе. Маржи обязаны
вести себя так же — сейчас они проверяют только `== 0`.

И ещё: `calculate_measure("ebitda", …)` сейчас возвращает `Measure`
с непустым `value` и пустым `lineage`. Это запрещено инвариантом I4,
который помечен `xfail` и потому молчит. После И9 сними с него метку.

**Готово:** golden-file зелёный, все пять строк таблицы дают колонку
«должно быть», I4 больше не `xfail`.

---

## Чего не делаем

Qt, LLM-слой, Industry View, провайдеры UK и CA, реальные сетевые
источники. Всё офлайн, на синтетике. Расширять область запрещено.

## Стек

Python 3.12+, обязана работать 3.14. Стандартная библиотека, `pytest`,
`sqlite3` из stdlib. `zstandard` необязателен, `gzip` — фолбэк.
`httpx`/`requests` только внутри `rusterm/providers/`. Запрещены ORM,
`alembic`, `pandas`, `numpy`, асинхронные фреймворки.

`list`, `dict`, `tuple` — встроенные типы, в `typing` их нет. Пиши
`list[str]` и `from __future__ import annotations` в шапке модуля.

## Приёмка и отчёт

`bash agent/acceptance.sh` — тринадцать проверок, запускай после каждого
коммита. **Править скрипт запрещено**, он сверяется с `origin/main`.
Считаешь проверку неверной — пиши в раздел «Спорное» отчёта.

Отчёт — `agent/REPORT-3.md`. На каждую задачу одна строка: команда
и её фактический вывод. Последняя строка файла всегда
`СЕЙЧАС: <задача>`.
