# Roadmap

## Overview

Проект разбит на маленькие, проверяемые фазы. Каждая фаза выполнима одной LLM и легко проверяема следующей.

---

## PHASE 0 — Foundation

### PHASE 0.1 — Documentation & Structure Setup (CURRENT)

**Задача:** Привести документацию и структуру репозитория в соответствие с multi-LLM Verification Protocol.

**Deliverables:**
- [x] Создать все документы (`00`–`17`)
- [x] `15_AGENT_RULES.md` — правила для LLM-агентов
- [x] `17_VERIFICATION_PROTOCOL.md` — протокол проверки
- [x] `16_NEXT_TASK.md` — следующая задача
- [x] Обновить `README.md`

**Критерии приёмки:**
- Все файлы существуют и заполнены
- Правила однозначны и исполнимы
- Следующая LLM может начать работу

**Status:** ✅ Complete

---

### PHASE 0.2 — Project Skeleton

**Задача:** Создать базовую структуру проекта (Flutter + Backend).

**Deliverables:**
- [ ] Flutter project structure
- [ ] Backend folder structure (Python/Go)
- [ ] Basic CI/CD pipeline
- [ ] Pre-commit hooks
- [ ] Initial tests setup

**Критерии приёмки:**
- `flutter create` выполнен
- Backend framework инициализирован
- Тесты запускаются (даже пустые)

**Status:** ⏳ Pending

---

## PHASE 1 — Data Layer

### PHASE 1.1 — MOEX ISS Integration

**Задача:** Реализовать подключение к MOEX ISS API.

**Deliverables:**
- [ ] MOEX ISS client
- [ ] Исторические данные (цены, объёмы)
- [ ] Дивидендная история
- [ ] Кэширование данных

**Критерии приёмки:**
- Данные загружаются и сохраняются
- Total Return рассчитывается корректно
- Тесты покрывают основные сценарии

**Status:** ⏳ Pending

---

### PHASE 1.2 — Additional Free Sources

**Задача:** Интеграция e-disclosure, RFSD, сайтов эмитентов.

**Deliverables:**
- [ ] E-disclosure parser
- [ ] RFSD data fetcher
- [ ] Company website scraper (если доступно)

**Критерии приёмки:**
- Все источники бесплатные
- Данные нормализованы
- Обработка ошибок реализована

**Status:** ⏳ Pending

---

## PHASE 2 — Analytics Layer

### PHASE 2.1 — Valuation Metrics

**Задача:** Расчёт valuation percentiles, P/E, EV/EBITDA и др.

**Deliverables:**
- [ ] Valuation calculations
- [ ] Percentile ranking
- [ ] Historical comparison

**Status:** ⏳ Pending

---

### PHASE 2.2 — Factor Analysis

**Задача:** ROIC, productivity, factor scores.

**Deliverables:**
- [ ] ROIC calculation
- [ ] Productivity metrics
- [ ] Factor scoring system

**Status:** ⏳ Pending

---

### PHASE 2.3 — Relative Strength & Dividends

**Задача:** Relative strength, dividend consistency.

**Deliverables:**
- [ ] Relative strength indicator
- [ ] Dividend consistency score
- [ ] Dividend yield forecasting

**Status:** ⏳ Pending

---

## PHASE 3 — AI Layer

### PHASE 3.1 — Remote AI API Integration

**Задача:** Подключение remote LLM API.

**Deliverables:**
- [ ] OpenAI/Anthropic API client
- [ ] Prompt templates
- [ ] Response parsing

**Status:** ⏳ Pending

---

### PHASE 3.2 — Local LLM Support

**Задача:** Поддержка локальной LLM (Ollama, LM Studio).

**Deliverables:**
- [ ] Local LLM client
- [ ] Model selection UI
- [ ] Offline mode

**Status:** ⏳ Pending

---

## PHASE 4 — Frontend

### PHASE 4.1 — Core UI Components

**Задача:** Базовые UI компоненты Flutter.

**Deliverables:**
- [ ] Stock list view
- [ ] Stock detail view
- [ ] Charts integration

**Status:** ⏳ Pending

---

### PHASE 4.2 — Analytics Dashboard

**Задача:** Панель аналитики.

**Deliverables:**
- [ ] Valuation dashboard
- [ ] Factor analysis view
- [ ] AI insights panel

**Status:** ⏳ Pending

---

### PHASE 4.3 — Mobile Optimization

**Задача:** Адаптация под мобильные устройства.

**Deliverables:**
- [ ] Responsive layouts
- [ ] Touch gestures
- [ ] Mobile-specific features

**Status:** ⏳ Pending

---

## PHASE 5 — Polish & Release

### PHASE 5.1 — Testing & QA

**Задача:** Полное тестирование.

**Deliverables:**
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests
- [ ] E2E tests

**Status:** ⏳ Pending

---

### PHASE 5.2 — Release Preparation

**Задача:** Подготовка к релизу.

**Deliverables:**
- [ ] Documentation complete
- [ ] Performance optimization
- [ ] Security audit

**Status:** ⏳ Pending

---

## Version History

| Version | Date       | Changes                          |
|---------|------------|----------------------------------|
| 1.0     | 2025-01-XX | Initial roadmap with phases      |
