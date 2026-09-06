# Логическая модель данных

Описание таблиц SQLite, ключей и инвариантов. Не DDL: здесь фиксируется
смысл и ограничения, физическая схема пишется на Фазе 1 по этому документу.

Опирается на ADR-0001 (факт, локатор), ADR-0002 (peer set), ADR-0003
(SQLite как система записи), ADR-0005 (идентификация).

---

## 1. Справочники инструментов

**`issuer`** — юридическое лицо, эмитент отчётности.
`issuer_id` (PK), `name`, `jurisdiction`, `registry_id` (CIK / company number),
`fiscal_year_end`, `reporting_standard` (`us_gaap` / `ifrs`), `reporting_currency`.

**`instrument`** — ценная бумага класса.
`instrument_id` (PK), `issuer_id` (FK), `isin`, `class`, `status`
(`active` / `delisted` / `merged`), `superseded_by` (FK, при слиянии).

**`listing`** — торговая площадка инструмента.
`listing_id` (PK), `instrument_id` (FK), `exchange`, `currency`,
`is_primary`, `first_trade_date`, `last_trade_date`.

**`ticker_history`** — история символов.
`listing_id` (FK), `ticker`, `valid_from`, `valid_to`, `reason`, `source_ref`.
Уникальность: `(listing_id, valid_from)`. Разрешение тикера всегда с датой.

**`concept`** — словарь показателей из data dictionary.
`concept` (PK), `period_type`, `unit_kind`, `description`.

**`formula`** — определения расчётов.
`formula_id` (PK), `method_version` (PK), `definition`, `definition_hash`,
`introduced_at`. Новая версия добавляется, старая никогда не правится.

**`fx_rate`** — курсы для витрины.
`from_ccy`, `to_ccy`, `date`, `rate`, `source_ref`. Конверсия без записи
курса запрещена.

---

## 2. Сырьё

**Носитель** — файловая система: `raw/store/<2>/<sha256>`.
**Журнал** — `raw/manifests/*.jsonl`, только добавление.
**Индекс** — таблица `raw_object` в БД: `sha256` (PK), `provider`, `url`,
`fetched_at`, `bytes`, `content_type`, `compression`, `instrument_id`,
`block`, `http_status`, `etag`.

Инвариант: **манифест ведущий, таблица производная.** `raw_object`
полностью восстанавливается из манифестов и файлов; при расхождении
права сторона манифеста. Это защита от повреждения базы: сырьё и журнал
переживают потерю `rusterm.db`.

**`source_cursor`** — состояние инкрементальности.
`provider` (PK), `index_kind` (PK), `last_seen_at`, `cursor`, `updated_at`.
Ключ составной: у одного источника несколько независимых потоков —
ежедневный индекс отчётности, поток сделок инсайдеров, документы
к собранию акционеров. Один курсор на провайдера склеил бы их и терял
изменения.
Узел опроса индекса читает и пишет только сюда.

---

## 3. Факты

**`fact`** — единица истины.
`fact_id` (PK), `issuer_id` либо `listing_id` (ровно одно — факты
отчётности принадлежат эмитенту, котировки площадке), `concept`,
`period_start`, `period_end`, `period_type`, `value`, `unit`, `currency`,
`basis`, `origin` (`extracted` / `manual`), `source_ref` (FK `raw_object`),
`locator` (JSON), `parser_version`, `status` (`ok` / `suspect`),
`superseded_by` (FK `fact`), `ingested_at`.

Инварианты:

1. `locator` и `basis` — NOT NULL. Ограничение схемы, не соглашение.
2. Факт неизменяем. Исправление и ревизия — новый факт, старому
   проставляется `superseded_by`. UPDATE по значению запрещён.
3. `origin = manual` имеет приоритет над `extracted` за тот же период
   и концепт (процесс верификации).
4. `status = suspect` не участвует в расчётах, но виден в coverage.
5. Уникальности по (сущность, концепт, период) **нет намеренно**:
   as_reported и restated сосуществуют, как и версии после исправлений.

Индексы: `(issuer_id, concept, period_end)`, `(listing_id, concept,
period_end)`, `(source_ref)`, `(status)`.

---

## 4. Снапшоты и расчёты

**`snapshot`** — `snapshot_id` (PK), `instrument_id`, `version`, `as_of`,
`built_at`, `peer_set_version`, `peer_set_status`, `status`.

**`snapshot_block`** — `snapshot_id` (FK), `block`, `status`
(`ready` / `partial` / `missing` / `error`), `reason`.

**`measure`** — посчитанное число.
`measure_id` (PK), `snapshot_id` (FK), `concept`, `value`, `unit`,
`period_start`, `period_end`, `formula_id`, `method_version`,
`null_reason`, `peer_set_version` (только для перцентилей).

**`measure_lineage`** — `measure_id` (FK), `fact_id` (FK), `role`.

Инварианты:

1. Каждый `measure` принадлежит версии снапшота. Пересчёт создаёт новую
   версию, не переписывает старую.
2. `value IS NULL` требует `null_reason` — «не рассчитывается» всегда
   с причиной.
3. Перцентиль без `peer_set_version` невалиден и не записывается.
4. `measure` без `measure_lineage` не записывается — **кроме** случая
   `value IS NULL` при отсутствующих входах: тогда lineage пуст,
   а `null_reason` обязателен и объясняет, чего не хватило. Если входы
   были, но результат не определён (отрицательный знаменатель), lineage
   записывается: видно, из чего пытались посчитать.
