# REPORT-83 — ТЗ-83, круг 117

Branch `agent/night-11`, head on arrival `a1b948e` («Эстафета: круг 117, ход у
executor — agent/TASK-83.md»), baton `agent/TASK-83.md`, report here. English
per AGENTS.md; command output quoted as it came out. Budgets: network 0 —
Hypothesis is already installed from TASK-82, so the one permitted request was
not spent (Runs 3); LLM calls 0. Every probe of a parser in this round reads
bytes from memory or from `tests/data/`, opens no base, and never runs
`rusterm` without an explicit `--root` under `/tmp` (PROTOCOL §2 P7).

## Arrival state (measured before the first source edit)

The hand landed green as transport but red as bookkeeping: `agent/BATON.json`
had moved to round 117 while `agent/STATE.json` still named the closed round
(`task: agent/TASK-82.md`, `report: agent/REPORT-82.md`,
`status: awaiting_review`). The report guards take the round number from the
baton and the report path from STATE, so the branch head screened round 117's
commits against TASK-82's item ids:

```
$ python3 -m pytest tests/test_report_sections.py -q -o addopts=""
FAILED tests/test_report_sections.py::test_done_items_have_code_commits_in_round
1 failed, 27 passed in 1.46s
AssertionError: пункты ['E1'] объявлены сделанными, но коммита круга с
реализацией (не только tests/) не найдено
```

This is the mechanism recorded as entry 1 of `## Disputed` in REPORT-82, seen
again from the other side: because the pre-commit hook runs acceptance, the
repair has to be the round's first commit, and it is the one below. Nothing in
`rusterm/` or `tests/` was red on arrival for a different reason — the failing
assertion is about bookkeeping, not about the tree's code.

## Done

### F1 — contract harness, and the defects it found

Harness: `tests/test_fuzz_parsers.py` — one property per row of the contract
table, plus a corpus census test so no property can be silently vacuous
(5 ownership XMLs, 22 companyfacts payloads, 8 synthetic fixtures, 40+ real DFP
rows read the way `CvmProvider.rows_for` reads them, latin-1 + `;`).

Corpus per the fixed decisions: byte mutation of those real files (truncate /
flip / splice / insert) and `st.binary()`. One addition, because it is needed
by row 2's stated suspicion («wrong shapes»): a byte mutation almost never
leaves valid JSON with a wrong shape, so a JSON-aware mutator replaces one drawn
node of a real document with `null`, an int, a string, `[]`, `{}`, `true` or a
NaN/inf literal.

Red before any source edit — the harness run against `193474d` in a temp
worktree (`$TMPDIR/rt83-base`, parsers unfixed), full log
`/tmp/rt83-baseline-final.log`:

```
$ cd "$TMPDIR/rt83-base" && PYTHONPATH="$TMPDIR/rt83-base" \
  python3 -m pytest tests/test_fuzz_parsers.py -p no:cacheprovider
5 failed, 2 passed, 5 deselected in 56.73s
FAILED ...::test_form4_refuses_or_returns_filing
FAILED ...::test_companyfacts_returns_parse_result
FAILED ...::test_parse_auto_returns_result_or_none
FAILED ...::test_cvm_rows_never_yield_non_finite_fact
FAILED ...::test_deeply_nested_json_refused_by_every_json_entry
```

Defects, entry by entry. Each row is a *family* (a hole), the count is how many
distinct error messages folded into it, and the input is the shrunk reproducer
committed under `tests/data/fuzz/<entry>/<sha8>.bin`. Shrinking is greedy byte
deletion under a stable coarse key (exception class, or «contract violated»),
run against the unfixed parsers; `hypothesis.find` was tried first and raised
`TypeError` on its own signature — see Runs 6.

