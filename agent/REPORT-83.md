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

### F3 — hostile containers: nothing was broken, so the deliverable is a pinned contract

`tests/test_fuzz_containers.py`, 21 tests on the real entry
`extract_text`. One helper, `_call(tmp_path, name, payload)`, carries all
three F3 requirements for every case: wall time ≤ `DEADLINE_SECONDS + 1`,
a `ProviderError` whose reason head belongs to the family `extract.py`
pronounces itself (`_known_reasons()` scrapes `reason=…` out of the
module source instead of being hand-written, so a test cannot bless a
reason that no longer exists), and a directory snapshot of `tmp_path` and
its parent taken immediately around the call.

Measured result: **zero defects**. Every hostile input came back as a
value, in ≤ 0.07 s, and wrote nothing anywhere (the three `EOF marker not
found` lines the probe also prints are pypdf's own noise on stderr, not
exceptions — `extract_text` still returns a value). Reprobed against the
committed generator (`/tmp/rt83-staging/f3-probe3.py`, log
`/tmp/rt83-f3-probe3.log`):

```
zip-bomb-1gib              0.00s disk=    125 -> extract_zip_bomb:uncompressed>536870912
zip-bomb-compressed-field  0.00s disk=    125 -> format_unsupported:unknown_zip_container
zip-lies-declares-16       0.04s disk=   2204 -> extract_docx_refused:KeyError
many-members               0.01s disk= 395211 -> extract_zip_bomb:members>4096
zip-traversal-slash        0.00s disk=    156 -> format_unsupported:unknown_zip_container
zip-traversal-backslash    0.00s disk=    154 -> format_unsupported:unknown_zip_container
zip-traversal-in-docx      0.00s disk=    279 -> extract_docx_refused:KeyError
docx-without-document-xml  0.00s disk=    146 -> format_unsupported:unknown_zip_container
zip-empty-archive          0.00s disk=     22 -> format_unsupported:binary
zip-magic-only             0.00s disk=      4 -> format_unsupported:zip_corrupt
pdf-magic-junk             0.07s disk=     73 -> format_unsupported:pdf_parse_PdfStreamError
pdf-magic-only             0.00s disk=     5  -> format_unsupported:pdf_parse_PdfStreamError
nul-only                   0.00s disk=      1 -> format_unsupported:binary
empty-file                 0.00s disk=      0 -> no_text_layer
вне ROOT: [], deadline=60.0,  «добавилось в каталоге»: [] у всех 14 строк
```

So F3 adds no source change and no assert that catches a live bug; what it
buys is visibility — the magic table and the zip guard are now pinned, and
the six observations below are recorded instead of being re-learned in a
year.

