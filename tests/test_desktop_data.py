"""TASK-C1: слой данных десктопа — без Qt, без сети, без модели.

Проверяется то, чем окно отвечает пользователю: каталог не создаётся
(B35/B40), поиск и дерево отраслей согласованы, ячейка без значения —
слова «нет данных» (не пустота и не прочерк), диаграммы не выдумывают
точек, гвард цитат — тот же, что в CLI, и без ключа модели окно
говорит причину словами.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from rusterm.desktop import data
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RawRepo,
                                 RepoRegistry, persist_ingestion_results)
from rusterm.core.snapshot import SnapshotBuilder

EDGAR = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"


def _connect(paths):
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture()
def env(tmp_path):
    """Три компании, два сектора, снапшот с мерами: живой/нулевой."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    plan = [
        # (instrument_id, ticker, name, market, sector)
        ("US-AAA", "AAA", "Alpha Alpha", "US", "energy"),
        ("US-BBB", "BBB", "Beta Beta", "US", "energy"),
        ("CA-CNQ", "CNQ", "Canadian Natural", "CA", None),
    ]
    for iid, ticker, name, market, _sector in plan:
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", name, market, None, None, "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{ticker}", iid, "XNAS" if market == "US" else "XTSE",
            "USD" if market == "US" else "CAD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{ticker}", ticker, "2000-01-01", None, None, None)
    # peer set «energy»: AAA и BBB; CNQ остаётся без сектора — честная
    # группа «без отрасли», не выбрасывание
    repos.peer_set.create_peer_set("energy", "industry", "energy")
    repos.peer_set.add_version("psv-1", "energy", 1, "2026-01-01",
                               None, "manual", "v1", True, None, None)
    repos.peer_set.add_member("psv-1", "US-AAA", None)
    repos.peer_set.add_member("psv-1", "US-BBB", None)

    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    version_id = repos.watchlist.new_version("wlv-1", "wl-1", 1,
                                             "seed", None)
    for iid, _t, _n, _m, _s in plan:
        repos.watchlist.add_member(version_id, iid, None)

    # снапшот AAA: net_margin со значением, roe — отказ словарной
    # причиной; период 2024 — якорь годовых колонок
    repos.snapshot.create_snapshot("s-1", "US-AAA", 1, "2026-09-01",
                                   "psv-1", "verified", "ready")
    repos.snapshot.insert_measure(
        "m-nm", "s-1", "issuer", "i-AAA", "net_margin", "0.2043",
        "ratio", "2024-01-01", "2024-12-31", "f-net-margin", "v1",
        None, None)
    repos.snapshot.insert_measure(
        "m-roe", "s-1", "issuer", "i-AAA", "roe", None,
        "ratio", "2024-01-01", "2024-12-31", "f-roe", "v1",
        "missing_prior_period", None)
    repos.snapshot.insert_measure(
        "m-rnci", "s-1", "issuer", "i-AAA", "roe_incl_nci", "0.2581",
        "ratio", "2024-01-01", "2024-12-31", "f-nci", "v1",
        None, None)
    repos.snapshot.insert_measure(
        "m-rev", "s-1", "issuer", "i-AAA", "revenue", "416161000000",
        "USD", "2024-01-01", "2024-12-31", "f-rev", "v1",
        None, None)

    yield repos, paths
    conn.close()


@pytest.fixture()
def cnq(tmp_path):
    """CNQ из сохранённых companyfacts EDGAR — пара переписи ТЗ-49:
    roe отказа́ет, roe_incl_nci посчитается, офлайн."""
    paths = AppPaths.from_root(tmp_path / "cnq")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    payload = (EDGAR / "companyfacts_m6_CNQ.json").read_bytes()
    cik = json.loads(payload)["cik"]
    repos.instrument.upsert_issuer(Issuer(
        "i-CNQ", "Canadian Natural", "CA", str(cik), None,
        "ifrs-full", "CAD"))
    repos.instrument.upsert_instrument(Instrument(
        "in-CNQ", "i-CNQ", None, "common", "active", None))
    obj = RawRepo(paths, repos.conn).put(
        payload, provider="edgar", block="fundamentals",
        url=f"https://data.sec.gov/api/xbrl/companyfacts/"
            f"CIK{cik:010d}.json")
    parsed = CompanyFactsParser().parse(
        payload, {"issuer_id": "i-CNQ", "source_ref": obj.sha256})
    facts = []
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        facts.append(fact)
    persist_ingestion_results(repos.conn, facts, [])
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("in-CNQ", "i-CNQ", "2026-09-09")
    yield repos, paths
    conn.close()


