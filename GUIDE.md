# GUIDE — руководство пользователя RusTerm

README — спецификация проекта; этот файл — инструкции: что набирать и
что вы увидите. **Все выводы ниже — реальные прогоны** на каталоге
`/tmp/rusterm-guide` без сети и ключей (пустой env-файл), сделанные
18.09.2026 на текущей ветке; вставки проверяет тест
`tests/test_guide_truth.py` при каждой приёмке.

RusTerm — локальный терминал по ценным бумагам: собирает раскрытия,
считает меры по явному словарю, показывает снапшоты. Без облака, без
аккаунта; база — SQLite в вашем каталоге данных.

## 0. Подготовка

Ключи и контакт — только через переменные окружения. Их читают из
`~/.rusterm.env` (файл создаёте вы) или берут из окружения:

```
RUSTERM_SEC_UA=Имя Фамилия email@example.com      # контакт для SEC (обязателен для сети)
RUSTERM_LLM_API_KEY=...                            # для импорта/чата (ТЗ-20/ТЗ-26)
RUSTERM_DART_KEY=...                               # раскрытия Кореи (ТЗ-19 F8)
RUSTERM_TWELVEDATA_KEY=...                         # котировки (ADR-0014)
```

Всё, чем пользуется программа, бесплатное (ADR-0018): ни подписки, ни
платного тарифа, ни карты при регистрации. Карта — это оплата, даже
если с неё ничего не списывается: канал, требующий карту, программа
не предлагает.

| Переменная | Где выдаётся | Что открывает | Стоимость | Потолок бесплатного тарифа |
|---|---|---|---|---|
| `RUSTERM_SEC_UA` | регистрация не нужна — ваш контакт (имя, email) | сеть SEC EDGAR: раскрытия, факты, архивы | бесплатно | SEC просит не больше 10 запросов/с; программа держит 5/с |
| `RUSTERM_DART_KEY` | opendart.fss.or.kr — регистрация, без карты | раскрытия Кореи (DART) | бесплатно | вендор число не публикует; в программе проектный потолок |
| `RUSTERM_LLM_API_KEY` | openrouter.ai — регистрация, без карты | чат и вопросы по снапшоту (бесплатные модели) | бесплатно | зависит от модели; в программе проектный потолок |
| `RUSTERM_TWELVEDATA_KEY` | twelvedata.com — регистрация, без карты | котировки и корпоративные действия | бесплатно | 8 запросов/мин и 800/день (число вендора) |

Без контакта SEC сетевые команды работают только в офлайн-режиме —
см. §6.

## 1. Первый запуск: init и демо

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide init
каталог: /tmp/rusterm-guide
применено миграций: 44; schema_version=45

