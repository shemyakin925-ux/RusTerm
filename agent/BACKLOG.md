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

## Coordinator rulings — TASK-19 (read once, then obey)

Accepted 11.09.2026, journal `agent/ACCEPTANCE-19.txt`. The three
"Disputed" points of `agent/REPORT-19.md` are settled here.

| # | Executor's point | Ruling |
|---|---|---|
| 1 | P1 in `selfcheck.sh` narrowed to `*.py` | **Upheld.** The guard is about code; `assert` inside Russian backlog prose is not a removed assertion. `acceptance.sh` stays protected by acceptance check 12, a separate mechanism. Do not re-widen. |
| 2 | `llm-api` counted as the eighth name in `available()` | **Upheld.** 5 network seats + 2 synthetic + `llm-api` with its own `HostLimit`. Leave it registered. |
| 3 | `near_miss` shares the `manual_unverified` outcome with `failed` | **Upheld for now.** One bucket until the measure side selects on `source_kind` (TASK-20 L6); the split is `agent/TASK-27.md` N4, not a lane decision. |

Noted, no action required: the honest incident note on commit `51795c9`
(selfcheck ran red, `;` instead of `&&`, the commit landed anyway). The
red was the rewritten-seat-test false positive, not a weakened
assertion — checked line by line by the coordinator. The correction
(`&&` always) is the right one.

## Queue

Refilled by the coordinator 10.09.2026 after accepting TASK-14…18.
Every item is small, pre-approved, and independent of the M8 lanes.
A parallel lane may take one **only inside its own zone** (ADR-0012 §2).

- [ ] B32 — README's test count stops being a hand-written number that
  rots inside one shift (it said "402 пройдено, 2 пропущено" while the
  same night ended at 411) — accept: either the number is generated, or
  the sentence names no number and a test asserts no bare test count
  survives in README.md — size: S
- [ ] B33 — `agent/selfcheck.sh` stops hard-coding "пройдено 13": read
  the expected count from `acceptance.sh` itself, so a fourteenth check
  does not make selfcheck lie — accept: add a check to a scratch copy of
  acceptance.sh, selfcheck still passes on green and still fails on red
  — size: S
- [ ] B34 — the OTC universe drift (12,794 live vs 12,867 in
  `agent/REPORT-MARKETS.md`) gets a written tolerance instead of a
  finding repeated every night — accept: REPORT-MARKETS states the
  tolerance band and the date of the last live count — size: S

- [→] B22, B27, B29 — **promoted to `agent/TASK-27.md`** (items N2,
  N3, N5) on 11.09.2026. Each was deferred in TASK-19 for a stated
  reason — `extract.py` absent, measure-side `source_kind` selection
  absent, six-market providers absent — and each reason is gone by the
  night TASK-27 is taken. Do not take them from here: they are a
  night's work now, not idle-time work.

## Done

- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
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
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — verify near-miss bucket — TASK-19 F11, verified 11.09 (verify_status: thousands/apostrophe mismatches land near_miss)
- [x] B20 — provider seat without module never reaches RequestGate — TASK-19 F11, verified 11.09 (ConfigError + calls_made == 0)
- [x] B19 — `logs/app.log` rotation: the test strengthened to the accept
  criterion (exactly two files, newest holds the last line) — TASK-12 Y7,
  verified 09.09
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
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
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — payload size guard as a test — TASK-19 F11, verified 11.09 (256 KB per file under tests/data/, offender named)
- [x] B23 — `trim_companyfacts` byte-stability on a recorded payload,
  sha256 of two runs — TASK-14 A8, verified 09.09
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — `audit.jsonl` capped and rolled over like `app.log` (same
  constants, imported) — TASK-14 A8, verified 09.09
- [x] B21 — import --dry-run writes nothing — TASK-19 F11, verified 11.09 (database sha256 unchanged; extraction attempts on the F8 seat, pipeline lands with L5/L6)
- [x] B31 — ADR number uniqueness guard — TASK-19 F11, verified 11.09 (deliberate 0011 duplicate ran red, removed, green)
- [x] B30 — GUIDE.md user guide — TASK-19 F11, verified 11.09 (every pasted output from real runs in /tmp/rusterm-guide; tui described, not screenshotted)
- [x] B28 — raw store retention pass — TASK-19 F11, verified 11.09 (prune_raw_store: fact/document-referenced survive, unreferenced rows+files and orphan files removed, manifest append-only)
- [x] B26 — manual_import_required advice copy-paste runnable — TASK-19 F11, verified 11.09 (printed string parsed by the CLI parser; import command registered as an honest seat for L5/L6)
- [x] B24 — per-host counters in doctor — TASK-19 F11, verified 11.09 (gate.host_usage -> provider_used_<host> samples; doctor prints used + registered ceiling per host)
- [x] B25 — `status --json` reports `schema_version_observed` beside
  `schema_version_expected` — TASK-14 A8, verified 09.09
