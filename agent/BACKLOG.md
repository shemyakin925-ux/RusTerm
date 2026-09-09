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