$ python3 -m rusterm.cli --root /tmp/rusterm-guide demo
создан демо-инструмент US-CLI-DEMO (эмитент issuer-cli-demo); данные синтетические, выдуманные — не данные эмитента
далее: rusterm ingest --instrument US-CLI-DEMO && rusterm snapshot --instrument US-CLI-DEMO
```

Без `--root` каталог данных выбирается по одним правилам для CLI,
окна и собранного `.app` (их держит `store/paths.resolve_root`):
`RUSTERM_DATA` (окружение или `~/.rusterm.env`) → каталог, где уже
лежит `rusterm.db` → `~/.rusterm`. Явный `--root` переопределяет все
три. Демо — единственное место, где программа создаёт синтетические
данные, и она об этом честно говорит.

## 1.1. Первые пятнадцать минут: одна команда и окно (ТЗ-96 R5)

`follow` проводит бумагу путь от пустого каталога до снапшота одним
вызовом: поиск в SEC, отчётность, цены, снапшот. Без ключей путь
остановится на второй стадии и скажет об этом словами — это же увидит и
первый запуск на вашей машине (страж `tests/test_guide_truth.py`
исполняет этот блок без сети и без ключей):

```console
$ RUSTERM_ENV_FILE=/nonexistent/env python3 -m rusterm.cli --root /tmp/rusterm-guide follow AAPL
каталог: /tmp/rusterm-guide
применено миграций: 0; schema_version=45
US-AAPL: 1/5 каталог — готово (запросов 0)
US-AAPL: 2/5 поиск в SEC — отказ (запросов 0)
нет контакта SEC (network_provider_requires_gate:edgar); офлайн-режим требует --cik и --name; задайте их или заполните ~/.rusterm.env
US-AAPL: стадия не прошла (код 1); починив, повторяют только её
без контакта SEC нужны оба значения вручную: --cik и --name (см. rusterm markets)
совет: rusterm add --ticker AAPL --market US
```

Миграций ноль, потому что каталог из §1 уже открыт: путь начинается с
того же места, а не с нуля. Строка `совет:` — та команда, которой чинят
стадию; её разбирает тот же парсер, что и всё остальное. Записей при
этом не появляется ни одних: стадия остановилась до скачивания.

Чтобы путь прошёл целиком, в `~/.rusterm.env` нужны две строки:
`RUSTERM_SEC_UA` (ваш контакт для SEC) и `RUSTERM_TWELVEDATA_KEY`
(котировки, §0). Реальный прогон 24.09.2026 на AAPL — он шёл по сети,
страж его не исполняет, числа живые:

```
создан инструмент US-AAPL (эмитент Apple Inc., CIK 320193, тикер AAPL на US, площадка Nasdaq)
US-AAPL: 2/5 поиск в SEC — готово (запросов 2)
US-AAPL: companyfacts загружены; фактов: 12452; неотображённых концептов: 10328
US-AAPL: 3/5 отчётность — готово (запросов 1)
US-AAPL: строк получено: 5000; записано новых: 5000; запросов: 1; последняя дата: 2026-09-23
US-AAPL: корп.действия: сплитов 5; дивидендов 83; записано новых: 88; запросов: 2; неразобрано: 0
US-AAPL: 4/5 цены — готово (запросов 3)
US-AAPL: мер: 28 — со значением 21, пусто 7; перцентилей: 0
US-AAPL: 5/5 снапшот — готово (запросов 0)
US-AAPL: путь пройден; всего запросов: 6
US-AAPL: отрасль и governance в этот путь не входят — их собирает не эта команда (см. rusterm industry, rusterm coverage)
```

Шесть запросов — это первая бумага. Повтор той же бумаги стоит один
запрос: скачанное не качается снова, а снапшот второй раз говорит прямо,
что значения идентичны предыдущей версии (это число измерено на том же
пути без сети, на записанных ответах). Бесплатный потолок Twelve Data — 8
запросов в минуту и 800 в день (§0), то есть путь целиком за один вечер —
это порядка ста бумаг; `rusterm budget` показывает, сколько уже
изведено.

Дальше — окно. Чтобы CLI, окно и собранное `.app` открыли одну и ту же
базу, добавьте в `~/.rusterm.env` третью строку (ТЗ-90 A5):

```
RUSTERM_DATA=/Users/you/equitylab
```

Без неё каталог ищется по тем же правилам для всех троих:
`RUSTERM_DATA` → каталог, где уже лежит `rusterm.db` → `~/.rusterm`
(§1). Двойной щелчок по `dist/EquityLab.app` открывает это же окно без
терминала (§10.1), а `python3 -m rusterm.cli desktop` — с терминалом
(§10).

Что окно показывает после `follow`, закреплено тестом
`tests/test_desktop_task96_r4_firsthour.py`: таблица мер, где число стоит
там, где мера посчитана, и слово «нет данных» — там, где её нет; клик по
ячейке открывает источник меры вплоть до пути к скачанному файлу;
«Настройки» называют ключи (именем и происхождением, без значений),
потолки запросов по хостам и открытый каталог. «Отрасль» и «Качество»
не молчат: первая говорит, что у компании нет peer set, вторая
показывает покрытие мер и строки governance с причиной отказа —
наполняет их ТЗ-73.

Если окно открыло базу старше программы, оно не мигрирует молча и не
падает — под шапкой появляется одна строка с версиями и командой
(ТЗ-95 F1; путь в ней — тот же каталог, который окно и показало):

```
база в /Users/you/equitylab — схема 44, программе нужна 45; обновите: rusterm --root /Users/you/equitylab init
```

После `init` то же окно покажет актуальную схему; ни одна из этих команд
данных не удаляет.

## 2. Списки наблюдения

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide watchlist create demo-list --name "Демо-список"
список demo-list создан (версия 1)

$ python3 -m rusterm.cli --root /tmp/rusterm-guide watchlist add demo-list --instrument US-CLI-DEMO
US-CLI-DEMO добавлен, версия 2
```

