# Verification Protocol (Протокол Проверки)

## ⚠️ ОБЯЗАТЕЛЬНО ДЛЯ СЛЕДУЮЩЕЙ LLM

Этот документ описывает **обязательный протокол проверки**, который должна выполнить **каждая следующая LLM** перед началом своей задачи.

**НЕ НАЧИНАЙТЕ работу, пока не выполните все шаги этого протокола.**

---

## Цель Протокола

Обеспечить качество и соответствие работы предыдущей LLM требованиям проекта до начала новой разработки.

---

## Шаг 1: Проверка Существования Файлов

**Задача:** Убедиться, что все файлы предыдущей задачи существуют и соответствуют ТЗ.

### Чеклист для PHASE 0.1

Проверить наличие всех файлов в `/workspace/docs/`:

| № | Файл | Статус | Примечание |
|---|------|--------|------------|
| 00 | `00_MASTER_SPEC.md` | ⬜ | Master Specification |
| 01 | `01_PROJECT_STATUS.md` | ⬜ | Project Status |
| 02 | `02_ROADMAP.md` | ⬜ | Roadmap |
| 03 | `03_ARCHITECTURE.md` | ⬜ | Architecture |
| 04 | `04_DATA_MODEL.md` | ⬜ | Data Model |
| 05 | `05_ANALYTICS_MODEL.md` | ⬜ | Analytics Model |
| 06 | `06_DATA_SOURCES.md` | ⬜ | Data Sources |
| 07 | `07_AI_LAYER.md` | ⬜ | AI Layer |
| 08 | `08_FRONTEND.md` | ⬜ | Frontend |
| 09 | `09_DECISIONS.md` | ⬜ | ADRs |
| 10 | `10_KNOWN_ISSUES.md` | ⬜ | Known Issues |
| 11 | `11_CHANGELOG.md` | ⬜ | Changelog |
| 12 | `12_BACKLOG.md` | ⬜ | Backlog |
| 13 | `13_HARDWARE_STORAGE.md` | ⬜ | Hardware/Storage |
| 15 | `15_AGENT_RULES.md` | ⬜ | **Agent Rules (критично)** |
| 16 | `16_NEXT_TASK.md` | ⬜ | Next Task |
| 17 | `17_VERIFICATION_PROTOCOL.md` | ⬜ | **Этот файл** |

**Действие:**
- Если файл отсутствует → 🔴 **BLOCKED**, записать в `10_KNOWN_ISSUES.md`
- Если файл существует → отметить ✅ и перейти к проверке содержания

---

## Шаг 2: Проверка Содержания Файлов

**Задача:** Убедиться, что файлы содержат требуемую информацию.

### Критичные Файлы для Проверки

#### `15_AGENT_RULES.md`

Проверить наличие разделов:
- [ ] Правило "Одна LLM = Одна Задача"
- [ ] Список обязательных документов для чтения
- [ ] Запрет на платные источники данных
- [ ] Запрет на архитектуру "на вырост"
- [ ] Запрет на отклонения от архитектуры
- [ ] Обязанности после завершения задачи
- [ ] Процесс передачи следующей LLM

**Действие:**
- Если разделы отсутствуют → 🔴 **CRITICAL**, записать в `10_KNOWN_ISSUES.md`

#### `17_VERIFICATION_PROTOCOL.md`

Проверить наличие:
- [ ] Шаги проверки (этот файл)
- [ ] Чеклисты для каждой фазы
- [ ] Инструкция при обнаружении проблем

**Действие:**
- Если отсутствует → 🔴 **CRITICAL**, невозможно продолжить

#### `00_MASTER_SPEC.md`

Проверить:
- [ ] Описание проекта
- [ ] Multi-LLM Development Process раздел
- [ ] Ссылки на `15_AGENT_RULES.md` и `17_VERIFICATION_PROTOCOL.md`

#### `03_ARCHITECTURE.md`

Проверить:
- [ ] System Overview diagram
- [ ] Multi-LLM Development Process раздел
- [ ] Core Principles (Free Data, Total Return, Cross-Platform)

#### `08_FRONTEND.md`

Проверить:
- [ ] Явно указано: "один codebase для телефона и компьютера"
- [ ] Flutter как технология
- [ ] Поддержка Mobile + Desktop

---

## Шаг 3: Запуск Тестов (если есть)

**Задача:** Запустить все имеющиеся тесты и убедиться, что они проходят.

```bash
# Backend tests (если есть)
cd backend && pytest

# Frontend tests (если есть)
cd flutter_app && flutter test
```

**Статус:**
- ✅ Все тесты проходят
- ⏭️ Тестов нет (skip для PHASE 0.1)
- 🔴 Тесты не проходят → записать в `10_KNOWN_ISSUES.md`

---

## Шаг 4: Проверка Соответствия Архитектуре

**Задача:** Убедиться, что код (если есть) соответствует `03_ARCHITECTURE.md`, `04_DATA_MODEL.md`, `05_ANALYTICS_MODEL.md`.

### Чеклист

- [ ] Структура папок соответствует архитектуре
- [ ] Имена файлов и классов соответствуют конвенциям
- [ ] Нет лишних сущностей не из текущей фазы
- [ ] Нет преждевременных оптимизаций

**Действие:**
- Если найдены несоответствия → 🟠 **HIGH**, записать в `10_KNOWN_ISSUES.md`