# ── B35/B40: каталог не создаётся ────────────────────────────────────────

def test_open_readonly_does_not_create_missing_catalog(tmp_path):
    root = tmp_path / "nowhere"
    paths, conn = data.open_readonly(root)
    assert conn is None
    assert not root.exists(), "правило B35/B40: чтение не строит каталог"
    assert "rusterm init" in data.empty_base_message(paths)


def test_open_readonly_opens_existing_catalog(env):
    repos, paths = env
    paths2, conn = data.open_readonly(paths.root)
    assert conn is not None
    assert paths2.root == paths.root
    conn.close()


# ── C1.1: поиск и дерево отраслей ────────────────────────────────────────

def test_sidebar_companies_come_from_list_rows_with_names(env):
    repos, _paths = env
    companies = data.sidebar_companies(repos, "wl-1")
    by_ticker = {c["ticker"]: c for c in companies}
    assert set(by_ticker) == {"AAA", "BBB", "CNQ"}
    assert by_ticker["CNQ"]["name"] == "Canadian Natural"
    assert by_ticker["AAA"]["sector"] == "energy"
    assert by_ticker["CNQ"]["sector"] is None


def test_matches_query_by_ticker_and_name_case_insensitive():
    company = {"ticker": "CNQ", "name": "Canadian Natural"}
    assert data.matches_query(company, "cn")
    assert data.matches_query(company, "CNQ")
    assert data.matches_query(company, "natural")
    assert not data.matches_query(company, "zzz")
    assert data.matches_query(company, "")


def test_sector_tree_groups_and_keeps_sectorless(env):
    repos, _ = env
    companies = data.sidebar_companies(repos, "wl-1")
    tree = data.sector_tree(companies)
    sectors = [node["sector"] for node in tree]
    assert sectors == ["energy", data.NO_SECTOR]
    energy = tree[0]["companies"]
    assert [c["ticker"] for c in energy] == ["AAA", "BBB"]


def test_search_and_tree_coherence(env):
    repos, _ = env
    companies = data.sidebar_companies(repos, "wl-1")
    tree = data.sector_tree(companies, "cnq")
    # при непустом поиске раскрыты отрасли с совпадениями
    assert data.expanded_sectors(tree, "cnq") == {data.NO_SECTOR}
    # совпадения только CNQ: энергия скрыта, не «пустая раскрытая»
    assert [c["ticker"] for node in tree
            for c in node["companies"]] == ["CNQ"]
    # поиск пуст — раскрыты только закреплённые
    full = data.sector_tree(companies)
    assert data.expanded_sectors(full, "") == set()
    assert data.expanded_sectors(full, "", {"energy"}) == {"energy"}


# ── C1.2: таблица «сейчас плюс годы истории» ─────────────────────────────

def test_measure_table_no_data_by_words_in_every_column(env):
    repos, _ = env
    table = data.measure_table_rows(repos, "US-AAA")
    rows = {r["concept"]: r for r in table["measures"]}
    assert rows["roe"]["current"] == data.NO_DATA
    assert rows["roe"]["null_reason"] == "missing_prior_period"
    assert all(cell == data.NO_DATA
               for cell in rows["roe"]["years"].values())
    assert rows["net_margin"]["current"] == "0.2043"
    assert len(table["years"]) >= data.MIN_YEAR_COLUMNS
    assert table["years"][0] == "2024"