Прочее: `watchlist list`, `watchlist show demo-list [--version N]`,
`watchlist remove demo-list --instrument ID`, `watchlist rollback
demo-list --to 1`, `watchlist export/import`.

## 3. Сбор и снапшот

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide ingest --instrument US-CLI-DEMO
US-CLI-DEMO: заданий закрыто: 2; фактов: 6; дублей sha256: 0; неразобрано (E4): 0; suspect (E5): 0; неотображённых концептов: 1 (теги вне карты концептов мерами не стали — это норма; карта узнала 6 из 7)

$ python3 -m rusterm.cli --root /tmp/rusterm-guide snapshot --instrument US-CLI-DEMO
US-CLI-DEMO: снапшот v1: 5c202d7f-12c0-42f4-92b9-8ebb516a783a
US-CLI-DEMO: мер: 28 — со значением 4, пусто 24; перцентилей: 0
```

Пустая мера — не ошибка: у неё есть причина, и она видна.

## 4. Экспорт

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide export --instrument US-CLI-DEMO --format md
concept_map_version: us-gaap.v4

| concept | value | unit | period_start | period_end |
|---|---|---|---|---|
| asset_turnover | — [1] |  |  |  |
| ... |  |  |  |  |
| effective_tax | 0.16666666666666666 | ratio | 2023-01-01 | 2023-12-31 |
| ... |  |  |  |  |
| net_margin | 0.1 | ratio | 2023-01-01 | 2023-12-31 |
| nopat | 166.66666666666669 | USD | 2023-01-01 | 2023-12-31 |
| operating_margin | 0.2 | ratio | 2023-01-01 | 2023-12-31 |
| ... (всего 27 мер; ниже — причины пустых) ...
Причины пустых значений:
- [1] asset_turnover: missing_data: total_assets
- ... 
- [9] gross_margin: missing_data: gross_profit
- ...
- [21] roe: missing_data: total_equity
- ...
```

Форматы: `--format json|csv|md`; `--out FILE` пишет в файл.

## 5. Состояние: status, coverage, metrics, budget, markets, doctor

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide status --json
{"data_dir": "/private/tmp/rusterm-guide", "schema_version": 45, "schema_version_expected": 45, "schema_version_observed": 45, "instruments": 1, "watchlists": 1, "snapshots": [{"instrument_id": "US-CLI-DEMO", "snapshot_id": "523637c9-89de-4039-a92d-af7c8c80a773", "version": 1, "as_of": "2026-09-18"}], "coverage": {"ready": 2, "stale": 1, "processing": 0, "missing": 5, "error": 0}, "concept_map_version": "us-gaap.v4", "concept_map_version_ifrs": "ifrs-full.v2", "market_codes": ["US", "CA", "OTC", "KR", "BR", "AU"], "peer_sets": [], "budget": {"ceiling_per_night": 5000, "rate_per_second": 5, "provider_ran": false, "used": 0, "samples": {}}, "env": {"file": "/tmp/empty-guide-env", "exists": true, "world_readable": false, "vars": {"RUSTERM_SEC_UA": "—", "RUSTERM_LLM_PROVIDER": "—", "RUSTERM_LLM_API_KEY": "—", "RUSTERM_LLM_MODEL": "—", "RUSTERM_TWELVEDATA_KEY": "—", "RUSTERM_DATA": "—", "RUSTERM_DART_KEY": "—", "RUSTERM_LLM_BASE_URL": "—"}}, "chat": {"calls_total": 0, "calls_today": 0, "per_model": {}}}

