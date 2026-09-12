# REPORT-22 — TASK-22: fiscal calendar, data durability, an installable program

## Done

- §0: branch `agent/night-4` cut from `agent/night-3` head (e324dee,
  the released-and-accepted state); selfcheck STATUS=0; `markets` shows
  all six rows with implemented modules; `_SCHEMA_VERSION` read from
  the file: 40.

### J1.0 — EDGAR parser records currency (DONE, coordinator's precondition)

- `rusterm/parsers/__init__.py`: new `currency_of_unit()` — a units key
  of exactly three capital letters (`USD`, `CAD`, `KRW`) is recorded to
  `fact.currency`; `shares`, `pure`, `USD/shares` are not currencies and
  stay `None`. Only `CompanyFactsParser` is touched; the synthetic
  parsers and `manual/pipeline.py` keep `None` deliberately.
- **The blank rule lands with this commit**: `currencies_for_measure`
  now returns blanks as empty strings, and `currency_guard` treats a
  recorded currency mixed with blanks as `currency_mismatch: (blank), X`
  — never "that one currency". All-blank (legacy) sets behave exactly as
  before. The TASK-21 Disputed trade-off is closed.
- Real output, fresh ingest of the recorded AAPL+RY payloads:
  ```
  SELECT DISTINCT currency FROM fact:
    None     (shares/USD-shares facts - honest) / USD/shares facts (correct, not missing)
    CAD
    USD
  ```
- Goldens: UNCHANGED — `tests/test_m2_golden.py` and the m6-ca golden
  test pass in the suite; they resolve values by locator, and the
  parser change adds a field without touching any value.
- Tests: `tests/test_j1_currency.py`, 5 passed. Full suite:
  531 passed, 3 skipped, exit 0.

### J2 — the peer set knows whom it holds (DONE)

- `PeerSetRepo.composition(version_id)`: markets of members (registry-
  known instrument_id prefixes), recorded currencies of their facts,
  members; `scope` names the set single-market or mixed. Thresholds I6
  untouched — information, not a filter; membership and versions do not
  change. The `origin` COLUMN keeps its verification vocabulary
  (manual/catalog/...); the composition lives in its own field instead
  — overwriting origin would have broken `evaluate()` verification.
- `rusterm status`: `peer_sets` in the json payload + a text line per
  set; `tools.get_peer_set` exposes composition too (read-only hash
  test still green).
- Tests `tests/test_j2_peers_composition.py`: mixed 6-issuer set
  reports markets KR+US, currencies KRW+USD, scope mixed; single-market
  set keeps exact membership and version. Suite green = goldens
  untouched.

### J3 — the fiscal year does not end in December for everyone (DONE,
### one documented deviation: no migration needed)

- `core/fact.py`: `fiscal_year(period_end, fye)` — a period belongs to
  the fiscal year ENDING next; a December filer gets the calendar year,
  a June filer (06-30): January 2024 period is FY2024, December 2024
  period is FY2025. No calendar recorded — no label (None), no guess.
- `snapshot.py`: `_issuer_inputs(issuer_id, as_of)` — a fact whose
  period ended after as_of is not closed yet and never enters the
  inputs, whatever the calendar. Percentile and sector aggregate: a gap
  of more than 100 days between members' period ends fires the
  EXISTING `period_mismatch` reason; each member still contributes its
  own latest closed period.
- `cmd_add --fye MM-DD` records `issuer.fiscal_year_end`.
- **Deviation from the letter of the task:** no migration — the column
  `issuer.fiscal_year_end` has existed since M1; a dummy migration is
  forbidden by P2. `_SCHEMA_VERSION` stays 40. The "migration applied
  twice creates no duplicates" assertion is therefore n/a.
- Tests `tests/test_j3_fiscal.py`, 5 passed; US-only behaviour
  byte-identical (all prior snapshot tests and both goldens green).

### J4 — data that exists nowhere else: backup/restore (DONE)

- `store/backup.py`: `create_backup` — one zip: a consistent DB
  snapshot (VACUUM INTO; watchlists and lineage inside), raw manifests
  and raw objects (imported document bodies). MANIFEST.json carries
  sha256 and size per member plus the schema version; member paths are
  relative to the data root, as on disk. A `backup.json` mark lands in
  the data dir; doctor reads it.
- `restore_backup` refuses: archive without manifest/db, schema NEWER
  than the running code, any member whose hash does not match (checked
  before writing anything), a non-empty target without `--force`;
  members cannot escape the data root; `--force` overlays without
  deleting foreign files.
