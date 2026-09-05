# RusEquity Terminal

Кросс-платформенное приложение для глубокого анализа российских акций (MOEX).

## Описание

**RusEquity Terminal** — это Desktop + Mobile приложение (единый codebase на Flutter) для инвесторов, предоставляющее аналитику уровня Bloomberg на основе исключительно бесплатных источников данных.

### Ключевые возможности

- **Total Return**: Расчёт полной доходности с учётом дивидендов
- **Valuation Analysis**: P/E, EV/EBITDA, percentiles vs история/сектор/рынок
- **Factor Scores**: Value, Quality, Momentum, Low Volatility (0-100)
- **Dividend Analytics**: Yield, growth, consistency score
- **Relative Strength**: Performance vs индекс (IMOEX)
- **AI Insights**: Remote API (OpenAI/Anthropic) + Local LLM (Ollama)

### Источники данных (только бесплатные)

- MOEX ISS — цены, дивиденды, индексы
- E-disclosure.ru — финансовая отчётность
- Сайты эмитентов — презентации, новости
- ЦБ РФ — курсы валют

### Платформы

- 📱 Mobile: iOS, Android
- 🖥️ Desktop: Windows, macOS, Linux

---

## Для Разработчиков (LLM Agents)

Этот проект разрабатывается поэтапно разными LLM с обязательной перепроверкой.

### 🔴 Начните здесь

Перед любой работой **ОБЯЗАТЕЛЬНО** прочитайте:

1. [`docs/00_MASTER_SPEC.md`](docs/00_MASTER_SPEC.md) — Общее описание
2. [`docs/03_ARCHITECTURE.md`](docs/03_ARCHITECTURE.md) — Архитектура
3. [`docs/15_AGENT_RULES.md`](docs/15_AGENT_RULES.md) — **Правила для агентов**
4. [`docs/16_NEXT_TASK.md`](docs/16_NEXT_TASK.md) — **Ваша текущая задача**
5. [`docs/17_VERIFICATION_PROTOCOL.md`](docs/17_VERIFICATION_PROTOCOL.md) — **Протокол проверки**

### Документация

| Файл | Описание |
|------|----------|
| `00_MASTER_SPEC.md` | Master Specification |
| `01_PROJECT_STATUS.md` | Текущий статус проекта |
| `02_ROADMAP.md` | Дорожная карта с фазами |
| `03_ARCHITECTURE.md` | Архитектура системы |
| `04_DATA_MODEL.md` | Модель данных |
| `05_ANALYTICS_MODEL.md` | Модель аналитики |
| `06_DATA_SOURCES.md` | Источники данных (free only) |
| `07_AI_LAYER.md` | AI-слой (remote + local LLM) |
| `08_FRONTEND.md` | Frontend архитектура (Flutter) |
| `09_DECISIONS.md` | Architecture Decision Records |
| `10_KNOWN_ISSUES.md` | Известные проблемы |
| `11_CHANGELOG.md` | История изменений |
| `12_BACKLOG.md` | Бэклог задач |
| `13_HARDWARE_STORAGE.md` | Требования к железу и хранению |
| `15_AGENT_RULES.md` | **⚠️ Правила для LLM-агентов** |
| `16_NEXT_TASK.md` | **Следующая задача** |
| `17_VERIFICATION_PROTOCOL.md` | **🔒 Протокол проверки** |

### Текущий статус

**PHASE 0.1** — Documentation & Structure Setup ✅ **COMPLETE**

См. [`docs/01_PROJECT_STATUS.md`](docs/01_PROJECT_STATUS.md) для деталей.

---

## Лицензия

[Указать лицензию]

---

## Контакты

[Контактная информация]
