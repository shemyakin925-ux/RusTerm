# BACKLOG — pre-approved small tasks for idle executor time

Maintained by the coordinator (Claude). The executor pulls items
top-down **only** when the main `agent/TASK-*.md` queue is empty, and
reports each pulled item in its report file.

## Item format

```
- [ ] <ID> — <one-line objective> — accept: <command or check> — size: <S/M/L>
```

**Closing an item moves the whole block.** Every continuation line of a
bullet belongs to that bullet: either move the whole block into `## Done`
and collapse it to one `- [x]` line, or delete the whole block and write
the `- [x]` line. Deleting only a bullet's first line leaves orphaned
prose in the queue — that happened on 09.09 and the coordinator repaired
it by hand.

Two ID namespaces, so parallel edits do not collide on one counter:
**B** — coordinator items, **R** — defects found by outside reviews and
re-verified by running them. Numbers are never reused within a namespace.

## Queue

- [ ] B20 — `refresh` counts requests in two places: `RefreshResult.calls`
  per instrument and the `requests` totals the CLI sums for `--json`.
  Nothing asserts they agree — add a test that the totals equal the sum
  over `results` for both a normal and a mixed (error) pass — accept:
  test asserting the two agree on a pass with one erroring instrument —
  size: S
- [ ] B21 — `IssuerStateRepo.get` returns `None` for an unknown issuer
  and for an issuer whose row exists under another source; only the first
  is covered. Pin the second once the key is composite — accept: test
  reading `source='synthetic'` for an issuer that has only an `edgar` row
  — size: S
- [ ] B22 — the 1100-day eligibility constant lives in
  `rusterm/core/snapshot.py` and appears in three docstrings and two
  tests as a literal. Name it once and reference it — accept: `grep -rn
  '1100' rusterm/ tests/` shows the constant's definition and no other
  literal in `rusterm/` — size: S
- [ ] B23 — `tools/trim_companyfacts.py` has no test that the output is
  byte-stable across two runs on the same input, although the docstring
  now promises it — accept: test trimming one recorded payload twice and
  comparing sha256 — size: S
- [ ] B24 — `logs/app.log` rotation caps size but nothing caps the audit
  JSONL, which only grows; apply the same cap and rollover to it —
  accept: test writing past the cap and asserting exactly two files, the
  newest holding the last line — size: M
- [ ] B25 — `rusterm status --json` does not report the schema version
  the database is actually at, only the one the code expects; a database
  behind its code is invisible until `doctor` runs — add the observed
  version beside the expected one — accept: test asserting both keys and
  that they differ on a deliberately old database — size: S

### Review findings (namespace R)

Found by outside reviewers, each re-verified by running it against
`agent/night-2` at `b90ac14` (303 passed, 2 skipped, 2 xfailed).
All nine still reproduce.

- [ ] R1 — `effective_tax_rate` computes a rate on a loss: the docstring
  says `pretax_income <= 0` -> jurisdiction rate, the code only tests
  `== 0`. `(-100, -1000)` -> `0.1`; `(100, -1000)` -> `0.0`, because
  `clip` floors at zero — a plausible-looking 0% that raises no
  suspicion. The rate feeds NOPAT, NOPAT feeds ROIC — accept: both
  pairs return null with a reason, test green — size: S
- [ ] R2 — margins accept a negative denominator: `gross_margin`,
  `operating_margin`, `net_margin` test `revenue == 0`, while the data
  dictionary requires null for a denominator `<= 0`.
  `gross_margin(10, -100)` -> `-0.1`, whereas `roic(10, -1, -1)` in the
  same module returns `(None, 'negative_denominator')` — accept: all
  three return `negative_denominator`, test green — size: S
- [ ] R3 — `calculate_measure("invested_capital")` raises on partial
  data: the branch admits a call with `total_equity`, `minority_interest`
  and `total_debt`, while the function itself needs five positional
  arguments. `docs/module-contracts.md` forbids exceptions — null with
  a reason only; missing cash is ordinary in filings — accept: the call
  without `cash`/`st_investments` returns null with `missing_data`,
  test green — size: S
