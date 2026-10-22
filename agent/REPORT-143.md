# REPORT-143 — TASK-143 (operating income without the line, PFE/XOM; F0a/F0b)

## Done
- F0a — `refresh_one`: ProviderError от submissions теперь отказ
  одной бумаги, а не падение прохода (rusterm/core/refresh.py:
  `isinstance(latest, (ConfigError, ProviderError))`; REPORT-142 Q1).
  Раньше у бумаги с отражённой датой падал TypeError на сравнении
  `latest <= last_filing_date`, у первой сборки ProviderError уезжал в
  issuer_state.put → ProgrammingError — обе ветки одной причины.
  Тест `tests/test_task143_f0a_submissions_refusal.py`: три бумаги,
  у средней submissions отдаёт ProviderError (значением, как живой
  403) → проход завершается (rc 1), AAA и CCC обновлены (факты в
  базе), BBB без фактов, итоговая строка «…новые отчёты: 2 …
  отказов: 1». Красно-зелёное: без фикса тест падает
  ProgrammingError («type 'ProviderError' is not supported»).

## Blocked
- (empty)

## What not to trust
- The copy `/tmp/rusterm-e-base` (49 instruments) was rebuilt fresh
  this round and still carries prices through 2026-10-20; F1's copy
  measurements happen after a reparse + history rebuild on it.

## Disputed
- F3 of the task text («relay.py verify → 13/0 on the final head»)
  contradicts the same file's «How to finish (new rule, 22.10)» and
  the coordinator's baton note («New rule: no separate verify before
  hand»). Implementing per the new rule: the hand's own acceptance
  (two full rolls) is the final-head gate; no standalone verify.

## HANDOFF
(interim — F0a done; F0b, F1, F2 ahead)
Status:          PARTIAL
Arrival state:   baton round 162 (c0d32f8), TASK-142 accepted
Items done:      F0a
Items not done:  F0b, F1, F2 (in progress), F3 per the new rule = the
                 hand's own acceptance; the contradiction is in
                 its section (dispute)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           F0a test quoted above (green with fix, red without)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 of 100 so far
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: F0a, step 6

