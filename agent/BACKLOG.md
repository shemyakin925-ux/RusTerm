# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file. The executor never edits
this file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

## Queue

- [ ] B12 — the audit JSONL has no failure path of its own: if
  `logs/audit.jsonl` cannot be written (read-only dir, full disk), the
  operation currently raises through. Return an error value and still
  attempt the DB write, so one destination's loss does not take the
  other — accept: test with a read-only log dir asserting the DB row
  exists and the failure is reported, not raised — size: M
- [ ] B13 — `export --format md`: a snapshot as a Markdown table for
  reading in a terminal or pasting into notes, null values as `—` with
  the reason in a footnote — accept: test asserting every null carries
  its reason and no number appears without a period — size: M
- [ ] B15 — the null-reason vocabulary is spread across `formulas.py`,
  `snapshot.py` and `coverage`: collect the allowed strings in one place
  and add a guard test asserting no measure row is ever written with a
  reason outside it — accept: test that seeds an unknown reason and
  fails — size: M
- [ ] B17 — `EdgarProvider.resolve()` is the only resolver, and nothing
  asserts what it does with a ticker that maps to two CIKs (a class
  change, a re-listing): pin the behaviour with a test on a hand-built
  two-row ticker map — accept: test asserting the documented outcome,
  whichever it is, and a docstring line stating it — size: S
- [ ] B18 — `tools/` has no test of its own beyond TASK-10 W1's: if a
  second dev tool lands there, add a one-line README in `tools/` saying
  what belongs there and that nothing under it is imported by the
  application — accept: `tools/README.md` exists and acceptance stays
  13/13 — size: S
- [ ] B19 — `logs/app.log` gets a traceback for every internal error but
  nothing rotates it; cap it at a size and roll one file over — accept:
  test writing past the cap and asserting exactly two files exist and the
  newest holds the last line — size: M

## Done

- [x] B1 — invariant numbering contiguity guard — TASK-7, verified 08.09
- [x] B2 — fixtures are synthetic, as a test — TASK-7, verified 08.09
- [x] B3 — job-queue idempotency on a second run — TASK-7, verified 08.09
- [x] B4 — second golden issuer with preferred class — TASK-7, verified 08.09
- [x] B5 — `price_adj` split/dividend order independence — TASK-7,
  verified 08.09 (first commit was red, fixed in the next one)
- [x] B6 — `doctor` reports schema drift, test added — TASK-7, verified 08.09
- [x] B7 — coverage blocks doc/code drift guard — TASK-7, verified 08.09
- [x] B8 — zstd branch covered by a fake module — TASK-7, verified 08.09
- [x] B14 — two AAPL payloads: folded into TASK-10 W2/W7 as a task item,
  removed from the queue 09.09
- [x] B9 — doctor сверяет raw store с базой в обе стороны — TASK-11 X5, проверено 09.09
- [x] B10 — watchlist show --version N — TASK-11 X5, проверено 09.09
- [x] B11 — вывод в pipe без ANSI, тест — TASK-11 X5, проверено 09.09
- [x] B16 — схема ключей четырёх --json команд закреплена — TASK-11 X5, проверено 09.09
