"""ТЗ-92 C4: проверенные ручные записи доходят до мер.

Красные до правки: `manual/pipeline.py` вставлял факты с
`canonical_concept = NULL` (метрика — свободный текст модели), а
`SnapshotRepo.as_reported_facts` фильтрует по `canonical_concept IN
(...)` — то есть ни один ручной факт не мог попасть в формулу. Зубы
проверяют: карту алиасов (ключи — денежные концепты словаря, исключений
нет кроме названных), разбор значения с триадами и масштабом единицы,
валюту (ISO в единице, иначе валюта эмитента, кроме XXX), фискальный год
по `fye` эмитента, версий карты `manual.v1`, и — главный — меру, чья
lineage указывает на факт `source_kind='manual'`.

Фикстуры: `tests/data/manual/answer_aliases_synthetic.json` +
`doc_aliases_synthetic.md` (рукописные, помечены в тексте документа) и
ЗАПИСАННЫЙ ответ настоящей модели `response_table2_fleet.json` — на нём
видно, что ставки «USD/day» карта не берёт.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.manual.pipeline import import_document
from rusterm.manual.records import parse_records, period_bounds
from rusterm.normalize.concepts import (
    MANUAL_MAP_EXCLUDED, MANUAL_MAP_VERSION, MANUAL_METRIC_MAP,
    canonical_for_manual)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "manual"
DOC = DATA / "doc_aliases_synthetic.md"
ANSWER = DATA / "answer_aliases_synthetic.json"
RECORDED_FLEET = DATA / "response_table2_fleet.json"
FLEET_DOC = (Path(__file__).resolve().parents[1] / "tests" / "data"
             / "n4_fleet_tables" / "table2_ten_column_fleet_by_class.html")

AS_OF = "2026-01-31"
# FY2025 у эмитента с fye 06-30: 2024-07-01 … 2025-06-30
FY_START, FY_END = "2024-07-01", "2025-06-30"

MONEY_CONCEPTS = ("revenue", "cogs", "gross_profit", "opex",
                  "operating_income", "d_and_a", "net_income",
                  "pretax_income", "tax_expense", "interest_expense",
                  "ocf", "capex", "cash", "st_investments", "total_debt",
                  "total_assets", "total_equity", "total_equity_incl_nci",
                  "minority_interest", "preferred_equity",
                  "buyback_amount")


class Client:
    """Подставной клиент ступени ②: отдаёт записанный/рукописный ответ."""

    model = "stub-c4"

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return self.answer


def _paths(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, paths


def _issuer(conn, repos, instrument_id, issuer_id, *, fye="06-30",
            currency="USD", standard="ifrs-full"):
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "AU", None, fye, standard,
        currency))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))


def _facts(conn, issuer_id):
    return conn.execute(
        """SELECT concept, value, unit, currency, period_start,
                  period_end, period_type, canonical_concept,
                  concept_map_version, locator, fact_id
           FROM fact WHERE issuer_id=? AND source_kind='manual'
           ORDER BY concept, period_end""", (issuer_id,)).fetchall()


def _by_canonical(conn, issuer_id):
    rows = {row[7]: row for row in _facts(conn, issuer_id)}
    return rows


def _import(tmp_path, issuer_id="AU-C4", *, answer=None, fye="06-30",
            currency="USD"):
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-C4-1", issuer_id, fye=fye, currency=currency)
    outcome = import_document(conn, paths, DOC, issuer_id,
                              Client(answer if answer is not None else
                                     ANSWER.read_text(encoding="utf-8")))
    assert not isinstance(outcome, Exception), outcome
    return conn, paths, repos, outcome


# ── карта алиасов ──────────────────────────────────────────────────────

def test_manual_map_keys_are_the_dictionary_money_concepts():
    """Ключи карты — не выдумка: ровно строки словаря §2 с единицей
    «валюта» (за вычетом названных исключений). Проверка читает сам
    документ словаря, а не повтор списка."""
    doc = (Path(__file__).resolve().parents[1] / "docs"
           / "data-dictionary.md").read_text(encoding="utf-8")
    money = set()
    for line in doc.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5:
            continue
        name = cells[1].strip("`")
        if not re.fullmatch(r"[a-z_]+", name):
            continue
        if cells[3] == "валюта":
            money.add(name)
    assert money, "словарь не прочитан"
    assert set(MANUAL_METRIC_MAP) == money - set(MANUAL_MAP_EXCLUDED)
    assert set(MANUAL_METRIC_MAP) == set(MONEY_CONCEPTS)


def test_manual_map_exclusions_are_named_and_absent():
    """shares/dps/eps/price_* в ручную карту не входят: units «шт.» и
    «валюта/акцию» — это не деньги за период, а цена класса акций;
    исключение названо в модуле, а не молча опущено."""
    assert set(MANUAL_MAP_EXCLUDED) >= {"price_close", "price_adj",
                                        "shares_outstanding",
                                        "shares_diluted", "eps_diluted",
                                        "dps"}
    for name in MANUAL_MAP_EXCLUDED:
        assert name not in MANUAL_METRIC_MAP
        assert canonical_for_manual(name.replace("_", " ")) is None


@pytest.mark.parametrize("concept", MONEY_CONCEPTS)
def test_every_alias_maps_from_the_written_answer(concept):
    """Правило 9: алиас без записанного ответа не появляется. Каждый
    ключ карты стоит в фикстуре-ответе, и именно он отображается."""
    aliases = MANUAL_METRIC_MAP[concept]
    assert canonical_for_manual(concept) == concept
    for alias in aliases:
        assert canonical_for_manual(alias) == concept
    text = ANSWER.read_text(encoding="utf-8")
    answer = json.loads(text)
    metrics = {r["metric"] for r in answer}
    hit = [a for a in aliases
           if any(m.lower().replace("_", " ").strip() == a
                  for m in metrics)]
    assert hit, f"алиасы {concept} не проверены записанным ответом"


def test_alias_spelling_variants_map():
    """Нормализация — регистр, подчёркивание, лишние пробелы и точка на
    конце; «Net_Income.» и «NET INCOME» — тот же концепт."""
    assert canonical_for_manual("Net_Income.") == "net_income"
    assert canonical_for_manual("NET   INCOME") == "net_income"
    assert canonical_for_manual(" total equity incl nci ") == \
        "total_equity_incl_nci"
    assert canonical_for_manual("Revenue growth") is None
    assert canonical_for_manual("") is None


# ── разборы значения и единицы ─────────────────────────────────────────

def test_thousands_separators_and_million_scale(tmp_path):
    """«1,234.5» с единицей «USD m» — 1 234 500 000, а не падение
    float() молча."""
    conn, _p, _r, outcome = _import(tmp_path)
    assert outcome.records_total == 26
    row = _by_canonical(conn, "AU-C4")["revenue"]
    assert float(row[1]) == pytest.approx(1_234_500_000.0), row[1]
    assert row[2] == "USD" and row[3] == "USD"


@pytest.mark.parametrize("unit,expected", [
    ("USD thousand", 1_000.0), ("USD k", 1_000.0), ("USD '000", 1_000.0),
    ("USD m", 1_000_000.0), ("USD mn", 1_000_000.0),
    ("USD million", 1_000_000.0), ("USD bn", 1_000_000_000.0),
    ("USD billion", 1_000_000_000.0), ("USD", 1.0),
])
def test_scale_tokens_from_the_unit(tmp_path, unit, expected):
    answer = [{
        "company": "Synthetic Corp", "category": "financial",
        "metric": "Revenue", "value": "2.5", "unit": unit,
        "period": "FY2025",
        "quote": "Revenue: 2.5 %s (FY2025)" % unit, "page_no": 1}]
    doc_text = DOC.read_text(encoding="utf-8").replace(
        "Revenue: 1,234.5 USD m (FY2025)",
        "Revenue: 2.5 %s (FY2025)" % unit)
    doc_path = tmp_path / "one_line.md"
    doc_path.write_text(doc_text, encoding="utf-8")
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-S1", "AU-S1")
    outcome = import_document(conn, paths, doc_path, "AU-S1",
                              Client(json.dumps(answer)))
    assert outcome.records_mapped == 1, outcome
    row = _by_canonical(conn, "AU-S1")["revenue"]
    assert float(row[1]) == pytest.approx(2.5 * expected), row[1]


def test_iso_currency_in_the_unit_beats_the_issuer_currency(tmp_path):
    conn, _p, _r, _o = _import(tmp_path, issuer_id="AU-C4",
                               currency="USD")
    row = _by_canonical(conn, "AU-C4")["revenue"]
    assert row[3] == "USD"          # из единицы «USD m»
    assert row[2] == "USD"


@pytest.mark.parametrize("issuer_currency,expected", [
    ("BRL", "BRL"), ("XXX", None),
])
def test_without_iso_in_unit_currency_is_the_issuer_unless_xxx(
        tmp_path, issuer_currency, expected):
    """Единица «$m» валюты не называет: берётся валюта эмитента (C2),
    а у XXX её просто нет — и единица остаётся как написана."""
    answer = [{"company": "Synthetic Corp", "category": "financial",
               "metric": "Revenue", "value": "3.0", "unit": "$m",
               "period": "FY2025", "quote": "Revenue: 3.0 $m (FY2025)",
               "page_no": 1}]
    doc_text = DOC.read_text(encoding="utf-8").replace(
        "Revenue: 1,234.5 USD m (FY2025)", "Revenue: 3.0 $m (FY2025)")
    doc_path = tmp_path / "dollar.md"
    doc_path.write_text(doc_text, encoding="utf-8")
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-S2", "AU-S2", currency=issuer_currency)
    outcome = import_document(conn, paths, doc_path, "AU-S2",
                              Client(json.dumps(answer)))
    assert outcome.records_mapped == 1, outcome
    row = _by_canonical(conn, "AU-S2")["revenue"]
    assert row[3] == expected
    assert row[2] == (expected if expected else "$m")
    assert float(row[1]) == pytest.approx(3_000_000.0)


def test_rate_unit_never_maps(tmp_path):
    """«USD/day» — ставка в сутки, не деньги за период; в словарь её
    нельзя, иначе годовой расход станет в 365 раз меньше."""
    conn, _p, _r, outcome = _import(tmp_path)
    rates = [row for row in _facts(conn, "AU-C4") if row[7] is None
             and row[0].lower().startswith("revenue")
             and "day" in (row[2] or "")]
    assert len(rates) == 1
    # неотображённая строка остаётся дословной: ни масштаба, ни «исправы»
    assert rates[0][1] == "41,000", rates[0][1]
    assert rates[0][7] is None and rates[0][8] is None
    assert outcome.records_mapped == 21


def test_recorded_real_answer_has_no_financial_mapping(tmp_path):
    """ЗАПИСАННЫЙ ответ настоящей модели (glm-5.3-flash, 14.09.2026) —
    весь его financial — ставки USD/day: карта не отображает ни одной
    строки, и это измерено, а не обещано."""
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-F1", "AU-F1")
    outcome = import_document(
        conn, paths, FLEET_DOC, "AU-F1",
        Client(RECORDED_FLEET.read_text(encoding="utf-8")))
    assert outcome.records_total == 36
    assert outcome.records_mapped == 0
    assert all(row[7] is None for row in _facts(conn, "AU-F1"))


def test_unknown_unit_keeps_the_value_verbatim(tmp_path):
    """Единица вне правил — факт остаётся с NULL и значением как
    написано: никакого «исправленного» числа (нынешнее поведение)."""
    answer = [{"company": "Fleet Co", "category": "physical",
               "metric": "fleet_size", "value": "42", "unit": "ships",
               "period": "FY2025",
               "quote": "the fleet comprised 42 ships", "page_no": 1}]
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-U1", "AU-U1")
    doc = paths.root / "ships.md"
    doc.write_text("the fleet comprised 42 ships\n", encoding="utf-8")
    outcome = import_document(conn, paths, doc, "AU-U1",
                              Client(json.dumps(answer)))
    assert outcome.records_mapped == 0
    row = _facts(conn, "AU-U1")[0]
    assert row[1] == "42"
    assert row[7] is None and row[8] is None


def test_excluded_concepts_stay_unmapped(tmp_path):
    """«Price close» и «Shares outstanding» в документе есть — и оба
    не отображаются: единицы «валюта/акцию» и «шт.» вне карты."""
    conn, _p, _r, outcome = _import(tmp_path)
    named = {row[0] for row in _facts(conn, "AU-C4") if row[7] is None}
    assert {"Price close", "Shares outstanding", "Revenue"} <= named
    assert outcome.records_mapped == 21


# ── версия карты ───────────────────────────────────────────────────────

def test_concept_map_version_is_manual_v1(tmp_path):
    conn, _p, _r, _o = _import(tmp_path)
    versions = {row[8] for row in _facts(conn, "AU-C4")
                if row[7] is not None}
    assert versions == {MANUAL_MAP_VERSION} == {"manual.v1"}
    assert {row[8] for row in _facts(conn, "AU-C4") if row[7] is None} \
        == {None}


# ── фискальный год ─────────────────────────────────────────────────────

def test_fy_bounds_use_the_issuer_fiscal_year_end():
    assert period_bounds("FY2025", "06-30") == (FY_START, FY_END,
                                                "duration")
    assert period_bounds("2025", "06-30") == (FY_START, FY_END, "duration")
    assert period_bounds("FY2025") == ("2025-01-01", "2025-12-31",
                                       "duration")
    assert period_bounds("2025-03-31", "06-30") == ("2025-03-31",
                                                    "2025-03-31", "instant")


def test_manual_fact_periods_and_locator_name_the_fiscal_calendar(
        tmp_path):
    conn, _p, _r, _o = _import(tmp_path)
    row = _by_canonical(conn, "AU-C4")["revenue"]
    assert (row[4], row[5], row[6]) == (FY_START, FY_END, "duration")
    assert "#fy=06-30" in row[9], row[9]


def test_without_fye_the_year_is_calendar_and_the_locator_says_so(
        tmp_path):
    conn, _p, _r, _o = _import(tmp_path, fye=None)
    row = _by_canonical(conn, "AU-C4")["revenue"]
    assert (row[4], row[5]) == ("2025-01-01", "2025-12-31")
    assert "#fy=calendar" in row[9], row[9]


# ── главное: ручные записи доходят до меры ─────────────────────────────

def test_a_measure_is_computed_from_manual_facts_and_lineage_proves_it(
        tmp_path):
    conn, paths, repos, outcome = _import(tmp_path)
    manual_ids = {row[10] for row in _facts(conn, "AU-C4")}
    assert manual_ids
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build("AU-C4-1", "AU-C4", AS_OF)
    rows = repos.snapshot.get_measures(result.snapshot_id)
    margin = next(m for m in rows if m[3] == "net_margin")
    assert margin[4] is not None, margin
    assert float(margin[4]) == pytest.approx(123.45 / 1234.5), margin[4]
    lineage = conn.execute(
        """SELECT ml.fact_id, f.source_kind FROM measure_lineage ml
           JOIN fact f ON f.fact_id = ml.fact_id
           WHERE ml.measure_id=?""", (margin[0],)).fetchall()
    kinds = {row[1] for row in lineage}
    assert kinds == {"manual"}, lineage
    assert {row[0] for row in lineage} <= manual_ids


def test_manual_and_machine_rows_feed_the_same_measure(tmp_path):
    """Нормализация единицы в ISO нужна дверце «у всех потоков меры одна
    unit»: ручная выручка и машинная чистая прибыль за тот же период
    дают net_margin вместе, а не две несовместимые строки."""
    conn, paths, repos, _o = _import(tmp_path)
    # один вход из машины, остальные ручные: эмитент, у которого
    # прибыль пришла из выгрузки, а выручка — из ручного импорта
    conn.execute("DELETE FROM fact WHERE canonical_concept='net_income'")
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis, origin,
           source_ref, locator, parser_version, status, ingested_at,
           canonical_concept, source_kind)
           VALUES ('m-ni', 'AU-C4', 'us-gaap:NetIncomeLoss', ?, ?,
           'duration', '246900000', 'USD', 'USD', 'as_reported',
           'extracted', 's', '{}', 'companyfacts.v1', 'ok', 0,
           'net_income', 'provider')""",
        (FY_START, FY_END))
    units = {row[2] for row in _facts(conn, "AU-C4") if row[7] is not None}
    assert units == {"USD"}
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build("AU-C4-1", "AU-C4", AS_OF)
    rows = repos.snapshot.get_measures(result.snapshot_id)
    margin = next(m for m in rows if m[3] == "net_margin")
    assert margin[4] is not None, margin
    lineage = conn.execute(
        """SELECT f.source_kind FROM measure_lineage ml
           JOIN fact f ON f.fact_id = ml.fact_id
           WHERE ml.measure_id=?""", (margin[0],)).fetchall()
    assert {row[0] for row in lineage} == {"manual", "provider"}, lineage