- [ ] R4 — EBITDA silently equals operating income when D&A is not
  disclosed: with `operating_income` set and `d_and_a` None the value
  stays at operating income and `null_reason` is empty. EBITDA is the
  base for EV/EBITDA and net debt / EBITDA. It also returns a `Measure`
  with a non-empty `value` and an empty `lineage`, which invariant I4
  forbids — accept: returns null with `missing_data`, I4 catches it,
  test green — size: S
- [ ] R5 — `Fact` is declared immutable but is not: the six locator
  classes are `@dataclass(frozen=True)`, `Fact` itself (`fact.py:141`)
  is a plain `@dataclass`, and `f.value = "2"` succeeds. Invariant I2
  misses this because it greps the text of `repos.py` via
  `inspect.getsource` instead of testing behaviour — accept:
  `frozen=True`, `superseded_by` updated through `dataclasses.replace`,
  I2 extended with a `FrozenInstanceError` check — size: M
- [ ] R6 — migrations take no backup of the database, against
  `docs/data-model.md` §8.4 and `db.py`'s own docstring: no
  `shutil.copy`, no temp file. Harmless while migrations only created
  tables; there are procedural migrations moving data now. Take the copy
  with `conn.backup(dst)`, not `shutil.copy` — the database runs in WAL
  and part of the data sits in the `-wal` file — accept: copy created
  before migrations and removed after success, plus a test that it
  survives a failed migration — size: M
- [ ] R7 — writes to the content-addressed store are not atomic:
  `raw_store.py` writes through `target.write_bytes(...)` with no temp
  file and no `os.replace`. A crash leaves a truncated object that
  `has_object` reports as present. The store is the only archive of
  primary sources; a corrupted object breaks lineage and
  `resolve(locator)` — accept: write to a temp file alongside and move
  it with `os.replace`, test green — size: M
- [ ] R8 — a failure in `RawRepo.put` leaves orphans: the object is
  written to disk, the line is appended to the manifest, and only then
  the `INSERT` runs. An exception on insert leaves file and manifest
  with no database row (reproduced: disk True, manifest 1, db 0).
  A retry does repair the row, but appends a second copy of the same
  record to the append-only manifest (manifest 2), which skews index
  rebuild — accept: either the insert precedes the manifest, or a
  failure rolls both back; tests for both branches green — size: M
- [ ] R9 — a migration's recorded `checksum` is never verified:
  `apply_migrations` writes it into `schema_version` but never compares
  it with the current SQL at startup. Editing an already-applied
  migration — the very defect that started this list — would go
  unnoticed — accept: a checksum mismatch on an applied version fails
  at startup with a clear message, test green — size: M

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
- [x] B9 — doctor cross-checks the raw store against the database in both
  directions — TASK-11 X5, verified 09.09
- [x] B10 — `watchlist show --version N` — TASK-11 X5, verified 09.09
- [x] B11 — piped output carries no ANSI, with a test — TASK-11 X5,
  verified 09.09
- [x] B12 — the audit JSONL failure path returns an error value and the
  database row is still written — TASK-12 Y7, verified 09.09
  (the CLI printing that value is TASK-14 A5)
- [x] B13 — `export --format md` with footnoted nulls — TASK-12 Y7,
  verified 09.09
- [x] B14 — two AAPL payloads: folded into TASK-10 W2/W7 as a task item,
  removed from the queue 09.09
- [x] B15 — the null-reason vocabulary collected in `rusterm/reasons.py`
  with a repository-level guard — TASK-12 Y7, verified 09.09
- [x] B16 — the key schema of the four `--json` commands pinned —
  TASK-11 X5, verified 09.09
- [x] B17 — `resolve()` duplicate-ticker behaviour pinned (last feed row
  wins) — TASK-12 Y7, verified 09.09
- [x] B18 — `tools/README.md` added — TASK-12 Y7, verified 09.09
- [x] B19 — `logs/app.log` rotation: the test strengthened to the accept
  criterion (exactly two files, newest holds the last line) — TASK-12 Y7,
  verified 09.09
- [x] R0 — connection factory with mandatory PRAGMAs — closed in
  `9155908`: `db.open_connection(paths)` sets WAL and `foreign_keys=ON`.
  Raised by an outside review as a latent defect, fixed before any
  calling code existed.