def test_history_returns_snapshotted_years(env):
    """ТЗ-72 Д1: история мер по годам считается из сохранённых
    снапшотов — не пустая заглушка."""
    repos, _ = env
    history = data.measure_history(repos, "US-AAA")
    assert isinstance(history, dict)
    # env fixture имеет факты и снапшот — история должна быть непустой
    assert len(history) > 0, "история мер пуста при наличии снапшотов"


@pytest.fixture()
def history_env(tmp_path):
    """ТЗ-75 V1: у одной бумаги снапшоты за прошлые годы — as_of
    2024 и 2023, у net_margin в каждом своё значение."""
    paths = AppPaths.from_root(tmp_path / "hist")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-AAA", "US-AAA", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-AAA", "AAA", "2000-01-01", None, None, None)
    repos.snapshot.create_snapshot("s-2023", "US-AAA", 1, "2023-06-30",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-2023", "s-2023", "issuer", "i-AAA", "net_margin", "0.226",
        "ratio", "2023-01-01", "2023-12-31", "f-2", "v1", None, None)
    repos.snapshot.create_snapshot("s-2024", "US-AAA", 2, "2024-06-30",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-2024", "s-2024", "issuer", "i-AAA", "net_margin", "0.2043",
        "ratio", "2024-01-01", "2024-12-31", "f-1", "v1", None, None)
    yield repos, paths
    conn.close()


def test_history_cells_carry_snapshotted_values(history_env):
    """ТЗ-75 V1: содержимое таблицы, а не форма словаря — у меры есть
    значение за год N, и это же значение стоит в ячейке года N."""
    repos, _ = history_env
    table = data.measure_table_rows(repos, "US-AAA")
    rows = {r["concept"]: r for r in table["measures"]}
    assert rows["net_margin"]["years"]["2024"] == "0.2043"
    assert rows["net_margin"]["years"]["2023"] == "0.226"
    assert rows["net_margin"]["years"]["2022"] == data.NO_DATA


def test_history_year_is_the_measure_period(env):
    """ТЗ-76 W3: снапшот собран в 2026 (as_of 2026-09-01), а мера за
    период 2024 — значение стоит в колонке 2024, год прогона колонкой
    не становится."""
    repos, _ = env
    table = data.measure_table_rows(repos, "US-AAA")
    rows = {r["concept"]: r for r in table["measures"]}
    assert rows["net_margin"]["years"]["2024"] == "0.2043"
    history = data.measure_history(repos, "US-AAA")
    assert "2024" in history and "2026" not in history


@pytest.fixture()
def same_run_env(tmp_path):
    """ТЗ-76 W3: два снапшота одного прогона (оба as_of 2026-09-15),
    меры за разными отчётными периодами — живая база AAPL выглядит
    именно так, и вся история в ней стоит в одной колонке 2026."""
    paths = AppPaths.from_root(tmp_path / "same-run")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-AAA", "US-AAA", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-AAA", "AAA", "2000-01-01", None, None, None)
    repos.snapshot.create_snapshot("s-run-1", "US-AAA", 1, "2026-09-15",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-fy24", "s-run-1", "issuer", "i-AAA", "net_margin", "0.226",
        "ratio", "2024-01-01", "2024-12-31", "f-1", "v1", None, None)
    repos.snapshot.create_snapshot("s-run-2", "US-AAA", 2, "2026-09-15",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-fy25", "s-run-2", "issuer", "i-AAA", "net_margin", "0.2043",
        "ratio", "2025-01-01", "2025-12-31", "f-1", "v1", None, None)
    yield repos, paths
    conn.close()


def test_one_run_two_periods_does_not_collapse_into_one_column(
        same_run_env):
    """ТЗ-76 W3: база, пересобранная одним прогоном, не обязана
    схлопывать историю в колонку года запуска — периоды разные, значит
    и колонки разные."""
    repos, _ = same_run_env
    table = data.measure_table_rows(repos, "US-AAA")
    rows = {r["concept"]: r for r in table["measures"]}
    assert table["years"][:2] == ["2025", "2024"]
    assert rows["net_margin"]["years"]["2025"] == "0.2043"
    assert rows["net_margin"]["years"]["2024"] == "0.226"


