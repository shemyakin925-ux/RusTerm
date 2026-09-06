# Industry: Maritime / Tanker

Файл: `maritime-tanker.md`

## Стандартные метрики
Применить общую схему. Дополнительно выделяется выручка по сегментам
(VLCC, Suezmax, Aframax, MR / LR1 / LR2 — для разных типов компаний).

## Специфичные метрики

#### Доходность флота
- **spot_TCE_per_day_by_class** — Time Charter Equivalent в день по
  классу судна. Основная метрика доходности. Источник: операционные
  релизы компаний, Clarksons, Baltic Exchange. Единица: USD/day.
- **time_charter_TCE_per_day_by_class** — то же для средне- и
  долгосрочных контрактов. Обычно ниже спота, но стабильнее.
- **fleet_utilization_%** — % дней в году, когда судно работало
  (не в ремонте, не на стоянке).
- **off_hire_days** — дней вне эксплуатации по судну / флоту.
- **revenue_per_ship_by_class** — годовая выручка, делённая на
  количество судов класса.

#### Операционные расходы
- **vessel_OPEX_per_day_by_class_and_age** — операционные расходы
  на судно в день (crew, insurance, maintenance, lub oil, provisions).
  Источник: годовые отчёты, segment disclosure. Растёт с возрастом
  судна.
- **technical_OPEX_per_day** — без учёта G&A и финансирования.
- **G&A_per_ship_per_year** — накладные расходы на одно судно в год.

#### Маржинальность
- **daily_vessel_margin** — TCE per day минус OPEX per day.
  Валовая маржа на судно в день.
- **vessel_breakeven_TCE** — TCE, при которой компания на нуле
  (OPEX + финансирование + G&A, делённые на количество судов).
  Используется в презентациях как «cash break-even».

#### Структура флота
- **fleet_count_by_class** — сколько судов каждого класса.
- **fleet_age_profile** — гистограмма возраста флота. Старение
  флота = рост OPEX + будущее списание.
- **average_residual_years_by_class** — сколько лет до следующего
  mandatory dry-dock / scrap.
- **spot_vs_time_charter_exposure_%** — доля доходов от краткосрочных
  контрактов (спот) vs долгосрочных.
- **orderbook_to_fleet_ratio_%** — отношение заказанных новых судов
  к текущему флоту. Высокий % = давление на ставки в будущем.

#### Рыночные индикаторы
- **newbuilding_price_index_by_class** — цена нового судна (USD).
  Источник: Clarksons, Baltic Exchange.
- **secondhand_price_index_by_class** — цена б/у судна по возрасту.
- **scrapping_age_profile** — средний возраст списанных судов по
  классу. Показывает, когда флот «созреет» для выбытия.
- **bunker_spread_HSFO_VLSFO** — разница цен тяжёлого мазута
  и низкосернистого. После IMO 2020 — стоимость compliance.

#### Экология
- **CII_per_ship** — Carbon Intensity Indicator (граммы CO2 на
  тонно-милю). Регулируется IMO с 2023.
- **scrubber_fitted_%** — % судов с установленными scrubber'ами
  (позволяют продолжать использовать дешёвый HSFO).
- **IMO_2020_readiness_%** — % флота, готового к работе после
  IMO 2020 / 2023 регулирования.

#### Контейнеровозы (специфика)
- **port_congestion_TEU_waiting** — TEU, ожидающие разгрузки
  в ключевых портах. Коррелирует со ставками.
- **idle_capacity_%** — % мощностей, не задействованных.
- **blank_sailings_%** — % отменённых рейсов.

## Источники
- **Операционные релизы компаний** — квартальные / годовые
  обновления по флоту, TCE, OPEX. Это первичный источник.
- **Annual report segment disclosure** — годовая детализация
  выручки и OPEX по сегментам.
- **Form 6-K / 20-F** — для иностранных эмитентов, листингованных
  в US (Frontline, INSW).
- **Stock exchange announcements** — крупные сделки (покупка /
  продажа судов, SPO, байбэк).
- **Clarksons Research, Braemar** — рыночные данные (платные).
- **Baltic Exchange** — Baltic Dirty Tanker Index, Baltic Clean
  Tanker Index.

## Сложности извлечения
- **Сегментация меняется.** Frontline отчитывается по классам
  (VLCC, Suezmax), Euronav — по другим классам. Нормализовать
  через единый справочник классов.
- **TCE считается по-разному:** net (после bunker) vs gross
  (до bunker). В снапшоте указывать явно.
- **Owned vs chartered-in:** флот включает суда в тайм-чартере
  или bareboat. TCE / OPEX для них считаются иначе.
- **Pool agreements:** несколько судов в одном пуле, выручка
  делится по формуле. Раскрытие обычно слабое.
- **Операционные данные:** часто доступны только в PDF-презентациях,
  не в формализованном виде. Требуется LLM-extraction или ручной
  ввод.

## Тесты
- Golden-file на 3 эмитентах: Frontline, Euronav, DHT Holdings
- Unit на расчёт per-ship, per-class, breakeven
- Интеграционный на получение segment data из annual report

## Peer set по умолчанию (tanker — pure play)
- Frontline (FRO)
- Euronav (EURN)
- DHT Holdings (DHT)
- International Seaways (INSW)
- Torm (TRMD)
- Scorpio Tankers (STNG)
- Tsakos Energy Navigation (TEN)
- Ardmore Shipping (ASC)
- Hafnia (HAFNI)
- BW LPG (BWLPG) — если танкер-газовоз

---
