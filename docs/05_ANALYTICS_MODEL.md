# Analytics Model

## Overview

Данная документация описывает модель аналитики для RusEquity Terminal.

---

## 1. Valuation Metrics

### 1.1 Price Multiples

| Metric | Formula | Description |
|--------|---------|-------------|
| P/E | Price / EPS | Цена к прибыли |
| P/B | Price / Book Value per Share | Цена к балансовой стоимости |
| P/S | Market Cap / Revenue | Цена к выручке |
| P/CF | Price / Cash Flow per Share | Цена к денежному потоку |
| EV/EBITDA | Enterprise Value / EBITDA | Стоимость компании к EBITDA |
| EV/EBIT | Enterprise Value / EBIT | Стоимость компании к операционной прибыли |
| PEG | P/E / EPS Growth Rate | P/E с учётом роста |

### 1.2 Percentile Ranking

Для каждой метрики рассчитывается процентиль:
- **Исторический**: позиция относительно собственной истории компании (5 лет)
- **Секторальный**: позиция относительно сектора экономики
- **Рыночный**: позиция относительно всего рынка (IMOEX)

```python
def calculate_percentile(value, distribution):
    """Рассчитывает процентиль значения в распределении."""
    count_below = sum(1 for x in distribution if x < value)
    return (count_below / len(distribution)) * 100
```

---

## 2. Profitability Metrics

### 2.1 Return Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| ROE | Net Income / Equity | Рентабельность собственного капитала |
| ROA | Net Income / Total Assets | Рентабельность активов |
| ROIC | NOPAT / Invested Capital | Рентабельность инвестированного капитала |
| ROC | EBIT / (Total Assets - Current Liabilities) | Рентабельность используемого капитала |
| CFROA | Operating Cash Flow / Total Assets | Рентабельность активов по денежному потоку |

### 2.2 Margin Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Gross Margin | Gross Profit / Revenue | Валовая маржа |
| Operating Margin | Operating Income / Revenue | Операционная маржа |
| Pretax Margin | EBT / Revenue | Маржа до налогов |
| Net Margin | Net Income / Revenue | Чистая маржа |
| FCF Margin | Free Cash Flow / Revenue | Маржа свободного денежного потока |

---

## 3. Productivity Metrics

### 3.1 Asset Efficiency

| Metric | Formula | Description |
|--------|---------|-------------|
| Asset Turnover | Revenue / Total Assets | Оборачиваемость активов |
| Fixed Asset Turnover | Revenue / Fixed Assets | Оборачиваемость внеоборотных активов |
| Working Capital Turnover | Revenue / Working Capital | Оборачиваемость оборотного капитала |

### 3.2 Cycle Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Inventory Days | (Inventory / COGS) × 365 | Дни запасов |
| Receivables Days | (Accounts Receivable / Revenue) × 365 | Дни дебиторской задолженности |
| Payables Days | (Accounts Payable / COGS) × 365 | Дни кредиторской задолженности |
| Cash Conversion Cycle | Inv Days + Rec Days - Pay Days | Финансовый цикл |

---

## 4. Factor Scores

### 4.1 Value Score (0-100)

Оценивает привлекательность оценки компании.

**Компоненты:**
- P/E Percentile (inverse) — вес 30%
- P/B Percentile (inverse) — вес 30%
- P/S Percentile (inverse) — вес 20%
- EV/EBITDA Percentile (inverse) — вес 20%

```python
value_score = (
    (100 - pe_percentile) * 0.30 +
    (100 - pb_percentile) * 0.30 +
    (100 - ps_percentile) * 0.20 +
    (100 - ev_ebitda_percentile) * 0.20
)
```

### 4.2 Quality Score (0-100)

Оценивает качество бизнеса.

**Компоненты:**
- ROE Percentile — вес 30%
- ROIC Percentile — вес 30%
- Debt/Equity inverse Percentile — вес 20%
- FCF Yield Percentile — вес 20%

```python
quality_score = (
    roe_percentile * 0.30 +
    roic_percentile * 0.30 +
    (100 - debt_equity_percentile) * 0.20 +
    fcf_yield_percentile * 0.20
)
```

### 4.3 Momentum Score (0-100)

Оценивает импульс цены.

**Компоненты:**
- Relative Strength 1M Percentile — вес 20%
- Relative Strength 3M Percentile — вес 30%
- Relative Strength 6M Percentile — вес 30%
- Relative Strength 1Y Percentile — вес 20%

```python
momentum_score = (
    rs_1m_percentile * 0.20 +
    rs_3m_percentile * 0.30 +
    rs_6m_percentile * 0.30 +
    rs_1y_percentile * 0.20
)
```

### 4.4 Low Volatility Score (0-100)

