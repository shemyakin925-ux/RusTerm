"""ТЗ-97 Q8: окно периодов отраслевого сравнения — 2 года (решение
пользователя 24.09, заменяет ТЗ-22 J3 для отрасли).

Правило до правки: концы периодов участников расходятся больше чем на
`_PERIOD_GAP_DAYS = 100` — и весь сектор получал `period_mismatch`.
Одна бумага с другим финансовым годом (Vodafone — март, BHP — июнь)
отменяла агрегат и перцентили всего набора.

После: разрыв до 730 дней считается; участник, чей последний период
старше самого свежего больше чем на 730 дней, исключается с пометкой,
остальные считаются; исключение опустило набор ниже порога — прежний
честный отказ `peer_set_too_small` с перечнем исключённых. Видимость
обязательна: диапазон периодов и исключённые с их концом периода — в
`rusterm industry` и на экране «Отрасль».

Новых причин нет (`rusterm/reasons.py` закрыт): в этих двух местах
`period_mismatch` больше не выдаётся. Схемы тоже не меняются: агрегаты
считаются на месте, диапазон перцентиля живёт в его же строке, пометка
исключённого — в роли строки lineage.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pytest

from rusterm.core.industry.aggregate import build_sector_aggregates
from rusterm.core.peers import AGGREGATE_MIN_PEERS, PERCENTILE_MIN_PEERS
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry)

# дата сборки: все снапшоты набора не позже неё
AS_OF = "2026-06-30"
# конец периода «прочих» участников
BASE = "2025-12-31"


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths), paths


def _members(n: int, odd: dict[int, str] | None = None,
             prefix: str = "in") -> list:
    """n участников net_margin: у всех конец периода BASE, кроме odd.

    Значения — целые 1..n: квартили выходят точными числами, а ожидание
    «исключённый не попал в медиану» проверяется без возни с float.
    """
    odd = odd or {}
    return [(f"{prefix}-{k}", odd.get(k, BASE), float(k + 1))
            for k in range(n)]


def _member_rows(repos, members):
    for n, (iid, end, value) in enumerate(members):
        repos.instrument.upsert_issuer(Issuer(
            f"i-{iid}", f"Corp {n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{iid}", None, "common", "active", None))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, end, None,
                                       "none", "ready")
        repos.snapshot.add_block(f"s-{iid}", "fundamentals", "ready", None)
        repos.snapshot.insert_measure(
            measure_id=f"m-{iid}", snapshot_id=f"s-{iid}", scope="issuer",
            scope_ref=f"i-{iid}", concept="net_margin", value=repr(value),
            unit="ratio", period_start="2025-06-01", period_end=end,
            formula_id="net_margin", method_version="v1",
            null_reason=None, peer_set_version=None)


def _sector(repos, members, sector: str = "tankers") -> str:
    """Сектор net_margin из участников: подтверждённая версия набора и
    снапшоты с мерами на концах периодов."""
    peers = repos.peer_set
    peers.create_peer_set(sector, "industry", sector)
    peers.add_version(f"psv-{sector}", sector, 1, "2025-01-01", None,
                      "manual", "v1", True, None, None)
    for _n, (iid, _end, _value) in enumerate(members):
        peers.add_member(f"psv-{sector}", iid, None)
    _member_rows(repos, members)
    return sector


def _aggregate(repos, members, sector="tankers"):
    built = build_sector_aggregates(repos, _sector(repos, members, sector),
                                    AS_OF, ("net_margin",))
    assert built["outcome"] == "resolved"
    return built["aggregates"][0]


def test_five_month_gap_computes_and_the_row_names_the_range(env):
    """Зуб 1 (красен до правки): набор из 9, у in-8 конец периода на 5
    месяцев позже прочих — 151 день, т.е. больше прежних 100 и меньше
    новых 730. Агрегат считается, диапазон периодов в строке."""
    _conn, repos, _paths = env
    agg = _aggregate(repos, _members(9, odd={8: "2026-05-31"}))
    assert agg.null_reason is None, agg.null_reason
    assert agg.n == 9
    assert (agg.period_from, agg.period_to) == (BASE, "2026-05-31")
    # все девятеро вложились: медиана девяти значений 1..9
    assert agg.median == repr(5.0), agg.median


def test_three_year_old_member_is_excluded_with_a_mark(env):
    """Зуб 2: у in-8 последний период на 3 года старше — он исключён с
    пометкой, остальные посчитаны (порог 8 ровно выполнен)."""
    _conn, repos, _paths = env
    stale = "2022-12-31"
    agg = _aggregate(repos, _members(9, odd={8: stale}))
    assert agg.null_reason is None, agg.null_reason
    assert agg.excluded == {"in-8": stale}
    assert agg.reason_counts.get("period_out_of_window") == 1
    assert agg.n == AGGREGATE_MIN_PEERS == 8
    # диапазон считает только включённые: in-8 его не тянет
    assert (agg.period_from, agg.period_to) == (BASE, BASE)
    # число — по восьмерым включённым: in-8 (значение 9) выпало,
    # медиана [1..8] ровно между 4 и 5
    assert agg.median == repr(4.5), agg.median


def test_exclusion_below_threshold_names_the_excluded(env):
    """Зуб 3: исключение опускает набор ниже порога — прежний честный
    отказ `peer_set_too_small` с перечнем исключённых."""
    _conn, repos, _paths = env
    agg = _aggregate(repos, _members(9, odd={7: "2022-06-30",
                                             8: "2022-12-31"}))
    assert agg.null_reason == "peer_set_too_small"
    assert agg.n == 0
    assert set(agg.excluded) == {"in-7", "in-8"}
    assert agg.reason_counts.get("period_out_of_window") == 2


def test_window_edge_is_exactly_seven_hundred_thirty_days(env):
    """Граница окна названа числом: ровно 730 дней — внутри, 731 — уже
    нет. «Около двух лет» не годится: без зафиксированной границы один и
    тот же набор считается или исключается по воле сборщика."""
    _conn, repos, _paths = env
    newest = date.fromisoformat(BASE)
    edge = (newest - timedelta(days=730)).isoformat()
    over = (newest - timedelta(days=731)).isoformat()
    # два набора в одной базе: участники названы по сектору, иначе
    # instrument_id второго набора столкнётся с первым
    ok = _aggregate(repos, _members(9, odd={8: edge}, prefix="e"),
                    sector="edge")
    assert ok.excluded == {}
    bad = _aggregate(repos, _members(9, odd={8: over}, prefix="o"),
                     sector="over")
    assert bad.excluded == {"o-8": over}


def _percentile_build(repos, peers_spec):
    """Сборка снапшота с перцентилями: у компании есть свои факты,
    пиры — (instrument_id, period_end, net_margin)."""
    _issuer_with_facts(repos, "US-S", "i-s")
    peers = repos.peer_set
    peers.create_peer_set("ps", "industry", "mixed")
    peers.add_version("psv", "ps", 1, "2024-01-01", None, "manual", "v1",
                      True, None, None)
    peer_measures, member_ids = [], []
    for n, (iid, end, value) in enumerate(peers_spec):
        _issuer_with_facts(repos, iid, f"i-p{n}")
        peers.add_member("psv", iid, None)
        repos.snapshot.insert_measure(
            measure_id=f"pm-{n}", snapshot_id=f"s-p{n}", scope="issuer",
            scope_ref=f"i-p{n}", concept="net_margin", value=repr(value),
            unit="ratio", period_start="2024-01-01", period_end=end,
            formula_id="net_margin", method_version="v1",
            null_reason=None, peer_set_version=None)
        peer_measures.append((iid, f"pm-{n}", "net_margin", repr(value),
                              True))
        member_ids.append(iid)
    assert len(peers_spec) >= PERCENTILE_MIN_PEERS
    result = SnapshotBuilder(repos.snapshot, peers,
                             coverage_repo=repos.coverage).build(
        "US-S", "i-s", "2025-01-15", peer_set_version="psv",
        peer_measures=peer_measures, peer_members_previous=[],
        peer_members_current=["US-S"] + member_ids)
    return result, repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-S"))


def _issuer_with_facts(repos, instrument_id: str, issuer_id: str):
    """Эмитент с годовыми revenue/net_income: у сборки есть собственная
    net_margin, иначе перцентиль не с чем сравнивать."""
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, "12-31", "us_gaap",
        "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    sid = f"s-{issuer_id}"
    repos.snapshot.create_snapshot(sid, instrument_id, 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.add_block(sid, "fundamentals", "ready", None)
    for concept, value in (("revenue", "100"), ("net_income", "20")):
        repos.conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at,
               canonical_concept, source_kind)
               VALUES (?, ?, ?, '2024-01-01', '2024-12-31', 'duration',
               ?, 'USD', 'USD', 'as_reported', 'extracted', 's', '{}',
               'companyfacts.v1', 'ok', 0, ?, 'provider')""",
            (f"f-{issuer_id}-{concept}", issuer_id, concept, value,
             concept))


