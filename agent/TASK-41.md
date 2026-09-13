# TASK-41 — Проект перестаёт врать о собственном состоянии

- **Status: READY** — take it last; it measures what the shifts before
  it built.
- **Report:** `agent/REPORT-41.md`
- **Protocol:** `agent/PROTOCOL.md`. State: `agent/CONTEXT.md`.
- **Budgets:** network **60 requests** across hosts; model 0.
- **Goal in one sentence:** three milestones were declared on offline
  branches (M9 with no vendor rows, M11 with every indicator grey, M12
  with no screen); tonight each is either proven on the real path or
  demoted in writing, and the MVP criterion is run end to end.

## Items

### M1. Вехи проверяются доказательствами, а не намерением

**Done when:** for M9, M11, M12 the report states, one line each: the
milestone's own acceptance sentence from its task, the command that
demonstrates it today, and the verdict `достигнута` / `не достигнута`.
A milestone whose evidence does not run is written down as not reached —
that is the deliverable, not a failure of the night.

### M2. Критерий MVP прогоняется целиком

README §15: «по любому тикеру US / CA снапшот собирается за один
проход, каждое число кликабельно до первоисточника, watchlist на 500
бумаг обновляется по расписанию без ручных действий».

**Done when:** the report holds one run per clause — a fresh US ticker
and a fresh CA ticker end to end with their measure counts; a sample of
five numbers traced from the screen to the source document by locator;
a watchlist refresh pass with its request count and the number of
instruments it would need to cover 500. Every clause gets `выполняется`
or a named gap.

### M3. README и GUIDE приводятся в соответствие

**Done when:** §15's milestone table matches M1's verdicts; the coverage
line (US 10/10, CA 3/10, OTC 3/10 at the time of writing) is stated as
measured today; `tests/test_docs_truth.py` stays green, so no
hand-typed count of the repository appears anywhere.

### M4. `agent/CONTEXT.md` обновляется последним

**Done when:** §4 «Where the product actually is» and §5 of
`agent/CONTEXT.md` carry tonight's measured numbers, so the next shift
reads one file instead of six reports.
