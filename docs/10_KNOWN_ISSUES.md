# Known Issues

## Overview

Этот документ отслеживает известные проблемы, ограничения и технические долги проекта.

---

## Issue Status Legend

| Status | Description |
|--------|-------------|
| 🔴 Open | Проблема активна, требует решения |
| 🟡 In Progress | В работе |
| 🟢 Resolved | Решена, ожидает закрытия |
| ⚪ Closed | Полностью закрыта |
| ⚪ Won't Fix | Не будет исправлена |

---

## Current Issues

### [PHASE-0.1-001] Documentation Completeness

**Status:** 🟢 Resolved

**Description:** Все документы `00`–`17` должны быть созданы и заполнены для PHASE 0.1.

**Impact:** Без полной документации следующая LLM не сможет начать работу.

**Workaround:** N/A

**Resolution:** Все документы созданы в PHASE 0.1.

**Closed By:** Phase 0.1 Completion

---

### [DATA-001] MOEX ISS Rate Limiting

**Status:** 🔴 Open

**Description:** MOEX ISS может применять rate limiting при частых запросах.

**Impact:** Возможны временные недоступности данных при интенсивном использовании.

**Workaround:** 
- Использовать кэширование
- Implement exponential backoff
- Batch requests where possible

**Target Phase:** 1.1

---

### [DATA-002] E-Disclosure Parsing Complexity

**Status:** 🔴 Open

**Description:** E-disclosure.ru требует парсинга HTML, структура может меняться.

**Impact:** Хрупкость data fetching, требуется постоянная поддержка.

**Workaround:**
- Использовать stable selectors
- Monitor for structure changes
- Have fallback sources

**Target Phase:** 1.2

---

### [ANALYTICS-001] Historical Data Gaps

**Status:** 🔴 Open

**Description:** Для некоторых акций могут отсутствовать исторические данные за длительные периоды.

**Impact:** Невозможность расчёта долгосрочных метрик (5Y+).

**Workaround:**
- Показывать доступный период
- Предупреждать пользователя
- Использовать proxy metrics

**Target Phase:** 2.1

---

### [AI-001] Local LLM Quality Variance

**Status:** 🔴 Open

**Description:** Локальные LLM (Ollama, etc.) могут давать менее качественные ответы vs remote API.

**Impact:** inconsistency в AI insights между режимами.

**Workaround:**
- Clearly indicate which model was used
- Provide confidence scores
- Allow user to switch models

**Target Phase:** 3.2

---

### [AI-002] Russian Language Support

**Status:** 🟡 In Progress

**Description:** Некоторые модели могут хуже работать с русским языком.

**Impact:** Качество AI-инсайтов на русском может варьироваться.

**Workaround:**
- Use models with good multilingual support
- Test prompts thoroughly
- Provide English fallback option

**Target Phase:** 3.1

---

### [FRONTEND-001] Desktop Layout Optimization

**Status:** 🔴 Open

**Description:** Адаптация UI под большие экраны desktop требует дополнительной работы.

**Impact:** Suboptimal UX на desktop без proper layouts.

**Workaround:**
- Use responsive breakpoints
- Test on multiple screen sizes
- Implement adaptive grids

**Target Phase:** 4.3

---

### [PERF-001] Initial Load Performance

**Status:** 🔴 Open

**Description:** Первая загрузка приложения может быть медленной из-за fetch данных.

**Impact:** Poor first impression for users.

**Workaround:**
- Pre-cache essential data
- Show skeleton loaders
- Lazy load non-critical data

**Target Phase:** 4.1

---

### [SEC-001] API Key Exposure Risk

**Status:** 🟢 Resolved

**Description:** Риск accidental commit API keys в репозиторий.

**Impact:** Compromised API credentials.

**Resolution:**
- Keys stored in environment variables only
- Added `.env` to `.gitignore`
- Documented in `07_AI_LAYER.md`

**Closed By:** Security guidelines documentation

---

## Technical Debt

| ID | Description | Priority | Target Phase |
|----|-------------|----------|--------------|
| TD-001 | Add comprehensive error handling | High | 0.2 |
| TD-002 | Implement structured logging | Medium | 0.2 |
| TD-003 | Add performance monitoring | Low | 5.1 |
| TD-004 | Write integration tests | High | 5.1 |

---

## Limitations

### Current System Limitations

1. **Data Coverage:** Только российские акции (MOEX)
2. **Update Frequency:** Near real-time, но не真正的 real-time
3. **AI Capabilities:** Basic insights, не financial advice
4. **Platforms:** Mobile + Desktop, Web отложен
5. **Languages:** Русский + English (partial)

### Future Considerations

- Расширение на другие рынки (CIS, emerging markets)
- Real-time data через WebSocket
- Advanced AI features (portfolio optimization)
- Web version
- Full localization

---

## Reporting New Issues

При обнаружении новой проблемы:

1. Создать запись в этом документе
2. Присвоить ID в формате `[CATEGORY-XXX]`
3. Описать проблему, impact, workaround
4. Назначить приоритет и target phase
5. Обновлять статус по мере прогресса

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial known issues doc   |
