# Architecture Decision Records (ADR)

## Overview

Этот документ содержит все архитектурные решения, принятые в проекте RusEquity Terminal.

Любое отклонение от утверждённой архитектуры должно быть зафиксировано здесь через ADR.

---

## ADR Template

```markdown
### ADR-XXX: [Title]

**Date:** YYYY-MM-DD

**Status:** Proposed | Accepted | Rejected | Deprecated

**Context:** 
Описание проблемы или ситуации, требующей решения.

**Decision:** 
Какое решение было принято.

**Consequences:** 
Последствия решения (положительные и отрицательные).

**Compliance:** 
Как решение будет проверяться.
```

---

## ADR Log

### ADR-001: Multi-LLM Development Process

**Date:** 2025-01-XX

**Status:** Accepted

**Context:**
Проект должен разрабатываться поэтапно разными LLM с обязательной перепроверкой друг друга. Необходимо определить правила и процессы для такого режима работы.

**Decision:**
Внедрить Multi-LLM Development Process со следующими правилами:
1. Одна LLM = одна атомарная задача/фаза
2. Обязательное чтение документации перед началом работы
3. Запрет на платные источники данных
4. Запрет на архитектуру «на вырост»
5. Обязательная проверка следующей LLM по протоколу
6. Обновление статус-документов после каждой задачи

**Consequences:**
- ✅ Более контролируемый процесс разработки
- ✅ Каждая фаза легко проверяема
- ⚠️ Требуется строгая дисциплина документации
- ⚠️ Может замедлить разработку из-за overhead проверки

**Compliance:**
- Проверка через `17_VERIFICATION_PROTOCOL.md`
- Статус отслеживается в `01_PROJECT_STATUS.md`

---

### ADR-002: Flutter for Cross-Platform Frontend

**Date:** 2025-01-XX

**Status:** Accepted

**Context:**
Требуется единый codebase для мобильных и десктопных платформ. Необходимо выбрать технологию.

**Decision:**
Использовать Flutter для frontend-разработки.

**Consequences:**
- ✅ Единый codebase для iOS, Android, Windows, macOS, Linux
- ✅ Хорошая производительность
- ✅ Богатая экосистема пакетов
- ⚠️ Web support менее зрелый (отложен до Phase 4+)
- ⚠️ Требует знания Dart

**Compliance:**
- Архитектура описана в `08_FRONTEND.md`
- Проверка через тесты и сборку для всех таргетов

---

### ADR-003: Free Data Sources Only

**Date:** 2025-01-XX

**Status:** Accepted

**Context:**
Проект должен использовать только бесплатные источники данных для обеспечения доступности и независимости.

**Decision:**
Использовать исключительно бесплатные источники:
- MOEX ISS
- E-disclosure.ru
- RFSD
- Сайты эмитентов
- ЦБ РФ
- Росстат

**Запрещено:** Bloomberg, Reuters, FactSet, любые платные API.

**Consequences:**
- ✅ Полностью бесплатный продукт
- ✅ Независимость от вендоров
- ⚠️ Ограничения в качестве/скорости данных
- ⚠️ Требуется парсинг некоторых источников
- ⚠️ Необходим careful rate limiting

**Compliance:**
- Источники задокументированы в `06_DATA_SOURCES.md`
- Проверка через code review на наличие платных API ключей

---

### ADR-004: Total Return Calculation Method

**Date:** 2025-01-XX

**Status:** Accepted

**Context:**
Необходимо стандартизировать расчёт доходности с учётом дивидендов.

**Decision:**
Использовать метод Adjusted Close для расчёта Total Return:
```
Total Return = (AdjustedClose_end - AdjustedClose_start) / AdjustedClose_start
```

Где Adjusted Close учитывает дивиденды и сплиты.

**Consequences:**
- ✅ Упрощённый расчёт
- ✅ Стандартная индустриальная практика
- ⚠️ Требуется корректный расчёт adjustment factors
- ⚠️ Исторические данные могут потребовать пересчёта

**Compliance:**
- Формула в `05_ANALYTICS_MODEL.md`
- Тесты на корректность расчёта

---

### ADR-005: Backend Language Choice

**Date:** 2025-01-XX

**Status:** Proposed

**Context:**
Необходимо выбрать язык для backend-разработки.

**Decision:**
Использовать Python для backend:
- Богатые возможности для data processing
- Отличные библиотеки для финансов (pandas, numpy)
- Простота интеграции с AI/ML
- Быстрая разработка

**Consequences:**
- ✅ Быстрая разработка
- ✅ Отличная экосистема для analytics
- ✅ Простая интеграция с AI
- ⚠️ Меньшая производительность vs Go/Rust
- ⚠️ GIL limitations для CPU-bound tasks

**Compliance:**
- Архитектура в `03_ARCHITECTURE.md`
- Code style через pre-commit hooks

---

## Pending Decisions

| ID | Topic | Status | Target Phase |
|----|-------|--------|--------------|
| ADR-006 | Database choice (PostgreSQL vs TimescaleDB) | Proposed | 0.2 |
| ADR-007 | Caching strategy (Redis vs in-memory) | Proposed | 0.2 |
| ADR-008 | API style (REST vs GraphQL) | Proposed | 0.2 |

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial ADR document       |