def test_percentile_gap_of_five_months_computes(env):
    """Зуб 4 (перцентили второго прохода): разрыв 184 день — ровно как
    в ТЗ-22 J3 (декабрьский и июньский календари). Раньше — отказ
    `period_mismatch` на весь набор; теперь перцентиль считается и несёт
    диапазон периодов."""
    _conn, repos, _paths = env
    result, rows = _percentile_build(repos, [
        ("US-D1", "2024-12-31", 1.0), ("US-D2", "2024-12-31", 2.0),
        ("US-D3", "2024-12-31", 3.0), ("US-D4", "2024-12-31", 4.0),
        ("AU-J1", "2024-06-30", 5.0), ("AU-J2", "2024-06-30", 6.0),
    ])
    pct = [m for m in rows if m[3] == "percentile"]
    assert pct, rows
    assert all(m[10] is None for m in pct), [m[10] for m in pct]
    assert all(m[4] is not None for m in pct)
    assert all((m[6], m[7]) == ("2024-06-30", "2024-12-31") for m in pct)
    assert result.excluded_period == []


def test_percentile_excludes_three_year_old_peer_with_a_mark(env):
    """Зуб 5: пир с периодом на 3 года старше исключается с пометкой,
    остальные пятеро считаются; исключённый назван в lineage меры.

    UK-V намеренно ниже собственной net_margin компании (0.1 против
    0.2): если бы он молча остался в наборе, доля была бы 1/5, а не 0.
    Так проверка держится на числе, а не на факте исключения.
    """
    _conn, repos, _paths = env
    result, rows = _percentile_build(repos, [
        ("US-D1", "2024-12-31", 1.0), ("US-D2", "2024-12-31", 2.0),
        ("US-D3", "2024-12-31", 3.0), ("US-D4", "2024-12-31", 4.0),
        ("US-D5", "2024-12-31", 5.0), ("UK-V", "2021-12-31", 0.1),
    ])
    assert result.excluded_period == ["UK-V"]
    pct = [m for m in rows if m[3] == "percentile"]
    assert pct and all(m[4] is not None for m in pct), rows
    # окно — по включённым: UK-V его не сдвигает
    assert all((m[6], m[7]) == ("2024-12-31", "2024-12-31") for m in pct)
    marks = repos.snapshot.lineage_roles(pct[0][0])
    assert any("UK-V" in r and "2021-12-31" in r for r in marks), marks
    # доля считается по пятерым включённым и собственным значением 0.2:
    # ни один из 1..5 не ниже 0.2, устаревший 0.5 в знаменатель не попал
    # (с ним доля была бы 1/5)
    assert pct[0][4] == repr(0.0), pct[0][4]


