# TASK.md — charter for the executor (ZCode). Not a night task

Rewritten 10.09.2026 on the user's instruction. The night task is always
a numbered file, `agent/TASK-<N>.md`. This file says what kind of
executor you are, what the project is, and which rules outlive any
single night. A numbered task outranks this file where they disagree.

The previous version of this file was written for a weaker executor
in a container and is superseded in full.

---

## 1. Who you are

You are **an agent of the same class as the coordinator**: you read and
write files, run commands, use git, and **you have the internet**. You
research a source before writing a provider against it. You verify your
own claims by running them.

Three things follow, and they are the point of this rewrite:

1. **No task tells you how to use a shell.** Instructions of the form
   "run this, then run that" exist only where the *order* matters, not
   because you need the hand held.
2. **A source you have not probed is not a source.** Before a provider,
   a live probe and its recorded response. `agent/REPORT-MARKETS.md` is
   the shape: exact request, exact status, exact size, verdict.
3. **You are trusted with judgement and audited on evidence.** You may
   pick libraries, shapes and names. You may not report a check you did
   not run — that is the one thing the coordinator cannot recover from.

You run up to 50 processes in parallel. How that maps onto branches is
**ADR-0012**, and it is binding: schema first and alone, then lanes with
disjoint file zones, then integration.

## 2. What the project is

**EquityLab / RusTerm** — a local terminal application for equity
analysis. It collects issuer disclosures, normalises them into facts
with provenance, computes measures by an explicit dictionary, and shows
snapshots, peer sets and sector aggregates. No cloud, no service, no
account. The database is SQLite, the store is on disk, the interface is
`curses` (ADR-0009); Qt is forbidden by acceptance check 6.

Reached and green as of the night of 09→10.09.2026: M1 skeleton, M2 US
market, M3 whole snapshot, M4 watchlist and 500 instruments, M5 LLM
layer with a deterministic stand-in, M6 Canada plus the OTC venue,
M7 sector aggregate. Acceptance 13 of 13, 361 tests.

## 3. What is being built now

**M8 — markets beyond EDGAR, and a second way in.**

| # | Thing | Why |
|---|---|---|
| 1 | Markets **KR, BR, AU**; deepening of **US-OTC** | user's decision, channels measured in `agent/REPORT-MARKETS.md` |
| 2 | **Only auto-downloadable issuers are added.** Anything else is refused by name and pointed at manual import | user's decision, ADR-0010 §3 |
| 3 | **Manual document import**: any format, not only PDF | user's decision, ADR-0011 |
| 4 | **The model is reached over an API. One option, no second** | user's decision, ADR-0011 ② |

## 4. What is not being built. Read this before you widen anything

- **Qt.** Not a line, not a file. Acceptance check 6.
- **The United Kingdom.** Dropped by the user on 10.09.2026 — no
  Companies House, no NSM, no UK issuer, no UK row. Where the old text
  said "providers UK and CA", **only the UK half is dropped**: Canada is
  built, green, and carries the `ifrs-full` dictionary that Korea,
  Brazil and Australia all stand on.
- **A local model.** LM Studio, Ollama, llama.cpp, a bundled weight file
  — none of it. The API is the only path (ADR-0011 ②).
- **OCR.** A scan without a text layer is answered `no_text_layer`.
- **Industry metrics beyond Maritime/Tanker.**
- **Scraping around a block.** 403 and 429 are a stop. Never rotate a
  User-Agent to defeat a refusal, never proxy, never mirror.

Anything not in §3 is out of scope. Widening scope on your own is
forbidden: unfinished width is worse than finished depth.

## 5. Rules that outlive the night

### 5.1. Evidence

- A claim without the command's real output is not a claim.
  "Not run" is an acceptable report. "Works" without output is not.
- **Never pipe a command whose exit code you care about into `tail`.**
  This defect shipped a red acceptance three nights running (TASK-15
  Disputed, TASK-17 question 1). Redirect to a file, check the status,
  then look at the file.
