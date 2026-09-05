# Data Sources

## Overview

RusEquity Terminal использует **только бесплатные источники данных**.

---

## Approved Sources

### 1. MOEX ISS (Information Statistical Server)

**URL:** https://iss.moex.com/iss/

**Тип данных:**
- Исторические цены (OHLCV)
- Дивидендная история
- Список акций и индексов
- Компоненты индексов
- Торговые статусы
- Параметры листинга

**API Format:** JSON, XML, CSV

**Rate Limits:** 
- Бесплатный доступ без ключа
- Рекомендуется кэширование

**Пример запроса:**
```bash
# Исторические данные по акции
curl "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json"

# Дивиденды
curl "https://iss.moex.com/iss/engines/stock/markets/shares/securities/SBER/dividends.json"
```

**Лицензия:** Открытые данные MOEX

---

### 2. E-Disclosure (Е-disclosure.ru)

**URL:** https://www.e-disclosure.ru/

**Тип данных:**
- Финансовая отчётность (IFRS, RAS)
- Факты раскрытия информации
- События компании
- Презентации
- Протоколы собраний

**API Format:** HTML (парсинг), некоторые данные в XML

**Ограничения:**
- Требуется парсинг
- Соблюдение robots.txt
- Rate limiting обязателен

**Лицензия:** Публичные данные

---

### 3. RFSD (Russian Financial Disclosure System)

**URL:** https://www.rfcd.ru/ (проверить актуальный URL)

**Тип данных:**
- Раскрытие информации эмитентами
- Отчётность
- Существенные факты

**API Format:** HTML, XML

**Лицензия:** Публичные данные

---

### 4. Company Websites

**Источники:** Официальные сайты эмитентов

**Тип данных:**
- Инвестор-реляции разделы
- Презентации
- Новости
- Отчёты для акционеров

**Примеры:**
- Gazprom: https://www.gazprom.ru/investors/
- Sberbank: https://www.sberbank.com/ru/investor-relations
- Lukoil: https://lukoil.ru/investorshareholdercenter

**Важно:**
- Проверять условия использования
- Уважать robots.txt
- Не перегружать сервера

---

### 5. Central Bank of Russia (CBR)

**URL:** https://cbr.ru/

**Тип данных:**
- Курсы валют
- Ключевая ставка
- Макроэкономические данные

**API Format:** XML, JSON

**Пример:**
```bash
# Курсы валют
curl "https://www.cbr-xml-daily.ru/daily_json.js"
```

**Лицензия:** Открытые данные ЦБ

---

### 6. Federal State Statistics Service (Rosstat)

**URL:** https://rosstat.gov.ru/

**Тип данных:**
- Макроэкономические показатели
- Отраслевые данные
- Инфляция, ВВП, производство

**API Format:** HTML, XML

**Лицензия:** Открытые государственные данные

---

## Prohibited Sources

**Запрещено использовать следующие платные источники:**

| Source | Reason |
|--------|--------|
| Bloomberg Terminal | Платный |
| Reuters Eikon | Платный |
| FactSet | Платный |
| Morningstar Direct | Платный |
| S&P Capital IQ | Платный |
| Any paid API | Нарушает принцип free-data only |

---

## Data Fetching Guidelines

### 1. Rate Limiting

```python
# Пример реализации rate limiting
import time
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, calls_per_minute=60):
        self.min_interval = 60 / calls_per_minute
        self.last_call = datetime.min
    
    def wait_if_needed(self):
        elapsed = datetime.now() - self.last_call
        if elapsed < timedelta(seconds=self.min_interval):
            time.sleep((timedelta(seconds=self.min_interval) - elapsed).total_seconds())
        self.last_call = datetime.now()
```

### 2. Caching Strategy

```python
# Рекомендуемая стратегия кэширования
CACHE_TTL = {
    'prices_intraday': 300,      # 5 минут
    'prices_daily': 3600,        # 1 час
    'dividends': 86400,          # 24 часа
    'financials': 604800,        # 7 дней
    'company_info': 604800,      # 7 дней
}
```

### 3. Error Handling

```python
# Обязательная обработка ошибок
def fetch_with_retry(url, max_retries=3, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(backoff_factor ** attempt)
```

### 4. Data Validation

```python
# Валидация полученных данных
def validate_price_data(data):
    required_fields = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME']
    
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing field: {field}")
    
    if data['HIGH'] < data['LOW']:
        raise ValueError("HIGH < LOW is invalid")
    
    if data['VOLUME'] < 0:
        raise ValueError("Negative volume is invalid")
    
    return True
```

---

## Data Normalization

### Standardized Format

Все данные приводятся к единому формату:

```python
class NormalizedPriceData:
    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    currency: str  # RUB, USD, EUR
    adjusted_close: float  # с учётом дивидендов
```

### Currency Conversion

Все цены конвертируются в RUB по курсу ЦБ на дату сделки:

```python
def convert_to_rub(amount, currency, date):
    if currency == 'RUB':
        return amount
    
    rate = get_cbr_rate(currency, date)
    return amount * rate
```

---

## Compliance Checklist

Перед добавлением нового источника данных:

- [ ] Источник бесплатный
- [ ] Лицензия позволяет использование
- [ ]robots.txt разрешает доступ
- [ ] Реализован rate limiting
- [ ] Реализовано кэширование
- [ ] Реализована обработка ошибок
- [ ] Данные нормализованы
- [ ] Добавлена документация в этот файл

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial data sources doc   |