| entry (row) | family, found as | msgs | reproducer | shrunk input, hex |
|---|---|---|---|---|
| `parse_form4` (1) | `ParseError` escapes instead of `ValueError` — 9 expat reasons (mismatched tag, junk after document element, unclosed token, unbound prefix, …) | 9 | `form4/e3b0c442.bin` | (empty file) |
| `CompanyFactsParser.parse` (2) | `UnicodeDecodeError` — strict utf-8 decode of a vendor body | 66 | `companyfacts/85f97e04.bin` | `d2` |
| ″ | `JSONDecodeError` — 9 reasons (Expecting value, Extra data, Unterminated string, Illegal trailing comma, Invalid \escape, …) | 9 | `companyfacts/e3b0c442.bin` | (empty file) |
| ″ | `AttributeError: 'int' object has no attribute 'get'` — JSON scalar as document | 1 | `companyfacts/ef2d127d.bin` | `35` |
| `parse_rows` (3) | non-finite fact from `VL_CONTA` `nan` | 5 | `cvm/cf898bab.bin` | `5b7b2244545f46494d5f4558455243223a2022323032332d31322d3331222c202243445f434f4e54` |
| ″ | same, `Infinity` | 1 | `cvm/20033030.bin` | `5b7b2244545f46494d5f4558455243223a2022323032332d31322d3331222c202243445f434f4e54` |
| ″ | same, `-Infinity` | 3 | `cvm/61670b62.bin` | `5b7b2244545f46494d5f4558455243223a2022323032342d31322d3331222c202243445f434f4e54` |
| ″ | `1e309` → `inf` from `float()` without an error | 1 | `cvm/6fe98963.bin` | `5b7b2244545f46494d5f4558455243223a2022323032342d31322d3331222c202243445f434f4e54` |
| ″ | 400-digit integer → `inf` (silent overflow), and the same after `× MIL` | 2 | `cvm/d44c3cda.bin` | `5b7b2244545f46494d5f4558455243223a2022323032332d31322d3331222c202243445f434f4e54` |
| `parse_auto` (4) | inherits row 2 through `doc_kind=companyfacts`: non-utf-8 / bad JSON / scalar document | 65+8+1 | `parse_auto/{85f97e04,e3b0c442,ef2d127d}.bin` | `d2` / (empty) / `35` |
| ″ | `AttributeError: 'str' object has no attribute 'get'` — a taxonomy section whose concept nodes are strings | 1 | `parse_auto/42dde40c.bin` | `7b22223a22222c22223a22222c22223a22222c22223a22222c226661637473223a7b22223a7b2222` |
| ″ (xbrl path) | `parse_auto` with `doc_kind=xbrl`: `SyntheticXBRLParser` on non-utf-8, bad JSON, scalar document | 70+7+1 | `parse_auto_xbrl/{966c7c47,e3b0c442,4b227777}.bin` | `f2` / (empty) / `34` |
| ″ (table path) | same three through `TableParser` with `doc_kind=table` | 70+7+1 | `parse_auto_table/{966c7c47,e3b0c442,4b227777}.bin` | `f2` / (empty) / `34` |
| `extract_text` (5) | none in this corpus: 2500 mutated synthetic/companyfacts payloads all answered `Document` or `ProviderError` | 0 | — | F3 attacks it with containers instead |

One more hole, found by hand and not by the generator, with a fixed test rather
than a file: `json.loads` is recursive-descent, and 400 000 opening brackets
raise `RecursionError` («Stack overflow (used 16352 kB)») — not a `ValueError`,
not a `ParseResult`. Committed as
`test_deeply_nested_json_refused_by_every_json_entry`, which is red on
`193474d` (Runs 8) and green now. No `.bin` for it: its size is a function of
the C stack, so a byte-exact blob would be a machine-specific fixture; the
generator in the test is the reproducer.

Fixes, all at the parser boundary, all refusals *as values*:

* `rusterm/parsers/__init__.py` — three shared helpers: `_document()` (decode,
  JSON and stack-overflow failures become one counted `unparsed` for the whole
  document), `_text()` (a non-string period is not a date: `determine_basis`
  and the fling comparison raise `TypeError` on mixed types), `_is_non_finite()`
  (fixed decision: a non-finite number is not a fact), plus `isinstance`
  guards wherever the code asked for a dict or a list. A missing or
  wrong-shaped `facts` / `tables` section counts as one unparsed, in all three
  parsers — the same rule, not three variants.
* `rusterm/parsers/ownership.py` — `ET.ParseError` wrapped into `ValueError`
  with the original as `__cause__`.
* `rusterm/parsers/cvm_dfp.py` — non-finite `VL_CONTA` and scale-overflowed
  results go to `unparsed`; `_cell()` so a non-string CSV field cannot raise
  `.strip()`/`int()` at the boundary.

Green and inside the budget:

```
$ python3 -m pytest tests/test_fuzz_parsers.py --durations=9
7 passed, 5 deselected in 1.90s
0.69s call  ...::test_cvm_rows_never_yield_non_finite_fact
0.44s call  ...::test_extract_text_never_raises
0.20s call  ...::test_parse_auto_returns_result_or_none
0.19s call  ...::test_companyfacts_returns_parse_result
0.16s call  ...::test_form4_refuses_or_returns_filing
```

1.90 s for the whole file against the 30 s default-run budget; the red run
above spent 56 s mostly in Hypothesis's own failure writing, not in parsers.

