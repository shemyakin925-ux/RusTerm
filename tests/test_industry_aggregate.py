"""TASK-17 E1: агрегат сектора — чистая функция с названным методом.

Квартили считаются statistics.quantiles(method="inclusive") — линейная
интерполяция между порядковыми статистиками; ожидания в тесте —
литералы, вычисленные вручную, а не вызовом той же функции:
- девять значений 1..9: p25=3.0, median=5.0, p75=7.0 (позиции 2, 4, 6);
- восемь значений 1..8: p25=2.75, median=4.5, p75=6.25
  (позиция 0.25*(n-1)=1.75: v[1] + 0.75*(v[2]-v[1]) = 2.75).
Null исключается и считается; 7 вкладчиков — peer_set_too_small (I6);
неподтверждённый набор — peer_set_not_confirmed.
"""
from __future__ import annotations

import tempfile

from rusterm.core.industry.aggregate import (
    METHOD_VERSION,
    sector_aggregate,
)


def test_nine_values_quartiles_are_hand_computed_literals():
    values = [(f"in-{i}", float(i)) for i in range(1, 10)]  # 1..9
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 == repr(3.0)
    assert agg.median == repr(5.0)
    assert agg.p75 == repr(7.0)
    assert agg.n == 9
    assert agg.null_reason is None
    assert agg.method_version == METHOD_VERSION == "industry.v1"


def test_eight_values_exercise_the_interpolation():
    values = [(f"in-{i}", float(i)) for i in range(1, 9)]  # 1..8
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 == repr(2.75), agg.p25
    assert agg.median == repr(4.5)
    assert agg.p75 == repr(6.25)
    assert agg.n == 8


def test_nulls_are_excluded_and_counted_not_zero():
    values = [(f"in-{i}", float(i)) for i in range(11)]  # 11 вкладчиков
    values += [(f"in-empty-{i}", None) for i in range(3)]
    agg = sector_aggregate("operating_margin", values, verified=True)
    assert agg.n == 11, "null приравнялся к вкладчику"
    assert agg.median == repr(5.0)  # медиана одиннадцати значений 0..10
    assert agg.reason_counts == {"no_value": 3}


def test_seven_contributors_yield_peer_set_too_small():
    values = [(f"in-{i}", float(i)) for i in range(7)]
    agg = sector_aggregate("net_margin", values, verified=True)
    assert agg.p25 is None and agg.median is None and agg.p75 is None
    assert agg.n == 0
    assert agg.null_reason == "peer_set_too_small"


def test_unverified_set_yields_peer_set_not_confirmed():
    values = [(f"in-{i}", float(i)) for i in range(12)]
    agg = sector_aggregate("net_margin", values, verified=False)
    assert agg.median is None
    assert agg.n == 0
    assert agg.null_reason == "peer_set_not_confirmed"
    # участники с пустыми значениями остались в счётчике причин
    values_with_null = values + [("in-x", None)]
    agg = sector_aggregate("net_margin", values_with_null, verified=False)
    assert agg.reason_counts == {"no_value": 1}


def test_reason_is_in_the_b15_vocabulary():
    from rusterm.reasons import is_known_reason
    assert is_known_reason("peer_set_too_small")


