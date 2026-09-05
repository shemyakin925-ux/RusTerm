# Data Model

## Overview

Данная документация описывает модель данных для RusEquity Terminal.

---

## Core Entities

### 1. Stock (Акция)

```yaml
Stock:
  ticker: string           # e.g., "GAZP", "SBER"
  name: string             # Полное название
  short_name: string       # Краткое название
  sector: string           # Сектор экономики
  industry: string         # Отрасль
  isin: string             # ISIN код
  listing_level: int       # Уровень листинга (1, 2, 3)
  currency: string         # Валюта торгов (RUB, USD, EUR)
  lot_size: int            # Размер лота
  active: boolean          # Торгуются ли сейчас
  first_trade_date: date   # Дата первой сделки
  last_trade_date: date    # Дата последней сделки
```

---

### 2. PriceData (Ценовые данные)

```yaml
PriceData:
  stock_ticker: string     # Ссылка на Stock
  date: date               # Дата
  open: decimal            # Цена открытия
  high: decimal            # Максимум
  low: decimal             # Минимум
  close: decimal           # Цена закрытия
  volume: int64            # Объём в бумагах
  value: decimal           # Объём в деньгах
  adjusted_close: decimal  # Скорректированная цена (на дивиденды/сплиты)
```

**Индексы:**
- `(stock_ticker, date)` — unique

---

### 3. Dividend (Дивиденды)

```yaml
Dividend:
  stock_ticker: string     # Ссылка на Stock
  announcement_date: date  # Дата объявления
  ex_dividend_date: date   # Дата отсечки
  record_date: date        # Дата фиксации реестра
  payment_date: date       # Дата выплаты
  dividend_per_share: decimal  # Дивиденд на акцию
  currency: string         # Валюта выплаты
  dividend_type: enum      # regular, special, liquidation
  period: string           # Период (e.g., "2023", "H1 2023")
  gross_yield: decimal     # Дивдоходность gross (%)
  net_yield: decimal       # Дивдоходность net (%)
```

**Индексы:**
- `(stock_ticker, ex_dividend_date)` — unique

---

### 4. FinancialStatement (Финансовая отчётность)

```yaml
FinancialStatement:
  stock_ticker: string     # Ссылка на Stock
  report_date: date        # Дата отчёта
  period_type: enum        # annual, quarterly
  currency: string         # Валюта отчётности
  standard: enum           # IFRS, RAS
  
  # Balance Sheet
  total_assets: decimal
  total_liabilities: decimal
  equity: decimal
  current_assets: decimal
  current_liabilities: decimal
  cash_and_equivalents: decimal
  debt_total: decimal
  debt_short_term: decimal
  debt_long_term: decimal
  
  # Income Statement
  revenue: decimal
  cost_of_revenue: decimal
  gross_profit: decimal
  operating_expenses: decimal
  operating_income: decimal
  ebitda: decimal
  net_income: decimal
  eps: decimal             # Earnings per share
  
  # Cash Flow
  operating_cash_flow: decimal
  investing_cash_flow: decimal
  financing_cash_flow: decimal
  free_cash_flow: decimal
  capex: decimal
```

**Индексы:**
- `(stock_ticker, report_date, standard)` — unique

---

### 5. CompanyInfo (Информация о компании)

```yaml
CompanyInfo:
  stock_ticker: string     # Ссылка на Stock
  website: string
  headquarters: string
  employees: int
  ceo: string
  founded_year: int
  description: text
  phone: string
  email: string
  address: text
```

---

### 6. Index (Индексы)

```yaml
Index:
  code: string             # e.g., "IMOEX", "RTS"
  name: string
  description: text
  base_date: date
  base_value: decimal
  currency: string
```

---

### 7. IndexConstituent (Компоненты индекса)

```yaml
IndexConstituent:
  index_code: string       # Ссылка на Index
  stock_ticker: string     # Ссылка на Stock
  weight: decimal          # Вес в индексе (%)
  inclusion_date: date
  exclusion_date: date     # NULL если текущий компонент
```

---

### 8. AnalyticsSnapshot (Снимок аналитики)

