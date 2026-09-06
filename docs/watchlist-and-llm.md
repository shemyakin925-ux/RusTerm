# Watchlist и массовые LLM-операции

Подробное описание watchlist и LLM-режима пополнения базы. В README —
краткая версия, здесь — детали.

---

## Watchlist: полная схема

### Хранение

```
data/watchlists/
├── main.json                       — основной watchlist
├── conservative-strategy.json      — именованный список
├── aggressive-strategy.json
├── tankers-pure-play.json
└── history/
    ├── main/                       — версии main.json
    │   ├── 2026-09-01.json
    │   ├── 2026-09-15.json
    │   └── ...
    └── tankers-pure-play/
        └── ...
```

Каждый watchlist — JSON со следующей структурой:

```json
{
  "name": "Мой основной watchlist",
  "description": "30-50 бумаг для еженедельного разбора",
  "created_at": "2026-09-01T10:00:00Z",
  "updated_at": "2026-09-20T14:30:00Z",
  "version": 7,
  "update_schedule": "weekly",
  "tickers": [
    {
      "ticker": "AAPL",
      "market": "US",
      "isin": "US0378331005",
      "sector": "BigTech",
      "note": "Кэш + buyback",
      "added_at": "2026-09-01T10:00:00Z"
    }
  ],
  "dynamic_filters": [
    {
      "name": "All tankers cap>500M",
      "market": ["US", "UK", "CA", "EU"],
      "sector": "Maritime/Tanker",
      "market_cap_min": 500000000,
      "market_cap_max": 5000000000,
      "exclude": ["delisted", "in_distress"]
    }
  ],
  "groups": [
    {
      "name": "BigTech",
      "tickers": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA"]
    },
    {
      "name": "Banks US",
      "tickers": ["JPM", "BAC", "WFC", "C", "GS"]
    }
  ]
}
```

### Версионирование

- При каждом изменении (добавление / удаление тикера, изменение
  фильтра, переименование группы) — создаётся новая версия в
  `data/watchlists/history/<name>/<YYYY-MM-DD>.json`
- Текущая версия — в `data/watchlists/<name>.json`
- Откат: «верни watchlist к состоянию на 1 сентября» → копирует
  указанную версию в текущий файл, инкрементит version

### Покрытие (coverage)

```
data/snapshots/<ticker>/coverage.json:
{
  "ticker": "AAPL",
  "as_of": "2026-09-20",
  "blocks": {
    "prices": {"status": "ready", "last_update": "2026-09-20"},
    "fundamentals": {"status": "ready", "last_update": "2026-09-15"},
    "ownership": {"status": "ready", "last_update": "2026-09-10"},
    "governance": {"status": "ready", "last_update": "2026-09-10"},
    "llm_summary": {"status": "ready", "last_update": "2026-09-20"}
  },
  "errors": []
}
```

`blocks.<name>.status` может быть:
- `ready` — данные актуальны
- `stale` — данные старше порога (настраивается)
- `processing` — идёт сбор
- `missing` — данные отсутствуют
- `error` — ошибка сбора

### Импорт / экспорт

**Экспорт:**

```csv
ticker,market,sector,note,added_at
AAPL,US,BigTech,"Cash + buyback",2026-09-01
FRO,US,Maritime/Tanker,Pure-play tanker,2026-09-15
```

**Импорт:**

- Из CSV: `ticker, market, sector, note`
- Из портфельных трекеров (на будущее):
  - Interactive Brokers: flex query response
  - Trading 212: CSV экспорт
  - Yahoo Finance: portfolio export

### Сценарии использования

**Сценарий 1: еженедельный разбор**
```
1. Открыть watchlist "Main"
2. Нажать "Обновить всё"
3. Дождаться завершения (прогресс по тикерам)
4. Перейти в "What\'s Changed" — список изменений за неделю
5. Открыть снапшоты по компаниям с интересными изменениями
```

**Сценарий 2: разовое изучение отрасли**
```
1. LLM-чат: "Добавь все танкерные компании cap>500M"
2. Подтвердить список из 12 компаний
3. Дождаться первичного сбора (1-2 дня, прогресс в UI)
4. Перейти в Industry View → Maritime/Tanker
5. Изучить peer comparison, цикл индустрии, leaders
```

**Сценарий 3: сравнение стратегий**
```
1. Три параллельных watchlist:
   - Conservative (utilities, REITs, staples)
   - Aggressive (tech, biotech, growth)
   - Dividend (high payout, stable cash flow)
2. Обновлять все три одновременно
3. Сравнивать aggregate-метрики по группам
```

---

## LLM: пополнение базы — детали

### Архитектура взаимодействия

```
User input → LLM intent classification → Tool calls → Confirmation → Execute
```

#### Шаг 1: Intent classification

LLM получает на вход сообщение пользователя + список доступных
интентов:

```
AVAILABLE INTENTS:
1. add_tickers_to_watchlist — добавить тикеры в существующий или новый watchlist
2. add_sector_to_watchlist — добавить все компании сектора с фильтром
3. add_index_to_watchlist — добавить ETF-холдеры или компоненты индекса
4. add_peers_to_watchlist — найти и добавить конкурентов существующей компании
5. update_watchlist_summary — обновить LLM-summary по всем компаниям watchlist
6. compare_companies — сравнить 2-5 компаний между собой
7. ask_about_company — обычный вопрос про снапшот
8. ask_about_industry — обычный вопрос про отрасль
```

LLM возвращает:
```json
{
  "intent": "add_sector_to_watchlist",
  "params": {
    "sector": "Maritime/Tanker",
    "market_cap_min": 500000000,
    "market_cap_max": 5000000000,
    "watchlist_name": "Maritime exploration"
  },
  "confidence": 0.92
}
```

Если `confidence < 0.7` — запрашивается уточнение у пользователя.

#### Шаг 2: Tool calls

LLM вызывает инструменты:
- `resolve_ticker(ticker, market)` — проверить существование
  тикера, получить ISIN, FIGI, сектор
- `list_sector_companies(sector, filters)` — получить список
  компаний сектора с фильтром по капитализации
- `get_peer_set(ticker)` — получить peer set для компании

Все инструменты — read-only. Никаких изменений без подтверждения.

#### Шаг 3: Confirmation (dry-run → review)

LLM показывает пользователю:

```
Найдено компаний: 12

1. Frontline (FRO) — US, Maritime/Tanker, cap $4.8B
2. Euronav (EURN) — EU, Maritime/Tanker, cap $3.2B
3. DHT Holdings (DHT) — US, Maritime/Tanker, cap $1.7B
4. International Seaways (INSW) — US, Maritime/Tanker, cap $0.9B
5. Torm (TRMD) — EU, Maritime/Tanker, cap $1.5B
6. Scorpio Tankers (STNG) — US, Maritime/Tanker, cap $0.8B
7. Tsakos Energy Navigation (TEN) — US, Maritime/Tanker, cap $0.6B
8. Ardmore Shipping (ASC) — US, Maritime/Tanker, cap $0.5B
9. Hafnia (HAFNI) — EU, Maritime/Tanker, cap $1.1B
10. BW LPG (BWLPG) — EU, Maritime/Tanker, cap $1.4B
11. Pyxis Tankers (PXS) — US, Maritime/Tanker, cap $0.4B  — НИЖЕ ПОРОГА, исключён
12. Eagle Bulk Shipping (EGLE) — US, Maritime/Bulk, не tanker — исключён

Будет добавлено в watchlist "Maritime exploration": 10 компаний.
Запустить первичный сбор данных? [Да / Редактировать список / Отмена]
```

#### Шаг 4: Execute

После подтверждения:
1. Создать / обновить watchlist (новая версия)
2. Поставить задачи на сбор по каждому тикеру
3. Вернуть пользователю статус: «Добавлено 10 компаний, сбор запущен,
   ориентировочное время готовности: 4-6 часов»

### LLM-summary по watchlist

Для каждой компании watchlist (параллельно):

```
Входные данные для LLM:
- Текущий снапшот (числа, мультипликаторы, ownership, события)
- Предыдущий снапшот (для diff)
- Последние N раскрытий из манифеста
- Peer set (краткий список + текущие мультипликаторы peerов)

Выходные данные:
- summary (3-5 предложений): что произошло, что выделяется
- highlights (3-5 буллетов): конкретные изменения
- risks (1-3 буллета): что обратить внимание
- citations: [список ссылок на первоисточники]
```

LLM не генерирует числа — только текст с ссылками. Если число
необходимо в тексте — оно из снапшота, не из LLM.

### Хранение LLM-summary

```
data/snapshots/<ticker>/llm_summaries/
├── 2026-09-15.json
├── 2026-09-20.json
└── ...
```

Каждый файл — структурированный JSON с текстом + метаданными
(model, version, prompt_hash, citations).

### Логирование массовых операций

```
data/audit/watchlist_operations.jsonl:
{"ts": "...", "user": "...", "action": "add_tickers", "watchlist": "...", "tickers": [...], "confirmed": true, "result": "ok"}
{"ts": "...", "user": "...", "action": "update_summary", "watchlist": "...", "n_companies": 30, "model": "claude-sonnet", "duration_s": 245}
{"ts": "...", "user": "...", "action": "rollback_watchlist", "watchlist": "main", "to_version": "2026-09-01", "result": "ok"}
```

Каждое действие можно откатить, если оно обратимо (добавление —
можно, изменение LLM-summary — можно, удаление — можно с
восстановлением из истории).

---

## Принципы безопасности массовых операций

1. **Dry-run по умолчанию.** Никаких изменений без явного
   подтверждения.
2. **Транзакционность.** Все операции атомарны: либо все тикеры
   добавлены, либо ни один.
3. **Откат.** Любое изменение watchlist можно откатить к
   предыдущей версии.
4. **Лимиты.** Максимум N компаний за одну операцию (например,
   100). Больше — запрос на подтверждение явно.
5. **Аудит.** Все действия логируются с возможностью просмотра
   истории.
6. **Неопределённость = вопрос.** Если LLM не уверен в результате
   (confidence < 0.7) — запрашивается уточнение, не действие
   наугад.