- CLI: `rusterm backup <archive>`, `rusterm restore <archive>
  [--force]`; doctor payload gains `last_backup` (archive, age_days) —
  a report, not a failure.
- Tests `tests/test_j4_backup.py`, 5 passed: round trip compares the
  DB table by table and the raw trees byte for byte; the manual fact
  arrives with locator and lineage intact.

### J5 — acceptance stops depending on someone remembering (DONE)

- `.github/workflows/acceptance.yml`: on push and pull_request;
  checkout with fetch-depth 0 (checks 10 and 12 compare against
  origin/main), setup-python matrix **3.12 and 3.14**,
  `pip install -e ".[test]"`, then `bash agent/acceptance.sh` — a
  non-zero status fails the job.
- No secret in the CI configuration, asserted by a test (no
  `secrets.`, no key env names, no key shapes); network tests skip
  cleanly without keys (N7) — CI proves that too.
- YAML parses: PyYAML 6.0.3 locally and `tests/test_j5_ci.py`
  (importorskip) assert the acceptance invocation, the matrix, and the
  absence of secrets.
- Results per Python version: **3.14.6 measured locally** — full suite
  563 passed, 3 skipped, exit 0; acceptance 13/13. **3.12 predicted
  green**, because there is no syntax newer than 3.12 in `rusterm/`
  (lazy annotations, `tomllib` needs 3.11), and the only test
  dependencies (pytest>=8, zstandard) support 3.12; the real verdict
  belongs to the matrix on GitHub.

### J6 — the industry tool stops lying by emptiness (DONE)