$ python3 -m rusterm.cli --root /tmp/rusterm-guide coverage --instrument US-CLI-DEMO
US-CLI-DEMO	corporate_actions	missing причина: no_data:corporate_actions
US-CLI-DEMO	fundamentals	ready
US-CLI-DEMO	governance	missing причина: no_data:governance
US-CLI-DEMO	industry_metrics	missing причина: industry_no_sector
US-CLI-DEMO	llm_summary	stale причина: cascade:after_fundamentals
US-CLI-DEMO	ownership	ready
US-CLI-DEMO	peer_set	missing причина: peer_set_not_confirmed
US-CLI-DEMO	prices	missing причина: no_data:prices

$ python3 -m rusterm.cli --root /tmp/rusterm-guide metrics
provider_success_rate	нет данных
provider_rate_limited	нет данных
data_lag	36.52869701385498
suspect_share	0.0
unparsed_share	0.0
verification_queue	нет данных
peer_set_coverage	0.0
peer_set_churn	нет данных
locator_resolve_failures	0.0

$ python3 -m rusterm.cli --root /tmp/rusterm-guide budget
потолок запросов за ночь: 5000 (Budget), 5 в секунду (RateLimiter); лимитеры не хранят состояние между процессами
сетевой провайдер не работал: использовано 0, отказано 0 (записей в metric_sample нет)

$ python3 -m rusterm.cli --root /tmp/rusterm-guide markets
US	US	exchange	edgar	cik	us-gaap	auto	implemented	edgar	меры	1
CA	CA	exchange	edgar	cik	ifrs-full	auto	implemented	edgar	—	1
OTC	US	otc	edgar	cik	us-gaap	partial	implemented	edgar	—	1
KR	KR	exchange	dart	corp_code	ifrs-full	auto	implemented	-	нет ключа	1
BR	BR	exchange	cvm	cvm_code	ifrs-full	auto	implemented	cvm	—	1
AU	AU	exchange	asx	asx_code	ifrs-full	partial	implemented	asx	—	1
```

`markets` — реестр рынков: провайдер, схема идентификатора, уровень
доступа (`auto` — качается само, `partial` — программа различает
эмитентов до создания, `manual` — только ручной импорт), степень
канала — «сырьё» / «факты» / «меры» — вычислена из того, что канал
реально произвёл в вашем каталоге (у демо US есть снапшот с мерами,
остальные каналы ничего не дали); канал без ключа показывает «нет
ключа» вместо обещания. doctor
печатает JSON-отчёт самопроверки базы и store (`python3 -m rusterm.cli
--root ... doctor`).

`budget` называет два счёта: «использовано запросов за жизнь
каталога» (сумма всех проб гейта) и «последняя проба гейта» — не
путайте их: после живого сбора первое растёт, второе показывает
стоимость последнего прохода. Сноски пустых мер в `export --format
md` советуют действие, где оно очевидно (нет цен — команда сбора
котировок), и несут происхождение: раздел «Источники» называет
документ, хэш и период каждой меры.

## 6. Настоящая компания: add

Онлайн (задан контакт SEC) `add` сам находит CIK и название по тикеру.
Офлайн команда требует `--cik` и `--name` и не делает вид, что
работает без них:

```console
$ RUSTERM_ENV_FILE=/nonexistent/env python3 -m rusterm.cli --root /tmp/rusterm-guide add --ticker MSFT --market US
нет контакта SEC (network_provider_requires_gate:edgar); офлайн-режим требует --cik и --name; задайте их или заполните ~/.rusterm.env
```

Если эмитент известен рынку, но его раскрытия нельзя скачать
автоматически, `add` откажет и назовёт команду ручного импорта
(`manual_import_required`) — пустого эмитента программа не создаст.
Если рынок не знает тикер — `unknown_issuer`, код 1.

## 7. Инкрементальный проход и массовые операции

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide refresh --watchlist demo-list --dry-run
US-CLI-DEMO: ошибка (unknown_issuer: registry_id is empty)
```