def test_industry_screen_shows_range_and_excluded(env):
    """Зуб 6 (видимость, экран «Отрасль» — он же у Qt-вкладки): строка
    несёт «периоды от … до …», исключённый назван со своим периодом."""
    from rusterm.tui.model import industry_rows, render_industry
    _conn, repos, _paths = env
    sector = _sector(repos, _members(9, odd={8: "2022-12-31"}))
    screen = industry_rows(repos, sector, AS_OF)
    body = "\n".join(render_industry(screen))
    assert f"периоды от {BASE} до {BASE}" in body, body
    assert "вне окна: in-8 (2022-12-31)" in body, body


def test_cli_industry_shows_range_and_excluded(env, monkeypatch, capsys):
    """Зуб 7 (видимость, `rusterm industry`): то же вслух в CLI —
    пользователь не обязан читать код, чтобы узнать, кто выпал."""
    import rusterm.cli as cli
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test q8.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    conn, repos, paths = env
    sector = _sector(repos, _members(9, odd={8: "2022-12-31"}))
    conn.close()
    assert cli.main(["--root", str(paths.root), "industry",
                     "--sector", sector, "--as-of", AS_OF]) == 0
    out = capsys.readouterr().out
    assert f"периоды от {BASE} до {BASE}" in out, out
    assert "вне окна: in-8 (2022-12-31)" in out, out


def test_qt_industry_tab_marks_range_and_excluded(env):
    """Зуб 8 (видимость, вкладка «Отрасль»): пометка живёт в той же
    строке, что читает Qt-таблица — и у посчитанной меры, и у отказа
    (набору, который после исключения стал меньше порога, тоже)."""
    from rusterm.desktop import data
    from rusterm.tui.model import industry_rows
    _conn, repos, _paths = env
    sector = _sector(repos, _members(9, odd={8: "2022-12-31"}))
    marks = {r["concept"]: r["mark"]
             for r in data.industry_table_rows(
                 industry_rows(repos, sector, AS_OF))}
    note = marks["net_margin"]
    assert f"периоды от {BASE} до {BASE}" in note, note
    assert "вне окна: in-8 (2022-12-31)" in note, note
    # отказ ниже порога — с тем же диапазоном и перечнем: пустая строка
    # без объяснения недопустима ни в каком состоянии меры. Row выбрана
    # по концепту: у прочих мер здесь нет ни одного вклада, им нечего
    # называть.
    below = _sector(repos, _members(9, odd={7: "2022-06-30",
                                            8: "2022-12-31"},
                                    prefix="t"), sector="below")
    refuse = {r["concept"]: r["mark"]
              for r in data.industry_table_rows(
                  industry_rows(repos, below, AS_OF))}["net_margin"]
    # ТЗ-111 U1: пометка отказа — фразой словаря причин
    assert refuse.startswith("отказ: слишком мало компаний в группе"), \
        refuse
    assert "периоды от" in refuse, refuse
    assert "t-7 (2022-06-30)" in refuse, refuse