- `list_industry_instruments` resolves the sector through its peer set
  (M7's source, the same key `cmd_industry` uses): the answer carries
  `peer_set_version_id`, the version number, `as_of`, and the
  membership from `member_snapshots_at`. Unknown sector — not_found;
  known sector without a version at date — resolved empty with note
  `no_version_at_date` (the gap is shown). `NO_INDUSTRY_SOURCE` is
  deleted outright — no surviving branch to explain.
- Read-only proven: the byte-identical-database test in test_tools
  passes. Its fixture renames the set to `tankers` — the tool had been
  hardcoded and never reached the database.
- Tests `tests/test_j6_industry_tool.py`, 4 passed.

### J7 — the third screen: industry (DONE)

- `tui/model.py`: `industry_rows()` — quartiles per sector measure
  (the four M7 ratio measures plus absolute revenue, where currency is
  visible), the set version, contributing members; `render_industry()`:
  a single-currency measure states its currency beside the quartiles
  (J1); mixed currencies and thin peer sets render the named refusal,
  not a number. Pure functions — `import curses` does not appear in
  the model source, asserted by a test.
- `tui/app.py`: key `o` on the list screen opens the industry screen
  for the selected instrument's peer set; Esc back, q quit.
- `tests/test_j7_tui_industry.py`, 4 passed (headless), and
  `tests/test_tui_model.py` stays green.

### J8 — rusterm, a command, not a module (DONE)

- `pyproject.toml`: extra `[documents]` = pypdf, python-docx,
  openpyxl — optional format libraries; their absence yields
  `format_unsupported:<package>` as a VALUE (ADR-0011 ①), proven by
  tests that make the import fail via `sys.modules`.
- Real install run (this machine, Python 3.14.6):
  ```
  $ python3 -m pip install -e .
  ... (quiet, exit 0)
  $ rusterm --help
  usage: rusterm [-h] [--root ROOT]
                 {init,ingest,demo,add,snapshot,export,verify,doctor,
                  backup,restore,status,watchlist,coverage,metrics,
                  budget,tui,refresh,ops,import,markets,industry} ...
  $ rusterm --root <tmp> init && rusterm --root <tmp> markets
  US  US  exchange  edgar  cik  us-gaap  auto    implemented  0
  CA  CA  exchange  edgar  cik  ifrs-full  auto  implemented  0
  OTC US  otc       edgar  cik  us-gaap  partial  implemented  0
  KR  KR  exchange  dart   corp_code  ifrs-full  auto  implemented  0
  BR  BR  exchange  cvm    cvm_code  ifrs-full  auto  implemented  0
  AU  AU  exchange  asx    asx_code  ifrs-full  partial  implemented  0
  ```
- README quick start now shows the commands actually run, including
  `pip install -e ".[documents]"`.
- `tests/test_j8_install.py`, 4 passed. The `extract_text` SEAT in
  `rusterm/manual/__init__.py` is untouched — its honest pin describes
  the pre-L5 period; the pipeline uses the real implementation
  (`rusterm/manual/extract`).

### J9 — what is on main (DONE; report only, no merge, no push)

Baseline: the coordinator released night-3 into `main`
(`f7c2495 -> 06e8efc`); `origin/main` = `06e8efc`, this branch's base
`e324dee` carries the coordinator's post-acceptance bookkeeping on top.

- `git diff --stat origin/main...HEAD` — what the branch adds:
  29 files changed, 2018 insertions(+), 43 deletions(-) — the
  coordinator's ACCEPTANCE-21/LAUNCH/BACKLOG bookkeeping plus this
  night's J-items (code + tests + workflow + README).
- `git diff origin/main -- agent/acceptance.sh` — **empty**: the
  acceptance script is byte-identical to `origin/main`; check 12's
  mechanism is intact.
- `git diff --name-status origin/main HEAD -- docs/` — **empty**: no
  docs/ change at all this night, so the "only added ADRs" rule holds
  vacuously; check 10 sees 0 new ADRs.
- A user cloning `main` today (clone of origin/main, fresh venv,
  Python 3.14.6): `pip install -e .` — exit 0; `rusterm --root <tmp>
  init && rusterm --root <tmp> markets` — six registry rows, exit 0
  (the same output as under J8; main is one bookkeeping commit behind
  the branch and carries no code difference: the code delta is exactly
  this night's items).
- **No merge into `main` and no push to `main` was attempted.**

### fx_rate note (J1 obligation)

The `fx_rate` table (from_ccy, to_ccy, date, rate, source_ref; PK on
the triple) exists in the schema and nothing fills it — left so. The
shape would serve conversion when a rates source is eventually
authorised: dated pairs with a source_ref match the project's
provenance discipline; a unit conversion would then read the latest
rate at or before the measure's as_of. Nothing was written into it and
no second table was created.

## Blocked

- none

## What not to trust

- Nothing yet: no work item has landed.

## Disputed

- (empty by design — nothing disputed yet)

## HANDOFF

Status:          DONE
Items done:      §0, J1.0, J1, J2, J3, J4, J5, J6, J7, J8, J9
Items not done:  J10 — backlog is conditional on finishing J1-J9 before 09:30; the queue continues with TASK-23 on the user's instruction
Acceptance:      Итог: пройдено 13, провалено 0 — Принято; SELFCHECK OK, captured exit status 0 at the commit
Tests:           563 passed, 3 skipped, 0 xfailed
Schema:          unchanged (_SCHEMA_VERSION 40; J3 needed no migration — the column existed since M1)
Goldens:         golden_m2.json and golden_m6_ca.json unchanged; both golden tests inside the 563
Currency:        EDGAR records USD/CAD from the units key (J1.0); export and the TUI card carry it; coverage counts currency_mismatch separately from missing_data; fx_rate left unfilled, shape assessed fit for future conversion
Fiscal:          fiscal_year labels by issuer calendar (06-30 vs 12-31 in tests); as_of keeps only closed periods; period gap over 100 days fires the existing period_mismatch
Backup:          round trip exact (DB per table, raw trees byte-for-byte, manual fact with locator and lineage); refusals proven: tampered member by name, future schema, non-empty root without --force; doctor reports backup age
CI:              .github/workflows/acceptance.yml committed, YAML parsed; matrix 3.12/3.14; 3.14 measured locally (563 passed), 3.12 predicted green with reasons — the matrix is the real verdict
Install:         pip install -e . exit 0; rusterm --help 21 subcommands; rusterm markets six rows exit 0; extra [documents] declared and its absence yields format_unsupported values
main:            branch adds 29 files (+2018/-43) over origin/main (06e8efc); agent/acceptance.sh byte-identical (empty diff); docs/ diff empty (no ADR added); no merge or push to main attempted
Network:         0 requests used by this session (all evidence from recorded payloads)
Model:           app llm_calls 0; GLM-5.3-Flash
Pushed:          yes, every work commit pushed to origin/agent/night-4 as it landed
Questions for the coordinator:
1. J3 has no migration by P2 (the column pre-existed) — accept the deviation from the letter of the task?
2. The origin COLUMN keeps its verification vocabulary; composition lives in its own field — confirm this reading of J2's "origin says single-market or mixed".
3. The extract_text SEAT in rusterm/manual/__init__.py still answers format_unsupported:manual_extract_not_implemented while the real implementation lives in rusterm/manual/extract (pipeline uses it) — wire the seat through, or leave it with its pin?

NOW: J9, step 3
