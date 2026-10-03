"""ТЗ-92 C0, зуб до конца Done-when: снапшот после правки считает `pe` по 200.

Мера `pe` = `market_cap_total / net_income_ttm` (ТЗ-97 Q10), знаменатель
приходит из `latest_annual_fact`. Правка `rusterm verify` оставляет старый
факт в таблице с `superseded_by`, и пока читатель его не отбрасывает, сборка
делит на отвергнутое число. Числа фикстуры подобраны так, чтобы различие
было видно одним взглядом: капитализация 70, знаменатель 100 или 200,
частное 0.7 или 0.35.
"""
from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

TODAY = date.today().isoformat()
# Свежие границы годового окна: дверь по давности акций — 550 дней от as_of
# (ТЗ-102 M1), годовой период внутри окна 350..380 дней (ТЗ-91 B4).
SHARES_END = date.fromordinal(date.today().toordinal() - 90).isoformat()
NI_END = date.fromordinal(date.today().toordinal() - 120).isoformat()
NI_START = date.fromordinal(date.today().toordinal() - 480).isoformat()


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(
        Issuer("i1", "Peaches Corp.", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(
        Instrument("US-P", "i1", None, "common", "active", None))
    repos.price.put_rows("US-P", "twelvedata",
                         [{"date": TODAY, "close": 10.0, "currency": "USD"}])
    return conn, repos


def _fact(conn, concept, value, fact_id, end, start=None):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, 'i1', ?, ?, ?, 'duration', ?, 'USD', 'USD',
           'as_reported', 'extracted', 's', '{}', 'companyfacts.v1', 'ok',
           0, ?, 'provider')""",
        (fact_id, concept, start or end, end, str(value), concept))


def _pe(conn, repos):
    SnapshotBuilder(repos.snapshot, repos.peer_set,
                    coverage_repo=repos.coverage,
                    price_repo=repos.price).build("US-P", "i1", TODAY)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-P"))
    m = next(r for r in rows if r[3] == "pe")
    # колонка measure.value — TEXT; сравниваем числом, иначе `round` падает
    return (None if m[4] is None else float(m[4])), m[10]


def test_pe_uses_the_live_annual_denominator(env):
    """Правка net_income 100 → 200: `pe` 0.7 → 0.35 (Done-when)."""
    conn, repos = env
    _fact(conn, "shares_outstanding", 7.0, "f-shares", SHARES_END)
    _fact(conn, "net_income", 100.0, "f-ni-old", NI_END, NI_START)
    value, reason = _pe(conn, repos)
    assert value is not None, reason
    assert round(value, 4) == 0.7, (value, reason)

    _fact(conn, "net_income", 200.0, "f-ni-new", NI_END, NI_START)
    repos.fact.mark_superseded("f-ni-old", "f-ni-new")
    value, reason = _pe(conn, repos)
    assert value is not None, reason
    assert round(value, 4) == 0.35, (
        f"знаменатель всё ещё отвергнутый факт: pe={value}, reason={reason}")


def test_lineage_points_at_the_surviving_fact(env):
    """Линейка меры не ссылается на снятый с учёта факт."""
    conn, repos = env
    _fact(conn, "shares_outstanding", 7.0, "f-shares", SHARES_END)
    _fact(conn, "net_income", 100.0, "f-ni-old", NI_END, NI_START)
    _fact(conn, "net_income", 200.0, "f-ni-new", NI_END, NI_START)
    repos.fact.mark_superseded("f-ni-old", "f-ni-new")
    _pe(conn, repos)
    ids = {r[0] for r in conn.execute(
        """SELECT l.fact_id FROM measure_lineage l
           JOIN measure m ON m.measure_id = l.measure_id
           WHERE m.concept = 'pe'""").fetchall()}
    assert "f-ni-old" not in ids, sorted(ids)
    assert "f-ni-new" in ids, sorted(ids)
