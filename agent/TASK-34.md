# TASK-34 — N4: извлечение проверено моделью, а не надеждой

- **Status: READY**
- **Report:** `agent/REPORT-34.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network 0; **model 80 calls, free models only**.
- **Goal in one sentence:** TASK-24 N4 was blocked on the model key —
  the four recorded table shapes go through the real pipeline and the
  audit says, in numbers, how often stage ③ catches the model.

**Scope is the text of TASK-24 N4 as written.**

## Items

### F1. Прогон четырёх форм таблиц

`tests/data/n4_fleet_tables/` — clean two-column, ten-column, with a
total row, with a footnote inside a number.

**Done when:** each is run through extract → model → deterministic
control; the report states per table: extracted records, `verified`,
`near_miss`, `failed`, and the model calls spent.

### F2. Проверенно-но-неверно измерено, а не предположено

**Done when:** the report names every case where the control passed a
record whose value is wrong against the table read by eye, or states
zero such cases with the evidence; a `verified=no` record is stored,
shown, and absent from every formula (asserted by an existing test).

### F3. Стоимость названа

**Done when:** the model calls used are counted in `STATE.json` and the
report states calls per table and the free-tier limit they ran against
(ADR-0018: the budget is requests, not money).

### F4. Фикстура ответа модели попадает в набор

**Done when:** one recorded model response is committed under
`tests/data/` and an offline test replays the whole pipeline on it, so
the path stays covered on a machine with no key.

### F5. Место `extract_text` перестаёт быть обойдённой дверью

Question 3 of `agent/REPORT-22.md`, ruled by the coordinator: **wire it
through.** `rusterm/manual/__init__.py:extract_text` still answers
`format_unsupported: manual_extract_not_implemented` while the real
implementation lives in `rusterm/manual/extract.py` and the pipeline
already uses it. A door built and then bypassed is the TASK-19 F6
defect, and it is closed the same way.

**Done when:** `extract_text` delegates to the real implementation; the
pin that asserted the refusal is **replaced by a stricter one** (the
seat returns what the implementation returns, on the committed
fixtures), and the report quotes both the old and the new assertion.
