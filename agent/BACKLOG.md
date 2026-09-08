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

- [ ] B9 — `doctor` does not check the raw store against the database:
  assert every `raw_object` row has its file on disk and every file under
  `raw/` has a row, and report drift in both directions with counts —
  accept: new test seeding one orphan row and one orphan file, `doctor`
  exits 1 naming both — size: M
- [ ] B10 — `watchlist show` cannot read a historical version from the
  CLI although `WatchlistRepo.members(version=…)` supports it: add
  `--version N` and make it print the version's action and members —
  accept: test asserting v1 members after a rollback created v3 — size: S
- [ ] B11 — CLI output ignores `NO_COLOR` and non-tty: if colour is ever
  added, gate it on both; until then add the test that asserts output is
  plain when stdout is a pipe — accept: subprocess test comparing piped
  output byte-for-byte with the expected plain text — size: S
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
