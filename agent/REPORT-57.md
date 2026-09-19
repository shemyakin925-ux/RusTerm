# REPORT-57 — TASK-57 (A1 + A2 + A3 + A4 + A5)

Round 68, executor, branch `agent/night-11`.

- Minutes to stop at start (Y0 command, verbatim):
  `python3 -c "from datetime import datetime,timezone,timedelta as T; n=datetime.now(timezone(T(hours=7))); s=n.replace(hour=10,minute=0,second=0,microsecond=0); print(int((s-n).total_seconds()//60))"`
  → **-93** at 11:32 Danang (NEGATIVE: the baton was handed to
  executor at 11:19 Danang, after the §10 night-shift stop of 10:00;
  see Questions 1). Decision: the hand itself is the coordinator's
  instruction to run this round now; taking A1 first (smallest,
  self-contained), the Y0 number is reprinted in every interim HANDOFF.
- Baseline selfcheck on arrival (before any commit), clean tree at
  `91e41ef`: 13/0, `SELFCHECK OK`, exit 0.

## A1. Circle-60 tail pinned by a test in both directions

Test name: `test_green_answer_survives_gray_measure_in_block`
(`tests/test_i2_does_not_know.py`), plus two neighbours pinning the
other branches: `test_guard_failure_with_known_reason_carries_data_reason`
(case б) and `test_guard_failure_without_data_reason_stays_generic`
(case в).

Commands and outputs:

- new tests on current code:
  `python3 -m pytest tests/test_i2_does_not_know.py -q` → `.......`
  (7 passed).
- redness proof: temporarily restored the pre-15c854f order (refusal
  before the guard) by hand, same command →
  `FAILED tests/test_i2_does_not_know.py::test_green_answer_survives_gray_measure_in_block`
  with `assert True is False` and result
  `{'answer': None, 'reason': 'no_data:missing_data', ..., 'rejected': True}`;
  `git checkout -- rusterm/core/chat.py`, same command → 7 passed.
  Cases (б) and (в) stay green under the old order by design — their
  outcome is identical in both orders; case (а) is the discriminating
  one, and it is the one that reddens.
- after the comment edit:
  `python3 -m pytest tests/test_i2_does_not_know.py tests/test_q_chat.py -q`
  → 17 passed.
- the chat.py comment is shortened to three short lines naming the
  test, no round numbers.

What would break without this test (two lines): a revert of 15c854f
would again let any single gray measure in a tool block cancel an
answer that was computed and cited from green measures of the same
block — the user loses real numbers to an unrelated refusal. And the
refusal path for a guard-rejected answer would drift silently: nothing
would pin `no_data:` + the dictionary token over the generic
«число не процитировано» when the data reason is known.

## A2. BR measures census — Ambev, offline, golden-pinned

Emitent: **BR-AMBEV (AMBEV S.A., CD_CVM 023264)** — the same payload
as Z2 (annual DFP 2024, recorded slices `tests/data/cvm/`). The
census runs offline through the REAL Z2 channel
(`add` → `ingest --source cvm` → `snapshot`), transport replaced by
the recorded bytes, real RequestGate counting; golden file
`tests/data/golden_census_task57_br.json`, tests
`tests/test_task57_br_census.py` (5 passed). The census covers the
ten TASK-49 measures **plus `roe_incl_nci`** (landed in ТЗ-56 Z1),
11 rows total — the ТЗ said «десять», the dictionary has grown by one
since; nothing was dropped.

Table in words (measure → value or refusal):

| measure | outcome |
|---|---|
| gross_margin | **0.5124228210563511** (computes) |
| net_margin | **0.16597550599636104** (computes) |
| roe_incl_nci | **0.16521917935689903** (computes) |
| effective_tax | **0.0** — see the candidate below; the true ratio from the payload is −4640375/19487327 = −0.2381 |
| roe | refuses `missing_data: total_equity` — CVM files capital only WITH NCI (2.03), Z1 rule holds, no substitution |
| operating_margin | refuses `missing_data: operating_income` — 3.05 is EBIT-like, deliberately unmapped (verdikt ТЗ-55) |
| ebitda | refuses `missing_data: d_and_a, operating_income` |
| nopat | refuses `missing_data: operating_income` |
| interest_coverage | refuses `missing_data: interest_expense, operating_income` |
| asset_turnover | refuses `missing_data: total_assets` — BPP slice has no asset lines |
| fcf | refuses `missing_data: capex, ocf` — no cash-flow statement in the recorded slices |

So: **4 rows carry a value, 7 refuse**; every refusal token is
dictionary-checked by an assert, none is a bare `missing_data`.
`rusterm census --instrument BR-AMBEV` prints the issuer like US/CA/
OTC (asserted in test_census_command_lists_br_like_us_ca_otc; live
offline run quoted in the prep: 36 facts, 11 rows).

### Candidate (no code written, per ТЗ): CVM 3.08 sign convention

DRE line 3.08 «Imposto de Renda e Contribuição Social sobre o Lucro»
is filed as a SIGNED deduction (negative). The dictionary maps 3.08 →
`tax_expense`, and `effective_tax = clip(tax/pretax, 0, 0.5)` clamps
−0.2381 to **0.0** — a green-looking number that says AMBEV pays 0%
tax. Options for the coordinator: normalize the sign at the map layer
(cvm-dfp.v2, magnitude) or give BR its own measure; both are code, so
per A2 this is reported, pinned as-is in the golden (`"0.0"` with the
artifact documented in the test docstring), not "fixed".

## Done

- A1: circle-60 tail pinned in both directions
  (test_green_answer_survives_gray_measure_in_block red on the
  reverted order, green after restore; cases б/в pinned on exact
  texts); chat.py comment names the test instead of the round.
- A2: BR census offline golden-pinned (4 values / 7 named refusals,
  dictionary-checked), candidate 3.08-sign reported without code.

## Blocked

- (empty so far)

## What not to trust

- The first A1 commit attempt was RED and not committed: the report
  you are reading did not yet carry the five required sections, which
  reds test_report_sections and, through the nested selfcheck, the i5
  guard-source test (cascade, same root). Fixed in this commit; the
  red run's pytest line: 11 passed checks / 2 failed checks (check 3
  and check 11, same three FAILED tests).

## Disputed

- Q1 (for the coordinator): §10 says the shift ends 10:00 Danang, but
  the round-68 baton was handed at 11:19 Danang with TASK-57 READY.
  Treated the hand as the instruction to run a daytime round; the Y0
  line is negative. Confirm the stop-time convention for daytime
  relay rounds (this report reprints the number but cannot compute a
  meaningful countdown against a stop already in the past).

## HANDOFF

Status:          working (interim)
Arrival state:   selfcheck STATUS=OK on clean tree at 91e41ef, exit 0
Items done:      A1 (commit 920d299, pushed), A2 (staged in this commit)
Items not done:  A3, A4, A5, backlog item — not started yet
Acceptance:      A1 commit: 13/0, Принято, exit 0 (both selfcheck runs);
                 this commit re-runs the same command
Tests:           test_task57_br_census.py 5 passed (new)
Guards:          none touched
Schema:          unchanged
Network:         0 requests used (census offline on recorded bytes)
Model:           app llm_calls 0; runner model GLM-5.3-Flash
Secrets:         no key material in tests/data/cvm/ or the report
Pushed:          this commit — yes, right after selfcheck passes
Questions for the coordinator:
1. Stop-time convention for daytime relay rounds (see Disputed Q1).
2. A2 candidate: CVM 3.08 sign normalization (see the candidate item).