## HANDOFF
(interim — supersedes the block above; the previous one tripped the
guard with a continuation line starting with the section's name)
Status:          PARTIAL
Arrival state:   baton round 162 (c0d32f8), TASK-142 accepted
Items done:      F0a
Items not done:  F0b, F1, F2 (in progress); F3 goes per the new rule
                 in «How to finish» — the hand's own acceptance is the
                 final-head gate, no standalone run (recorded as a
                 dispute in its section)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           F0a test quoted above (green with fix, red without)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 of 100 so far
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: F0b, step 3

## What not to trust (addendum)
- One continuation line inside this report's FIRST interim HANDOFF
  block was reworded in place («Disputed» → «its section (dispute)»)
  to satisfy the report guard, which reds on any line starting with
  that word outside its section — and the guard scans the whole file,
  so an append-only workaround does not exist. The line carried no
  record content (it pointed to the dispute section).
- F0b — desktop-тесты не запускают проход при старте: фикстура
  `_desktop_tests_without_startup_refresh` в tests/conftest.py (строка
  271) ставит `RUSTERM_NO_AUTO_REFRESH=1` всей семье
  `tests/test_desktop_*` разом; уже выставленное значение не
  перекрывается (собственные настройки тестов живы), тест самого
  прохода при старте снимает выключатель явно
  (test_desktop_task110_b2_refresh, monkeypatch.delenv). Готовность:
  `pytest tests/test_desktop_*.py` — 3 прогона подряд зелёные
  (220 тестов, exit 0, ни одного failed в каждом); grep показывает
  фикстуру; тест прохода при старте зелёный и по-прежнему требует,
  чтобы проход реально бежал (счётчики цен/снапшота в его ассертах).

## HANDOFF
(interim — F0a, F0b done; F1, F2 ahead)
Status:          PARTIAL
Items done:      F0a (b64e462), F0b (this commit)
Items not done:  F1, F2; F3 per the new rule — the hand's own
                 acceptance (dispute recorded in its section)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           quoted above (F0a red/green; F0b 3×220 green)
Guards:          none touched
Schema:          unchanged (48)
Network:         0 of 100 so far
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator: (none yet)

NOW: F0b, step 6
- F1 — операционная прибыль без своей строки: правило одной функцией
  `derive_operating_income` в rusterm/core/operating.py (pretax +
  interest_expense − interest_income; доходы не поданы — ноль; нет
  расходов или pretax — вывода нет). Карта: + `interest_income` <-
  `InvestmentIncomeInterest`, версия us-gaap.v9 (пины пяти тестов
  обновлены по прецеденту v8, страж роста карты дополнен сознательно).
  Снапшот: `_synthesize_operating_income` в by_concept на каждый
  период (unit, start, end) без своего тега; ранг дна (1 << 30) — свой
  тег всегда сильнее; роль входа в lineage называет вывод
  (mark_derived_oi на трёх путях: окно, общий период, цепочка nopat).
  Карточка: `statement_series` заполняет выводом только годы без тега.
  - Фикстуры (tests/test_task143_operating_income.py, 5 passed):
    без строки → маржа 0.9, ebitda 950, роль «выведено: pretax_income
    + interest_expense − interest_income»; свой тег 700 сильнее вывода
    900 и роли не называют вывод; карточка: год без тега выведен,
    год с тегом остался тегом.
  - Копия (reparse: 3797 фактов переканонизированы; snapshot +
    history --rebuild по PFE и XOM: 10 лет каждый):
    `card_fill.py US-PFE US-XOM` → **US-PFE 170/180 = 94 %,
    US-XOM 170/185 = 92 %, ИТОГ 340/365 = 93 %** (цель 90 %, по
    бумагам ≥ 80 % выполнено); ожила цепочка: roic у XOM 2021–2025 и
    PFE 2022–2025, nopat у PFE 2023–2025.
  - `yahoo_check.py` контрольная десятка → **ИТОГ 188/190 = 99 %,
    exit 0** (не изменилось); PFE и XOM перечислены: расхождения
    operating_income названы методикой Yahoo (справочно, вне зачёта:
    у XOM наше число выше — pretax включает доходы от разовых продаж
    активов, у PFE 2023 ниже — разовые расходы Seagen в pretax).
- F2 — вторая пара долга (XOM): `SECOND_PAIR_TAGS`
  (LongTermDebtAndCapitalLeaseObligations + DebtCurrent) в
  core/debt.py; `pair_total_at` пробует первую пару, при её отсутствии
  на дате — вторую; дверь `debt_pair_facts` отдаёт оба множества.
  Фикстуры (tests/test_task143_debt_second_pair.py, 5 passed): сумма
  пары, половина пары — не долг, первая пара сильнее при обеих,
  чужие даты/теги игнорируются.
  - `yahoo_check.py US-XOM` total_debt: 2023 +9.2 %, 2024 +9.5 %,
    2025 +14.5 % против Yahoo — вне 5 %, остаток назван (лизинг):
    тег XOM включает финансовый лизинг (`FinanceLeaseLiability`
    2,66 млрд на 2025-12-31 в фактах копии), методика Yahoo лизинг
    не считает. PFE 2023 +10 % — прежний именованный остаток
    (лизинг, REPORT-141 Q2, принят как методика).
  - Сеть F1+F2: 12 запросов Yahoo (кэш tools/yahoo_check) из 100.

## HANDOFF
(interim — F0a, F0b, F1, F2 done; F3 per the new rule)
Status:          PARTIAL
Items done:      F0a (b64e462), F0b (8462418), F1 (this commit),
                 F2 (next commit, same round)
Items not done:  F3 — по новому правилу «How to finish» отдельный
                 verify не гоняется (запись в Disputed выше)
Acceptance:      this commit's pre-commit selfcheck runs the full
                 acceptance; the final HANDOFF quotes it
Tests:           quoted above (F1 5 passed + карта/пины обновлены;
                 F2 5 passed; F0a/F0b ранее)
Guards:          none touched
Schema:          unchanged (48)
Network:         12 of 100 (Yahoo через кэш yahoo_check)
Model:           GLM 5.3 (zai individual coding plan) via ZCode
Secrets:         report and diff grepped for RUSTERM_* values — 0 hits
Pushed:          (with this commit)
Questions for the coordinator:
1. Вывод operating_income расходится с методикой Yahoo на 15–63 %
   у PFE/XOM (справочно, вне зачёта): формула честно собирает pretax +
   проценты, но Yahoo считает операционную прибыль иначе (исключает
   разовые статьи). Правило F1 выполнено дословно; если нужна
   сходимость с Yahoo — это новый вердикт.
2. XOM total_debt +9–14 % против Yahoo — лизинг внутри парного тега
   (назван в F2); если нужно точнее к Yahoo — пара без лизинга как
   третий уровень (новый вердикт).

NOW: F1, step 6
