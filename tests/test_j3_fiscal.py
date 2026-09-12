"""ТЗ-22 J3: финансовый год не у всех кончается в декабре.

- период размечается фискальным годом по календарю эмитента;
- на дату as_of каждый участник вносит свой последний ЗАКРЫТЫЙ период;
- разрыв концов периодов участников больше порога — существующая
  причина period_mismatch, новой нет;
- декабрийские наборы ведут себя байт-в-байт как раньше (золотые —
  в общем наборе).

Миграция не нужна: issuer.fiscal_year_end существует с M1 (TEXT,
NULL); запись значения даёт `add --fye`. Отчёт фиксирует это
отклонение от буквы ТЗ («one migration») в пользу P2: выдумывать
миграцию ради миграции нельзя.
"""
from __future__ import annotations

import sqlite3

import pytest

import rusterm.cli as cli
from rusterm.core.fact import fiscal_year
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


def test_fiscal_year_labels_by_issuer_calendar():
    # декабрьский филяр: фискальный год = календарный
    assert fiscal_year("2024-12-31", "12-31") == "FY2024"
    assert fiscal_year("2023-12-31", "12-31") == "FY2023"
    # июньский (30.06): январский период — ещё FY2024, декабрьский — FY2025
    assert fiscal_year("2024-06-30", "06-30") == "FY2024"
    assert fiscal_year("2024-01-31", "06-30") == "FY2024"
    assert fiscal_year("2024-12-31", "06-30") == "FY2025"
    assert fiscal_year("2025-06-30", "06-30") == "FY2025"
    # календарь не задан или невалиден — метки нет, догадки тоже
    assert fiscal_year("2024-12-31", None) is None
    assert fiscal_year("2024-12-31", "не дата") is None
    assert fiscal_year("мусор", "06-30") is None


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return conn, repos


def _issuer_with_revenue(conn, repos, instrument_id, issuer_id, cur,
                         periods: list[tuple[str, str, str]],
                         fye: str | None = None):
    """Эмитент с фактами revenue/net_income на заданные концы периодов
    (значение = номер дня конца периода, чтобы различать)."""
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, fye, "us_gaap", cur))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    repos.snapshot.create_snapshot(f"s-{issuer_id}", instrument_id, 1,
                                   "2024-12-31", None, "none", "ready")
    repos.snapshot.add_block(f"s-{issuer_id}", "fundamentals", "ready",
                             None)
    for i, (start, end, kind) in enumerate(periods):
        for concept, value in (("revenue", str(100 + i)),
                               ("net_income", str(20 + i))):
            conn.execute(
                """INSERT INTO fact(fact_id, issuer_id, concept,
                   period_start, period_end, period_type, value, unit,
                   currency, basis, origin, source_ref, locator,
                   parser_version, status, ingested_at,
                   canonical_concept, source_kind)
                   VALUES (?, ?, ?, ?, ?, 'duration', ?, 'USD', ?,
                   'as_reported', 'extracted', 's', '{}',
                   'companyfacts.v1', 'ok', 0, ?, 'provider')""",
                (f"f-{issuer_id}-{kind}-{concept}", issuer_id, concept,
                 start, end, value, cur, concept))


