# TASK-134 — clean screen: words not tokens, hide what is frozen

- **Status: READY**
- **Report:** `agent/REPORT-134.md`
- **Protocol:** `agent/PROTOCOL.md` (§12). State: `agent/CONTEXT.md`.
- **Scenario:** `agent/PRODUCT.md` С2–С4 (presentation). Queue rules:
  `agent/TASK-131.md`.
- **Budgets:** network 0, LLM 0.

## W1. Reason words — residue only (U1 `9e16aea` did the dictionary)
`rusterm/reasons_ru.py` exists and the card uses it (`card._reason_words`).
Residue: no visible label anywhere in the window matches
`[a-z]+_[a-z_]+:` or `Disputed|REPORT-` (peer header, quality, settings,
banners).
**Done when:** look.py report on 40 companies: zero such labels.

## W2. Hide frozen surfaces
Hide the «Качество» tab (frozen by PRODUCT.md — code stays, tab not
added). «Настройки»: show only hosts used by the US path (SEC, Yahoo,
Twelve Data, OpenRouter). Remove «1 из 6 рынков · US — меры» under the
tree.
**Done when:** look.py — tabs are exactly «Компания», «Аналоги»,
«Настройки» (+ home); settings table has ≤ 4 hosts.

## W3. No developer placeholders (was TASK-111 U4)
«прошлые разговоры: ждёт двери…», «списков нет» with a full tree, empty
combos, «v39 · 38 бумаг» → removed or replaced by working state.
**Done when:** look.py report: none of these strings on any tab.

## W4. Chat row frozen, not broken
The chat input stays (frozen) but must not show errors or key names when
no key: one grey line «вопросы к модели — позже».
**Done when:** offscreen test without key — no exception, the line shown.

## Do not
Same list as `agent/TASK-131.md` «Do not».