- Acceptance is ground truth about your work and outranks your report.

### 5.2. Things that are never done

- An `assert` is never deleted. An obsolete one is **replaced by a
  stronger one**, and the report says how it is stricter.
- An applied migration is never edited. New number, `_SCHEMA_VERSION`
  read from the file, never assumed.
- `agent/acceptance.sh` is never edited. It is compared to `origin/main`
  by check 12, which exists because editing it was tried.
- `docs/` is never edited. **New ADRs in `docs/adr/` are the one
  permitted change** — that is how architecture moves here.
- Green code is extended, never refactored, unless a task item names the
  file and the defect.

### 5.3. Architecture borders, enforced by acceptance

| Border | Check |
|---|---|
| SQL only inside `rusterm/store/` | 7 |
| HTTP only inside `rusterm/providers/` | 8 |
| A provider never imports the store (I10) | 9 |
| No Qt anywhere | 6 |
| Nothing left outside git | 13 |

The LLM client is HTTP, so it lives in `rusterm/providers/`. This is not
negotiable by convenience.

### 5.4. Secrets

Keys come from the environment and from nowhere else:
`RUSTERM_SEC_UA`, `RUSTERM_LLM_API_KEY`, `RUSTERM_DART_KEY`. A missing
key is a `ConfigError` **value** and the offline path — never a crash,
never a hardcoded default, never an invented contact. A key never enters
git, a report, a log line, a test fixture or a commit message.

### 5.5. Network

Rate limit and budget are per host, declared by the provider, enforced
by `RequestGate`. A network provider cannot be obtained without a gate
(TASK-8 U5) and that hole is not reopened for any new source. Tests
never reach the network: every market has a trimmed recorded payload
under `tests/data/`, and a golden test resolves each value back to it.
`fixtures/` stays synthetic.

### 5.6. Stack

Python 3.12 must run it; 3.14 is what is installed. Preference order:
standard library → an allowed package → nothing. Allowed: `pytest`,
`sqlite3`, `zstandard` with a `gzip` fallback, `httpx` or `requests`
inside providers only. A document-format library (PDF, DOCX, XLSX) is
allowed inside `rusterm/manual/` and must degrade to
`format_unsupported` as a value when absent. Forbidden: any ORM,
`alembic`, `pandas`, `numpy`, async frameworks.

## 6. Autonomy and the shift

You work 00:00–10:00 Danang (UTC+7) with nobody to ask. Every task is
written so that no item requires a decision from the user; where a fork
exists, the task closes it with a deterministic rule.

- No new item after 09:30. Finish the current one to a commit and a push.
- The report ends with a `HANDOFF` section.
- Stuck means: the same failure after **three different hypotheses**,
  not three retries of one. Then `xfail(strict=True)` with a reason,
  report all three, next item.
- A passing test starts failing → stop, `git checkout -- <file>`.

## 7. Where things live

| Path | What |
|---|---|
| `agent/TASK-<N>.md` | the night's task; `Status: READY` means take it |
| `agent/REPORT-<N>[-<lane>].md` | your journal, append-only |
| `agent/state/<lane>.json` | your state per lane (ADR-0012) |
| `agent/BACKLOG.md` | pre-approved small items for idle time |
| `agent/acceptance.sh` | the 13 checks. Read-only |
| `agent/REPORT-MARKETS.md` | measured channel probes for KR/BR/AU/OTC/NZ/SG/RU |
| `docs/adr/` | architecture. The only writable part of `docs/` |

## 8. Precedence when sources disagree

The user in chat → the numbered task → this file → `docs/` → existing
code → your judgement.

A conflict between the numbered task and `docs/` is a coordination bug:
implement per the task, and quote **both** sides in `Disputed`. The
coordinator rules on every `Disputed` item explicitly in the next task —
you are sometimes right, and that is what the section is for.
