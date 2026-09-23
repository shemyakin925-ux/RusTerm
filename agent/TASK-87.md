# TASK-87 — more measures from what we already fetch: synonyms, sectors, KSPI

- **Status: READY**
- **Report:** `agent/REPORT-87.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-87.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Stop:** day round — by the list; night round — PROTOCOL §10.
- **Budgets:** network — read-only GitHub raw of `dgunning/edgartools`
  (≤ 5 requests); SEC ≤ 20 requests via `RequestGate` (G3 only). LLM 0.
- **How to work:** as TASK-82. Closes BACKLOG B58; complements B59 /
  TASK-73 T2 (if T2 already derived sectors, G2 only adds the range table).

## Where we are

- User's base `/Users/anton/equitylab` (read-only connection only):
  measures with a value of 56 — AAPL 40, ADBE 40, VZ 14, VALE 12, **KSPI 0**;
  all papers «без отрасли».
- `rusterm/normalize/concepts.py`: 56 concept names. edgartools
  `edgar/xbrl/standardization/concept_mappings.json` (MIT): 156 us-gaap
  tags, 122 not in ours, only 2 `ifrs-full` — it will not fix KSPI/VALE.
- `edgar/entity/data/industry_mappings.json`: SIC ranges → industry.

## Fixed decisions

| Question | Rule |
|---|---|
| edgartools as dependency | **forbidden** (its own HTTP breaks acceptance 8, `dependencies = []`). Reference data only. |
| Porting | only entries used by our measures' inputs; each ported line carries `# src: edgartools <file>@<commit sha>, MIT`; licence text in `docs/adr/0025-*.md` (new ADR). |
| A synonym is accepted | only if it adds a measure value on the user's base **and** the value equals, within 1e-9, the same concept from the filing's own statement where both exist (no look-alike tags — PROTOCOL rule 9). |
| Priority among synonyms | existing tag first; ported ones after, in edgartools' order. |
| Sector names | our industry vocabulary wins; SIC ranges are mapped onto it, unmapped ranges → none, not a guess. |

## G1. Synonym census and port

**Done when:** report table: our measure input → tags we have → edgartools
tags we lack → ported yes/no + reason; test per ported tag on a trimmed
real payload in `tests/data/edgar/`; measure count per paper on
`/Users/anton/equitylab` (read-only copy in `tmp_path`) **before/after**;
acceptance green.

## G2. SIC → sector

**Done when:** SIC (from SEC submissions, already fetched or ≤ 6
requests) mapped to our sectors via the ported ranges; test on
boundary SIC codes (range ends, just outside); on the user-base copy
no paper with a known SIC stays «без отрасли»; count before/after.

## G3. Why KSPI has zero (B58)

Measure, do not guess: companyfacts for KSPI exists? which taxonomies?
which of our inputs appear under `ifrs-full`? period/currency filters?

**Done when:** report names the cause with the evidence (URL path,
counts, the filter that drops them); the window/CLI say that cause in
words from the reasons dictionary instead of an empty column; if the
cause is a mapping gap, the `ifrs-full` tags are added under G1's
acceptance rule and KSPI's count before/after is given; same line for
VALE.
