# TASK-139 — acceptance 13/0 again; «add a company» works for new tickers (С5)

- **Status: ACCEPTED (09.10, coordinator) — B1 46ca7a1, B2+B3 406e3f9; verify 13/0 (executor's hand). Questions answered in TASK-141.**
- **Report:** `agent/REPORT-139.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С5 (add by ticker → card in a minute), С1.
- **Budgets:** network ≤ 300 requests (SEC + Yahoo + Twelve Data, free
  keys you have), LLM 0. Work on a COPY of the user's base (P7).
- **Relay:** hand in — `python3 agent/relay.py hand --to coordinator
  --report agent/REPORT-139.md --note "<one line>"`; then
  `python3 agent/relay.py wait --for executor --timeout 3600`.

## Where we are (coordinator, 08.10 evening, head `c899dc9`)
- TASK-130…138 ACCEPTED; BACKLOG P1–P8 done (coordinator). Gates on the
  control ten met: fill 90 %, Yahoo 99 %.
- Acceptance on `c899dc9`: **12/1**. Item 11 (suite without zstandard)
  red on `tests/test_task65_k4_firsthour.py::test_first_hour_scenario`
  («Assertio…», full text lost). The same test is green alone, with and
  without zstandard. Item 12 (suite with zstandard) was green.
- Window hints are buttons now (TASK-134 W5, `desktop_actions.split_hint`,
  `run_core_command`).

## B1. Acceptance item 11 green (first)
Reproduce: full suite with zstandard blocked, exactly as
`agent/acceptance.sh` item 11 does (`PYTHONPATH=<dir with zstandard.py
raising ImportError>`). Quote the full assertion. Name the cause (order
dependence, timing, leaked env, the coordinator's change in `c899dc9` or
`7166518`). Fix the cause, not the test; never relax the limits on line
130–131.
**Done when:** `python3 agent/relay.py verify` → 13/0; REPORT quotes the
assertion and the cause in one line each.

## B2. Five new tickers through the window door (С5)
On a copy: `NVDA, KO, XOM, PFE, WMT` — none of them is in the base. Add
each through the same door as «+ компания»
(`desktop_actions.follow_instrument`, not the CLI), timing each.
Then `tools/card_fill.py --root <copy> US-NVDA …` and
`tools/yahoo_check.py --root <copy> --cache <dir> US-NVDA …`.
Every miss > 5 % or empty applicable cell: cause in one line; fix in
code what is a defect (map tag, rule), list what is Yahoo methodology.
**Done when:** REPORT table ticker · seconds · fill % · Yahoo % ; each
ticker ≤ 90 s, fill ≥ 80 %, Yahoo ≥ 90 %, or the gap named with a test
for each code fix.

## B3. Start time (С1)
Measure the window start on the copy (process start → home table filled)
5 times; median in REPORT. If > 5 s, profile (`python3 -m cProfile`) and
fix the top item.
**Done when:** median ≤ 5 s on the copy, or the top-3 profile lines
quoted with a fix of the first one and a before/after number.

## Do not
Same list as `agent/TASK-131.md` «Do not». Coordinator's code from
08.10 is accepted — do not rewrite it, fix only what a measurement shows.