### F2 — hostile XML: the refusal must belong to the parser, not to libexpat

`tests/test_fuzz_xml.py`, 7 tests, all on the real entry `parse_form4`.
Every case carries the three F2 requirements: the row-1 contract
(`OwnershipFiling` or `ValueError`, re-checked through
`test_fuzz_parsers.check_form4_contract`), wall time under
`LIMIT_SECONDS = 2.0`, and the marker string absent from `repr` of
whatever came back.

Measured on `779422d` (F1 merged, before the F2 fix) — the two teeth tests
are red, five are green:

```
$ python3 -m pytest tests/test_fuzz_xml.py
2 failed, 5 passed in 0.39s
test_harmless_entity_is_refused_too  - Failed: DID NOT RAISE ValueError
test_dtd_in_a_comment_still_refused  - Failed: DID NOT RAISE ValueError
```

The five greens are not evidence of our own strength. A probe outside
pytest (scratch, `/tmp/rt83-staging/f2-probe.py`) showed what actually
refused the attacks on this host:

```
billion-laughs: 0.115s peak_rss=76.3MB leak=False -> ValueError: неразобран XML:
    limit on input amplification factor (from DTD and entities) breached
xxe-file: 0.000s leak=False -> ValueError: неразобран XML: undefined entity &xxe;
xxe-parameter: 0.000s leak=False -> filing insider='' issuer=None
control: 0.000s -> filing insider='JANE DOE' issuer='Apple Inc.'
```

So: billion laughs was stopped by libexpat 2.8.1 (`EXPAT_VERSION =
expat_2.8.1`, measured), an amplification ceiling that does not exist in
libexpat < 2.6; the external general entity was refused because stdlib
expat never fetches external entities; and the parameter-entity variant
came back as a *filing* (no fetch, no marker — allowed by the contract,
and the test accepts either outcome as long as the marker stays out). A
contract held by the host's XML library is not held by RusTerm, so F2
moves the refusal into `parse_form4`.

Fix, `rusterm/parsers/ownership.py`:

* `_refuse_dtd(raw)` runs before any parsing: a `<!DOCTYPE` or `<!ENTITY`
  (case-insensitive) in the buffer raises `ValueError` naming what was
  found. A Form 4 cover never carries a DTD — measured: `grep -rliE
  "<!\[CDATA|<!DOCTYPE|<!ENTITY" tests/data/` returns nothing — so a
  declared entity is an attack marker, not a weird-but-parseable input.
* Scan is over the whole buffer, not the prolog: a prolog cut at the
  first `<letter` tag is evaded by `<!-- <x> --> <!DOCTYPE ...>`, which is
  `test_dtd_in_a_comment_still_refused`. The false-positive direction is
  closed by XML itself — literal `<!` cannot appear in text, it arrives
  escaped (`test_escaped_markup_in_text_is_not_a_dtd`).
* `parse_form4` docstring now names the DTD branch.

Corpus: the billion-laughs document is stored as
`tests/data/fuzz/form4/093619a6.bin` (1041 B, generated by the same
`_lol_dtd()` the test uses) and is replayed by F4. The XXE input is not
stored — it embeds a machine-specific temp path, same limitation as the
`RecursionError` reproducer in Disputed 3.

Green after the fix, together with the F1 harness and the pre-existing
ownership tests:

```
$ python3 -m pytest tests/test_fuzz_xml.py tests/test_ownership.py tests/test_fuzz_parsers.py
21 passed, 6 deselected in 4.72s
```

and the parser-adjacent subset (`-k "parser or parse or pipeline or store
or cvm or edgar or manual or extract or ownership or fact or ingest"`):
`231 passed, 1 skipped, 1016 deselected, 1 xfailed in 28.40s`.

## Blocked

none

## What not to trust

* F1 proves the found holes stay shut at 200 examples per property (default
  profile, `derandomize=True`) — it does not prove there are no other holes.
  The wider net is F5's deep run, and it is a net, not a proof.
* Row 5 (`extract_text`) came back with **zero** defects from a byte/JSON
  corpus. That is weak evidence: containers, not JSON text, are what this
  function parses. Do not read its green property as «extract is hardened» —
  F3 is where it is actually attacked.
* The non-finite rule is applied where a fact carries a value. `_check_fact_value`
  treats a value that does not parse as a number at all as out of scope
  (returns early) — a vendor string like `"1 234"` still becomes a fact. That
  is the pre-existing behaviour of all three JSON parsers, not something F1
  changed.
