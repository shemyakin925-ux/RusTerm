# Next Task (Следующая Задача)

## ⚠️ Важно

Этот файл содержит задачу для **текущей/следующей LLM**.

**НЕ начинайте работу, пока не прочитали:**
- `00_MASTER_SPEC.md`
- `03_ARCHITECTURE.md`
- `15_AGENT_RULES.md`
- `17_VERIFICATION_PROTOCOL.md`

---

## Текущая Задача: PHASE 0.1 — Documentation & Structure Setup

**Статус:** ✅ COMPLETE

**Описание:** Привести документацию и структуру репозитория в соответствие с multi-LLM Verification Protocol.

### Выполненные Подзадачи

- [x] Создать `00_MASTER_SPEC.md` — Master Specification
- [x] Создать `01_PROJECT_STATUS.md` — Project Status
- [x] Создать `02_ROADMAP.md` — Roadmap с фазами
- [x] Создать `03_ARCHITECTURE.md` — Architecture documentation
- [x] Создать `04_DATA_MODEL.md` — Data Model
- [x] Создать `05_ANALYTICS_MODEL.md` — Analytics Model
- [x] Создать `06_DATA_SOURCES.md` — Data Sources (free only)
- [x] Создать `07_AI_LAYER.md` — AI Layer specification
- [x] Создать `08_FRONTEND.md` — Frontend architecture (Flutter)
- [x] Создать `09_DECISIONS.md` — Architecture Decision Records
- [x] Создать `10_KNOWN_ISSUES.md` — Known Issues
- [x] Создать `11_CHANGELOG.md` — Changelog
- [x] Создать `12_BACKLOG.md` — Backlog
- [x] Создать `13_HARDWARE_STORAGE.md` — Hardware & Storage requirements
- [x] Создать `15_AGENT_RULES.md` — Agent Rules (критично!)
- [x] Создать `16_NEXT_TASK.md` — Этот файл
- [x] Создать `17_VERIFICATION_PROTOCOL.md` — Verification Protocol (критично!)
- [x] Обновить `README.md` — Описание проекта

### Критерии Приёмки

- [x] Все файлы существуют в `/workspace/docs/`
- [x] `15_AGENT_RULES.md` написан жёстко и однозначно
- [x] `17_VERIFICATION_PROTOCOL.md` содержит чёткий протокол проверки
- [x] Любая следующая LLM может понять:
  - что уже сделано
  - какие правила действуют
  - как проверять предыдущую работу
  - какую задачу делать следующей

### Следующая Задача (для следующей LLM)

**PHASE 0.2 — Project Skeleton**

После успешной проверки PHASE 0.1, следующая LLM должна выполнить:

```markdown
## PHASE 0.2 — Project Skeleton

**Задача:** Создать базовую структуру проекта (Flutter + Backend).

**Deliverables:**
- [ ] Инициализировать Flutter проект
- [ ] Инициализировать Backend проект (Python)
- [ ] Настроить структуру папок согласно архитектуре
- [ ] Настроить CI/CD pipeline (GitHub Actions)
- [ ] Настроить pre-commit hooks
- [ ] Добавить базовый framework для тестов
- [ ] Создать `.gitignore`
- [ ] Добавить LICENSE файл
- [ ] Настроить dependency management

**Критерии приёмки:**
- `flutter create` выполнен успешно
- Backend framework инициализирован
- Тесты запускаются (даже пустые)
- CI pipeline проходит

**Файлы для обновления:**
- `01_PROJECT_STATUS.md` — обновить статус
- `11_CHANGELOG.md` — добавить запись
- `12_BACKLOG.md` — отметить выполненные задачи
```

---

## Для Проверки (Verification)

Следующая LLM должна выполнить проверку по `17_VERIFICATION_PROTOCOL.md`:

1. ✅ Проверить, что все файлы существуют
2. ✅ Проверить соответствие ТЗ
3. ⏭️ Запустить тесты (пока нет — skip)
4. ✅ Проверить соответствие архитектуре
5. ✅ Проверить отсутствие платных источников
6. ✅ Проверить Total Return и cross-platform требования
7. ✅ Записать результат в `01_PROJECT_STATUS.md` и `10_KNOWN_ISSUES.md`

---

## Контакты и Вопросы

При возникновении вопросов:
1. Проверьте документацию
2. Запишите вопрос в `10_KNOWN_ISSUES.md`
3. При необходимости создайте ADR в `09_DECISIONS.md`

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial task definition    |
