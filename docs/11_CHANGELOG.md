# Changelog

## Overview

История всех значимых изменений проекта RusEquity Terminal.

Формат основан на [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added
- Initial project documentation structure
- Multi-LLM development process
- Verification protocol for LLM handoff
- Agent rules for LLM contributors

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- API key management guidelines documented

---

## [0.1.0] - 2025-01-XX

### Added — PHASE 0.1: Documentation & Structure Setup

#### Documentation Files Created

| File | Description |
|------|-------------|
| `00_MASTER_SPEC.md` | Общее описание проекта, Multi-LLM процесс |
| `01_PROJECT_STATUS.md` | Текущий статус проекта |
| `02_ROADMAP.md` | Дорожная карта с фазами (0.1–5.2) |
| `03_ARCHITECTURE.md` | Архитектура системы, компонентная модель |
| `04_DATA_MODEL.md` | Модель данных, сущности, relationships |
| `05_ANALYTICS_MODEL.md` | Модель аналитики, метрики, factor scores |
| `06_DATA_SOURCES.md` | Источники данных (free only), guidelines |
| `07_AI_LAYER.md` | AI-слой, remote API + local LLM |
| `08_FRONTEND.md` | Frontend архитектура (Flutter) |
| `09_DECISIONS.md` | Architecture Decision Records (ADR) |
| `10_KNOWN_ISSUES.md` | Известные проблемы и technical debt |
| `11_CHANGELOG.md` | Этот файл |
| `12_BACKLOG.md` | Бэклог задач |
| `13_HARDWARE_STORAGE.md` | Требования к хранению данных |
| `15_AGENT_RULES.md` | **Критично:** Правила для LLM-агентов |
| `16_NEXT_TASK.md` | Следующая задача для LLM |
| `17_VERIFICATION_PROTOCOL.md` | **Критично:** Протокол проверки между LLM |

#### Key Features Documented

- **Multi-LLM Development Process**
  - Одна LLM = одна фаза
  - Обязательная проверка следующей LLM
  - Запрет платных источников
  - Запрет архитектуры «на вырост»

- **Project Roadmap**
  - PHASE 0: Foundation (0.1, 0.2)
  - PHASE 1: Data Layer (1.1, 1.2)
  - PHASE 2: Analytics Layer (2.1, 2.2, 2.3)
  - PHASE 3: AI Layer (3.1, 3.2)
  - PHASE 4: Frontend (4.1, 4.2, 4.3)
  - PHASE 5: Polish & Release (5.1, 5.2)

- **Architecture Principles**
  - Free data sources only
  - Total Return calculation
  - Cross-platform Flutter frontend
  - Expandable to Bloomberg-class

- **Analytics Model**
  - Valuation metrics with percentiles
  - Factor scores (Value, Quality, Momentum, Low Volatility)
  - Relative Strength analysis
  - Dividend consistency scoring

- **AI Layer**
  - Remote API support (OpenAI, Anthropic)
  - Local LLM support (Ollama, LM Studio)
  - Prompt templates
  - Response caching

### Changed
- Updated `README.md` with project description

### Fixed
- N/A

### Security
- Documented API key management best practices
- Added `.env` to recommended `.gitignore`

---

## Version History Summary

| Version | Date       | Phase         | Focus                    |
|---------|------------|---------------|--------------------------|
| 0.1.0   | 2025-01-XX | PHASE 0.1     | Documentation Setup      |
| 0.2.0   | TBD        | PHASE 0.2     | Project Skeleton         |
| 1.0.0   | TBD        | PHASE 1.x     | Data Layer               |
| 2.0.0   | TBD        | PHASE 2.x     | Analytics Layer          |
| 3.0.0   | TBD        | PHASE 3.x     | AI Layer                 |
| 4.0.0   | TBD        | PHASE 4.x     | Frontend                 |
| 5.0.0   | TBD        | PHASE 5.x     | Release                  |

---

## Contributing (LLM Agents)

При внесении изменений в changelog:

1. Добавляйте запись в `[Unreleased]` секцию
2. Используйте категории: Added, Changed, Deprecated, Removed, Fixed, Security
3. Указывайте номер фазы/задачи если применимо
4. При релизе перемещайте `[Unreleased]` в версию с датой

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial changelog          |
