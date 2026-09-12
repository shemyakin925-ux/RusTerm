"""ТЗ-23 K4/K6: оценочные меры получают входы и знают свою валюту.

- нет цены — missing_data: price_close на всех шести; перенос и
  устаревание запрещены: цена старше порога — причина;
- с ценой и фактами: market_cap/market_cap_total/ev/pb/ev_ebitda/roic
  считаются написанными формулами (ничего не переписывается);
- K6: ratio с числителем и знаменателем в разных валютах —
  currency_mismatch, а не частное; агрегат по абсолютной мере в
  разных валютах отказывается, по ratio считается.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from rusterm.core.industry.aggregate import build_sector_aggregates
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)

TODAY = date.today().isoformat()
OLD = date.fromordinal(date.today().toordinal() - 30).isoformat()


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return conn, repos, paths


def _issuer(conn, repos, instrument_id, issuer_id, currency="USD"):
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, None, "us_gaap",
        currency))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))


def _fact(conn, issuer_id, concept, value, currency="USD",
          end="2024-12-31"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-' || ?, ?, ?, '2024-01-01', ?, 'duration', ?,
           ?, ?, 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"{issuer_id}-{concept}-{end}", issuer_id, concept, end,
         str(value), currency, currency, concept))


def _build(conn, repos, instrument_id, issuer_id, as_of=TODAY):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(instrument_id, issuer_id, as_of)
    return repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(instrument_id))


def _measure(rows, concept):
    return next(m for m in rows if m[3] == concept)


def test_missing_price_yields_reason_on_all_six(env):
    conn, repos, paths = env
    _issuer(conn, repos, "US-P", "i1")
    rows = _build(conn, repos, "US-P", "i1")
    for concept in ("market_cap", "market_cap_total", "ev", "pb",
                    "ev_ebitda", "div_yield", "roic"):
        m = _measure(rows, concept)
        assert m[4] is None, (concept, m[4])
        assert m[10] == "missing_data: price_close", (concept, m[10])


def test_stale_price_yields_reason_not_number(env):
    conn, repos, paths = env
    _issuer(conn, repos, "US-P", "i1")
    repos.price.put_rows("US-P", "twelvedata",
                         [{"date": OLD, "close": 50.0,
                           "currency": "USD"}])
    rows = _build(conn, repos, "US-P", "i1")
    m = _measure(rows, "market_cap")
    assert m[4] is None
    assert m[10] == f"missing_data: price_close_stale:{OLD}"


def test_valuation_measures_compute_from_price_and_facts(env):
    conn, repos, paths = env
    _issuer(conn, repos, "US-P", "i1")
    repos.price.put_rows("US-P", "twelvedata",
                         [{"date": TODAY, "close": 10.0,
                           "currency": "USD"}])
    # цена * акция; фундаментал в фактах; ebitda/nopat — первый проход
    _fact(conn, "i1", "shares_outstanding", 7.0)
    _fact(conn, "i1", "total_equity", 35.0)
    _fact(conn, "i1", "total_debt", 5.0)
    _fact(conn, "i1", "cash", 2.0)
    _fact(conn, "i1", "st_investments", 1.0)
    _fact(conn, "i1", "minority_interest", 0.0)
    _fact(conn, "i1", "invested_capital", 40.0)
    _fact(conn, "i1", "operating_income", 6.0)
    _fact(conn, "i1", "d_and_a", 1.0)
    _fact(conn, "i1", "revenue", 100.0)
    _fact(conn, "i1", "net_income", 4.0)
    _fact(conn, "i1", "tax_expense", 1.0)
    _fact(conn, "i1", "pretax_income", 5.0)
    rows = _build(conn, repos, "US-P", "i1")
    mcap = _measure(rows, "market_cap")
    assert mcap[4] is not None and float(mcap[4]) == pytest.approx(70.0)
    assert mcap[5] == "USD", "капитализация в валюте цены"
    total = _measure(rows, "market_cap_total")
    assert float(total[4]) == pytest.approx(70.0)
    ev = _measure(rows, "ev")
    assert float(ev[4]) == pytest.approx(70.0 + 5.0 - 2.0 - 1.0 + 0.0)
    pb = _measure(rows, "pb")
    assert float(pb[4]) == pytest.approx(2.0)
    ev_ebitda = _measure(rows, "ev_ebitda")
    # ebitda = operating_income + d_and_a = 7; ev = 72
    assert float(ev_ebitda[4]) == pytest.approx(72.0 / 7.0)
    roic = _measure(rows, "roic")
    # nopat = 6 * (1 - 1/5) = 4.8; roic = 4.8/40
    assert float(roic[4]) == pytest.approx(4.8 / 40.0)


def test_k6_ratio_with_mixed_currencies_is_refused(env):
    """pb: числитель в USD (цена), знаменатель в KRW (факт) — отказ."""
    conn, repos, paths = env
    _issuer(conn, repos, "US-P", "i1")
    repos.price.put_rows("US-P", "twelvedata",
                         [{"date": TODAY, "close": 10.0,
                           "currency": "USD"}])
    _fact(conn, "i1", "shares_outstanding", 7.0)
    _fact(conn, "i1", "total_equity", 3500.0, currency="KRW")
    rows = _build(conn, repos, "US-P", "i1")
    pb = _measure(rows, "pb")
    assert pb[4] is None
    assert pb[10] == "currency_mismatch: KRW, USD"


def test_k6_dividend_yield_mixed_currency_refused(env):
    conn, repos, paths = env
    _issuer(conn, repos, "US-P", "i1")
    repos.price.put_rows("US-P", "twelvedata",
                         [{"date": TODAY, "close": 10.0,
                           "currency": "USD"}])
    _fact(conn, "i1", "dps_ttm", 0.5, currency="KRW")
    rows = _build(conn, repos, "US-P", "i1")
    dy = _measure(rows, "div_yield")
    assert dy[4] is None
    assert dy[10] == "currency_mismatch: KRW, USD"


def test_k6_mixed_currency_aggregate_refused_ratio_computes(env):
    """Агрегат сектора: абсолютная market_cap_total в двух валютах —
    currency_mismatch; ratio net_margin считается."""
    conn, repos, paths = env
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "mixed")
    peers.add_version("v1", "ps", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    for i, (iid, issuer, cur, price_ccy) in enumerate([
            ("US-A", "u0", "USD", "USD"), ("US-B", "u1", "USD", "USD"),
            ("US-C", "u2", "USD", "USD"), ("US-D", "u3", "USD", "USD"),
            ("KR-E", "k0", "KRW", "KRW"), ("KR-F", "k1", "KRW", "KRW"),
            ("KR-G", "k2", "KRW", "KRW"), ("KR-H", "k3", "KRW", "KRW")]):
        _issuer(conn, repos, iid, issuer)
        peers.add_member("v1", iid, None)
        repos.price.put_rows(iid, "twelvedata",
                             [{"date": TODAY, "close": 10.0 + i,
                               "currency": price_ccy}])
        _fact(conn, issuer, "shares_outstanding", 7.0 + i,
              currency=cur)
        _fact(conn, issuer, "revenue", 100.0 + i, currency=cur)
        _fact(conn, issuer, "net_income", 10.0 + i, currency=cur)
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage,
                                  price_repo=repos.price)
        builder.build(iid, issuer, TODAY)
    built = build_sector_aggregates(repos, "ps", TODAY,
                                    ("market_cap_total", "net_margin"))
    by_concept = {a.concept: a for a in built["aggregates"]}
    mcap = by_concept["market_cap_total"]
    assert mcap.null_reason and \
        mcap.null_reason.startswith("currency_mismatch")
    assert "KRW" in mcap.null_reason and "USD" in mcap.null_reason
    nm = by_concept["net_margin"]
    assert nm.null_reason is None and nm.n == 8, nm
