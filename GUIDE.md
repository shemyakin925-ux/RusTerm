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

`--root` — каталог данных; по умолчанию текущий каталог. Демо —
единственное место, где программа создаёт синтетические данные, и она
об этом честно говорит.

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
US-CLI-DEMO: заданий закрыто: 2; фактов: 6; дублей sha256: 0; неразобрано (E4): 0; suspect (E5): 0; неотображённых концептов: 1

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
{"data_dir": "/private/tmp/rusterm-guide", "schema_version": 45, "schema_version_expected": 45, "schema_version_observed": 45, "instruments": 1, "watchlists": 1, "snapshots": [{"instrument_id": "US-CLI-DEMO", "snapshot_id": "523637c9-89de-4039-a92d-af7c8c80a773", "version": 1, "as_of": "2026-09-18"}], "coverage": {"ready": 2, "stale": 1, "processing": 0, "missing": 5, "error": 0}, "concept_map_version": "us-gaap.v4", "concept_map_version_ifrs": "ifrs-full.v2", "market_codes": ["US", "CA", "OTC", "KR", "BR", "AU"], "peer_sets": [], "budget": {"ceiling_per_night": 5000, "rate_per_second": 5, "provider_ran": false, "samples": {}}, "env": {"file": "/tmp/empty-guide-env", "exists": true, "world_readable": false, "vars": {"RUSTERM_SEC_UA": "—", "RUSTERM_LLM_PROVIDER": "—", "RUSTERM_LLM_API_KEY": "—", "RUSTERM_LLM_MODEL": "—", "RUSTERM_TWELVEDATA_KEY": "—"}}, "chat": {"calls_total": 0, "calls_today": 0, "per_model": {}}}

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
US	US	exchange	edgar	cik	us-gaap	auto	implemented	edgar	1
CA	CA	exchange	edgar	cik	ifrs-full	auto	implemented	edgar	1
OTC	US	otc	edgar	cik	us-gaap	partial	implemented	edgar	1
KR	KR	exchange	dart	corp_code	ifrs-full	auto	implemented	-	1
BR	BR	exchange	cvm	cvm_code	ifrs-full	auto	implemented	cvm	1
AU	AU	exchange	asx	asx_code	ifrs-full	partial	implemented	asx	1
```

`markets` — реестр рынков: провайдер, схема идентификатора, уровень
доступа (`auto` — качается само, `partial` — программа различает
эмитентов до создания, `manual` — только ручной импорт). doctor
печатает JSON-отчёт самопроверки базы и store (`python3 -m rusterm.cli
--root ... doctor`).

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
  --root ROOT           каталог данных (по умолчанию — как у окна:
                        $RUSTERM_DATA или ~/.rusterm)
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

## 11. Что дальше

M8 в работе: рынки KR/BR/AU и ручной импорт (ТЗ-19 — фундамент, ТЗ-20 —
полосы). Дорожная карта — README §15; архитектура — `docs/adr/`.
