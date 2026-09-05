# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Flutter)                       │
│              ┌──────────────┬──────────────┬─────────────┐      │
│              │   Mobile     │    Desktop   │    Web*     │      │
│              │  (iOS/Andr)  │ (Win/Mac/Lin)│  (future)   │      │
│              └──────────────┴──────────────┴─────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway / BFF                          │
│                   (REST / GraphQL / WebSocket)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend Services                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Data Layer  │  │ Analytics   │  │ AI Service              │  │
│  │             │  │ Layer       │  │                         │  │
│  │ - MOEX ISS  │  │ - Valuation │  │ - Remote API (OpenAI)   │  │
│  │ - E-disclos │  │ - Factors   │  │ - Local LLM (Ollama)    │  │
│  │ - RFSD      │  │ - RS, Div   │  │ - Prompt Engineering    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Storage                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ PostgreSQL  │  │   Redis     │  │   File Storage          │  │
│  │ (Primary)   │  │  (Cache)    │  │   (Reports, Files)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-LLM Development Process

Проект разрабатывается поэтапно разными LLM с обязательной перепроверкой.

### Ссылки на ключевые документы

- **Правила для агентов:** [`15_AGENT_RULES.md`](./15_AGENT_RULES.md)
- **Протокол проверки:** [`17_VERIFICATION_PROTOCOL.md`](./17_VERIFICATION_PROTOCOL.md)
- **Следующая задача:** [`16_NEXT_TASK.md`](./16_NEXT_TASK.md)

### Процесс

1. **Одна LLM = одна фаза/задача**
2. **Обязательное чтение перед началом:**
   - `00_MASTER_SPEC.md`
   - `03_ARCHITECTURE.md`
   - `15_AGENT_RULES.md`
   - `16_NEXT_TASK.md`
   - `17_VERIFICATION_PROTOCOL.md`
3. **Запрещено:**
   - Добавлять платные источники данных
   - Делать архитектуру «на вырост»
   - Отклоняться от утверждённой архитектуры без ADR
4. **После завершения:**
   - Обновить `01_PROJECT_STATUS.md`
   - Обновить `11_CHANGELOG.md`
   - Оставить репо готовым к проверке
5. **Следующая LLM обязана выполнить проверку** по `17_VERIFICATION_PROTOCOL.md` перед началом работы.

---

## Core Principles

### 1. Free Data Only

- **Разрешено:** MOEX ISS, e-disclosure.ru, rfcd.ru, сайты эмитентов
- **Запрещено:** Bloomberg, Reuters, платные API

### 2. Total Return

Все расчёты доходности включают дивиденды:
```
Total Return = (Price_end - Price_start + Dividends) / Price_start
```

### 3. Cross-Platform Frontend

- **Единый codebase** для Mobile и Desktop
- **Технология:** Flutter
- **Поддерживаемые платформы:**
  - iOS
  - Android
  - Windows
  - macOS
  - Linux

### 4. Expandable to Bloomberg-Class

Архитектура должна позволять добавление:
- Real-time data streams
- Advanced charting
- Portfolio optimization
- Risk analytics
- AI-driven insights

---

## Component Details

### Frontend (Flutter)

**Ответственность:**
- UI/UX для всех платформ
- Локальное кэширование
- Offline mode (базовый)

**Структура:**
```
lib/
├── main.dart
├── app/
│   ├── app.dart
│   └── routes.dart
├── features/
│   ├── stocks/
│   ├── analytics/
│   ├── portfolio/
│   └── ai_insights/
├── shared/
│   ├── widgets/
│   ├── utils/
│   └── theme/
└── services/
    ├── api_client.dart
    ├── storage.dart
    └── auth.dart
```

### Backend

**Ответственность:**
- Data fetching & normalization
- Analytics calculations
- AI service integration
- API provision

**Структура:**
```
backend/
├── src/
│   ├── data/
│   │   ├── moex_iss.py
│   │   ├── edisclosure.py
│   │   └── storage.py
│   ├── analytics/
│   │   ├── valuation.py
│   │   ├── factors.py
│   │   └── dividends.py
│   ├── ai/
│   │   ├── remote_api.py
│   │   └── local_llm.py
│   └── api/
│       ├── rest.py
│       └── graphql.py
├── tests/
└── config/
```

### Data Layer

**Источники:**
1. **MOEX ISS** — цены, объёмы, дивиденды, индексы
2. **E-disclosure** — отчётность, факты, события
3. **RFSD** — раскрытие информации
4. **Company websites** — презентации, новости

**Хранение:**
- **PostgreSQL** — основные данные
- **Redis** — кэш горячих данных
- **File system** — сырые файлы, отчёты

### Analytics Layer

**Метрики:**
- Valuation: P/E, EV/EBITDA, P/S, P/B, percentiles
- Profitability: ROE, ROA, ROIC, margins
- Productivity: Asset turnover, inventory days
- Factors: Value, Quality, Momentum, Low Volatility
- Relative Strength vs index/peers
- Dividend: Yield, consistency, growth, payout ratio

### AI Layer

**Режимы:**
1. **Remote API** — OpenAI GPT, Anthropic Claude
2. **Local LLM** — Ollama, LM Studio (offline)

**Use Cases:**
- Summarization of reports
- Insight generation
- Q&A on company data
- Alert explanations

---

## Data Flow

```
[Data Sources] → [Data Fetcher] → [Normalizer] → [Storage]
                                              ↓
[User Request] → [API] → [Analytics Engine] → [Response]
                                              ↓
                                      [AI Service] → [Insights]
```

---

## Security Considerations

- API keys stored in environment variables
- No sensitive user data stored locally (Phase 1)
- HTTPS for all external communications
- Rate limiting on API endpoints

---

## Version History

| Version | Date       | Changes                          |
|---------|------------|----------------------------------|
| 1.0     | 2025-01-XX | Initial architecture with        |
|         |            | Multi-LLM process documentation  |