@pytest.fixture()
def no_period_env(tmp_path):
    """ТЗ-76 W3: у net_margin периода нет вовсе (пустые period_*), у
    revenue он есть и якорит колонки 2026-м годом."""
    paths = AppPaths.from_root(tmp_path / "no-period")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-AAA", "US-AAA", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-AAA", "AAA", "2000-01-01", None, None, None)
    repos.snapshot.create_snapshot("s-np", "US-AAA", 1, "2026-09-15",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-rev-np", "s-np", "issuer", "i-AAA", "revenue", "100",
        "USD", "2026-01-01", "2026-12-31", "f-rev", "v1", None, None)
    repos.snapshot.insert_measure(
        "m-nm-np", "s-np", "issuer", "i-AAA", "net_margin", "0.2",
        "ratio", "", "", "f-1", "v1", None, None)
    yield repos, paths
    conn.close()


def test_run_year_fallback_shows_in_the_cell(no_period_env):
    """ТЗ-76 W3: фолбэк на as_of разрешён, только когда он виден —
    ячейка без периода помечена как отнесённая к году прогона, а
    ячейка с периодом пометки не несёт."""
    repos, _ = no_period_env
    table = data.measure_table_rows(repos, "US-AAA")
    rows = {r["concept"]: r for r in table["measures"]}
    assert rows["net_margin"]["years"]["2026"] == "0.2" + data.RUN_YEAR_MARK
    assert rows["revenue"]["years"]["2026"] == "100"
    basis = data.measure_history_basis(repos, "US-AAA")
    assert basis["2026"]["net_margin"] == "run_year"
    assert basis["2026"]["revenue"] == "period"


def test_run_year_mark_does_not_steal_the_chart_point(no_period_env):
    """ТЗ-76 W3: пометка — аннотация отображения, а не ещё один отказ:
    клетка «0.2 · год прогона» остаётся точкой линии, а не разрывом."""
    repos, _ = no_period_env
    table = data.measure_table_rows(repos, "US-AAA")
    spec = data.chart_spec("line", table, None, "net_margin")
    assert spec["kind"] == "line"
    assert spec["values"] == [0.2, None, None, None]


@pytest.fixture()
def stale_env(tmp_path):
    """ТЗ-75 V2 (Д4): у меры без значения 25 устаревших входов и один
    свежий якорь — стена строк «устаревший …» в панели источника."""
    paths = AppPaths.from_root(tmp_path / "stale")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-s9", "Corp Nine", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-S9", "i-s9", None, "common", "active", None))
    repos.snapshot.create_snapshot("s-s9", "US-S9", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-s9", "s-s9", "issuer", "i-s9", "net_margin", None,
        "ratio", "2024-01-01", "2024-12-31", None, "v1",
        "missing_prior_period", None)
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
    # свежий якорь и 25 устаревших фактов выручки: входы net_margin
    repos.fact.insert_fact(
        "f-fresh", "i-s9", None, "Revenues", "2024-01-01", "2024-12-31",
        "duration", "100", "USD", "USD", "as_reported", "extracted",
        raw.sha256, {"endpoint": "companyfacts", "kind": "10-K"},
        "t75-test", canonical_concept="revenue")
    for i in range(25):
        repos.fact.insert_fact(
            f"f-stale-{i}", "i-s9", None, "Revenues", "2009-01-01",
            "2009-12-31", "duration", f"{100 + i}", "USD", "USD",
            "as_reported", "extracted", raw.sha256,
            {"endpoint": "companyfacts", "kind": "10-K"},
            "t75-test", canonical_concept="revenue")
    yield repos, paths
    conn.close()