Ожидаемо: у демо-эмитента нет CIK, реальный проход ему не нужен. На
настоящих эмитентах `refresh` ставится в cron; `--dry-run` печатает
план, не делая ни одного запроса.

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide ops --watchlist demo-list --request "добавь AAPL" --json
{"watchlist_id": "demo-list", "intent": "add_instruments", "outcome": "dry-run", "reason": null, "rows": [{"ticker": "AAPL", "status": "не разрешилась", "instrument_id": null, "reason": null}], "version": null}
```

`ops` без `--confirm` — только показ; применение — с `--confirm`.
Каждый исход (включая отказ) оставляет строку аудита. Без ключа
модели намерение распознаёт правило (выше); с заданным ключом модель
может ответить уточнением — исход и причина будут в `outcome`/`reason`.

## 8. Ручной импорт (каркас; конвейер — ТЗ-20)

Импорт не создаёт эмитентов: сначала инструмент, потом файл. Dry-run
извлекает текст и ничего не записывает:

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide add --ticker FAKE --market US --cik 1 --name "Fake Co"
создан инструмент US-FAKE (эмитент Fake Co, CIK 1, тикер FAKE на US, площадка unknown)

$ printf 'fleet of 42 ships\n' > /tmp/guide-report.txt

$ python3 -m rusterm.cli --root /tmp/rusterm-guide import /tmp/guide-report.txt --issuer FAKE --market US --dry-run
/tmp/guide-report.txt: извлечено, sha 0b4ddb6bac03… (dry-run: ничего не записано)
```

Без инструмента импорт отказывает по имени (`инструмент 'US-FAKE' не
найден; импорт не создаёт эмитентов — сначала rusterm add`); полный
конвейер «файл → страницы → модель по API → детерминированный
контроль» поставляют полосы ТЗ-20 L5/L6.

## 9. Терминальный интерфейс

```console
# требует терминала
$ python3 -m rusterm.cli --root /tmp/rusterm-guide tui
```

Только чтение, curses; выход — `q`. (Скриншот не вставляю — интерактив.)

## 10. Десктопное окно

То же окно, что `python3 -m rusterm.desktop`, открывает и обычная
команда (ТЗ-60 E3); без установленного PySide6 она не падает
трассировкой, а говорит словами, что поставить:

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide desktop --help
usage: rusterm desktop [-h] [--root ROOT] [--watchlist WATCHLIST]

options:
  -h, --help            show this help message and exit
  --root ROOT           каталог данных (по умолчанию — те же правила, что у
                        CLI: $RUSTERM_DATA, ./rusterm.db, ~/.rusterm)
  --watchlist WATCHLIST
