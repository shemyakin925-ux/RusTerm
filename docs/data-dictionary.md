# Data dictionary

**Статус: предложено (06.09.2026), требует подтверждения.**

В спецификации формулы были названы, но не выписаны. Здесь они зафиксированы
с явным выбором варианта. Там, где вариантов несколько и выбор — вопрос вкуса,
выбор назван прямо. Там, где данных нет, стоит **нет данных**, а не догадка.

`method_version` формулы меняется при любой правке определения. Изменение
формулы без нового `method_version` — баг (ADR-0001).

---

## 1. Общие правила

1. **Валюта.** Факт хранится в отчётной валюте эмитента. Конверсия — только
   на витрине, с фиксацией курса, даты и источника курса как отдельного факта.
2. **TTM.** Для `duration`-концептов — сумма четырёх последних завершённых
   кварталов; для `instant` — последнее значение. Смешивать годовой и TTM
   в одном показателе запрещено; какой использован, указывается рядом.
3. **Неполный период** (первый год после IPO, переходный период при смене
   финансового года) не приводится к году и не участвует в CAGR.
4. **Отрицательный или нулевой знаменатель** даёт `null`, а не бесконечность
   и не отрицательное значение мультипликатора.
5. **`null` — это значение.** Он показывается как «не рассчитывается» с
   причиной, а не как пустая ячейка.
6. **Никаких adjusted-величин эмитента.** Adjusted EBITDA, non-GAAP EPS и
   подобное берутся только как отдельные концепты с явным префиксом
   `reported_adj_*` и никогда не подставляются в формулы.

---

## 2. Концепты

`duration` — величина за период, `instant` — на дату.

| Концепт | Тип | Единица | Комментарий |
|---|---|---|---|
| `revenue` | duration | валюта | выручка |
| `cogs` | duration | валюта | себестоимость |
| `gross_profit` | duration | валюта | = revenue − cogs, если не раскрыт |
| `opex` | duration | валюта | операционные расходы без COGS |
| `operating_income` | duration | валюта | операционная прибыль |
| `d_and_a` | duration | валюта | амортизация из отчёта о движении средств |
| `net_income` | duration | валюта | прибыль, приходящаяся на акционеров |
| `pretax_income` | duration | валюта | прибыль до налога |
| `tax_expense` | duration | валюта | расход по налогу |
| `interest_expense` | duration | валюта | процентные расходы |
| `eps_diluted` | duration | валюта/акцию | разводнённая |
| `shares_diluted` | duration | шт. | средневзвешенное разводнённое |
| `shares_outstanding` | instant | шт. | на отчётную дату |
| `ocf` | duration | валюта | операционный денежный поток |
| `capex` | duration | валюта | приобретение основных средств; **без** покупок бизнесов |
| `cash` | instant | валюта | деньги и эквиваленты |
| `st_investments` | instant | валюта | краткосрочные вложения |
| `total_debt` | instant | валюта | кратко- и долгосрочный долг **включая** финансовую аренду |
| `total_assets` | instant | валюта | |
| `total_equity` | instant | валюта | капитал акционеров без неконтролирующей доли |
| `minority_interest` | instant | валюта | |
| `preferred_equity` | instant | валюта | |
| `dps` | duration | валюта/акцию | объявленные дивиденды на акцию |
| `buyback_amount` | duration | валюта | фактически выкуплено |
| `price_close` | instant | валюта | цена закрытия |
| `price_adj` | instant | валюта | скорректированная на сплиты и дивиденды |

---

## 3. Формулы, `method_version` v1

### Прибыльность

```
ebitda            = operating_income + d_and_a
                    если operating_income не раскрыт:
                    revenue - cogs - opex + d_and_a
gross_margin      = gross_profit / revenue
operating_margin  = operating_income / revenue
net_margin        = net_income / revenue
effective_tax     = clip(tax_expense / pretax_income, 0, 0.5)
                    при pretax_income <= 0 -> ставка юрисдикции из справочника
nopat             = operating_income * (1 - effective_tax)
```

Выбор: EBITDA считается **снизу от операционной прибыли**, а не от чистой
через обратное добавление процентов и налогов. Второй вариант даёт другую
величину при наличии неоперационных статей и чаще расходится с отраслевой
практикой.

### Капитал и отдача

```
invested_capital  = total_equity + minority_interest + total_debt
                    - cash - st_investments
roic              = nopat / avg(invested_capital_начало, invested_capital_конец)
roe               = net_income / avg(total_equity_начало, total_equity_конец)
asset_turnover    = revenue / avg(total_assets)
```

Выбор: знаменатель — **среднее за период**, не на конец. На конец даёт
завышенный ROIC в год крупного выбытия активов.

### Долг

```
net_debt          = total_debt - cash - st_investments
net_debt_ebitda   = net_debt / ebitda_ttm            (null при ebitda <= 0)
interest_coverage = operating_income / interest_expense
```

### Денежный поток

```
fcf               = ocf - capex
fcf_yield         = fcf_ttm / market_cap
```

Выбор: FCF — **простой**, `OCF − capex`. Варианты с вычетом дивидендов
по привилегированным акциям и арендных платежей не используются.

### Оценка

```
market_cap        = price_close * shares_outstanding
ev                = market_cap + total_debt - cash - st_investments
                    + minority_interest + preferred_equity
pe                = market_cap / net_income_ttm      (null при <= 0)
ev_ebitda         = ev / ebitda_ttm                  (null при <= 0)
pb                = market_cap / total_equity        (null при <= 0)
ps                = market_cap / revenue_ttm
div_yield         = dps_ttm / price_close
```

### Рост

```
cagr(V, n)        = (V_end / V_start)^(1/n) - 1
                    null при V_start <= 0 — рост от убытка не определён
```

### Котировки

```
total_return(t0,t1) = price_adj(t1) / price_adj(t0) - 1
drawdown(t)         = price_adj(t) / max(price_adj[t0..t]) - 1
```

`price_adj` по определению пересчитывается задним числом при каждом
дивиденде и сплите, поэтому хранится с `basis=restated`, а `price_close` —
с `basis=as_reported`. Diff «что изменилось» строится по `price_close`.

### Сектор

```
hhi               = sum(share_i^2) * 10000, share по капитализации
percentile(x, S)  = метод ближайшего ранга по набору S
                    обязательные атрибуты: n = |S|, peer_set_version
                    null при n < 5 (ADR-0002)
```

---

## 4. Отраслевые метрики

Формулы специфичных метрик живут в файле отрасли
(`docs/industry-metrics/<industry>.md`), а не здесь. Выписана одна отрасль —
Maritime / Tanker. Для остальных четырнадцати **формул нет**: метрики
перечислены в README §3.3 по названиям, определения не зафиксированы.

---

## 5. Чего в спецификации нет

Перечислено прямо, чтобы не выглядело решённым:

- Правило нормализации отчётности при смене финансового года.
- Обработка эмитентов, отчитывающихся по МСФО и по US GAAP, в одной
  сравнительной таблице.
- Источник и правило пересчёта валют для мультипликаторов peer set,
  где эмитенты отчитываются в разных валютах.
- Ставки налога по юрисдикциям для случая `pretax_income <= 0`.
- Определения отраслевых метрик для четырнадцати отраслей из пятнадцати.