def test_unverified_and_near_miss_records_never_reach_a_fact(tmp_path):
    conn, _p, _r, outcome = _import(tmp_path)
    values = {row[1] for row in _facts(conn, "AU-C4")}
    assert "1.234" not in values                      # near_miss
    assert "9,999.9" not in values                   # failed
    assert not any(str(v).startswith("9999") for v in values), values
    assert outcome.records_verified == 24
    assert outcome.facts_stored == 24
    assert outcome.records_mapped == 21
    assert outcome.records_unverified == 2
    assert outcome.records_near_miss == 1


def test_import_still_runs_on_the_real_recorded_fleet_answer(tmp_path):
    """Ступень ② на записанном ответе настоящей модели прогоняется
    целиком: 36 записей, ни одной отображённой, факты с NULL."""
    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-F2", "AU-F2")
    outcome = import_document(
        conn, paths, FLEET_DOC, "AU-F2",
        Client(RECORDED_FLEET.read_text(encoding="utf-8")))
    assert outcome.records_total == 36
    assert outcome.records_mapped == 0
    assert outcome.facts_stored == outcome.records_verified
    assert all(row[7] is None for row in _facts(conn, "AU-F2"))

def test_cli_import_names_the_mapped_count(tmp_path, monkeypatch, capsys):
    """Пользователь `rusterm import` обязан видеть, сколько записей
    отображено: счётчик в выводе команды — единственное место, где это
    видно без SQL."""
    import rusterm.cli as cli

    conn, paths = _paths(tmp_path)
    repos = RepoRegistry(conn, paths)
    _issuer(conn, repos, "AU-C4T", "AU-C4T")
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test c4.invalid")
    monkeypatch.setattr("rusterm.providers.llm_api.LlmApiClient.from_env",
                        classmethod(lambda cls, gate, environ=None:
                                    Client(ANSWER.read_text(
                                        encoding="utf-8"))))
    code = cli.main(["--root", str(paths.root), "import", str(DOC),
                     "--issuer", "C4T", "--market", "AU"])
    assert code == 0, capsys.readouterr().err
    out = capsys.readouterr().out
    assert "отображено в словарь: 21" in out, out
