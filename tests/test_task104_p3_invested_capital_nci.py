"""ТЗ-104 P3: строка `invested_capital` включает неконтролирующую долю.

Словарь §3: invested_capital = total_equity + minority_interest +
total_debt − cash − st_investments — ровно та формула, которой `roic`
собирает знаменатель (`formulas.invested_capital`, calls it at both
borders). До пункта строка пропускала NCI, поэтому у эмитента с живым
меньшинством (форма SCCO: меньшинство отдельной строкой) строка
расходилась с числом внутри `roic` — тот же вход, два разных ответа.

| где | было | стало |
|---|---|---|
| строка при NCI 4 | 37 (без NCI) | 41 |
| то же число внутри `roic` | 41 | 41 — строка и знаменатель совпали |
| lineage строки | без NCI | id NCI-факта, а при производном нуле — роль `nci_absent_in_equity_block` |
| NCI в чужой валюте | число в валюте остальных входов | `currency_mismatch` |
| NCI отчитывалась, но строки меньшинства нет | 37 | `missing_data: minority_interest` |

D7 («отсутствие NCI — ноль, если блок капитала подавался») сохраняется:
ноль по-прежнему производен и никогда не выдуман, а знак NCI не берётся
по модулю.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.formulas import invested_capital
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

# Дата сборки в прошлом всех периодов фикстуры: границы и давность
# меряются от неё, иначе тест краснел бы со временем.
AS_OF = "2025-06-30"
PRICE_DATE = "2025-06-27"          # 3 дня: порог _PRICE_STALE_DAYS = 7
SHARES_DATE = "2025-03-31"         # свежее порога M1 (550)
FY_END = "2024-12-31"              # годовой поток — он же окно NOPAT
FY_START = (date.fromisoformat(FY_END) - timedelta(days=364)).isoformat()
PRIOR_END = "2023-12-31"           # капитал на начало окна (граница +2 дня)

NOPAT = 4.8                        # 6 * (1 - 1/5)
EQUITY_END, DEBT_END, CASH_END, STINV_END, NCI_END = 35.0, 5.0, 2.0, 1.0, 4.0
EQUITY_BEGIN, DEBT_BEGIN, CASH_BEGIN, STINV_BEGIN, NCI_BEGIN = \
    25.0, 8.0, 3.0, 1.0, 6.0
IC_END = EQUITY_END + NCI_END + DEBT_END - CASH_END - STINV_END      # 41
IC_BEGIN = EQUITY_BEGIN + NCI_BEGIN + DEBT_BEGIN - CASH_BEGIN - STINV_BEGIN  # 35
# прежний пропуск NCI: те же балансы без меньшинства
IC_END_WITHOUT_NCI = EQUITY_END + DEBT_END - CASH_END - STINV_END    # 37


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-P3", issuer="i1", price=True):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    if price:
        repos.price.put_rows(iid, "twelvedata",
                             [{"date": PRICE_DATE, "close": 10.0,
                               "currency": "USD"}])


def _fact(conn, issuer_id, concept, value, start, end, period_type,
          currency="USD"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-' || ? || '-' || ? || '-' || ?, ?, ?, ?, ?, ?, ?,
           ?, ?, 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (issuer_id, concept, end, issuer_id, concept, start, end,
         period_type, str(value), currency, currency, concept))


def _stock(conn, issuer_id, concept, value, end=FY_END, currency="USD"):
    _fact(conn, issuer_id, concept, value, end, end, "instant", currency)


def _flow(conn, issuer_id, concept, value, start=FY_START, end=FY_END):
    _fact(conn, issuer_id, concept, value, start, end, "duration")


def _balance(conn, issuer_id="i1", end=FY_END, equity=EQUITY_END,
             debt=DEBT_END, cash=CASH_END, stinv=STINV_END, nci=NCI_END,
             shares=None, nci_currency="USD"):
    if shares is not None:
        _fact(conn, issuer_id, "shares_outstanding", shares, shares, shares,
              "instant")
    _stock(conn, issuer_id, "total_debt", debt, end)
    _stock(conn, issuer_id, "cash", cash, end)
    _stock(conn, issuer_id, "st_investments", stinv, end)
    _stock(conn, issuer_id, "total_equity", equity, end)
    if nci is not None:
        _stock(conn, issuer_id, "minority_interest", nci, end,
               currency=nci_currency)


def _prior_balance(conn, issuer_id="i1", end=PRIOR_END,
                   equity=EQUITY_BEGIN, debt=DEBT_BEGIN, cash=CASH_BEGIN,
                   stinv=STINV_BEGIN, nci=NCI_BEGIN):
    _stock(conn, issuer_id, "total_debt", debt, end)
    _stock(conn, issuer_id, "cash", cash, end)
    _stock(conn, issuer_id, "st_investments", stinv, end)
    _stock(conn, issuer_id, "total_equity", equity, end)
    if nci is not None:
        _stock(conn, issuer_id, "minority_interest", nci, end)


def _flows(conn, issuer_id="i1"):
    _flow(conn, issuer_id, "revenue", 100.0)
    _flow(conn, issuer_id, "net_income", 4.0)
    _flow(conn, issuer_id, "operating_income", 6.0)
    _flow(conn, issuer_id, "d_and_a", 1.0)
    _flow(conn, issuer_id, "tax_expense", 1.0)
    _flow(conn, issuer_id, "pretax_income", 5.0)


def _base(conn, repos, iid="US-P3", issuer="i1", price=True, nci=NCI_END):
    """SCCO-форма: NCI отдельной строкой на обеих годовых границах."""
    _paper(repos, iid, issuer, price=price)
    _balance(conn, issuer, shares=SHARES_DATE, nci=nci)
    _prior_balance(conn, issuer,
                   nci=NCI_BEGIN if nci is not None else None)
    _flows(conn, issuer)


def _build(repos, iid="US-P3", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


def _lineage(conn, rows, concept):
    return list(conn.execute(
        """SELECT fact_id, role FROM measure_lineage WHERE measure_id=?""",
        (rows[concept][0],)))


# ── строка = число внутри roic (Done-when) ─────────────────────────────

def test_row_includes_the_reported_minority_interest(env):
    """35 + 4 + 5 − 2 − 1: NCI входит в строку, а не только в
    знаменатель roic."""
    conn, repos = env
    _base(conn, repos)
    rows = _build(repos)
    assert float(rows["invested_capital"][4]) == pytest.approx(IC_END), \
        rows["invested_capital"]
    assert rows["invested_capital"][10] is None, rows["invested_capital"][10]
    # прежняя арифметика без меньшинства
    assert float(rows["invested_capital"][4]) != pytest.approx(
        IC_END_WITHOUT_NCI)


def test_row_equals_the_number_inside_roic(env):
    """Зуб Done-when: строка — тот же конец знаменателя, что видит roic.
    4.8 / ((35 + строка) / 2) обязано совпасть с записанным roic; пока
    строка теряла NCI, она расходилась с частным на 41/37."""
    conn, repos = env
    _base(conn, repos)
    rows = _build(repos)
    row = float(rows["invested_capital"][4])
    assert float(rows["roic"][4]) == pytest.approx(NOPAT / ((IC_BEGIN + row)
                                                             / 2.0)), \
        (rows["roic"], row)


def test_row_is_the_dictionary_formula_not_an_inline_sum(env):
    """Строку считает та же `formulas.invested_capital`, чем roic:
    подпись совпадает побайтово, и расхождение двух путей больше нельзя
    починить «одной скобкой»."""
    conn, repos = env
    _base(conn, repos)
    rows = _build(repos)
    assert float(rows["invested_capital"][4]) == pytest.approx(
        invested_capital(EQUITY_END, NCI_END, DEBT_END, CASH_END, STINV_END))


def test_nci_fact_is_signed_into_the_row_lineage(env):
    """Мера читается по своим входам (I4): id факта меньшинства лежит в
    lineage строки наряду с остальными слагаемыми."""
    conn, repos = env
    _base(conn, repos)
    rows = _build(repos)
    facts = {r[0] for r in _lineage(conn, rows, "invested_capital")}
    assert f"f-i1-minority_interest-{FY_END}" in facts, facts
    for concept in ("total_equity", "total_debt", "cash", "st_investments"):
        assert f"f-i1-{concept}-{FY_END}" in facts, (concept, facts)


# ── D7: производный ноль остаётся нулём, а не выдумкой ─────────────────

def test_issuer_that_never_reported_nci_keeps_the_old_number(env):
    """AAPL-форма: строк NCI нет ни разу → 0.0 производен от блока
    капитала, строка не меняется и несёт роль, объясняющую ноль."""
    conn, repos = env
    _base(conn, repos, nci=None)
    rows = _build(repos)
    assert float(rows["invested_capital"][4]) == pytest.approx(
        IC_END_WITHOUT_NCI), rows["invested_capital"]
    roles = {r[1] for r in _lineage(conn, rows, "invested_capital")}
    assert "nci_absent_in_equity_block" in roles, roles


def test_nci_reported_once_but_not_as_a_minority_line_refuses(env):
    """Эмитент раскрывает меньшинство внутри капитала
    (total_equity_incl_nci), отдельной строки NCI не подавал никогда:
    вычитать её из капитала пункт не просит, а молча посчитать без неё —
    тот же пропуск, из-за которого строка расходилась с roic. Ответ —
    названный вход, как у `ev` и капитала на границе окна."""
    conn, repos = env
    _base(conn, repos, nci=None)
    conn.execute("""DELETE FROM fact
                    WHERE canonical_concept='minority_interest'""")
    _stock(conn, "i1", "total_equity_incl_nci", 39.0, FY_END)
    _stock(conn, "i1", "total_equity_incl_nci", 31.0, PRIOR_END)
    rows = _build(repos)
    assert rows["invested_capital"][4] is None, rows["invested_capital"]
    assert rows["invested_capital"][10] == "missing_data: minority_interest", \
        rows["invested_capital"][10]


# ── валюта и знак ──────────────────────────────────────────────────────

def test_minority_in_another_currency_refuses_the_row(env):
    """K6: NCI в GBP под балансом в USD — это не сумма, а две валюты.
    До пункта вход в спор валют не входил, потому что его не было."""
    conn, repos = env
    _base(conn, repos)
    conn.execute("""UPDATE fact SET currency='GBP', unit='GBP'
                    WHERE canonical_concept='minority_interest'
                      AND period_end=?""", (FY_END,))
    rows = _build(repos)
    assert rows["invested_capital"][4] is None, rows["invested_capital"]
    assert rows["invested_capital"][10] == "currency_mismatch: GBP, USD", \
        rows["invested_capital"][10]


def test_negative_minority_is_added_not_absorbed(env):
    """Уменьшинство с накопленным убытком — отрицательная строка:
    35 − 5 + 5 − 2 − 1 = 32. Знак берётся не по модулю."""
    conn, repos = env
    _base(conn, repos)
    _set_nci(conn, -5.0, FY_END)
    rows = _build(repos)
    assert float(rows["invested_capital"][4]) == pytest.approx(
        EQUITY_END - 5.0 + DEBT_END - CASH_END - STINV_END), \
        rows["invested_capital"]


def _set_nci(conn, value, end):
    conn.execute("""UPDATE fact SET value=? WHERE issuer_id='i1'
                    AND canonical_concept='minority_interest'
                      AND period_end=?""", (str(value), end))


# ── чего пункт не должен задеть ────────────────────────────────────────

def test_roic_does_not_start_counting_nci_twice(env):
    """roic и до пункта делил на капитал с NCI. Строка переезжает на то
    же число, а частное остаётся прежним: 4.8 / ((35 + 41) / 2)."""
    conn, repos = env
    _base(conn, repos)
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(
        NOPAT / ((IC_BEGIN + IC_END) / 2.0)), rows["roic"]


def test_the_row_still_computes_without_a_price(env):
    """ТЗ-91 B2 сохраняется: цена — не вход invested_capital, и с NCI
    внутри строки её по-прежнему нет."""
    conn, repos = env
    _base(conn, repos, price=False)
    rows = _build(repos)
    assert float(rows["invested_capital"][4]) == pytest.approx(IC_END), \
        rows["invested_capital"]
    assert rows["invested_capital"][5] == "USD", rows["invested_capital"][5]