---

## Шаг 5: Проверка на Платные Источники

**Задача:** Убедиться, что не появились платные источники данных.

### Методы Проверки

1. **Поиск по коду:**
```bash
grep -r "bloomberg" .
grep -r "reuters" .
grep -r "factset" .
grep -r "morningstar" .
grep -r "paid" .
```

2. **Проверка environment variables:**
```bash
grep -r "BLOOMBERG" .
grep -r "REUTERS_API" .
```

3. **Проверка зависимостей:**
```bash
# Python
cat requirements.txt | grep -i bloomberg

# Flutter
cat pubspec.yaml | grep -i bloomberg
```

**Действие:**
- Если найдены платные источники → 🔴 **CRITICAL**, немедленно заблокировать задачу

---

## Шаг 6: Проверка Ключевых Требований

### 6.1 Total Return Требование

Проверить, что в документации (`05_ANALYTICS_MODEL.md`) присутствует:
- [ ] Формула Total Return
- [ ] Учёт дивидендов в расчётах
- [ ] Adjusted Close метод

### 6.2 Free Data Only Требование

Проверить `06_DATA_SOURCES.md`:
- [ ] Перечислены ТОЛЬКО бесплатные источники
- [ ] Есть раздел "Prohibited Sources"
- [ ] MOEX ISS указан как основной источник

### 6.3 Cross-Platform Требование

Проверить `08_FRONTEND.md`:
- [ ] Явно указано: один codebase для Mobile и Desktop
- [ ] Flutter как технология
- [ ] Поддерживаемые платформы: iOS, Android, Windows, macOS, Linux

**Действие:**
- Если требования не соблюдены → 🔴 **CRITICAL** или 🟠 **HIGH**

---

## Шаг 7: Запись Результата Проверки

**Задача:** Задокументировать результат проверки.

### Обновить `01_PROJECT_STATUS.md`

Добавить запись в секцию "Verification Status":

```markdown
## Verification Status

| Check                                      | Status | Verified By | Date       |
|--------------------------------------------|--------|-------------|------------|
| Все файлы предыдущей задачи существуют     | ✅/❌  | [LLM Name]  | 2025-01-XX |
| Файлы соответствуют ТЗ                     | ✅/❌  | [LLM Name]  | 2025-01-XX |
| Тесты запущены и проходят                  | ✅/❌/⏭️| [LLM Name]  | 2025-01-XX |
| Соответствие архитектуре (03, 04, 05)      | ✅/❌  | [LLM Name]  | 2025-01-XX |
| Нет платных источников                     | ✅/❌  | [LLM Name]  | 2025-01-XX |
| Total Return требование соблюдено          | ✅/❌  | [LLM Name]  | 2025-01-XX |
| Cross-platform требование соблюдено        | ✅/❌  | [LLM Name]  | 2025-01-XX |
```

### Обновить `10_KNOWN_ISSUES.md`

Если найдены проблемы, добавить запись:

```markdown
### [PHASE-X.X-XXX] Описание проблемы

**Status:** 🔴 Open

**Description:** [Подробное описание]

**Found By:** [LLM Name]

**Severity:** Critical / High / Medium / Low

**Blocking:** Yes / No
```

---

## Шаг 8: Решение о Продолжении

### Если ВСЕ проверки пройдены (✅)

→ **Можно начинать работу над задачей из `16_NEXT_TASK.md`**

### Если есть проблемы (❌)

→ **НЕ НАЧИНАТЬ новую задачу**

**Действия:**
1. Задокументировать проблемы в `10_KNOWN_ISSUES.md`
2. Обновить `01_PROJECT_STATUS.md` со статусом "BLOCKED"
3. Ожидать исправления предыдущей LLM

---

## Шаблон Отчёта о Проверке

```markdown
# Verification Report — PHASE X.X

**Verified By:** [LLM Name]
**Date:** 2025-01-XX
**Phase Verified:** PHASE X.X

## Summary

| Category | Status | Notes |
|----------|--------|-------|
| Files Existence | ✅/❌ | |
| File Content | ✅/❌ | |
| Tests | ✅/❌/⏭️ | |
| Architecture Compliance | ✅/❌ | |
| No Paid Sources | ✅/❌ | |
| Key Requirements | ✅/❌ | |

## Issues Found

[Список проблем если есть]

## Recommendation

[Can proceed / Blocked pending fixes]
```

---

## Верификация для Конкретных Фаз

### PHASE 0.1 Verification

- Фокус на наличии и качестве всех документов
- Проверка `15_AGENT_RULES.md` и `17_VERIFICATION_PROTOCOL.md`
- Тесты: N/A (skip)

### PHASE 0.2 Verification

- Наличие структуры проекта
- CI/CD настроен
- Тесты запускаются

### PHASE 1.x Verification

- Data fetching работает
- Кэширование реализовано
- Тесты покрывают основные сценарии

### PHASE 2.x Verification

- Метрики рассчитываются корректно
- Factor scores работают
- Юнит-тесты >80% coverage

### PHASE 3.x Verification

- AI интеграция работает
- Prompt templates тестированы
- Rate limiting реализован

### PHASE 4.x Verification

- UI рендерится на всех платформах
- Responsive layouts работают
- Integration tests проходят

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial verification protocol |
