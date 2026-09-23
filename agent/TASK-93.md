# TASK-93 — the model never produces a number: citation guard, message roles, host identity

- **Status: READY**
- **Report:** `agent/REPORT-93.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Relay:** hand in — `python3 agent/relay.py --branch agent/night-11
  hand --to coordinator --report agent/REPORT-93.md --note "<line>"`;
  **then at once** `python3 agent/relay.py --branch agent/night-11 wait
  --for executor --timeout 3600`.
- **Budgets:** network 0; LLM 0 (recorded answers and fake transports
  only). Optional D1 live confirmation: ≤ 5 model calls, `live` marker.
- **How to work:** as TASK-90. Standing rule 3 of CONTEXT («an uncited
  number rejects the whole answer») is the acceptance bar for D1–D2.
- **Place in queue:** after TASK-92 (queue tail, see TASK-91). D1 is the most
  important item of the whole review — take it first.

## D1. The guard cites values, not digit runs

`core/chat.py:161` adds **every digit run** of the JSON-dumped tool
result to the allowed set: UUIDs (`measure_id`), dates, versions, ids.
Reproduced on `3f7dcc9`:

```
tool result: net_margin value "0.2399", roe value null,
             measure_ids 07784ae3-3304-…, 5c1e2a90-1250-…
answer: «Маржа 0.2399, ROE 31%, P/E 8, выручка выросла на 55%.»
ChatSession.guard_answer → ['0.2399', '31', '55', '8']   # accepted
answer: «Чистая маржа -0.2399 (убыток).» → ['0.2399']    # sign flip accepted
```

ROE is null; 31, 8 and 55 come from UUID digits. `_NUMBER_RE`
(`core/llm.py:23`) has no sign.

Fixed decisions:
- allowed numbers come only from value fields of tool results — keys
  `value`, `p25`, `median`, `p75`, `n` (walk the structure, not the
  dump); nothing from keys ending in `_id`, `hash`, `sha256`, or from
  any string that is a UUID;
- a date in the answer is allowed only as a whole ISO date equal to a
  `period_start` / `period_end` / `as_of` value;
- the sign is part of the number (`-0.2399` ≠ `0.2399`);
- `reverify_transcript` (`:297`) and `LlmSummarizer._citations_for`
  use the same extractor.

**Done when:** both reproduced answers are rejected by a test; the
recorded corpus (`tests/data/chat_corpus.json`, G4 replay) stays green
or every moved case is quoted with the reason; a property test: a
number absent from every value field is never accepted, whatever ids
the result carries.

## D2. A rejected answer keeps its real reason

`unknown_reason_from_tools` (`chat.py:217`) returns the first
`null_reason` of **any** measure in the block. Every snapshot carries
~10 null measures, so a guard-rejected answer about a measure that
**has** a value is reported as `no_data:missing_data`.

Rule: `no_data:<reason>` only when every measure named in the question
(match on measure names present in the tool results) is null;
otherwise `guard_rejected_uncited_number`.

**Done when:** tests for both branches; the I2 test
`test_green_answer_survives_gray_measure_in_block` stays green.

## D3. Instructions travel as a system message

`_ChatAdapter.chat` (`core/llm.py:161`) JSON-dumps the whole message
list — system instructions, history, the fenced document — into one
string and sends it through `complete(prompt)`, which wraps it as a
single `user` message. The model never sees a system role; untrusted
document text and instructions share one user string (ADR-0016: data
never in the instruction position).

**Done when:** `LlmApiClient.complete_messages(messages)` sends the
roles as given (same gate, retries, errors-as-values as `complete`);
the adapter uses it; a recorded-payload test asserts
`messages[0]["role"] == "system"` and that document text occurs only
inside the fence of a `user` message; `complete(prompt)` keeps its
contract for `classify` and manual import.

## D4. Each host receives only its own identity

`providers/budget.py:93` `NetworkGate`: **every** request of every
provider requires `RUSTERM_SEC_UA` and sends it as `User-Agent` — to
OpenRouter, Twelve Data, CVM, DART, ASX, OTC Markets (each
`_default_transport` forwards `headers`). By SEC policy that string
carries the user's name and e-mail; five other hosts receive it, and
without it chat, prices, CVM and ASX refuse `sec_ua_unset` though they
do not need it.

Rule: hosts under `sec.gov` → contact UA required (unchanged);
every other host → `User-Agent: EquityLab/<package version>`, no
contact, no `RUSTERM_SEC_UA` requirement. Budgets and rate pools per
host unchanged.

**Done when:** a test per provider inspects the headers its transport
receives: no non-SEC request carries the `RUSTERM_SEC_UA` value; chat
and Twelve Data build and send with `RUSTERM_SEC_UA` unset; SEC without
it still refuses `sec_ua_unset`; `doctor` freeness section unchanged.

## D5. `classify` accepts fenced JSON

`core/intent.py:142` does `json.loads(raw)`; live models wrap JSON in
```` ```json ```` fences (the chat adapter already extracts `{…}`,
`llm.py:169`). With a key, `ops` burns its one retry and returns
«ответ модели не JSON». **Done when:** the same extraction is used;
a fenced recorded answer yields `Intent` in one client call (test
counts calls).

## D6. `llm_summary`: wired, not only promised

`LlmSummarizer` (`core/llm.py:240`) has tests and **no caller**; no
client implements `summarize()`; coverage shows `llm_summary`
`missing no_data:llm_summary` or `stale cascade:…` for every
instrument; the user base has 0 `llm_summary` rows.

Fixed decision: wire it. `rusterm summary --instrument X` → an adapter
behind the single door (`core/llm.py`, next to `make_chat_client`)
turns `complete()` into the `{summary, highlights, risks}` dict; the
same guard (after D1); one audit row per run; the desktop «Качество»
tab shows the block's real state.

**Done when:** fake-transport end-to-end test: a stored row with
citations; an answer with an uncited number ⇒ block `missing` with
`GUARD_REASON`; `tests/test_single_door.py` green; zero network.