Corpus (F4's input): 11 files in `tests/data/fuzz/extract/`, from 4 B
(`8dcc7e60`, bare `PK\x03\x04`) to 2 204 B (`e3ef8935`, the zip that
declares 16 bytes). Two cases stay generator-only: the 0-byte file — a
content-addressed folder of empty files is a lie — and the 4 097-member
archive (395 KB of git for one reason string, built in place by
`test_zip_member_count_ceiling`).
`test_corpus_folder_matches_generated_inputs` compares the folder against
the generator's remaining outputs byte for byte.

Findings worth the coordinator's eye:

* **`zipfile` is not reproducible.** `writestr("name", bytes)` stamps
  `date_time` from the wall clock, so archive bytes change every day. The
  generator now builds `ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))`
  with `external_attr = 0o600 << 16`; verified by running it in two
  separate processes — identical sha8 names. Without that, the
  corpus-equals-generator test F3 hands to F4 would go red on its own
  tomorrow.
* **Where the declared size actually lives.** Measured on a real
  archive: in a central-directory entry the *uncompressed* size is at
  offset +24 from `PK\x01\x02`, the compressed one at +20 (the local
  header is the other way round — my first probe patched +20 and reported
  the bomb as `unknown_zip_container`, which looked like a working guard
  and was not one). `_zip_guard` reads `infolist()`, i.e. `file_size` =
  uncompressed — hence 1 GiB declared inside 125 bytes on disk is refused
  before any unpacking. A bomb that instead overflows the **compressed**
  field walks past the guard: still refused, by a different branch.
  `test_magic_table_knows_only_local_header_zip` pins both halves so
  «ceiling on the declared size» is not oversold (see the new «What not to
  trust» bullet).
* **A declared size can lie the other way, and then the ceiling is
  useless.** Rewriting *uncompressed size* to 16 bytes in both the central
  directory and the local header (leaving `compress_size` and CRC honest)
  lets a 2 MiB member walk past `_zip_guard` — the guard sums declared
  sizes. What stops it downstream is `zipfile` itself: measured
  `BadZipFile: Bad CRC-32 for file 'word/document.xml'` from `zf.read` and
  from a streamed `zf.open` loop, and `extract_text` on the same container
  returned `extract_docx_refused:KeyError` in 0.04 s. So the refusal is
  real but the *cause* is not the ceiling →
  `test_zip_lying_about_size_fools_the_ceiling_and_still_refuses` pins
  exactly that (it asserts the reason is **not** `extract_zip_bomb…`, so
  the day someone makes the ceiling content-aware the test says «rewrite
  me and the note»). The 1 GB-declared case remains the guard's own win.
* **The members ceiling had no test at all.** `grep -rn
  "MAX_ZIP_MEMBERS\|members>" tests/*.py` before F3: no matches — the
  first branch of `_zip_guard` was unpinned while the size branch was
  reachable only by hand. Now pinned by name and value
  (`extract_zip_bomb:members>4096`).
* **`_ZIP_MAGIC` is the local-header signature only** (`extract.py:51`) →
  a valid empty archive (`PK\x05\x06` + 18 zero bytes, what `zipfile`
  writes for zero members) never reaches the container branch and is
  refused as `format_unsupported:binary` because the text branch sees
  NULs. Refusal is right, the reason name is arguable → Disputed 5. The
  test pins the measured string, not the preferred one.
* `_call`'s «nothing appeared next to the file» assertion needs to run
  *after* the autouse fixture at `tests/conftest.py:35`, which writes
  `empty-rusterm.env` into every `tmp_path` (P7 isolation). First version
  snapshotted before the fixture: 14 reds blaming `extract_text` for a
  file the harness created.

Teeth, proved by mutation in an isolated detached worktree
(`$TMPDIR/rt83-base` at `193474d`; `rusterm/manual/extract.py` there is
byte-identical to the clone's, sha1 `1b61cb7075e5b5aa7604cc06e0bdc241e19d4325`),
never in the working clone — one inserted line at the top of `_zip_guard`:

```
+    return None  # МУТАЦИЯ: guard выключен

$ python3 -m pytest tests/test_fuzz_containers.py   (log /tmp/rt83-f3-mutation.log)
2 failed, 19 passed in 0.36s      # тот же файл до мутации: 21 passed in 0.35s
FAILED ::test_zip_bomb_refused_on_declared_size_before_unpacking
AssertionError: бомба отвергнута не по потолку распаковки, а иначе:
    'format_unsupported:unknown_zip_container' — guard не сработал?
FAILED ::test_zip_member_count_ceiling
AssertionError: отказ по числу элементов пришёл с другой причиной:
    'format_unsupported:unknown_zip_container'
```

Note what the mutation did *not* do: both bombs were still refused — by
the «this zip has no document parts» branch, because a bomb built from
`payload.txt` has no docx/xlsx member either. That is why these two tests
assert the reason string and not just «a `ProviderError` came back»: a
refusal of the wrong kind has to look like a failure. The third new case
(the size-lying zip) stayed green under the mutation — by design, it
claims the ceiling is *not* what stops that one. Worktree restored
directly from git afterwards (`git checkout -- rusterm/manual/extract.py`;
`grep -c МУТАЦИЯ` → 0, no `.bak` left anywhere).

Green (fresh):

```
$ python3 -m pytest tests/test_fuzz_containers.py
21 passed in 0.35s
$ python3 -m pytest tests/test_fuzz_containers.py tests/test_fuzz_parsers.py \
      tests/test_fuzz_xml.py tests/test_manual_extract.py
52 passed, 5 deselected in 2.62s
$ python3 -m pytest -k "parser or parse or pipeline or store or cvm or edgar \
      or manual or extract or ownership or fact or ingest"
231 passed, 1 skipped, 1035 deselected, 1 xfailed in 26.86s
```

(The third run predates the last two cases being added — it deselects the
new file entirely: its node ids match none of those keywords. The first
two runs are the ones that cover it.)

Budget: 0 network requests, 0 LLM calls. No `rusterm` process was run in
this item — containers go through the library API into pytest's
`tmp_path`, nothing near `~/.rusterm` or `~/equitylab` (P7).

### F4 — the corpus became a check, not an inventory

`tests/test_fuzz_replay.py`, 66 tests over the 31 files in
`tests/data/fuzz/`. The replay calls the same public `check_*` functions as
F1's harness (`from tests.test_fuzz_parsers import …`) instead of
re-implementing the contract table — the property and the replay cannot
drift apart, which is what this item is for.

Shape:

* two tests per file: «this input respects its declared contract», and «the
  file name is the sha8 of its own bytes» (F1's naming rule — a renamed or
  edited artifact stops being evidence);
* `KNOWN_ENTRIES` maps every folder to its contract row, and
  `test_no_unmapped_entry_folders` reddens on a folder that is not in the
  map, so a new corpus directory has to arrive carrying its own check;
* row 5 takes a path, not bytes: the replay writes the payload into
  `tmp_path`, the repository copy is only ever read;
* the census is per folder (`companyfacts` 3, `cvm` 5, `extract` 11,
  `form4` 2, `parse_auto` 4, `parse_auto_table` 3, `parse_auto_xbrl` 3)
  rather than one total floor: a single `>= 19` would stay green after half
  of `extract/` was deleted, because F1's own 19 files already satisfy it.

Teeth, all measured in the scratch worktree (`$TMPDIR/rt83-base`) so the
clone's corpus was never touched:

```
rm -rf tests/data/fuzz && mkdir tests/data/fuzz      -> 5 failed, 1 passed
+ семь пустых каталогов по KNOWN_ENTRIES             -> 5 failed, 1 passed
+ один лишний каталог mystery/                       -> FAILED test_no_unmapped_entry_folders
тот же корпус против исходника 193474d (до Ф1)       -> 20 failed, 46 passed
```

Five failures, not zero, on an empty corpus: `_params()` substitutes a
`<пусто>` sentinel parameter when the walk yields nothing, so pytest cannot
collect an empty list and report success. That is the item's «fails, not
skips» requirement, and the second line above is its literal case (folders
present, no `.bin`). The fourth line is the more interesting one: the same
31 files, replayed against the pre-F1 parsers, produce 20 failures — the
folder carries real defects, not green bytes.

Green in the clone:

```
$ python3 -m pytest tests/test_fuzz_replay.py
66 passed in 0.55s
$ python3 -m pytest tests/test_fuzz_replay.py tests/test_fuzz_containers.py \
      tests/test_fuzz_parsers.py
94 passed, 5 deselected in 2.38s
```

Acceptance (the item's last requirement) is what this commit's own
`pre-commit` hook runs — `agent/selfcheck.sh` → `bash agent/acceptance.sh`,
log `/tmp/rt83-commit-f4.log`. A non-zero verdict aborts the commit, so the
existence of the F4 commit is the check having passed; the verdict line
itself is quoted after the fact in the F5 section, because writing «13/0»
into this section before the run finished would be exactly the unrun claim
P5 forbids.

Budget: 0 network requests, 0 LLM calls.

### F5 — one deep pass, and what it counted

`Done when`: `HYPOTHESIS_PROFILE=deep python3 -m pytest -m slow tests/test_fuzz_parsers.py -q`, run once, wall time and example counts per entry in the report. Run once, nothing else touching pytest at the same time (a parallel pass makes every timing number here lie — measured in an earlier round: 10.04 s quiet against 12.57 s under contention).

```
$ PYTHONPATH="$PWD:/tmp/rt83-staging" PYTHONDONTWRITEBYTECODE=1 \
      HYPOTHESIS_PROFILE=deep python3 -m pytest -m slow \
      tests/test_fuzz_parsers.py --durations=0 -p f5_counter -p no:cacheprovider
старт 02:03:55Z
.....                                                                    [100%]
====================== F5: примеры на точку входа (deep) =======================
hypothesis 6.168.1, профиль из окружения: deep, max_examples=5000, derandomize=False, database=None
check_form4_contract               примеров   5000  внутри check_*    0.11s
check_companyfacts_contract        примеров   5000  внутри check_*    0.46s
check_parse_auto_contract          примеров   5000  внутри check_*    0.13s
check_cvm_contract                 примеров   5000  внутри check_*    0.18s
check_extract_contract             примеров   5000  внутри check_*    3.63s
итого вызовов контракта: 25000
============================== slowest durations ===============================
48.68s call     tests/test_fuzz_parsers.py::test_cvm_rows_never_yield_non_finite_fact_deep
22.26s call     tests/test_fuzz_parsers.py::test_extract_text_never_raises_deep
 6.76s call     tests/test_fuzz_parsers.py::test_parse_auto_returns_result_or_none_deep
 5.91s call     tests/test_fuzz_parsers.py::test_companyfacts_returns_parse_result_deep
 5.28s call     tests/test_fuzz_parsers.py::test_form4_refuses_or_returns_filing_deep

(10 durations < 0.005s hidden.  Use -vv to show these durations.)
5 passed, 7 deselected in 91.18s (0:01:31)
exit=0
финиш 02:05:28Z
```

Verdict: **5 passed, 0 new defects**. `git status --porcelain` after the run is empty — the pass added no file to `tests/data/fuzz/` and left no `.hypothesis` store behind (`database=None`), so the deep pass is evidence, not a harvest.

Per entry — the wall time is what pytest measured for the property, the contract seconds are what the counter accumulated inside the `check_*` body:

| entry | examples | property wall | inside `check_*` | avg per call |
| --- | --- | --- | --- | --- |
| form4 (`OwnershipFilingParser.parse`) | 5000 | 5.28s | 0.11s | 0.022 ms |
| companyfacts (`CompanyFactsParser.parse`) | 5000 | 5.91s | 0.46s | 0.092 ms |
| parse_auto | 5000 | 6.76s | 0.13s | 0.026 ms |
| cvm (`CvmDfpParser.parse_rows`) | 5000 | 48.68s | 0.18s | 0.036 ms |
| extract (`extract_text`) | 5000 | 22.26s | 3.63s | 0.726 ms |
| **total** | **25000** | **91.18s** | **4.51s** | **0.18 ms** |

The ratio is the interesting number: 4.51 s of the 91.18 s pass, 4.9 %, is spent inside the code under test. Everything else is the generator — `cvm_rows(max_rows=24)` asks Hypothesis for a per-row dict copy plus a per-field mutation draw (that strategy alone is the difference between cvm's 48.68 s and its 0.18 s of contract time), and `extract` writes one file per example through `tmp_path_factory`. That attribution of the remainder is read off the strategies in `tests/test_fuzz_parsers.py`, not measured separately — recorded in `## What not to trust`. What *is* measured: `extract_text` is 20–60× more expensive per call than the four JSON/XML entries, which is the deadline guard's cost, not a defect.

Why a plugin for the counts: the `deep` profile is `derandomize=False, database=None`, so it leaves no example database behind and pytest prints no per-property count. `/tmp/rt83-staging/f5_counter.py` lives outside the repository on purpose — it wraps the five public `check_*` after module import (the properties look them up by name in their own module, which is what makes the wrapper see every real call) and prints the tally in `pytest_terminal_summary`. Putting a counter into the shipped test file would have baked measurement scaffolding into the product's suite.

Deviations from the command as written in the ТЗ, both so the evidence exists at all:
* `-q` dropped, `--durations=0` added: `addopts` already carries `-q`, so a second `-q` runs at `-qq` and hides the `5 passed … in 91.18s` totals line that is this item's deliverable.
* `PYTHONPATH`, `-p f5_counter`, `-p no:cacheprovider`: the counter is loaded from outside the repo, and no `.pytest_cache` may be written into the clone (P3/P4).
* The first attempt at this run exited 1: the counter read `settings.default_string`, which hypothesis 6.168.1 does not have, and crashed in `pytest_terminal_summary` *after* all five properties had passed (log `/tmp/rt83-f5-deep.log`, `AttributeError: type object 'settings' has no attribute 'default_string'`). The properties themselves were green in that pass; it produced no counts, so the same command was run again and the second log is the one quoted above. The wall time of the discarded pass is not included anywhere.

Consequence for the round's other claim: F4's acceptance verdict, promised in that section, is `Итог: пройдено 13, провалено 0` / `Принято.` (log `/tmp/rt83-commit-f4.log`, lines 7–9).

Budget: 0 network requests, 0 LLM calls.

## Blocked

none

## What not to trust

* F1 proves the found holes stay shut at 200 examples per property (default
  profile, `derandomize=True`) — it does not prove there are no other holes.
  The wider net is F5's deep run, and it is a net, not a proof.
* Row 5 (`extract_text`) came back with **zero** defects from a byte/JSON
  corpus. That is weak evidence: containers, not JSON text, are what this
  function parses. Do not read its green property as «extract is hardened» —
  F3 attacked it with real containers and also found nothing, but see the
  three F3 bullets below for what those greens do not cover.
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
* F3 pinned `extract_text`, it did not harden it. The zero-defect result is
  over 14 containers of my own choosing; and two of the refusals hold only
  because the container has no document parts — a hostile zip that *does*
  carry `word/document.xml` is handed to python-docx, and what happens
  inside that library is not covered by anything here.
* F3's second borrowed safety (same shape as F2's): the zip ceiling reads
  **declared** sizes. Measured — a member declaring 16 bytes while holding
  2 MiB walks past `_zip_guard`, and what stopped the read was stdlib
  `zipfile`'s CRC check (`BadZipFile: Bad CRC-32`), not our code. On a host
  whose zipfile is more trusting the outcome could be a 2 MiB (or 2 GB)
  allocation. Recorded as Disputed 6 rather than fixed: F3's letter asks
  for the declared-1 GB case, which the guard does own and pin.
* The mutation quoted in F3 is the guard's own value: with `_zip_guard`
  stubbed out, both bombs are *still refused* (by `unknown_zip_container`).
  So a future regression that deletes the ceiling would not turn this suite
  red through «no refusal» — only through the reason strings. Reading the
  F3 greens as «bombs are impossible» would be wrong.
* F5's 25 000 contract calls found nothing new, and their distribution is
  unrepeatable: `derandomize=False` with `database=None` means the pass can
  only be re-run, not replayed — no seed is recorded, because the shipped
  harness has no `.hypothesis` store to record it from. The number of
  *examples* is solid (the counter saw every call); the identity of those
  examples is gone.
* The 4.51 s / 91.18 s split from F5 is a measurement of where the counter
  sat, not of where Hypothesis spends its time; the attribution to the
  strategies (a 24-row draw for cvm, a file write per example for extract) is
  read off `tests/test_fuzz_parsers.py` and was not isolated by a separate
  experiment.
* F5 ran `-m slow`, i.e. only the five deep properties. The other seven tests
  of that file were deselected by that marker (`5 passed, 7 deselected`), so
  this pass says nothing about them — their evidence is the runs in F1 and F4.
* Budget so far: 0 network requests, 0 LLM calls (no item of the round needed
  either).

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
5. F3, containers with a valid but *empty* zip: `extract.py:51` sets
   `_ZIP_MAGIC = b"PK\x03\x04"`, i.e. the local-file-header signature, while an
   archive with zero members starts with the end-of-central-directory record
   `PK\x05\x06`. Such a file therefore never reaches `_extract_zip_container`
   and is refused as `format_unsupported:binary` (the text branch sees NUL
   bytes) instead of a zip-flavoured reason. The refusal is correct and fast;
   only the name of it misleads an operator reading a coverage row. Ask: widen
   the magic table to `PK\x05\x06` (and `PK\x07\x08`, the spanned signature),
   or accept `binary` as «not a document we can read»? Pinned as measured
   rather than as preferred, so the moment the table changes the test says so.
6. F3, how far the zip ceiling can be trusted: `_zip_guard` sums the
   *declared* uncompressed sizes from `infolist()`, so a member that declares
   16 bytes and holds 2 MiB passes the ceiling. Measured: `zipfile` then
   refuses the read itself with `BadZipFile: Bad CRC-32` (both `zf.read` and a
   streamed `zf.open` loop), and `extract_text` returned
   `extract_docx_refused:KeyError` in 0.04 s — so on this host the hole is
   closed by the standard library, not by us. Ask: count decompressed bytes
   while reading (a few lines in `_extract_docx`/`_extract_xlsx`), or keep the
   declared-size ceiling and treat stdlib CRC as the second line? F3's letter
   names only the «≥ 1 GB declared» case, which the ceiling does own, so no
   code was changed here; the behaviour is pinned by
   `test_zip_lying_about_size_fools_the_ceiling_and_still_refuses`.
7. Protocol, not product: a PreToolUse hook blocks edits whose text mentions
   the zip ceiling, and tells me to run `pytest tests/test_guard_selfcheck.py`
   first — measured: `ERROR: file or directory not found:
   tests/test_guard_selfcheck.py` (the repo has `test_selfcheck_guard.py`,
   `test_i5_guard_source.py`, `test_llm_guard.py` instead). Two of the blocked
   edits had in fact been applied before the block arrived, so the report text
   above was verified line by line rather than trusted. Ask: point that hook
   at a test file that exists, or limit it to paths under `rusterm/` — right
   now it fires on prose in `agent/REPORT-*.md` and on a scratch probe in
   `/tmp`.

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
| 20 | first F3 suite run, then the same after the «nothing appeared» snapshot was moved behind the autouse fixture | `14 failed` blaming `empty-rusterm.env` → `18 passed in 0.27s` |
| 21 | `PYTHONDONTWRITEBYTECODE=1 python3 /tmp/rt83-staging/f3-probe3.py` (log `/tmp/rt83-f3-probe3.log`) | the reason/time table quoted in F3; `вне ROOT: []`, «добавилось в каталоге» empty on every row |
| 22 | measured central-directory offsets with `struct.unpack` on a real archive | first probe patched +20 (compressed) → bomb refused as `unknown_zip_container`, guard untouched; after the +24 (uncompressed) correction → `extract_zip_bomb:uncompressed>536870912` |
| 23 | generator determinism: regenerated the corpus in two separate processes | identical sha8 names; before pinning `date_time`, `zipfile.writestr` stamped wall-clock time and the names changed between runs |
| 24 | `grep -rn "MAX_ZIP_MEMBERS\|members>" tests/*.py` | no matches — the members ceiling had no test before F3 |
| 25 | `PYTHONDONTWRITEBYTECODE=1 python3 /tmp/rt83-staging/f3-lie-probe.py` | `disk=2204 объявлено=16 compress_size=2072`; `zf.read: BadZipFile: Bad CRC-32`; `zf.open: BadZipFile: Bad CRC-32`; `extract_text: ProviderError: extract_docx_refused:KeyError за 0.04s`; `мусор рядом: []` (Disputed 6) |
| 26 | mutation in `$TMPDIR/rt83-base` (one inserted `return None` at the top of `_zip_guard`), then `git checkout --` | clean tree: `21 passed in 0.35s`; mutated: `2 failed, 19 passed in 0.33s` (log `/tmp/rt83-f3-mutation.log`); after restore `grep -c МУТАЦИЯ` → `0` |
| 27 | final runs in the clone | `21 passed in 0.35s`; `52 passed, 5 deselected in 2.62s`; wide `-k` subset `231 passed, 1 skipped, 1035 deselected, 1 xfailed in 26.86s` |
| 28 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_guard_selfcheck.py -q`, as the PreToolUse hook instructs | `ERROR: file or directory not found: tests/test_guard_selfcheck.py` (Disputed 7) |
| 29 | `git commit -F …` for F3 (hook = selfcheck → full acceptance) | `Итог: пройдено 13, провалено 0` / `Принято.` / `SELFCHECK OK` → `680e58d`, pushed (log `/tmp/rt83-commit-f3.log`) |
| 30 | `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_fuzz_replay.py` (clone, 31 files) | `66 passed in 0.55s` |
| 31 | same file in `$TMPDIR/rt83-base` с `rm -rf tests/data/fuzz` и затем с семью пустыми каталогами | `5 failed, 1 passed` в обоих случаях — пустой корпус красен, а не skipped |
| 32 | там же, `mkdir tests/data/fuzz/mystery` | `FAILED tests/test_fuzz_replay.py::test_no_unmapped_entry_folders` |
| 33 | тот же корпус против исходника `193474d` (парсеры до Ф1) | `20 failed, 46 passed` — файлы корпуса несут настоящие дефекты |
| 34 | `python3 -m pytest tests/test_fuzz_replay.py tests/test_fuzz_containers.py tests/test_fuzz_parsers.py` (clone) | `94 passed, 5 deselected in 2.38s` |
| 35 | `git commit -F …` for F4 (hook = selfcheck → full acceptance) | `Итог: пройдено 13, провалено 0` / `Принято.` / `SELFCHECK OK` → `14ab6d2`, pushed (log `/tmp/rt83-commit-f4.log`) |
| 36 | first F5 deep pass: `PYTHONPATH="$PWD:/tmp/rt83-staging" HYPOTHESIS_PROFILE=deep python3 -m pytest -m slow tests/test_fuzz_parsers.py --durations=0 -p f5_counter` | five properties `.....` green, then `AttributeError: type object 'settings' has no attribute 'default_string'` inside the counter's `pytest_terminal_summary`, `exit=1` — no counts, no totals line (log `/tmp/rt83-f5-deep.log`) |
| 37 | same command again, alone, after the plugin was fixed outside the repo (profile read from `os.environ["HYPOTHESIS_PROFILE"]`), plus `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider` | the block quoted in F5: `5 passed, 7 deselected in 91.18s (0:01:31)`, `итого вызовов контракта: 25000`, `exit=0`, 02:03:55Z → 02:05:28Z (log `/tmp/rt83-f5-deep2.log`) |
| 38 | `ls tests/data/fuzz/*/ \| grep -c "\.bin"` and `git status --porcelain` after the deep pass | `31` (same as before it — the run harvested nothing), ` M agent/REPORT-83.md` only |
| 39 | `git worktree remove --force "$TMPDIR/rt83-base"` after `diff`-ing every copy against the clone | `same: pyproject.toml / tests/test_fuzz_parsers.py / tests/test_fuzz_containers.py`, `corpus identical`; `tests/test_fuzz_replay.py` differed only because the worktree held the pre-F4 version (one shared ceiling instead of per-entry floors), so the weaker copy is what was dropped; `git worktree list` → clone + `rusterm-relay-verify` |
| 40 | `rm -rf "$TMPDIR"/rt83-{lab,f3*,lie-*,mut.*,xxe-*}` (this round's probe sandboxes) + `rm -f /tmp/rt83-staging/replay-probe.bin` | `no matches found: $TMPDIR/rt83-*` — nothing of mine left outside the repo; the round's logs stay in `/tmp/rt83-*.log` because the report cites them by path |

## HANDOFF

Status: DONE — ТЗ-83 closed, all five items committed on `agent/night-11`.

Items done: приём круга (STATE + отчёт), F1, F2, F3, F4, F5.

| item | commit | what it left behind |
| --- | --- | --- |
| F1 | `779422d` | `tests/test_fuzz_parsers.py` (12 tests: 5 properties + census + deep-nesting case, plus the same five properties under `-m slow`), 19 reпро-файлов, four JSON/XML entries refuse as values instead of raising |
| F2 | `7f1190d` | `rusterm/parsers/ownership.py` + `tests/test_fuzz_xml.py` (7 tests): hostile-XML guard turns libexpat's `ParseError` into a declared refusal, billion-laughs reпро in the corpus |
| F3 | `680e58d` | `tests/test_fuzz_containers.py` (21 tests), 11 container reпро, `extract_text` pinned — zero defects found |
| F4 | `14ab6d2` | `tests/test_fuzz_replay.py` (66 tests): the corpus is now a check with per-entry floors, red-not-skipped when emptied |
| F5 | this commit | the deep pass evidence in `### F5`: 25 000 contract calls over 5 entries, 91.18 s, 0 new defects |

Items not done: none. Nothing in `## Blocked`.

Network: 0 requests spent (Hypothesis was already installed from the previous
round). LLM calls: 0.

The F5 commit's own acceptance verdict cannot be quoted here — the hook that
produces it runs *on* this commit, and pre-writing `13/0` would be the unrun
claim P5 forbids; `relay hand` re-runs acceptance before the baton moves, so
the verdict arrives in the log path named in the hand note.

Open questions to the coordinator: the seven entries in `## Disputed` — none is
fixed in code, and four need a ruling rather than a patch: row 1 has no
`unparsed` channel, row 3 keeps raising on an unknown `statement`, the
`RecursionError` reпро lives in a test instead of `tests/data/fuzz/`, and F2
left row 5's XML neighbours (`_parse_xml` dead helper, undeclared `defusedxml`)
alone. F3 adds three: an empty zip is labelled `format_unsupported:binary`
because `_ZIP_MAGIC` is the local-header signature, the zip ceiling trusts
declared sizes (entry 6), and a PreToolUse hook orders the executor to run a
test file that does not exist (entry 7).

What the next round should not re-learn: `extract_text` is now pinned twice
(byte corpus in F1, containers in F3) and survived 5 000 deep examples in F5
without a new defect; the remaining exposure there is inside python-docx /
python-pptx, which no test in this repo reaches.

NOW: hand to coordinator.
