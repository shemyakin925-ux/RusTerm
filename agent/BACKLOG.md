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

Refilled by the coordinator 10.09.2026 after accepting TASK-14…18.
Every item is small, pre-approved, and independent of the M8 lanes.
A parallel lane may take one **only inside its own zone** (ADR-0012 §2).

- [ ] B21 — `import --dry-run`: extract and verify, write nothing —
  accept: test asserts database sha256 unchanged — size: S
- [ ] B22 — document formats table in README from the code, not by hand
  — accept: test asserts every format `extract.py` handles is listed —
  size: S
- [ ] B27 — a manual fact and a provider fact for the same concept and
  period coexist without either overwriting the other — accept: test
  asserts both rows present and the provider one wins the measure —
  size: M
- [ ] B28 — raw store retention: it grows forever and nothing prunes it
  — accept: test asserts a retention pass removes only objects no fact
  or document references, in both directions — size: M
- [ ] B29 — scale pass with six markets and prices together (M4 measured
  500 US instruments with no price path) — accept: the M4 budget still
  holds, report states seconds per issuer — size: L
- [ ] B30 — a user guide separate from README (README is a specification,
  not instructions) — accept: a new file, every command in it actually
  run and its output pasted — size: M
- [ ] B31 — ADR numbers are claimed by tasks (0013 TASK-20 L10, 0015
  TASK-24 N10, 0016 TASK-26 Q11); a test asserts no two ADR files share
  a number — accept: test fails on a deliberate duplicate — size: S

## Done

- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — verify near-miss bucket — TASK-19 F11, verified 11.09 (verify_status: thousands/apostrophe mismatches land near_miss)
- [x] B20 — provider seat without module never reaches RequestGate — TASK-19 F11, verified 11.09 (ConfigError + calls_made == 0)
- [x] B19 — `rusterm markets --json` — TASK-19 F11, verified 11.09 (json.tool parses; all registry fields asserted)
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
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — verify near-miss bucket — TASK-19 F11, verified 11.09 (verify_status: thousands/apostrophe mismatches land near_miss)
- [x] B20 — provider seat without module never reaches RequestGate — TASK-19 F11, verified 11.09 (ConfigError + calls_made == 0)
- [x] B19 — `logs/app.log` rotation: the test strengthened to the accept
  criterion (exactly two files, newest holds the last line) — TASK-12 Y7,
  verified 09.09
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — verify near-miss bucket — TASK-19 F11, verified 11.09 (verify_status: thousands/apostrophe mismatches land near_miss)
- [x] B20 — `refresh --json` request totals pinned to the sum of
  `RefreshResult.calls`, normal and mixed (error) pass — TASK-14 A8,
  verified 09.09
- [x] B21 — `IssuerStateRepo.get` returns `None` for a known issuer
  under a different source — TASK-14 A8, verified 09.09
- [x] B22 — the 1100-day rule named once (`_STALE_LOOKBACK_DAYS`),
  prose refers to the name — TASK-14 A8, verified 09.09
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — `trim_companyfacts` byte-stability on a recorded payload,
  sha256 of two runs — TASK-14 A8, verified 09.09
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — `audit.jsonl` capped and rolled over like `app.log` (same
  constants, imported) — TASK-14 A8, verified 09.09
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — `status --json` reports `schema_version_observed` beside
  `schema_version_expected` — TASK-14 A8, verified 09.09
