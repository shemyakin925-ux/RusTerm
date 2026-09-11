# Отчёт агента, 2026-09-06

## Сделано

| Инкремент | Статус | Коммит | Тесты |
|---|---|---|---|
| И1 — И5 | Зеленый | 0640869 | тесты fact + repos (14+24 = 38) |
| И6 | Зеленый | — | провайдеры (market + disclosures, фейковые синтетические) |
| И7 | Зеленый | — | парсеры (SyntheticXBRLParser, TableParser, can_parse + parse) |
| И8 | Зеленый | — | pipeline (9 узлов сбора, идемпотентность, ветки E1-E5, каскад) |
| И9 | Зеленый | — | формулы (calculate_measure, roic, roe, asset_turnover, nopat, margin с null reasons) |
| И10 | Зеленый | — | peer set (модель, версии, происхождение, статусы verified/unverified, пороги 5 и 8, дрейф) |
| И11 | Зеленый | — | снапшот (двухпроходная сборка по processes.md P2, три вида diff, coverage, latest_measure) |
| И12 | Зеленый | — | экспорт (CSV и JSON из готовых величин, без пересчёта, побайтовое совпадение с содержимым снапшота) |
| И13 | Зеленый | — | CLI (init, ingest, snapshot, export, verify, doctor — все на синтетических данных) |

## Прогоны

`pytest -q tests/` — 74 passed in 2.1s.

## Реализовано

I13: CLI с шестью командами:
- `init` — инициализация app данных директории
- `ingest` — запуск pipeline для инструментов (планирование джобов, fetch + store + parse + validate + persist)
- `snapshot` — сборка снапшота для инструмента (resolve_instrument → load_facts → compute_measures → peer_set → assemble)
- `export` — экспорт в CSV/JSON из готового снапшота (без пересчёта, побайтовое совпадение)
- `verify` — проверка целостности фактов (обязательные поля, locator, basis, null reasons)
- `doctor` — полная проверка: manifest vs store, schema_version, orphaned/extra ссылки

Все команды работают на синтетических данных и имеют флаги/аргументы.

## Заблокировано

Нет.

## Не начато

Нет — все инкременты И1 — И13 закрыты.

## Чему верить нельзя

Все проверено на синтетических фикстурах. Реальные данные SEC EDGAR не проверялись (нет сети/времени).