```

Окно открывается только на чтение: каталог не создаётся, миграций
нет (B35/B40). В окне: поиск по эмитентам и спискам наблюдения,
таблица мер с пометкой «· нет данных» и причиной отказа словами,
диаграммы по годам, вкладка разговора с цитатами, настройки (ключи —
откуда, без значений; лимиты хостов; каталог данных со сменой через
вопрос). Пробный прогон без экрана — окно стартовало и само
закрылось:

```console
# требует экрана
$ QT_QPA_PLATFORM=offscreen RUSTERM_APP_SMOKE=1 python3 -m rusterm.cli --root /tmp/rusterm-guide desktop
```

### 10.1 Приложение без терминала (ТЗ-81 B3)

Собранный `.app` открывается двойным щелчком, и окна терминала рядом нет:
в спеке стоит `console=False` — это эквивалент ключа `--windowed`.
Spec лежит в репозитории (`EquityLab.spec`), поэтому сборка воспроизводима
из клона одной командой:

```console
# требует PyInstaller и ~20 с: пишет 167 МБ в dist/, поэтому страж её не исполняет
$ python3 -m PyInstaller EquityLab.spec --noconfirm
$ open dist/EquityLab.app
```

Здесь `otool`, `xattr` и smoke-прогон ниже тоже помечены: они смотрят в
файлы конкретной сборки, а не в песочницу стража на tmp-каталоге.

Каталог данных приложение находит тем же путём, что и CLI — одной
функцией `store/paths.resolve_root` (с круга 111): `--root`, затем
`RUSTERM_DATA`, затем каталог, где уже лежит `rusterm.db`, затем
`~/.rusterm`. Двойной щелчок — запуск без шелла, поэтому с круга 109
`RUSTERM_DATA` читается и из `~/.rusterm.env`, из того же файла, откуда
берутся ключи:

```console
# требует HOME: правит ~/.rusterm.env пользователя, а не tmp-песочницу
$ grep -q "^RUSTERM_DATA=" ~/.rusterm.env || printf 'RUSTERM_DATA=%s\n' "$HOME/equitylab" >> ~/.rusterm.env
```

Линковка Qt остаётся динамической (LGPL, ADR-0004 §6): библиотеки лежат
отдельными Mach-O файлами с `@rpath`-идентичностями, ничего не встраивается
статически и не сжимается (`upx=False`). Проверяется так — и именно по этим
файлам, потому что главный бинарник окна к Qt не прилинкован вовсе
(`otool -L Contents/MacOS/EquityLab | grep Qt` даёт пустой вывод, это не
признак статической линковки):

```console
# требует собранный dist/EquityLab.app: эти строки — прогон по файлам сборки
$ ls dist/EquityLab.app/Contents/Frameworks | grep -c '^Qt'
18
$ otool -D dist/EquityLab.app/Contents/Frameworks/QtWidgets
dist/EquityLab.app/Contents/Frameworks/QtWidgets:
@rpath/QtWidgets
$ otool -L dist/EquityLab.app/Contents/Frameworks/PySide6/QtCore.abi3.so | grep '@rpath/Qt'
	@rpath/QtCore (compatibility version 6.0.0, current version 6.11.2)
```

Те же три проверки живём не только руками: `otool -D` по каждой из 18
библиотек сверяется тестом `test_qt_is_linked_dynamically_not_embedded`.

Старт и честный отказ собранного окна проверяет smoke-тест: без собранного
`.app` и переменной он пропускается, в обычном прогоне набора не участвует:

```console
# требует собранный dist/EquityLab.app — без него тест пропускается, а не падает
$ QT_QPA_PLATFORM=offscreen RUSTERM_APP_SMOKE=1 python3 -m pytest tests/test_desktop_app.py -q
4 passed in 5.59s
```

В этом прогоне окно до закрытия печатает строку
`rusterm-app root=<каталог> (правило: N)` — по ней видно, какую базу
открыл именно собранный бинарник и каким правилом её нашёл, а не только
то, что он запустился.

Подпись и нотаризация не делаются: и то, и другое платно, а всё в проекте
бесплатно (ADR-0018). Практический смысл: при первом запуске macOS скажет,
что приложение «повреждено или не от установленного разработчика», и
потребует снять карантин — один раз, правой кнопкой «Открыть» или командой:

```console
# требует собранный dist/EquityLab.app: путь существует только после сборки
$ xattr -dr com.apple.quarantine dist/EquityLab.app
```

## 11. Что дальше

M8 в работе: рынки KR/BR/AU и ручной импорт (ТЗ-19 — фундамент, ТЗ-20 —
полосы). Дорожная карта — README §15; архитектура — `docs/adr/`.