def test_source_panel_collapses_stale_inputs(stale_env):
    """ТЗ-75 V2 (Д4): главное — сначала (значение, документ, хэш,
    период), устаревшие входы — одна строка с числом; полный перечень
    только по требованию."""
    repos, paths = stale_env
    row = next(r for r in
               data.measure_table_rows(repos, "US-S9")["measures"]
               if r["concept"] == "net_margin")
    view = data.source_panel_view(repos, paths, row)
    lines = view["text"].splitlines()
    assert len(lines) <= 12, "стена строк вернулась"
    assert "значение: нет данных" in lines
    collapsed = [l for l in lines if l.startswith("устаревших входов")]
    assert collapsed == [
        "устаревших входов: 25, самый свежий 2009-12-31"]
    assert "устаревший (последний" not in view["text"]
    assert view["stale_count"] == 25
    detail = data.source_panel_view(
        repos, paths, row, stale_detail=True)
    per_entry = [l for l in detail["text"].splitlines()
                 if "устаревший (последний" in l]
    assert len(per_entry) == 25
    assert "устаревших входов:" not in detail["text"]


def test_no_history_no_year_columns_and_command_offered(env):
    """ТЗ-75 V1, правило ТЗ-72 Д1: истории нет ни у одной меры —
    годовые колонки не рисуются, окно предлагает посчитать ряд одним
    действием, исполнимой строкой с подстановкой."""
    repos, _ = env
    table = data.measure_table_rows(repos, "US-BBB")
    assert table["years"] == [], "пустая колонка запрещена"
    assert all(r["years"] == {} for r in table["measures"])
    assert "rusterm snapshot --instrument US-BBB" in table["suggestion"]


def test_census_pair_cnq_roe_refuses_roe_incl_nci_counts(cnq):
    """Пара из переписи: roe — «нет данных» во всех колонках,
    roe_incl_nci — значение; оба из одной карточки."""
    repos, _ = cnq
    table = data.measure_table_rows(repos, "in-CNQ")
    rows = {r["concept"]: r for r in table["measures"]}
    roe = rows["roe"]
    assert roe["current"] == data.NO_DATA
    assert all(cell == data.NO_DATA for cell in roe["years"].values())
    assert roe["null_reason"], "причина отказа — из словаря"
    value = rows["roe_incl_nci"]["current"]
    assert value != data.NO_DATA
    float(value)  # значение — число, не выдумка и не прочерк


# ── C1.3: спецификации диаграмм ─────────────────────────────────────────

def test_candles_refuse_honestly_no_fake_ohlc():
    spec = data.chart_spec("candles", {"measures": [], "years": []},
                           None)
    assert spec["kind"] == "message"
    assert "close" in spec["text"]


def test_line_spec_gap_is_none_not_zero():
    table = {"years": ["2024", "2023", "2022", "2021"],
             "measures": [{
                 "concept": "net_margin", "current": "0.2",
                 "has_value": True, "unit": "ratio",
                 "years": {"2024": "0.2043", "2023": data.NO_DATA,
                           "2022": "0.226", "2021": "0.3011"}}]}
    spec = data.chart_spec("line", table, None, "net_margin")
    assert spec["kind"] == "line"
    assert spec["values"] == [0.2043, None, 0.226, 0.3011]


def test_line_spec_without_history_says_no_data(env):
    """Мера без истории (в `env` у roe один отказанный снапшот) —
    диаграмма говорит словами, а не рисует пустую линию. net_margin с
    ТЗ-76 W3 историю имеет, поэтому пример берётся с roe."""
    repos, _ = env
    table = data.measure_table_rows(repos, "US-AAA")
    spec = data.chart_spec("line", table, None, "roe")
    assert spec == {"kind": "message", "text": data.NO_DATA,
                    "concept": "roe"}


def test_box_spec_from_industry_quartiles():
    table = {"measures": [{"concept": "net_margin", "current": "0.2",
                           "has_value": True, "unit": "ratio",
                           "years": {}}]}
    screen = {"sector": "energy", "version": 3, "rows": [
        {"concept": "net_margin", "null_reason": None, "n": 5,
         "p25": 0.1, "median": 0.2, "p75": 0.3}]}
    spec = data.chart_spec("box", table, screen, "net_margin")
    assert spec["kind"] == "box"
    assert (spec["p25"], spec["median"], spec["p75"]) == (0.1, 0.2, 0.3)
    assert spec["n"] == 5