Оценивает стабильность цены.

**Компоненты:**
- Beta (inverse percentile) — вес 40%
- Standard Deviation (inverse percentile) — вес 40%
- Max Drawdown (inverse percentile) — вес 20%

```python
low_vol_score = (
    (100 - beta_percentile) * 0.40 +
    (100 - std_dev_percentile) * 0.40 +
    (100 - max_drawdown_percentile) * 0.20
)
```

### 4.5 Composite Score (0-100)

Общий рейтинг акции.

```python
composite_score = (
    value_score * 0.25 +
    quality_score * 0.35 +
    momentum_score * 0.25 +
    low_vol_score * 0.15
)
```

---

## 5. Relative Strength

### 5.1 Definition

Relative Strength (RS) показывает performance акции относительно индекса (IMOEX).

```
RS(period) = (Stock Return over period) - (Index Return over period)
```

### 5.2 Periods

- RS 1M — за 1 месяц
- RS 3M — за 3 месяца
- RS 6M — за 6 месяцев
- RS 1Y — за 1 год
- RS YTD — с начала года

### 5.3 Interpretation

| RS Value | Interpretation |
|----------|----------------|
| > 10%    | Сильный аутперформер |
| 5-10%    | Аутперформер |
| -5% to 5% | В линии с рынком |
| -10% to -5% | Андерперформер |
| < -10%   | Сильный андерперформер |

---

## 6. Dividend Analysis

### 6.1 Dividend Yield

```
Dividend Yield = (Annual Dividend per Share / Price) × 100
```

### 6.2 Dividend Growth

| Period | Formula |
|--------|---------|
| 1-Year Growth | (Div₂₀₂₄ - Div₂₀₂₃) / Div₂₀₂₃ × 100 |
| 3-Year CAGR | (Div₂₀₂₄ / Div₂₀₂₁)^(1/3) - 1 |
| 5-Year CAGR | (Div₂₀₂₄ / Div₂₀₁₉)^(1/5) - 1 |

### 6.3 Payout Ratio

```
Payout Ratio = (Dividends per Share / EPS) × 100
```

### 6.4 Dividend Consistency Score (0-100)

Оценивает надёжность дивидендной политики.

**Компоненты:**
- Years of consecutive payments — вес 30%
- Years of consecutive growth — вес 30%
- Payout Ratio stability (inverse std dev) — вес 20%
- FCF Coverage Ratio — вес 20%

```python
consistency_score = (
    consecutive_years_score * 0.30 +
    growth_years_score * 0.30 +
    payout_stability_score * 0.20 +
    fcf_coverage_score * 0.20
)
```

**Шкала оценки:**
- 90-100: Дивидендный аристократ (10+ лет роста)
- 70-89: Надёжный плательщик (5+ лет выплат)
- 50-69: Нерегулярные выплаты
- < 50: Рискованные дивиденды

---

## 7. Total Return

### 7.1 Definition

Total Return включает ценовую доходность и дивиденды.

```
Total Return = (Price_end - Price_start + Dividends) / Price_start × 100
```

### 7.2 Adjusted Close Method

Для упрощения расчётов используется скорректированная цена закрытия:

```
Adjusted Close = Close × (Cumulative Adjustment Factor)
```

Где adjustment factor учитывает:
- Дивиденды
- Сплиты
- Консолидации

### 7.3 Annualized Returns

Для периодов > 1 года:

```
Annualized TR = (1 + Total Return)^(1/Years) - 1
```

---

## 8. Risk Metrics

### 8.1 Volatility

- **Standard Deviation** — стандартное отклонение дневных доходностей (annualized)
- **Beta** — чувствительность к рынку (IMOEX)

### 8.2 Drawdown

- **Max Drawdown** — максимальное падение от пика до минимума
- **Current Drawdown** — текущее падение от последнего пика

### 8.3 Value at Risk (VaR)

- **VaR 95%** — максимальный убыток с вероятностью 95%
- **VaR 99%** — максимальный убыток с вероятностью 99%

---

## 9. Screening & Ranking

### 9.1 Predefined Screens

| Screen Name | Criteria |
|-------------|----------|
| Deep Value | P/E < 5, P/B < 1, EV/EBITDA < 4 |
| Quality Growth | ROE > 15%, Revenue Growth > 10%, Debt/Equity < 0.5 |
| High Dividend | Dividend Yield > 8%, Payout < 80%, 3+ years payments |
| Momentum Leaders | RS 6M > 10%, RS 1Y > 15%, Price > 200DMA |
| Low Volatility | Beta < 0.8, Std Dev < 20%, Max DD < 30% |

### 9.2 Custom Screening

Пользователь может задать собственные фильтры по всем метрикам.

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial analytics model    |