def test_each_calendar_contributes_its_own_latest_closed_period(env):
    """June-филяр и Dec-филяр на одну дату: каждый вносит свой последний
    закрытый период; разрыв в перцентиле — period_mismatch."""
    conn, repos = env
    _issuer_with_revenue(
        conn, repos, "US-D", "id", "USD",
        [("2024-01-01", "2024-12-31", "fy24")], fye="12-31")
    _issuer_with_revenue(
        conn, repos, "AU-J", "ij", "USD",
        [("2023-07-01", "2024-06-30", "fy24")], fye="06-30")
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "mixed-calendars")
    peers.add_version("v1", "ps", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    for iid in ("US-D", "AU-J"):
        peers.add_member("v1", iid, None)
    # меры пиров: каждый — на свой последний закрытый период
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-us", snapshot_id="s-id", scope="issuer",
             scope_ref="id", concept="revenue", value="101", unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="revenue", method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-id-fy24-revenue", "peer_measure_id": None,
          "role": "input"}])
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-au", snapshot_id="s-ij", scope="issuer",
             scope_ref="ij", concept="revenue", value="102", unit="USD",
             period_start="2023-07-01", period_end="2024-06-30",
             formula_id="revenue", method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-ij-fy24-revenue", "peer_measure_id": None,
          "role": "input"}])
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    builder.build("US-D", "id", "2025-01-15", peer_set_version="v1",
                  peer_measures=[("US-D", "m-us", "revenue", "101", True),
                                 ("AU-J", "m-au", "revenue", "102", True)],
                  peer_members_previous=[],
                  peer_members_current=["US-D", "AU-J"])
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    percentile = [m for m in rows if m[3] == "percentile"]
    assert percentile
    # разрыв концов 184 дня больше порога — отказ по имени, не число
    assert all(m[10] == "period_mismatch" for m in percentile)
    assert all(m[4] is None for m in percentile)


def test_same_calendar_computes_without_reason(env):
    conn, repos = env
    _issuer_with_revenue(
        conn, repos, "US-D", "id", "USD",
        [("2024-01-01", "2024-12-31", "fy24")], fye="12-31")
    _issuer_with_revenue(
        conn, repos, "US-E", "ie", "USD",
        [("2024-01-01", "2024-12-31", "fy24")], fye="12-31")
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "dec-only")
    peers.add_version("v1", "ps", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    for iid in ("US-D", "US-E"):
        peers.add_member("v1", iid, None)
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-us", snapshot_id="s-id", scope="issuer",
             scope_ref="id", concept="revenue", value="101", unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="revenue", method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-id-fy24-revenue", "peer_measure_id": None,
          "role": "input"}])
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-e", snapshot_id="s-ie", scope="issuer",
             scope_ref="ie", concept="revenue", value="101", unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="revenue", method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-ie-fy24-revenue", "peer_measure_id": None,
          "role": "input"}])
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    builder.build("US-D", "id", "2025-01-15", peer_set_version="v1",
                  peer_measures=[("US-D", "m-us", "revenue", "101", True),
                                 ("US-E", "m-e", "revenue", "101", True)],
                  peer_members_previous=[],
                  peer_members_current=["US-D", "US-E"])
    # два пира — меньше порога 5: перцентильной строки нет вообще,
    # но и отказа period_mismatch нет (поведение прежнее)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    assert not [m for m in rows if m[3] == "percentile"]


def test_facts_after_as_of_are_not_closed_yet(env):
    """as_of выбирает последний закрытый период: факт с концом позже
    as_of в входы не попадает, даже если он новее."""
    conn, repos = env
    _issuer_with_revenue(
        conn, repos, "US-D", "id", "USD",
        [("2024-01-01", "2024-12-31", "fy24"),
         ("2025-01-01", "2025-06-30", "h1fy25")], fye="12-31")
    builder = SnapshotBuilder(repos.snapshot, peers := repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("US-D", "id", "2025-01-15")
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    net_margin = next(m for m in rows if m[3] == "net_margin")
    assert net_margin[4] is not None
    assert net_margin[7] == "2024-12-31", "h1fy25 ещё не закрыт на дату"
    # на более позднюю дату тот же конвейер берёт уже полугодие
    builder.build("US-D", "id", "2025-07-15")
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    net_margin = next(m for m in rows if m[3] == "net_margin")
    assert net_margin[7] == "2025-06-30"


def test_add_records_fiscal_year_end(tmp_path, monkeypatch, capsys):
    import os
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test j3.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    assert cli.main(["--root", str(root), "add", "--ticker", "BHP",
                     "--market", "AU", "--cik", "8", "--name",
                     "BHP GROUP", "--fye", "06-30"]) == 0
    conn = sqlite3.connect(str(root / "rusterm.db"))
    try:
        fye = conn.execute(
            "SELECT fiscal_year_end FROM issuer WHERE issuer_id='cik-8'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert fye == "06-30"