def test_e2_as_of_selects_versions_composition_and_numbers_survive():
    """TASK-17 E2: сектор из 10 участников, агрегат на 2025-06-30; затем
    меняется СОСТАВ (новая версия с 2025-09-01) и приезжают новые
    снапшоты. Пересчёт на 2025-06-30 даёт тот же состав и те же числа;
    на 2025-12-31 — другие."""
    import os
    import shutil
    import sqlite3
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import (
        Instrument,
        Issuer,
        RepoRegistry,
    )

    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    peers = repos.peer_set
    peers.create_peer_set("sector", "industry", "tankers")
    peers.add_version("psv-june", "sector", 1, "2025-01-01",
                      "2025-09-01", "manual", "v1", True, None, None)

    def member(n: int) -> str:
        iid = f"in-{n}"
        repos.instrument.upsert_issuer(Issuer(
            f"i-{n}", f"Issuer {n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{n}", None, "common", "active", None))
        return iid

    june_members = [member(n) for n in range(10)]
    for n, iid in enumerate(june_members):
        peers.add_member("psv-june", iid, None)
        sid = f"s-june-{n}"
        repos.snapshot.create_snapshot(sid, iid, 1, "2025-06-30",
                                       None, "none", "ready")
        repos.snapshot.insert_measure(
            measure_id=f"m-june-{n}", snapshot_id=sid, scope="issuer",
            scope_ref=f"i-{n}", concept="net_margin",
            value=repr(0.01 * (n + 1)), unit="ratio",
            period_start="2025-01-01", period_end="2025-06-30",
            formula_id="net_margin", method_version="v1",
            null_reason=None, peer_set_version=None)

    concepts = ("net_margin",)
    first = sector_aggregate
    from rusterm.core.industry.aggregate import build_sector_aggregates
    june = build_sector_aggregates(repos, "sector", "2025-06-30", concepts)
    assert june["outcome"] == "resolved"
    assert june["peer_set_version_id"] == "psv-june"
    assert sorted(june["members"]) == sorted(june_members)
    june_tuple = [(a.concept, a.p25, a.median, a.p75, a.n,
                   a.null_reason, tuple(sorted(a.reason_counts.items())))
                  for a in june["aggregates"]]

    # меняется состав (версия с 2025-09-01: уходит in-0, приходят новые)
    sep_members = [member(n) for n in range(100, 112)]
    peers.add_version("psv-sep", "sector", 2, "2025-09-01",
                      None, "manual", "v1", True, None, None)
    for n, iid in enumerate(sep_members):
        peers.add_member("psv-sep", iid, None)
        sid = f"s-sep-{n}"
        repos.snapshot.create_snapshot(sid, iid, 1, "2025-09-15",
                                       None, "none", "ready")
        repos.snapshot.insert_measure(
            measure_id=f"m-sep-{n}", snapshot_id=sid, scope="issuer",
            scope_ref=f"i-{100 + n}", concept="net_margin",
            value=repr(0.5 + 0.01 * n), unit="ratio",
            period_start="2025-06-01", period_end="2025-09-15",
            formula_id="net_margin", method_version="v1",
            null_reason=None, peer_set_version=None)

    # воспроизведение на прошлую дату: тот же состав и те же числа
    again = build_sector_aggregates(repos, "sector", "2025-06-30", concepts)
    assert again["peer_set_version_id"] == "psv-june"
    assert sorted(again["members"]) == sorted(june_members)
    again_tuple = [(a.concept, a.p25, a.median, a.p75, a.n,
                    a.null_reason, tuple(sorted(a.reason_counts.items())))
                   for a in again["aggregates"]]
    assert again_tuple == june_tuple, "агрегат уплыл на воспроизведённой дате"

    # на новую дату — новая версия, новый состав, другие числа
    dec = build_sector_aggregates(repos, "sector", "2025-12-31", concepts)
    assert dec["peer_set_version_id"] == "psv-sep"
    dec_tuple = [(a.p25, a.median, a.p75, a.n)
                 for a in dec["aggregates"]]
    assert dec_tuple != [(a.p25, a.median, a.p75, a.n)
                         for a in june["aggregates"]]
    conn.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    del first


def test_e3_store_aggregates_repeat_build_no_duplicates():
    """TASK-17 E3: миграция 39 создаёт industry_aggregate на свежей базе;
    повторная сборка той же (версия, дата, мера, метод) обновляет строку,
    а не плодит дубли; NULL-тройка без причины из словаря B15 не пишется."""
    import os
    import shutil
    import sqlite3
    from rusterm.core.industry.aggregate import AggregateMeasure
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import RepoRegistry

    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    try:
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        from rusterm.store.repos import Instrument, Issuer
        repos.instrument.upsert_issuer(Issuer(
            "i1", "Issuer 1", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        peers = repos.peer_set
        peers.create_peer_set("sector", "industry", "tankers")
        peers.add_version("psv1", "sector", 1, "2025-01-01", None,
                          "manual", "v1", True, None, None)

        agg = sector_aggregate(
            "net_margin", [(f"in-{i}", float(i)) for i in range(10)],
            verified=True)
        assert repos.industry.store_aggregates(
            "psv1", "2025-06-30", [agg]) == 1
        rows = repos.industry.get_aggregates("psv1", "2025-06-30")
        assert len(rows) == 1
        assert rows[0][0] == "net_margin" and rows[0][4] == 10

        # повторная сборка: обновление, не дубль
        repos.industry.store_aggregates("psv1", "2025-06-30", [agg])
        assert len(repos.industry.get_aggregates("psv1", "2025-06-30")) == 1

        # NULL-тройка обязана нести причину из словаря
        null_agg = AggregateMeasure(concept="fcf",
                                    null_reason="peer_set_too_small")
        repos.industry.store_aggregates("psv1", "2025-06-30", [null_agg])
        rows = repos.industry.get_aggregates("psv1", "2025-06-30")
        assert len(rows) == 2
        by_concept = {r[0]: r for r in rows}
        assert by_concept["fcf"][6] == "peer_set_too_small"
        assert by_concept["fcf"][1:4] == (None, None, None)
        try:
            repos.industry.store_aggregates("psv1", "2025-06-30", [
                AggregateMeasure(concept="ebitda",
                                 null_reason="bogus_reason")])
            raised = False
        except ValueError:
            raised = True
        assert raised, "причина вне словаря B15 записалась"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
