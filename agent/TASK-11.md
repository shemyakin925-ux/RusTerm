# TASK-11 — the end-to-end path, and what the program says it cannot do

- **Status: ACCEPTED** — X1–X4 done, X5 partial (B9, B10, B11, B16).
  Verified on a clean detached checkout at `6246fa1`. The remaining
  backlog items are queued in `agent/TASK-12.md` Y7.
- **Branch:** `agent/night-2` (continue on it; do not open a new branch)
- **Report:** `agent/REPORT-11.md` (a new file; TASK-10's report stays as
  it is)
- **Goal, in one sentence:** a person who has never seen this repository
  can type four commands and get real numbers for a company they chose —
  and where a number is missing, the program says which filing it would
  have needed.

Section 1 of `agent/TASK-10.md` — the working protocol — **applies here
unchanged**. Read it there; it is not repeated. Everything it says about
prohibitions, selfcheck, the report, the network and the stop time holds
for this file too, with `agent/REPORT-11.md` in place of
`agent/REPORT-10.md` and `agent/ACCEPTANCE-9.txt` in place of
`agent/ACCEPTANCE-8.txt`.

---

## 0. Where this starts

TASK-10 ended with the payloads carrying the tags the formulas need, the
trim reproducible, and `rusterm add` no longer crashing. What is still
untrue: nobody has walked the whole path on a company that is not in the
twenty, and `coverage` explains a gap in the vocabulary of the code
rather than in the vocabulary of a filing.

---

## 1. The work, in priority order

### X1. Four commands, one company, from an empty directory

A test that drives the CLI **as a subprocess**, not by calling functions
— the seam where W0's crash lived is exactly the seam a function-level
test does not cross.

```
rusterm init
rusterm add --ticker <T> --market US
rusterm ingest --ticker <T> --market US --source edgar
rusterm snapshot --ticker <T> --market US
```

- The EDGAR calls go through a fake transport serving recorded payloads,
  so the test is hermetic and needs no contact. Ticker map from
  `tests/data/edgar/company_tickers.json`, companyfacts from the M3 set.
- Pick an issuer **from the twenty** so the payload exists, and pass its
  ticker on the command line — the point is the path, not new data.
- Assert on stdout, byte for byte where you can: `add` names the issuer
  by its real name; `ingest` reports a non-zero fact count and zero
  unmapped concepts; `snapshot` reports at least eight measures with a
  value.
- Assert `logs/app.log` contains no traceback for the whole run.
- Then run the same four commands a second time and assert nothing new
  is created and every exit code is 0.

**Done when** `python3 -m pytest tests/test_e2e_cli.py -q` exits 0 and
the test drives real subprocesses (`subprocess.run([sys.executable, "-m",
"rusterm.cli", …])`); `python3 -m pytest -q` exits 0.

---

### X2. `python3 -m rusterm` should work

`python3 -m rusterm.cli` works; `python3 -m rusterm` says
`No module named rusterm.__main__`. Anyone who has not run
`pip install -e .` will type the short one first.

Add `rusterm/__main__.py` — two lines, delegating to
`rusterm.cli.main`. Do not move or rename anything else.

**Done when** a subprocess test asserts `python3 -m rusterm --help` and
`python3 -m rusterm.cli --help` produce identical stdout and exit 0;
acceptance check 1 stays green (the new module must import cleanly).

---

### X3. A missing number names the filing it needed

`coverage` reports a block as `missing` with a reason like
`missing_data`. True, and useless to a person: it does not say *what*
was missing or *where it would have come from*.

For every `missing_data` on an issuer with at least one fact, the
coverage row's reason gains the canonical concepts that had no fact, by
name, in the dictionary's vocabulary — for example
`missing_data: operating_income, tax_expense`. The concepts are already
known at the point the reason is written; nothing new is computed.

- The reason string keeps `missing_data` as its **first token** so the
  fixed-set assertion in `tests/test_m3_snapshot.py` keeps working —
  match on the token, not on the whole string, and say so in the test.
- Do not add a column. Do not change the fixed set of reasons.
- `rusterm coverage --json` carries the concept list as an array
  alongside the reason string, not only inside it.

**Done when** a test seeds an issuer with `revenue` but no
`operating_income` and asserts the coverage reason names
`operating_income`, that the reason still starts with `missing_data`,
and that `--json` carries the list; `python3 -m pytest -q` exits 0.

---

### X4. `export` says which map produced the numbers

`concept_map_version` reached `status --json` and `coverage --json` in
TASK-9 V6 but not the export. A file that outlives the database must
carry the version of the mapping that made it.

Add `concept_map_version` to every export format's header or metadata
block, alongside whatever provenance it already carries.

**Done when** `tests/test_snapshot_export.py` asserts the field is
present in each format the command supports and that existing assertions
are untouched; `python3 -m pytest -q` exits 0.

---

### X5. Queue empty

Take `agent/BACKLOG.md` top down, reporting each pulled item by its ID.
B9, B10, B11, B12, B13, B15 and B16 are pre-approved. B14 was closed by
TASK-10 W2/W7 — if it is still open in the file, mark it and move on.

---

## 2. Night end

```bash
bash agent/acceptance.sh 2>&1 | tee agent/ACCEPTANCE-9.txt
git add agent/ACCEPTANCE-9.txt agent/REPORT-11.md agent/STATE.json
git commit -m "Финальная приёмка ночи: журнал, отчёт, состояние"
git push origin agent/night-2
```

`agent/REPORT-11.md` uses the same sections as TASK-10's report —
**Done**, **Blocked**, **What not to trust**, **Disputed**, **HANDOFF** —
and `agent/STATE.json` ends at `"status": "awaiting_review"` naming this
task and this report.

## 3. Scope boundary

Same as `agent/TASK-10.md` §4, unchanged. Nothing here needs a new
dependency, a new taxonomy, a price vendor or a GUI.
