"""ТЗ-91 B3: денежная мера помечена валютой своих входов, а не цены.

Правило пункта: unit денежной меры — валюта её фактов; входы в более чем
одной валюте (цена участвует там, где она вход) — `currency_mismatch: A, B`
того же стиля, что у pb (ТЗ-23 K6).

| где | было | стало |
|---|---|---|
| net_debt | `unit=price_currency` | валюта фактов долга и денег |
| invested_capital | `unit=price_currency` | валюта фактов капитала |
| ev | капитализация цены складывалась с долгом без проверки | `currency_mismatch` |
| ev_ebitda | считалась поверх отказанного ev и звала его `missing_data: ev` | тот же `currency_mismatch` |
| net_debt_ebitda | `missing_data: net_debt` при валютном отказе net_debt | тот же `currency_mismatch` |
| roic | знаменатель из GBP-фактов подписывался валютой цены | стороны сравниваются по фактам |

Вход без валюты (легасивная строка факта) в спор не вступает: иначе там,
где валюта просто не записана, выдуманный «USD» сменился бы отказом.

Валюта числителя roic берётся со строки nopat: потоковые концепты в этот
проход не попадают (`_VALUATION_INPUT_CONCEPTS` — балансовые входы), так
что сравнивать сторону можно только с уже записанной мерой. Отсюда —
расхождение с буквой Done-when (её случай «цена USD + факты GBP» после
B3 даёт roic без отказа: ни одного ценового входа у него нет), см. раздел
«Спорное» отчёта.

Отказ из-за отсутствующего входа первее валютного спора: спор касается
только тех входов, что на месте, а без входа мера невозможна при любых
валютах.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = date.today().isoformat()
FRESH_SHARES = date.fromordinal(date.today().toordinal() - 90).isoformat()
FY_END = "2025-12-31"      # годовой период, закрытый до as_of


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-B3", issuer="i1", price_currency="USD"):
    """Бумага с ценой в `price_currency`; отчётность — у `_fact`."""
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "GB", None, None, "ifrs", "GBP"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    repos.price.put_rows(iid, "twelvedata",
                         [{"date": AS_OF, "close": 10.0,
                           "currency": price_currency}])


def _fact(conn, issuer_id, concept, value, start, end, period_type,
          currency="GBP", unit=None):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-' || ? || '-' || ? || '-' || ?, ?, ?, ?, ?, ?, ?,
           ?, ?, 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (issuer_id, concept, end, issuer_id, concept, start, end,
         period_type, str(value), unit if unit is not None else currency,
         currency, concept))


def _stock(conn, issuer_id, concept, value, end, currency="GBP"):
    _fact(conn, issuer_id, concept, value, end, end, "instant", currency)


def _flow(conn, issuer_id, concept, value, end=FY_END, days=364,
          currency="GBP"):
    start = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    _fact(conn, issuer_id, concept, value, start, end, "duration", currency)


def _base(conn, issuer_id="i1", balance="GBP", flows="GBP"):
    """Эмитент прохода оценки: долг 5, деньги 2 и 1, капитал 35 →
    net_debt = 2, invested_capital = 37; ebitda = 6 + 1 = 7,
    nopat = 6 x (1 - 1/5) = 4.8, net_income = 10, revenue = 100.
    `balance` — валюта моментных фактов, `flows` — потоковых.

    Число акций — без валюты (unit `shares`): на базе пользователя у
    3243 строк shares_outstanding валюта NULL, и иначе рыночная
    капитализация отбивалась бы К6-стражем ТЗ-23 раньше, чем успеет
    сказать своё слово проверка валют в самой мере.
    """
    _fact(conn, issuer_id, "shares_outstanding", 7.0, FRESH_SHARES,
          FRESH_SHARES, "instant", currency="", unit="shares")
    _flow(conn, issuer_id, "revenue", 100.0, currency=flows)
    _flow(conn, issuer_id, "net_income", 10.0, currency=flows)
    _flow(conn, issuer_id, "operating_income", 6.0, currency=flows)
    _flow(conn, issuer_id, "d_and_a", 1.0, currency=flows)
    _flow(conn, issuer_id, "tax_expense", 1.0, currency=flows)
    _flow(conn, issuer_id, "pretax_income", 5.0, currency=flows)
    _stock(conn, issuer_id, "total_debt", 5.0, FY_END, balance)
    _stock(conn, issuer_id, "cash", 2.0, FY_END, balance)
    _stock(conn, issuer_id, "st_investments", 1.0, FY_END, balance)
    _stock(conn, issuer_id, "total_equity", 35.0, FY_END, balance)


def _build(repos, iid="US-B3", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


# ── подписка деньгами: валюта фактов, а не цены ───────────────────────

def test_net_debt_and_invested_capital_carry_the_filing_currency(env):
    """Цена в USD, отчётность в GBP: число из GBP-фактов не имеет права
    называться USD — это ровно OTC/ADR-дефект из пункта."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    rows = _build(repos)
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert rows["net_debt"][5] == "GBP", rows["net_debt"][5]
    assert float(rows["invested_capital"][4]) == pytest.approx(37.0)
    assert rows["invested_capital"][5] == "GBP", \
        rows["invested_capital"][5]


def test_the_label_survives_a_missing_price(env):
    """B2 уже пустил эти меры без цены; подпись обязана остаться той же:
    цены нет — валюты цены тем более нет."""
    conn, repos = env
    _paper(repos)
    conn.execute("DELETE FROM price")
    _base(conn)
    rows = _build(repos)
    assert rows["net_debt"][5] == "GBP", rows["net_debt"]
    assert rows["invested_capital"][5] == "GBP", rows["invested_capital"]
    assert rows["market_cap"][10] == "missing_data: price_close"


