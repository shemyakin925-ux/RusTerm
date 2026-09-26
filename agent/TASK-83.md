# TASK-83 — fuzzing the parsers: garbage in, a refusal out

- **Status: READY**
- **Report:** `agent/REPORT-83.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-83.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network 0 (Hypothesis comes from TASK-82; absent →
  `pip install hypothesis`, one request). LLM 0.
- **How to work:** as TASK-82 (no questions, Disputed, one item = one
  commit). TASK-82's "Fixed decisions" table applies here in full.

РАЗРЕШЕНО ПРАВИТЬ: pyproject.toml

## Where we are

Every parser reads bytes someone else wrote. Tests feed them recorded
payloads only. Coordinator's reading of the contracts:

| Entry | Declared contract | Suspected hole |
|---|---|---|
| `parsers.ownership.parse_form4(raw)` | `OwnershipFiling` or `ValueError` | **measured:** `parse_form4(b'<not xml')` raises `ET.ParseError` (a `SyntaxError`, not `ValueError`) |
| `parsers.CompanyFactsParser().parse(raw, ctx)` | `ParseResult` | bad JSON / wrong shapes → ? |
| `parsers.cvm_dfp.CvmDfpParser().parse_rows(rows, st, ctx)` | `(facts, unparsed)` | `float("NaN")`, `"1e309"` in `VL_CONTA` → non-finite fact |
| `parsers.parse_auto(raw, meta, ctx)` | `ParseResult \| None` | — |
| `manual.extract.extract_text(path)` | `Document \| ProviderError`, never raises, `DEADLINE_SECONDS` | truncated zip/pdf, zip bomb |

## Fixed decisions

| Question | Rule |
|---|---|
| Allowed outcomes | exactly the "Declared contract" column. Anything else raised = defect → wrap into the declared refusal at the parser boundary. |
| Non-finite number in a fact | not a fact: counted in `unparsed`. |
| Corpus | mutation fuzzing over real files in `tests/data/` and `fixtures/`: truncate at a drawn offset, flip drawn bytes, splice two files. Plus `st.binary()`. |
| Reproducer | each crash found → minimal input saved as `tests/data/fuzz/<entry>/<sha8>.bin`; one regular test replays the whole folder through the contract. |
| Deep runs | marker `slow` (add to `pyproject.toml` markers and to `addopts` as `-m "not live and not slow"` if not present). Default-run fuzz ≤ 30 s total. |

## F1. Contract harness

`tests/test_fuzz_parsers.py`: one property per row of the table, each
asserting "outcome ∈ declared contract", plus: facts' values finite,
`unparsed >= 0`, `len(facts) <= number of input rows` (CVM).

**Done when:** green in default profile; every defect found is fixed and
has a reproducer file; report table: entry → defects found → shrunk input
(hex, ≤ 80 bytes shown).

## F2. Hostile XML

For `parse_form4`: billion-laughs entity expansion and an external
entity pointing at a temp file with a known marker string.

**Done when:** both return `ValueError` or a filing within 2 s; the
marker string never appears anywhere in the returned object
(`repr` checked); test green.

## F3. Hostile containers for manual import

For `extract_text`: zip bomb (≥ 1 GB declared, tiny on disk), zip with
`../` member name, PDF magic + junk, docx with a missing
`word/document.xml`, empty file, 0-byte-after-magic.

**Done when:** each yields `ProviderError` with a reason from the
existing `extract_*` family (or `format_unsupported` when the library is
absent), wall time ≤ `DEADLINE_SECONDS + 1`; nothing written outside
`tmp_path`; test green.

## F4. Replay folder

**Done when:** `tests/test_fuzz_replay.py` walks `tests/data/fuzz/**`
and is green; it fails (not skips) if the folder exists but is empty
when F1 reported defects; `bash agent/acceptance.sh` green.

## F5. Deep run evidence

**Done when:** `HYPOTHESIS_PROFILE=deep python3 -m pytest -m slow
tests/test_fuzz_parsers.py -q` run once; the report gives wall time and
example counts per entry.
