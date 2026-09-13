# TASK-39 — N7, австралийская половина: `ingest --source asx`

- **Status: READY**
- **Report:** `agent/REPORT-39.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **30 requests** to `asx.api.markitdigital.com`
  at 1/s; model 0.
- **Goal in one sentence:** the honest half of TASK-27 N7 — AU collects
  announcements and header metadata, says so, and invents no
  fundamentals channel.

**Scope is the AU half of TASK-27 N7 as written.** ADR-0010 §5 records
that ASX has no fundamentals contract; ADR-0018 forbids buying the paid
ASX DataAPI to get one.

## Items

### K1. Раскрытия доезжают

**Done when:** `ingest --source asx` writes `document` rows with
provenance for one issuer; the trimmed payload is committed under
`tests/data/asx/`; an offline test replays it.

### K2. Фактов нет, и это сказано вслух

**Done when:** the fact path returns the existing named refusal —
`manual_import_required` — never an empty success; asserted by a test;
the PDF route is manual import, which already exists, and no scraper is
written here.

### K3. Экран и покрытие не врут об AU

**Done when:** `coverage` for the AU issuer shows documents present and
measures missing with the reason; the report pastes it.