* `_document()` now swallows every `ValueError` out of `json.loads` and the
  stack-overflow `RecursionError`: what used to crash `pipeline.py`,
  `core/refresh.py:51` and `cli/__init__.py:483` on a corrupt body is now a
  `ParseResult(facts=[], unparsed=1)`. Loudness moved from a traceback to
  `coverage_reason = f"unparsed:{…}"` (`rusterm/pipeline.py:285-286`, read, not
  executed at runtime here) — the coordinator may want that string to reach the
  user, not only the coverage row.
* A missing or wrong-shaped `facts` / `tables` section now counts as one
  unparsed (it used to count as zero in `TableParser`). Nothing in the suite
  depends on the old number; an external expectation would.
* `cli/__init__.py:789` still catches `(_ET.ParseError, ValueError)` although
  `ParseError` can no longer escape `parse_form4`. Left alone: F1's scope is
  the parser boundary, and dead half of a catch tuple is not a defect.
* F2's guard is a byte check, so its risk is a false refusal, not a missed
  attack: a hypothetical Form 4 that printed the literal `<!ENTITY` or
  `<!DOCTYPE` anywhere — including inside a CDATA section — would now be
  rejected. Measured: no file under `tests/data/` contains either marker, and
  EDGAR covers carry CIKs, dates and names, not XML source. Nothing in the
  suite forces a *hostile* DTD past the guard either way: after `_refuse_dtd`
  fires, the tests can no longer tell "expat refused" from "we refused". The
  probe quoted in F2 is that attribution, and a probe is a measurement, not a
  check the suite keeps honest.
* Budget so far: 0 network requests, 0 LLM calls (F1 and F2 needed neither).

## Disputed

1. Row 1 (`parse_form4`) has no counted channel: the fixed decision «non-finite
   number in a fact → counted in `unparsed`» cannot be applied to it, because
   `OwnershipFiling` has no `unparsed` field and adding one is a data-model
   change, not a boundary fix. Measured consequence: `shares`/`price` drawn as
   `"NaN"`/`"inf"` pass `_float()` and land in a legal return value
   (`OwnershipTransaction(shares=nan)`). Left as is; ask: should
   `OwnershipFiling` grow a counter, or should `_float()` return `None` for
   non-finite text (the second option is one line and loses nothing)?
2. Row 3 (`parse_rows`) declares `(facts, unparsed)`, yet a `statement` outside
   `DRE`/`BPP` raises `ValueError`. `statement` is a caller-side enum, not
   vendor bytes, and no fuzz domain draws it, so the raise is a
   programming-error signal rather than a hostile-input path — kept. Say the
   word if the contract column is meant literally and I will turn it into
   `(facts, len(rows))`.
3. F1's «Done when» asks that every defect has a reproducer *file*. The
   `RecursionError` hole gets a fixed test instead: its minimal size is a
   function of the C stack (measured: 5 000 brackets parse, 100 000 do not), so
   a byte-exact `.bin` would be a fixture that only fails on this machine.
   Treating the generator as the reproducer — flagged as a deviation from the
   letter of the item.
4. F2 hardens row 1 only. Row 5's XML neighbours are a different story and I
   did not touch them: `rusterm/manual/extract.py:115 _parse_xml` is dead code
   (no callers — `grep -rn _parse_xml rusterm/` returns the definition plus a
   `.pyc`), and the module's `defusedxml` import at `extract.py:53-59` is a
   preference, not a dependency: `pyproject.toml` declares `dependencies = []`
   and defusedxml appears in no extra group. Measured here: `_XML_PARSER_NAME
   = "defusedxml"`, version 0.7.1 — installed, undeclared, so a user's install
   can land on the stdlib branch whose name promises «DTD и внешние сущности
   отключены». Ask: delete the dead helper, declare defusedxml, or move F2's
   byte guard into `_parse_xml` and actually route the docx/xlsx parts through
   it? All three are outside F2's letter, so none is done here.

## Runs