def test_box_spec_without_sector_version_refuses(env):
    repos, _ = env
    table = data.measure_table_rows(repos, "US-AAA")
    screen = {"sector": "mining", "version": None, "rows": []}
    spec = data.chart_spec("box", table, screen, "net_margin")
    assert spec["kind"] == "message"
    assert "нет данных" in spec["text"]


def test_radar_only_ratio_measures_with_values(env):
    repos, _ = env
    table = data.measure_table_rows(repos, "US-AAA")
    spec = data.chart_spec("radar", table, None)
    assert spec["kind"] == "radar"
    concepts = [axis["concept"] for axis in spec["axes"]]
    assert "net_margin" in concepts and "roe_incl_nci" in concepts
    assert "roe" not in concepts, "мера без значения не рисуется"
    assert "revenue" not in concepts, "абсолютная мера — не ось радара"


# ── C1.4: разговор ──────────────────────────────────────────────────────

def test_chat_unavailable_reason_without_key_is_words():
    from rusterm.core.llm import make_chat_client
    client = make_chat_client(environ={})
    reason = data.chat_unavailable_reason(client)
    assert reason, "без ключа — причина словами, не молчание"


def test_guard_on_recorded_answer_same_as_cli():
    """Гвард тот же, что в CLI: непокрытое число бракует ответ."""
    from rusterm.core.chat import ChatSession
    allowed = ["{\"value\": 0.1912}"]
    cited = ChatSession.guard_answer("нетто-маржа 0.1912", allowed)
    assert cited == ["0.1912"]
    uncited = ChatSession.guard_answer("нетто-маржа 0.9999", allowed)
    assert uncited is None


def test_header_info_schema_and_requests(env):
    repos, _ = env
    info = data.header_info(repos)
    assert info["schema_version"] >= 1
    assert info["requests_today"] == 0


def test_header_info_counts_only_today(env):
    import time
    repos, _ = env
    repos.metrics.record_sample(time.time(), "provider_requests_used",
                                "edgar", 3.0)
    repos.metrics.record_sample(time.time() - 7 * 24 * 3600,
                                "provider_requests_used", "edgar", 100.0)
    assert data.header_info(repos)["requests_today"] == 3


# ── ТЗ-75 S5: «источник почти ничего не даёт» — словами, не прочерки ────

@pytest.fixture()
def thin_env(tmp_path):
    """Бумага с 8 мерами карточки, из них значащая одна — тонкий
    источник, как Kaspi (4 факта) и Vale у живого пользователя."""
    paths = AppPaths.from_root(tmp_path / "thin")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-thin", "Thin Corp", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-THIN", "i-thin", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-thin", "US-THIN", "NASDAQ", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-thin", "THIN", "2000-01-01", None, None, None)
    repos.snapshot.create_snapshot("s-thin", "US-THIN", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-thin-ok", "s-thin", "issuer", "i-thin", "net_margin", "0.2",
        "ratio", "2024-01-01", "2024-12-31", "f-1", "v1", None, None)
    for i in range(7):
        repos.snapshot.insert_measure(
            f"m-thin-{i}", "s-thin", "issuer", "i-thin",
            f"concept_{i}", None, "ratio", "2024-01-01", "2024-12-31",
            None, "v1", f"missing_data: input_{i}", None)
    yield repos, paths
    conn.close()


def test_thin_source_summary_in_table_and_words(thin_env, env):
    repos, paths = thin_env
    table = data.measure_table_rows(repos, "US-THIN")
    summary = table["summary"]
    assert summary is not None, "тонкий источник не распознан"
    assert summary["valued"] == 1 and summary["total"] == 8
    assert summary["dominant_reason"] == "missing_data"
    line = table["summary_line"]
    assert "1 из 8" in line and "missing_data" in line
    # сытая карточка (3 значения из 4 мер) — сводки нет
    full = data.measure_table_rows(env[0], "US-AAA")
    assert full["summary"] is None and full["summary_line"] is None
