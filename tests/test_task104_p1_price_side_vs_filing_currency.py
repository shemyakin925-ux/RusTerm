"""ТЗ-104 P1: `pe`, `ps`, `fcf_yield` отказываются делить разные валюты.

Правило то же, что у `pb` (ТЗ-23 K6) и у мер B3 (ТЗ-91): стороны частного
в разных валютах → `currency_mismatch: <A>, <B>`, а не частное.
FX-пересчёта нет и не будет: бесплатного источника курсов в проекте нет
(ADR-0018), а выдуманный курс дал бы число, которого никто не подавал.

| где | было | стало |
|---|---|---|
| pe | капитализация USD / чистая прибыль GBP = 7,0 | `currency_mismatch: GBP, USD` |
| ps | то же с выручкой | то же |
| fcf_yield | fcf из GBP-потоков / капитализация класса в USD | то же |

Валюта стороны-рынка — unit рыночной капитализации (валюта цены, строки
`market_cap`/`market_cap_total`); валюта стороны-отчётности — unit
TTM-окна, а на запасном годовом пути — unit этого годового факта; у
fcf_yield числитель — unit меры `fcf` из первого прохода.

Отсутствующий вход первее валютного спора (ТЗ-91 B3): спор касается тех
сторон, что на месте. Валютного спора хватает раньше знака знаменателя
(ТЗ-91 B2): при разных валютах частного не существует ни при каком знаке,
и отрицательная прибыль в GBP не обязана становиться отрицательной
прибылью в USD.

Вход без записанной валюты (факт, разобранный до J1.0) в спор не
вступает — то же правило B3: там, где валюта просто не записана,
выдуманный отказ вытеснил бы прежнюю подпись.
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
FY_END = "2025-12-31"          # годовой период, закрытый до as_of
MISMATCH = "currency_mismatch: GBP, USD"


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _paper(repos, iid="US-P1", issuer="i1", price_currency="USD"):
    """Бумага с ценой в `price_currency`; отчётность — у `_fact`.

    Эмитент — британский, как OTC/ADR-случай из пункта ТЗ: цена в USD,
    отчётность в GBP.
    """
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
           VALUES ('f-' || ? || '-' || ? || '-' || ? || '-' || ?, ?, ?, ?,
           ?, ?, ?, ?, ?, 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (issuer_id, concept, start, end, issuer_id, concept, start, end,
         period_type, str(value), unit if unit is not None else currency,
         currency, concept))


def _flow(conn, issuer_id, concept, value, end=FY_END, days=364,
          currency="GBP", start=None):
    start = start or (date.fromisoformat(end)
                      - timedelta(days=days)).isoformat()
    _fact(conn, issuer_id, concept, value, start, end, "duration",
          currency)


def _base(conn, issuer_id="i1", currency="GBP"):
    """Эмитент трёх мер: прибыль 10, выручка 100, fcf = 20 - 8 = 12 в
    `currency`; цена 10.0 x 7 акций = капитализация 70.

    Число акций — без валюты (unit `shares`), как на базе пользователя:
    иначе рыночная капитализация отбивается раньше, чем мера успевает
    сказать своё слово про валюту своего знаменателя.
    """
    _fact(conn, issuer_id, "shares_outstanding", 7.0, FRESH_SHARES,
          FRESH_SHARES, "instant", currency="", unit="shares")
    _flow(conn, issuer_id, "revenue", 100.0, currency=currency)
    _flow(conn, issuer_id, "net_income", 10.0, currency=currency)
    _flow(conn, issuer_id, "ocf", 20.0, currency=currency)
    _flow(conn, issuer_id, "capex", 8.0, currency=currency)


def _build(repos, iid="US-P1", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


# ── окно TTM: обе стороны частного ─────────────────────────────────────

def test_pe_ps_and_fcf_yield_refuse_usd_market_over_gbp_filings(env):
    """Случай из Done-when: цена USD, отчётность GBP — все три меры
    отказывают, а не делят 70 на GBP-число."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, currency="GBP")
    rows = _build(repos)
    for concept in ("pe", "ps", "fcf_yield"):
        assert rows[concept][4] is None, (concept, rows[concept])
        assert rows[concept][10] == MISMATCH, (concept, rows[concept][10])


