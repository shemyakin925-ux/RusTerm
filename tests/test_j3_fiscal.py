"""ТЗ-22 J3: финансовый год не у всех кончается в декабре.

- период размечается фискальным годом по календарю эмитента;
- на дату as_of каждый участник вносит свой последний ЗАКРЫТЫЙ период;
- разрыв концов периодов в отраслевом сравнении больше окна — участник
  исключается с пометкой, а не отменяет расчёт (ТЗ-97 Q8: окно 730
  дней вместо прежних 100; новой причины нет, `period_mismatch`
  осталась за сверкой входов одной меры);
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
    закрытый период — и смешанный календарь сравнение не отменяет.

    ТЗ-97 Q8 (решение пользователя 24.09) передвинул окно отраслевого
    сравнения со 100 дней на 730: разрыв 184 дня (декабрьский против
    июньского) больше не `period_mismatch` на весь набор. Булавка
    прежняя («отказ по имени») проверяла меньшее: теперь строка
    считается, значение есть, а диапазон периодов назван прямо в строке
    — июньский конец не выровнен на декабрьский и не выброшен.
    """
    conn, repos = env
    # (instrument_id, issuer_id, старт, конец): два календаря, шести
    # пиров хватает на порог перцентиля (5)
    calendars = [("US-D", "id", "2024-01-01", "2024-12-31", "12-31"),
                 ("AU-J", "ij", "2023-07-01", "2024-06-30", "06-30"),
                 ("AU-K", "ik", "2023-07-01", "2024-06-30", "06-30"),
                 ("US-E", "ie", "2024-01-01", "2024-12-31", "12-31"),
                 ("US-F", "if", "2024-01-01", "2024-12-31", "12-31"),
                 ("US-G", "ig", "2024-01-01", "2024-12-31", "12-31")]
    for iid, issuer_id, _start, _end, fye in calendars:
        _issuer_with_revenue(
            conn, repos, iid, issuer_id, "USD",
            [("2024-01-01", "2024-12-31", "fy24")] if fye == "12-31"
            else [("2023-07-01", "2024-06-30", "fy24")], fye=fye)
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "mixed-calendars")
    peers.add_version("v1", "ps", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    peer_measures = []
    for n, (iid, issuer_id, start, end, _fye) in enumerate(calendars):
        peers.add_member("v1", iid, None)
        # мера пира — на его собственный последний закрытый период;
        # net_margin, а не revenue: перцентиль считается только когда у
        # самой компании есть посчитанное значение той же меры
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id=f"m-{n}", snapshot_id=f"s-{issuer_id}",
                 scope="issuer", scope_ref=issuer_id, concept="net_margin",
                 value=repr(round(0.1 + 0.01 * n, 4)), unit="ratio",
                 period_start=start, period_end=end,
                 formula_id="net_margin", method_version="v1",
                 null_reason=None, peer_set_version=None),
            [{"fact_id": f"f-{issuer_id}-fy24-revenue",
              "peer_measure_id": None, "role": "input"}])
        peer_measures.append((iid, f"m-{n}", "net_margin",
                              repr(round(0.1 + 0.01 * n, 4)), True))
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    builder.build("US-D", "id", "2025-01-15", peer_set_version="v1",
                  peer_measures=peer_measures, peer_members_previous=[],
                  peer_members_current=[c[0] for c in calendars])
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    percentile = [m for m in rows if m[3] == "percentile"]
    assert percentile
    assert all(m[10] is None for m in percentile), [m[10] for m in percentile]
    assert all(m[4] is not None for m in percentile)
    assert all((m[6], m[7]) == ("2024-06-30", "2024-12-31")
               for m in percentile), [(m[6], m[7]) for m in percentile]


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
    # ТЗ-97 Q10: на более позднюю дату полугодие в знаменатель само не
    # идёт — поток не имеет права быть смесью шести месяцев и года. Без
    # прошлогоднего полугодия берётся последний годовой, и это не тихо:
    # база периода и недостающее слагаемое названы в lineage.
    builder.build("US-D", "id", "2025-07-15")
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-D"))
    net_margin = next(m for m in rows if m[3] == "net_margin")
    assert net_margin[7] == "2024-12-31", net_margin
    marks = repos.snapshot.period_marks(net_margin[0])
    assert marks, net_margin
    assert any("2024-01-01…2024-12-31" in m for m in marks), marks
    assert any("ytd_prior" in m and "2024-06-30" in m for m in marks), marks


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

