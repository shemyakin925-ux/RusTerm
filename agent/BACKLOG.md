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

Two questions from the REPORT-19 HANDOFF are answered here as well.
**Q1, merge ordering:** settled by **ADR-0017** — the integration night
merges the lanes itself, head-before-lanes, and the one predicted
conflict (the `import` block in `rusterm/cli/__init__.py`) is
pre-decided in favour of the lane. **Q2, `nightly_max` ownership:**
confirmed — the 5000/host default is the project-wide fallback, and a
lane overrides it inside its own provider module with a measured
ceiling. A lane that does not measure one leaves the default and says so
in its report.

Noted, no action required: the honest incident note on commit `51795c9`
(selfcheck ran red, `;` instead of `&&`, the commit landed anyway). The
red was the rewritten-seat-test false positive, not a weakened
assertion — checked line by line by the coordinator. The correction
(`&&` always) is the right one.

## Guards the coordinator added 11.09.2026. Do not weaken them

Two guard tests were written by the coordinator, not by a lane. **P1
covers them: not one assertion in either file is deleted or loosened.**
A guard that becomes inconvenient is a `Disputed` entry, never an edit.

| File | What it forbids | How it is satisfied |
|---|---|---|
| `tests/test_docs_truth.py` | a hand-typed number about the repository in README («402 пройдено», «тринадцати ADR») | say no number, or derive it; every file in `docs/adr/` must be named in README §15 — so a new ADR forces a roadmap update |
| `tests/test_single_door.py` | a door built and then bypassed — the TASK-19 F6 defect, where `make_intent_client` was written, tested and called by nothing while `cmd_ops` constructed `RuleClient()` directly | while the door is listed in `PENDING`, the debt stays visible and addressed to a task item; **wiring it means deleting that line**, and the rule flips to forbidding any direct construction |

The second guard is deliberately narrow. A blanket "every public
function must have a caller" rule was measured on this repository and
fires 109 times out of 170 — it would flag the twenty industry
functions and every formula reached from a registry by name. A guard
that is red by default teaches people to ignore it.

## Queue

Refilled by the coordinator 10.09.2026 after accepting TASK-14…18.
Every item is small, pre-approved, and independent of the M8 lanes.
A parallel lane may take one **only inside its own zone** (ADR-0012 §2).

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

- [x] B32 — README states no hand-typed count of itself — done by the coordinator 11.09.2026, not by an idle evening: guard `tests/test_docs_truth.py` (bans «N пройдено», «N тестов», «N ADR», and requires every file in docs/adr/ to be named in §15), README §15 cleaned of «402 пройдено» and «тринадцати ADR». Both tests were shown red before the fix.

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