```yaml
AnalyticsSnapshot:
  stock_ticker: string     # Ссылка на Stock
  snapshot_date: date      # Дата расчёта
  
  # Valuation
  pe_ratio: decimal
  pb_ratio: decimal
  ps_ratio: decimal
  ev_ebitda: decimal
  peg_ratio: decimal
  
  # Percentiles (vs sector/history)
  pe_percentile: decimal   # 0-100
  pb_percentile: decimal
  ps_percentile: decimal
  ev_ebitda_percentile: decimal
  
  # Profitability
  roe: decimal
  roa: decimal
  roic: decimal
  gross_margin: decimal
  operating_margin: decimal
  net_margin: decimal
  
  # Productivity
  asset_turnover: decimal
  inventory_days: decimal
  receivables_days: decimal
  
  # Factor Scores (0-100)
  value_score: decimal
  quality_score: decimal
  momentum_score: decimal
  low_volatility_score: decimal
  composite_score: decimal
  
  # Relative Strength
  rs_1m: decimal           # vs индекс за 1 месяц
  rs_3m: decimal
  rs_6m: decimal
  rs_1y: decimal
  
  # Dividend Metrics
  dividend_yield: decimal
  dividend_growth_1y: decimal
  dividend_growth_3y: decimal
  dividend_growth_5y: decimal
  payout_ratio: decimal
  dividend_consistency_score: decimal  # 0-100
  
  # Total Return
  tr_1m: decimal           # Total Return за период
  tr_3m: decimal
  tr_6m: decimal
  tr_1y: decimal
  tr_3y_annualized: decimal
  tr_5y_annualized: decimal
```

**Индексы:**
- `(stock_ticker, snapshot_date)` — unique

---

### 9. AIInsight (AI-инсайты)

```yaml
AIInsight:
  stock_ticker: string     # Ссылка на Stock
  insight_date: date
  insight_type: enum       # summary, alert, recommendation, qa
  content: text            # Текст инсайта
  model_used: string       # e.g., "gpt-4", "llama-3"
  confidence_score: decimal # 0-1
  source_data_refs: array  # Ссылки на исходные данные
```

---

## Relationships

```
Stock ──┬── PriceData (1:N)
        ├── Dividend (1:N)
        ├── FinancialStatement (1:N)
        ├── CompanyInfo (1:1)
        ├── AnalyticsSnapshot (1:N)
        └── AIInsight (1:N)

Index ──┬── IndexConstituent (1:N)
        └── Stock (N:M через IndexConstituent)
```

---

## Calculated Fields

### Total Return Formula

```sql
-- Для периода [start_date, end_date]
Total Return = 
  (adjusted_close_end - adjusted_close_start + SUM(dividends)) 
  / adjusted_close_start * 100
```

### Factor Scores

```
Value Score = weighted_average(
  1/PE_percentile * 0.3,
  1/PB_percentile * 0.3,
  1/PS_percentile * 0.2,
  1/EV_EBITDA_percentile * 0.2
) * 100

Quality Score = weighted_average(
  ROE_percentile * 0.3,
  ROIC_percentile * 0.3,
  Debt/Equity_inverse_percentile * 0.2,
  FCF_Yield_percentile * 0.2
) * 100

Momentum Score = weighted_average(
  RS_1m_percentile * 0.2,
  RS_3m_percentile * 0.3,
  RS_6m_percentile * 0.3,
  RS_1y_percentile * 0.2
) * 100

Composite Score = weighted_average(
  Value Score * 0.25,
  Quality Score * 0.35,
  Momentum Score * 0.25,
  Low Volatility Score * 0.15
)
```

---

## Data Retention Policy

| Entity              | Retention Period | Notes                        |
|---------------------|------------------|------------------------------|
| PriceData           | All available    | Исторические данные важны    |
| Dividend            | All available    | Для расчёта Total Return     |
| FinancialStatement  | 10 years         | Долгосрочный анализ          |
| AnalyticsSnapshot   | 5 years          | Можно пересчитать            |
| AIInsight           | 1 year           | Кэшированные инсайты         |

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial data model         |
