# REPORT-18 — TASK-18: Canada and OTC, the market becomes a registry

## Done
- §0 `git merge origin/main` → Already up to date; acceptance → `Итог: пройдено 13, провалено 0`.
- §0 `printenv RUSTERM_SEC_UA` → empty in shell, but `~/.rusterm.env` exists and the application reads it itself (N2); live path available (proven by TASK-15 C6).

## Blocked

## What not to trust

## Disputed
- DISPUTED (procedure): G1+G2+G5 сведены в один коммит — изменения
  переплетены в cmd_add и edgar.py (валидация рынка, биржа в листинге,
  404-значение идут через один поток add/ingest); раздельная нарезка
  hunks riskier than the combined commit.

## HANDOFF
Status:          DONE
Items done:      §0, G1, G2, G3, G4, G5, G6, G7, G8, G9, G10, G11, G12
                 (queue empty), G13
Items not done:  none. UK отсутствует по решению пользователя (§0.1.1),
                 не «не успели».
Acceptance:      пройдено 13, провалено 0   (agent/ACCEPTANCE-16.txt)
Tests:           361 passed, 2 skipped, 0 xfailed
Markets:         ровно {US, CA, OTC}; неизвестный код — exit 1 с
                 перечнем; литералов рынка в formulas/core/normalize нет
Issuers taken:   CA IFRS: RY 1000275, BMO 927971, CNQ 1017413;
                 OTC: CPTP 202947 (фид победил ТЗ-21175), NGGTF 1004315
                 (ifrs-full — OTC с полным XBRL). Пропуск по правилу:
                 эмитенты OTC без filings (TRUFF-класс) — честный 404.
Measure table:   M6 measure -> n/5 + reasons:
                   net_margin: 5/5 причины: —
                   operating_margin: 1/5 причины: {'missing_data: operating_income': 4}
                   effective_tax: 1/5 причины: {'missing_data: tax_expense': 4}
                   fcf: 1/5 причины: {'missing_data: capex': 3, 'missing_data: ocf': 1}
                   ebitda: 0/5 причины: {'missing_data: operating_income': 3, 'missing_data: d_and_a, operating_income': 1, 'missing_data: d_and_a': 1}
                   interest_coverage: 1/5 причины: {'missing_data: interest_expense, operating_income': 3, 'missing_data: operating_income': 1}
                   nopat: 0/5 причины: {'missing_data: effective_tax, operating_income': 3, 'missing_data: operating_income': 1, 'missing_data: effective_tax': 1}
                   roe: 4/5 причины: {'missing_data: total_equity': 1}
                   asset_turnover: 4/5 причины: {'missing_prior_period': 1}
                   gross_margin: 0/5 причины: {'missing_data: gross_profit': 5}
Golden m6 CA:    120 значений (RY 39 / BMO 39 / CNQ 42), каждое
                 разрешается из записанного payload по accn + json_pointer
No-filings path: NOFILE (стаб, companyfacts 404) — инструмент создан,
                 coverage missing no_sec_filings, exit 0, ноль raw_object
formulas.py:     байт-в-байт равен голове старта TASK-18 (23737a7) —
                 тест-гвард; origin/main файл не содержит (Disputed)
Payload size:    du -sk tests/data/edgar/ = 608 КБ, лимит 1024 КБ соблюдён
Both taxonomies: ни один из пяти записанных не несёт us-gaap и
                 ifrs-full одновременно; при таком payload побеждает
                 us-gaap — покрыто тестом G4 (двух-таксономичный
                 синтетический payload)
Milestones:      M6 (Canada) yes — доказательства: тест G7 (golden по
                 accn+pointer), таблица G8, гвард G4 formulas.py;
                 UK half dropped by decision, not missed.
                 OTC yes — 2 из 2 записанных OTC имеют XBRL; эмитент без
                 filings честно отвечает coverage missing no_sec_filings
                 (тест G5), а не падением или тишиной.
Strict xfail:    none
Network:         RUSTERM_SEC_UA set via ~/.rusterm.env; 6 запросов из
                 бюджета 40 (карта тикеров + 5 companyfacts)
Model:           app LLM calls 0; own model GLM-5.3-Flash
Pushed:          yes (through the final acceptance commit)
Questions for the coordinator:
1. TSX-only эмитенты (CSU-класс) остаются недостижимыми — где это
   задокументировать для пользователя, кроме README-обещаний?
2. CPTP: ТЗ звало CIK 21175, живой фид даёт 202947 — фид побеждил.
   Верно ли поняты «venue/jurisdiction» для CA-эмитентов, торгующихся
   на NYSE (venue NYSE, рынок CA)?

NOW: G13, step 8