def test_one_currency_everywhere_keeps_the_usual_label(env):
    """Случай «золотых» AAPL: цена и отчётность в одной валюте — та же
    подпись, ни одной новой отказной строки."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, balance="USD", flows="USD")
    rows = _build(repos)
    assert rows["net_debt"][5] == "USD"
    assert rows["invested_capital"][5] == "USD"
    assert rows["ev"][5] == "USD", rows["ev"]
    assert rows["ev"][4] is not None, rows["ev"]
    for concept in ("net_debt", "invested_capital", "ev", "ev_ebitda",
                    "roic"):
        assert rows[concept][10] is None, (concept, rows[concept][10])


# ── ev: складывать можно только одно и то же ──────────────────────────

def test_ev_refuses_a_usd_market_cap_over_gbp_debt(env):
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    rows = _build(repos)
    assert rows["ev"][4] is None, rows["ev"]
    assert rows["ev"][10] == "currency_mismatch: GBP, USD", rows["ev"][10]
    # отказ по валюте не выставляет валютную подпись несуществующему числу
    assert rows["ev"][5] == "", rows["ev"][5]


def test_chain_measures_repeat_the_refusal_instead_of_calling_ev_missing(env):
    """Отказанное по валютам ev — не «нет ev»: B2 запретила называть
    отсутствующим то, что на месте, и валюта не исключение."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    rows = _build(repos)
    assert (rows["ev"][10] or "").startswith("currency_mismatch"), rows["ev"]
    assert rows["ev_ebitda"][4] is None, rows["ev_ebitda"]
    assert rows["ev_ebitda"][10] == "currency_mismatch: GBP, USD", \
        rows["ev_ebitda"][10]
    # net_debt цены в входах не видит: его валюта одна, и его цепочка
    # считает, а не повторяет чужой отказ — отказ ev касается только мер,
    # у которых ev сам вход.
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert rows["net_debt"][10] is None, rows["net_debt"][10]
    assert float(rows["net_debt_ebitda"][4]) == pytest.approx(2.0 / 7.0), \
        rows["net_debt_ebitda"]
    assert rows["net_debt_ebitda"][10] is None, rows["net_debt_ebitda"][10]


def test_a_missing_input_outweighs_a_currency_dispute(env):
    """Спор валют касается только тех входов, что на месте: без входа ev
    невозможен при любых валютах, и причина называет именно его."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    conn.execute("DELETE FROM fact WHERE canonical_concept='total_debt'")
    rows = _build(repos)
    assert rows["ev"][4] is None, rows["ev"]
    assert rows["ev"][10] == "missing_data: total_debt", rows["ev"][10]
    assert rows["ev"][5] == "", rows["ev"][5]


def test_roic_refuses_when_its_sides_are_in_different_currencies(env):
    """nopat из GBP-потоков над знаменателем из USD-баланса: частное двух
    валют — K6-отказ, а не число."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, balance="USD", flows="GBP")
    rows = _build(repos)
    assert rows["roic"][4] is None, rows["roic"]
    assert rows["roic"][10] == "currency_mismatch: GBP, USD", \
        rows["roic"][10]
    # ratio-мера остаётся ratio: подписью отказа валюта не делается
    assert rows["roic"][5] == "ratio", rows["roic"][5]


def test_roic_never_saw_the_price_currency_after_b3(env):
    """Скользящий случай из Done-when (цена USD + факты GBP): у roic нет
    ценового входа, и когда весь отчёт в одной валюте, отказывать ему не
    по чему — частное остаётся. Отказ B3 появляется только там, где
    валюты сторон действительно расходятся (зуб выше)."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    rows = _build(repos)
    assert float(rows["roic"][4]) == pytest.approx(4.8 / 37.0), rows["roic"]
    assert rows["roic"][10] is None, rows["roic"][10]
    assert rows["roic"][5] == "ratio"


# ── смеси валют между фактами ─────────────────────────────────────────

def test_two_fact_currencies_refuse_net_debt(env):
    """Долг в USD, деньги в GBP: вычитать нельзя и подписать результат
    нечем."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, balance="USD", flows="USD")
    conn.execute("UPDATE fact SET currency='GBP', unit='GBP'"
                 " WHERE canonical_concept='cash'")
    rows = _build(repos)
    assert rows["net_debt"][4] is None, rows["net_debt"]
    assert rows["net_debt"][10] == "currency_mismatch: GBP, USD", \
        rows["net_debt"][10]
    assert rows["invested_capital"][10] == "currency_mismatch: GBP, USD", \
        rows["invested_capital"][10]
    # цепочка повторяет отказ входа, а не объявляет net_debt отсутствующим
    assert rows["net_debt_ebitda"][4] is None, rows["net_debt_ebitda"]
    assert rows["net_debt_ebitda"][10] == "currency_mismatch: GBP, USD", \
        rows["net_debt_ebitda"][10]


def test_a_fact_without_a_currency_is_not_a_second_side(env):
    """Легасивная строка факта с пустой валютой: отказ был бы новым
    поведением на данных, где валюта просто не записана, — подпись
    пустеет, число остаётся."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn)
    conn.execute("UPDATE fact SET currency='', unit=''")
    rows = _build(repos)
    assert float(rows["net_debt"][4]) == pytest.approx(2.0), rows["net_debt"]
    assert rows["net_debt"][5] == "", rows["net_debt"][5]
    assert rows["ev"][4] is not None, rows["ev"]
    assert rows["ev"][5] == "USD", rows["ev"][5]
