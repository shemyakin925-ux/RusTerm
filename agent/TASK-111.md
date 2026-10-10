# TASK-111 — the window speaks to the user, and does by click what now needs the terminal

- **Status: SUPERSEDED — user 06.10.2026 approved `agent/PRODUCT.md`; queue is TASK-130…136. Do not take.**
- **Report:** `agent/REPORT-111.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Budgets:** network 0, LLM 0.
- **Queue:** MVP queue 109 → 123, numeric order (user 03.10: «делаем MVP;
  всё, кроме выгрузки в Excel»). One task ≈ 1/5 of a night.
- Measure on a **copy** of the user's base (P7). Window changes: offscreen
  Qt test + `python3 .claude/skills/rusterm-check/look.py --code . --root <copy> --out <dir> --companies 40`
  (report.json is the machine check).

## Where we are

User 03.10: «делай как у аналогов», «делай для пользователя». The window
prints developer tokens (`period_mismatch`, `stale_data: st_investments:
last 2019`, `concept_not_mapped`, «Disputed REPORT-C7») and sends the user
to the terminal («обновите: rusterm init», «rusterm add …», import, peers).

## U0. The I5 test never touches the real repository (first)
Rounds 145–147: `tests/test_i5_guard_source.py` stages edits to
`agent/p6_rule.sh` in the REAL index («# i5 green case: staged
widening»); any interrupted or parallel run leaves a guard staged and the
next acceptance goes red (seen twice by the coordinator, three hand
attempts in round 147). Run it on a temp clone (`git clone --local` into
tmp_path) with the hook path pointed there.
**Done when:** test — after the I5 tests, `git -C <repo> status
--porcelain agent/` is empty even if the test body raises midway
(simulated); grep: no `git add` against the repo root in tests/.

## U1. Reason dictionary in words
One table `rusterm/reasons_ru.py`: every reason token → short Russian
phrase («нет данных за период», «показатель не раскрывается с 2019»,
«не применимо к банкам»). Cells show the phrase; the raw token goes to the
tooltip and the source panel.
**Done when:** test — every token in `reasons.py` has a phrase; look.py
report: no cell/label matches `[a-z]+_[a-z_]+:` or `Disputed|REPORT-`.

## U2. Readable measure names and sections
Name table: `gross_margin` → «Валовая маржа», … Table grouped: Оценка ·
Рентабельность · Эффективность · Долг · Денежный поток · Доходность; header
rows bold. Tooltip: formula from `docs/data-dictionary.md` + unit.
**Done when:** test — every concept has a name and a section; look.py:
column 0 has no `_`.

## U3. Terminal advice becomes a button
Banner «схема N, нужна M» → button «Обновить базу» (runs migrations with
backup first). Unknown ticker, import, peer set edit, fact verify → dialog
+ the same core command (ADR-0027). No message tells the user to type a
command.
**Done when:** offscreen tests per action; grep in `rusterm/desktop/` — no
user-visible string containing «rusterm » except the source panel.

## U4. No developer placeholders
«прошлые разговоры: ждёт двери…», «списков нет» with a full tree, empty
combos — removed or replaced by working state.
**Done when:** look.py report: none of these strings on any tab.

## U5. Terminal output is a summary, not a dump
`rusterm snapshot --watchlist peers` (user, 03.10) printed thousands of
«ревизии: us-gaap:… за …» items in one line (`cli/__init__.py`
`print("ревизии: " …)`). Print «ревизии: N фактов (топ-5 концептов …);
полный список: --verbose». Same rule for any list > 20 items.
**Done when:** test — 1000 revisions → output line < 300 chars with the
count; `--verbose` prints all.

## Do not

- Touch `acceptance.sh`, `selfcheck.sh`, `p1_rule.sh`, `p6_rule.sh`,
  `githooks/`, `PROTOCOL.md`, `BACKLOG.md`, `LAUNCH.md`, `TASK-*.md`.
- Edit existing `docs/` files or applied migrations (new ADR / new
  migration only).
- Write to `~/EquityLab` or the KINGSTON drive (P7). The KINGSTON
  dataset is the user's future base: read-only reference, not imported.
- Paid tariffs, cards, deposits (ADR-0018).