| # | command | output |
|---|---|---|
| 1 | `python3 -m pytest tests/test_report_sections.py -q -o addopts=""` (arrival, `a1b948e`) | `1 failed, 27 passed in 1.46s` |
| 2 | `python3 agent/relay.py --branch agent/night-11 status --assert-holder executor` | `круг 117: ход у executor  task=agent/TASK-83.md  report=agent/REPORT-83.md`, exit 0 |
| 3 | `python3 -c "import hypothesis; print(hypothesis.__version__)"` | `6.168.1` |
| 4 | `git worktree add --detach "$TMPDIR/rt83-base" 193474d` + `PYTHONPATH="$TMPDIR/rt83-base" python3 -m pytest tests/test_fuzz_parsers.py -p no:cacheprovider` (parsers unfixed) | `5 failed, 2 passed, 5 deselected in 56.73s` |
| 5 | same command in the fixed tree | `7 passed, 5 deselected in 1.90s`; slowest property `0.69s` |
| 6 | first harvest used `hypothesis.find(strategy, predicate, settings=…, database=None)` | `TypeError` on the signature for every entry; replaced by a greedy minimizer (`/tmp/rt83-staging/harvest.py`) |
| 7 | `REPO="$TMPDIR/rt83-base" … python3 /tmp/rt83-staging/harvest.py "$TMPDIR/rt83-lab/repro3"` (SAMPLE=2500) then `python3 /tmp/rt83-staging/curate.py … tests/data/fuzz` | 148 distinct defect messages → 19 families → 19 files, 5 entry folders |
| 8 | `REPO="$TMPDIR/rt83-base" FUZZ="$TMPDIR/rt83-base/tests/data/fuzz" python3 /tmp/rt83-staging/replay.py` (unfixed parsers) | `файлов: 19, с дефектом: 19` |
| 9 | same in the fixed tree (`REPO=/tmp/rt-night11-exec`) | `файлов: 19, с дефектом: 0` |
| 10 | `python3 -m pytest tests/test_fuzz_parsers.py::test_deeply_nested_json_refused_by_every_json_entry` in `$TMPDIR/rt83-base` | `AssertionError: CompanyFactsParser.parse бросил RecursionError на входе из 400000 байт`; `RecursionError: Stack overflow (used 16352 kB) while decoding a JSON array` |
| 11 | `python3 -m pytest tests/ -k "parser or parse or pipeline or store or cvm or edgar or manual or extract or ownership or fact"` (fixed tree) | all dots, 1 xfail, 1 skip, exit 0 |
| 12 | `git commit -F …` for F1 (hook = `agent/selfcheck.sh` → full acceptance) | `Итог: пройдено 13, провалено 0` / `Принято.` → `779422d`, pushed |
| 13 | `python3 -m pytest tests/test_fuzz_xml.py` on `779422d`, before the F2 guard | `2 failed, 5 passed in 0.39s` — `DID NOT RAISE ValueError` in `test_harmless_entity_is_refused_too` and `test_dtd_in_a_comment_still_refused` |
| 14 | `PYTHONDONTWRITEBYTECODE=1 python3 /tmp/rt83-staging/f2-probe.py` (same tree, no guard) | output quoted in F2: expat's amplification ceiling refuses billion laughs in 0.115s, `undefined entity` refuses the XXE, the parameter-entity variant returns a filing |
| 15 | `python3 -c "import xml.parsers.expat as e; print(e.EXPAT_VERSION)"` | `expat_2.8.1` |
| 16 | `grep -rliE "<!\[CDATA|<!DOCTYPE|<!ENTITY" tests/data/` | no matches (empty output) |
| 17 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_fuzz_xml.py tests/test_ownership.py tests/test_fuzz_parsers.py` (guard in) | `21 passed, 6 deselected in 4.72s` |
| 18 | `python3 -m pytest -k "parser or parse or pipeline or store or cvm or edgar or manual or extract or ownership or fact or ingest"` (guard in) | `231 passed, 1 skipped, 1016 deselected, 1 xfailed in 28.40s` |
| 19 | `python3 -c "import rusterm.manual.extract as e; print(e._XML_PARSER_NAME)"` + `import defusedxml` | `defusedxml` / `defusedxml 0.7.1` — installed here, declared nowhere (Disputed 4) |

## HANDOFF

Status: WORKING — круг 117 идёт, F1 и F2 закрыты коммитами.

Items done: приём круга (STATE + отчёт), F1, F2.
Items not done: F3 (hostile containers for `extract_text`), F4
(`tests/test_fuzz_replay.py` + acceptance), F5 (one deep run with
`HYPOTHESIS_PROFILE=deep -m slow`). Queue order is F3 → F4 → F5, one commit
each.

Network: 0 requests spent (Hypothesis уже установлен в прошлом круге).
LLM calls: 0.
Open questions to the coordinator: the four entries in `## Disputed` — row 1
of the contract table has no `unparsed` channel, row 3 keeps raising on an
unknown `statement`, the `RecursionError` reproducer lives in a test rather
than in `tests/data/fuzz/`, and F2 left row 5's XML neighbours (`_parse_xml`
dead helper, undeclared `defusedxml`) alone. None of the four is fixed in
code.
NOW: F3, step 1