def test_the_refusal_keeps_the_ratio_label(env):
    """Отказ по валюте не подписывает безразмерную меру валютой одной из
    сторон — то же, что постановила B3 для roic."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, currency="GBP")
    rows = _build(repos)
    for concept in ("pe", "ps", "fcf_yield"):
        assert rows[concept][5] == "ratio", (concept, rows[concept][5])


def test_one_currency_on_both_sides_still_divides(env):
    """Зуб против перенормировки: цена и отчётность в USD — все три меры
    остаются частными, ни одной новой отказной строки."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, currency="USD")
    rows = _build(repos)
    assert float(rows["pe"][4]) == pytest.approx(70.0 / 10.0), rows["pe"]
    assert float(rows["ps"][4]) == pytest.approx(70.0 / 100.0), rows["ps"]
    assert float(rows["fcf_yield"][4]) == pytest.approx(12.0 / 70.0), \
        rows["fcf_yield"]
    for concept in ("pe", "ps", "fcf_yield"):
        assert rows[concept][10] is None, (concept, rows[concept][10])


def test_a_currency_less_denominator_does_not_start_a_dispute(env):
    """Легасивная строка факта без валюты — не спор (правило B3): где
    валюта не записана, отказывать не по чему."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, currency="")
    rows = _build(repos)
    for concept in ("pe", "ps", "fcf_yield"):
        assert rows[concept][10] is None, (concept, rows[concept][10])
        assert rows[concept][4] is not None, (concept, rows[concept])


def test_a_missing_market_cap_outweighs_the_currency_dispute(env):
    """B3 по порядку: без числителя частного нет при любых валютах, и
    причина называет именно его, а не вымышленный спор."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _base(conn, currency="GBP")
    conn.execute("DELETE FROM fact WHERE canonical_concept="
                 "'shares_outstanding'")
    rows = _build(repos)
    for concept in ("pe", "ps"):
        assert rows[concept][10] == "missing_data: market_cap_total", \
            (concept, rows[concept][10])
    assert rows["fcf_yield"][10] == "missing_data: market_cap", \
        rows["fcf_yield"][10]


# ── запасной годовой путь: валюта там же, где и вход ──────────────────

def test_the_annual_backup_denominator_refuses_too(env):
    """Окно по выручке не собралось (кварталы в двух валютах — K6 не
    пускает такое окно во вход) — знаменатель берётся последним годовым,
    и его валюта обязана пройти ту же проверку."""
    conn, repos = env
    _paper(repos, price_currency="USD")
    _fact(conn, "i1", "shares_outstanding", 7.0, FRESH_SHARES,
          FRESH_SHARES, "instant", currency="", unit="shares")
    _flow(conn, "i1", "net_income", 10.0)
    # годовой 2024 в GBP — он и есть запасной знаменатель: позже него
    # годовых нет, а квартальные строки окно не собирают
    prior_end = "2024-12-31"
    prior_start = "2024-01-01"
    _flow(conn, "i1", "revenue", 100.0, start=prior_start, end=prior_end,
          currency="GBP")
    # четыре подряд квартала в двух валютах — окно выручки отброшено
    quarters = [("2025-09-30", "USD"), ("2025-12-31", "USD"),
                ("2026-03-31", "GBP"), ("2026-06-30", "GBP")]
    for end, currency in quarters:
        start = (date.fromisoformat(end) - timedelta(days=90)).isoformat()
        _flow(conn, "i1", "revenue", 25.0, start=start, end=end,
              currency=currency)
    rows = _build(repos)
    assert rows["ps"][4] is None, rows["ps"]
    assert rows["ps"][10] == MISMATCH, rows["ps"][10]
    # прибыль в том же GBP-окне: у неё окно есть, и она отказывается тоже
    assert rows["pe"][10] == MISMATCH, rows["pe"][10]
