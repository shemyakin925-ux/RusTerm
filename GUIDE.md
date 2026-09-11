# GUIDE — руководство пользователя RusTerm

README — спецификация проекта; этот файл — инструкции: что набирать и
что вы увидите. **Все выводы ниже — реальные прогоны** на каталоге
`/tmp/rusterm-guide`, сделанные 11.09.2026 на текущей ветке.

RusTerm — локальный терминал по ценным бумагам: собирает раскрытия,
считает меры по явному словарю, показывает снапшоты. Без облака, без
аккаунта; база — SQLite в вашем каталоге данных.

## 0. Подготовка

Ключи и контакт — только через переменные окружения. Их читают из
`~/.rusterm.env` (файл создаёте вы) или берут из окружения:

```
RUSTERM_SEC_UA=Имя Фамилия email@example.com      # контакт для SEC (обязателен для сети)
RUSTERM_LLM_API_KEY=...                            # для импорта/чата (ТЗ-20/ТЗ-26)
```

Без контакта SEC сетевые команды работают только в офлайн-режиме —
см. §6.

## 1. Первый запуск: init и демо

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide init
каталог: /tmp/rusterm-guide
применено миграций: 39; schema_version=40

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
US-CLI-DEMO: мер: 27 — со значением 4, пусто 23; перцентилей: 0
```

Пустая мера — не ошибка: у неё есть причина, и она видна.

## 4. Экспорт

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide export --instrument US-CLI-DEMO --format md
concept_map_version: us-gaap.v3

| concept | value | unit | period_start | period_end |
|---|---|---|---|---|
| asset_turnover | — [1] |  |  |  |
| effective_tax | 0.16666666666666666 | ratio | 2023-01-01 | 2023-12-31 |
| net_margin | 0.1 | ratio | 2023-01-01 | 2023-12-31 |
| nopat | 166.66666666666669 | USD | 2023-01-01 | 2023-12-31 |
| operating_margin | 0.2 | ratio | 2023-01-01 | 2023-12-31 |
| ... (всего 23 меры; ниже — причины пустых) ...
Причины пустых значений:
- [1] asset_turnover: missing_data: total_assets
- [9] gross_margin: missing_data: gross_profit
- [21] roe: missing_data: total_equity
```

Форматы: `--format json|csv|md`; `--out FILE` пишет в файл.

## 5. Состояние: status, coverage, metrics, budget, markets, doctor

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide status --json
{
 "data_dir": "/private/tmp/rusterm-guide",
 "schema_version": 40,
 "instruments": 1,
 "watchlists": 1,
 "market_codes": [
  "US", "CA", "OTC", "KR", "BR", "AU"
 ]
}

$ python3 -m rusterm.cli --root /tmp/rusterm-guide coverage --instrument US-CLI-DEMO
US-CLI-DEMO	corporate_actions	missing причина: no_data:corporate_actions
US-CLI-DEMO	fundamentals	ready
US-CLI-DEMO	governance	missing причина: no_data:governance
US-CLI-DEMO	industry_metrics	stale причина: cascade:after_fundamentals
US-CLI-DEMO	llm_summary	stale причина: cascade:after_fundamentals
US-CLI-DEMO	ownership	ready
US-CLI-DEMO	peer_set	missing причина: peer_set_not_confirmed
US-CLI-DEMO	prices	missing причина: no_data:prices

$ python3 -m rusterm.cli --root /tmp/rusterm-guide metrics
provider_success_rate	нет данных
provider_rate_limited	нет данных
data_lag	28.15988826751709
suspect_share	0.0
unparsed_share	0.0
verification_queue	нет данных

$ python3 -m rusterm.cli --root /tmp/rusterm-guide budget
потолок запросов за ночь: 5000 (Budget), 5 в секунду (RateLimiter); лимитеры не хранят состояние между процессами
сетевой провайдер не работал: использовано 0, отказано 0 (записей в metric_sample нет)

$ python3 -m rusterm.cli --root /tmp/rusterm-guide markets
US	US	exchange	edgar	cik	us-gaap	auto
CA	CA	exchange	edgar	cik	ifrs-full	auto
OTC	US	otc	edgar	cik	us-gaap	partial
KR	KR	exchange	dart	corp_code	ifrs-full	auto
BR	BR	exchange	cvm	cvm_code	ifrs-full	auto
AU	AU	exchange	asx	asx_code	ifrs-full	partial
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
US-CLI-DEMO: ошибка (у эмитента нет CIK)
```

Ожидаемо: у демо-эмитента нет CIK, реальный проход ему не нужен. На
настоящих эмитентах `refresh` ставится в cron; `--dry-run` печатает
план, не делая ни одного запроса.

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide ops --watchlist demo-list --request "добавь AAPL" --json
{"watchlist_id": "demo-list", "intent": "add_instruments", "outcome": "dry-run", "rows": [{"ticker": "AAPL", "status": "не разрешилась", "instrument_id": null, "reason": null}], "version": null}
```

`ops` без `--confirm` — только показ; применение — с `--confirm`.
Каждый исход (включая отказ) оставляет строку аудита.

## 8. Ручной импорт (каркас; конвейер — ТЗ-20)

```console
$ printf 'fleet of 42 ships\n' > /tmp/guide-report.txt
$ python3 -m rusterm.cli --root /tmp/rusterm-guide import /tmp/guide-report.txt --issuer FAKE --market US --dry-run
/tmp/guide-report.txt: format_unsupported:manual_extract_not_implemented
```

`--dry-run` уже ничего не пишет (база байт в байт та же); полный
конвейер «файл → страницы → модель по API → детерминированный
контроль» поставляют полосы ТЗ-20 L5/L6.

## 9. Терминальный интерфейс

```console
$ python3 -m rusterm.cli --root /tmp/rusterm-guide tui
```

Только чтение, curses; выход — `q`. (Скриншот не вставляю — интерактив.)

## 10. Что дальше

M8 в работе: рынки KR/BR/AU и ручной импорт (ТЗ-19 — фундамент, ТЗ-20 —
полосы). Дорожная карта — README §15; архитектура — `docs/adr/`.
