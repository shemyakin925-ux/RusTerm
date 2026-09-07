# TASK-6 — Stage D: verification, governance, industry metrics

- **Status: READY**
- **Branch:** `agent/night-2`
- **Report file:** `agent/REPORT-6.md`
- **Take this only after TASK-5 items T0–T5 are committed.** If TASK-5
  is unfinished, finish TASK-5 first — do not interleave.

This task is self-contained. Section 1 ("How to work") outranks the task
list — read it first, in full.

---

## 0. Where we are

Stage A and increments I1–I13 are accepted (147 tests, acceptance 13/13
as of `a11ec89` + coordinator's `main` sync). Stage C (TASK-5) adds
watchlist, coverage, metrics and logs.

Stage D closes the three specified subsystems that still have schema but
no code: **verification / ground truth** (`verification` table),
**governance traffic light** (no table yet — new migration), and
**Maritime/Tanker industry metrics**.

Everything stays offline and synthetic. No network.

---

## 1. HOW TO WORK. Read this whole section; it is the important part

Four agents in a row failed on method, not on difficulty. Every rule
below exists because of a specific loss.

### 1.1. The cycle. One task item = one pass

```
1. READ     the file you are about to change, in full. Not from memory.
2. SHOW     current state with a command, and look at the output.
3. CHANGE   exactly one item. Not two.
4. VERIFY   with the command from that item's "Done when".
5. SELFCHECK  four commands from §1.3. All must be clean.
6. COMMIT   immediately, before moving to the next item.
7. RECORD   one line in agent/REPORT-6.md: command + its output.
```

Step 6 does not get deferred.

### 1.2. Five prohibitions

**P1. Never delete an `assert`.** A test that blocks your change is a
signal the change is wrong. An obsolete assertion is **replaced by a
stronger one**, and the report says how the new one is stricter.

**P2. Never edit an existing migration.** `_MIGRATIONS` in
`rusterm/store/db.py` is history already applied elsewhere;
`apply_migrations` skips versions already recorded. Schema change =
**new** migration with a new number, and bump `_SCHEMA_VERSION`.

**P3. Leave nothing outside git.** Everything you report must be in
`git ls-files`.

**P4. No `.bak`, `.orig`, temp databases or junk.**

**P5. Never claim a check you did not run.** "Not run" is acceptable;
"works" without command output is not.

### 1.3. Selfcheck. Four commands before every commit

```bash
git diff --cached | grep '^-.*assert'                # P1: must be empty
git diff --cached rusterm/store/db.py | grep '^-'    # P2: empty except _SCHEMA_VERSION
git status --porcelain | grep '^??'                  # P3, P4: must be empty
bash agent/acceptance.sh                             # must not get worse
```

### 1.4. When stuck

Same thing fails after **three different hypotheses** about the cause:
stop, mark the test `@pytest.mark.xfail(strict=True, reason="…")`,
write the three hypotheses into the report, move on. This is an
accepted outcome.

### 1.5. Stop rule

A test that used to pass starts failing — stop immediately, roll back
with `git checkout -- <file>`, re-enter. Do not fix forward.

### 1.6. Commit format

Russian, imperative, one thought. First line — what was done; body —
how it was verified, with command output.

### 1.7. Bookkeeping

- `agent/REPORT-6.md`, written as you go. Sections: Done (one line per
  item, command + output), Blocked, What not to trust, Disputed. Last
  line always `NOW: <item>, step <n>`.
- `agent/STATE.json` after every cycle step: `{"task":
  "agent/TASK-6.md", "report": "agent/REPORT-6.md", "item": "<D-id>",
  "step": "<1-7>", "status": "working"|"awaiting_review",
  "last_commit": "<sha>", "updated_at": "<ISO8601 UTC>"}`.
- At 10:00 Danang (UTC+7): current item to a commit, `## HANDOFF`
  appended, `"status": "awaiting_review"`.

---

## 2. Tasks

Strictly in order, priority-ordered.

### D1. Process 5 — fact verification and ground truth

`docs/processes.md` §263-284. Table `verification` exists; nothing
writes it. Five nodes, all five required:

| Node | Contract |
|---|---|
| `capture` | what was shown, what it should be, link to the document; row in `verification` |
| `store_ground_truth` | new `fact` with `origin='manual'`, priority over the extracted one; **the extracted fact is not deleted** — it gets `superseded_by` pointing at the manual one |
| `recompute` | recompute every `measure` whose lineage touches the superseded fact |
| `propose_golden` | append the (raw, expected) pair to a golden-file proposal set on disk |
| `flag_parser` | counter of mismatches per `(provider, concept)`; over threshold the parser is marked degraded |

- `superseded_by` needs a new migration (34) if the column does not
  exist. New migration, never an edit to an old one (P2).
- Threshold for `flag_parser`: **5 mismatches per (provider, concept)
  within a rolling 30 days.** Deterministic, no judgement call.
- A degraded parser is surfaced through `coverage.reason`, not only in
  logs.

**Done when** `tests/test_verification.py` is green and asserts: the
extracted fact still exists after `store_ground_truth` and carries
`superseded_by`; a measure derived from it changed value after
`recompute`; the 5th mismatch flips the parser to degraded and the 4th
does not.

### D2. Governance traffic light, `governance.v1`

`docs/governance-thresholds.md`, all five indicators, thresholds
verbatim from that file. This is deterministic computation over facts —
no LLM, no heuristics.

- New module `rusterm/core/governance.py`, new table via **migration
  35**: `governance_assessment(instrument_id, indicator, color,
  method_version, as_of, lineage_ref, reason)`.
- Five indicators: independent directors share; CEO/chair combination;
  related-party transactions to revenue; net insider transactions
  (rolling 12 months); auditor.
- **Hard rules from the doc, each its own test:**
  - No aggregate score. Five separate colors, never summed or weighted.
  - Missing data is `gray`, never `green`.
  - A color without `lineage_ref` is never emitted — raise, do not
    return a color with an empty lineage.
  - Thresholds apply to the last completed reporting year, except
    indicator 4 (rolling window).
- `method_version = "governance.v1"` stored on every row. A threshold
  change means a new version; history is not recomputed in place.

**Done when** `tests/test_governance.py` is green with, at minimum: one
test per indicator hitting all four colors on synthetic facts; one test
asserting no aggregate/score field exists on the result; one test
asserting a color with empty lineage raises.

### D3. Maritime / Tanker industry metrics

`docs/industry-metrics/maritime-tanker.md`. Implement the specific
metrics listed in "Специфичные метрики" and the tests named in that
file's "Тесты" section, plus the default pure-play peer set from its
last section.

- `rusterm/core/industry/maritime_tanker.py`. Metric definitions live
  next to the formula engine, not in the CLI.
- Every metric carries `scope` and null-reasons exactly like the
  existing `rusterm/formulas.py` measures — reuse that machinery, do
  not fork it.
- Only Maritime/Tanker. No other industry.

**Done when** `tests/test_industry_maritime.py` is green and each test
named in the doc's "Тесты" section exists by name.

### D4. LLM-summary guard rail — deterministic half only, no model

`docs/watchlist-and-llm.md` §2.6 and `docs/quality-and-observability.md`.
No network, no model call, no API key. What gets built is the part that
must be right regardless of which model is used later:

- A summary template renderer where **numbers are substituted by the
  application from the snapshot**, never taken from model text.
- A validator: any statement containing a number that has no
  corresponding entry in `citations` is rejected, and the whole text is
  discarded — the block stays `missing` with reason "model could not
  stay within the data". A partially-cleaned text is never stored.
- Storage in the existing `llm_summary` table: `instrument_id`,
  `created_at`, `model`, `prompt_hash`, `snapshot_version`, text,
  `citations`.
- The model client is a `typing.Protocol` with one synthetic fake
  implementation in tests. No HTTP anywhere.

**Done when** `tests/test_llm_guard.py` is green and asserts: a fake
response with an invented number is rejected in full (nothing written
to `llm_summary`, coverage block `missing` with the reason string); a
response whose every number is cited is stored; `grep -rn 'httpx\|requests'
rusterm/core/ rusterm/normalize/` is empty.

---

## 3. Out of scope

Qt UI, LLM chat and intent classification, Industry View, UK/CA
providers, industry metrics beyond Maritime/Tanker, any real network
source, any real model call. All work offline, on synthetic data.

Time left over — `agent/BACKLOG.md`, top down. Do not invent work.

## 4. Stack

Same as TASK-5 §4. Python 3.12+, must also work on 3.14; stdlib +
`pytest`; `sqlite3` from stdlib; `zstandard` optional with `gzip`
fallback; `httpx`/`requests` only inside `rusterm/providers/`.
Forbidden: ORM, `alembic`, `pandas`, `numpy`, async frameworks.

## 5. Acceptance

`bash agent/acceptance.sh` — thirteen machine checks. Run after every
commit; never let it get worse. **Editing that file is forbidden** —
check 12 compares it against `origin/main`. Disagree with a check —
write it in the report's "Disputed" section.