5. Перцентиль ссылается на `peer_set_version` и на `measure` пиров,
   а не на их первичные факты: `measure_lineage.role = 'peer'`,
   `fact_id` заменяется на `peer_measure_id`. Разворачивать перцентиль
   до фактов пятидесяти компаний бессмысленно — уровень объяснения здесь
   «вот эти компании и их значения».

**`latest_measure`** — проекция для экрана списка.
`instrument_id` (PK), `concept` (PK), `value`, `unit`, `period_end`,
`method_version`, `snapshot_version`. Хранит только показатели, выводимые
в таблице watchlist. Без неё экран на 500 строк собирается соединением
по всем снапшотам на каждую сортировку. Производная, восстанавливается
пересчётом, обновляется вместе со `snapshot`.

**`coverage`** — текущее состояние для экрана списка.
`instrument_id` (PK), `block` (PK), `status`, `last_update`, `reason`.
Производная от последних снапшотов, денормализована ради скорости при
500 бумагах. Восстанавливается пересчётом.

---

## 5. Peer set

**`peer_set`** — `peer_set_id` (PK), `scope_kind` (`company` / `industry`),
`scope_ref`.
**`peer_set_version`** — `peer_set_version_id` (PK), `peer_set_id` (FK),
`version`, `valid_from`, `valid_to`, `origin`, `method_version`,
`approved_by_user`, `approved_at`, `criteria` (JSON).
**`peer_set_member`** — `peer_set_version_id` (FK), `instrument_id` (FK),
`reason`.

Инварианты: версия неизменяема; при `origin = classifier` поле
`approved_by_user` ложно и набор считается `unverified`; членов меньше
пяти — перцентили по этой версии не рассчитываются.

---

## 6. Watchlist

**`watchlist`** — `watchlist_id` (PK), `name`, `description`,
`update_schedule`, `created_at`.
**`watchlist_version`** — `watchlist_version_id` (PK), `watchlist_id` (FK),
`version`, `created_at`, `action`, `note`.
**`watchlist_member`** — `watchlist_version_id` (FK), `instrument_id` (FK),
`note`, `added_at`.
**`watchlist_group`** и **`watchlist_group_member`** — по той же схеме,
привязаны к версии.
**`watchlist_filter`** — `watchlist_version_id` (FK), `criteria` (JSON).

Инварианты: текущее состояние — максимальная версия; изменение создаёт
версию целиком, включая неизменившиеся элементы; откат — новая версия,
копирующая состав указанной. История не переписывается.

---

## 7. Очередь и аудит

**`job`** — `job_id` (PK), `instrument_id`, `block`, `provider`,
`target_date`, `url`, `priority`, `status` (`queued` / `running` / `done` /
`failed` / `dead`), `attempt`, `not_before`, `created_at`, `finished_at`,
`idempotency_key`, `last_error`.

`idempotency_key` = хеш от `(instrument_id, block, provider, target_date)`.
Уникален среди незавершённых. Повторная постановка того же задания
не создаёт дубля — это половина требования идемпотентности; вторая
половина — дедупликация по `sha256` в узле сохранения.

**`job_attempt`** — `job_id` (FK), `attempt`, `started_at`, `finished_at`,
`result`, `error`, `http_status`.

**`audit_log`** — `ts`, `action`, `target`, `payload` (JSON), `confirmed`,
`result`. Дублируется в `logs/audit.jsonl` только на добавление: журнал
должен пережить базу.

**`verification`** — `verification_id` (PK), `fact_id_wrong` (FK),
`fact_id_correct` (FK), `reported_at`, `note`, `promoted_to_golden`.

**`metric_sample`** — `ts`, `name`, `provider`, `value`. Системные метрики
из требования 4 свода: success rate, лаг, доля suspect, доля на ручной
верификации, `peer_set_coverage`, `peer_set_churn`.

**`llm_summary`** — `instrument_id`, `created_at`, `model`, `prompt_hash`,
`snapshot_version`, `summary`, `highlights` (JSON), `risks` (JSON),
`citations` (JSON).

---

## 8. Версионирование схемы

**`schema_version`** — `version`, `applied_at`, `checksum`.

Правила:

1. Миграции только вперёд, пронумерованы, применяются по порядку.
2. **База пользователя никогда не пересоздаётся** — на диске лежат
   собранные за месяцы данные.
3. Каждая миграция обратимо описана в комментарии, но откат не
   автоматизируется: восстановление — из резервной копии каталога.
4. Перед миграцией снимается копия `rusterm.db` рядом; удаляется после
   успешного применения.
5. Пересчёт производных данных (`measure`, `coverage`) миграцией
   не выполняется: помечается `stale`, пересчитывается фоново.

---

## 9. Что осознанно не нормализовано

- `coverage` — денормализованная витрина ради экрана списка на 500 строк.
- `locator` — JSON внутри строки факта, а не отдельные таблицы на каждый
  тип локатора. Типов шесть, схемы у них разные, запросов по внутренностям
  локатора не предполагается.
- `criteria` фильтров и peer set — JSON: это пользовательские условия
  произвольной формы, реляционная раскладка дала бы таблицу-мешок.
