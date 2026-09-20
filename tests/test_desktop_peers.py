"""TASK-C3: peer set и отрасль в слое данных — без Qt, без сети.

Peer set с правилом отбора словами (пороги импортируются из ядра,
не копируются), таблица отрасли с пометками отказов, box-plot и
радар «компания против медианы группы»: меры без данных исключаются,
а не занижают медиану, и число исключённых показано.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.desktop import data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)
from rusterm.tui import model as tui_model

MEMBERS = [f"US-E{i:02d}" for i in range(1, 9)]  # ровно порог агрегата
NET_MARGINS = [0.30, 0.26, 0.24, 0.22, 0.20, 0.18, 0.16, 0.12]


@pytest.fixture()
def env(tmp_path):
    """Отрасль energy из восьми участников с net_margin; выбранная
    компания E01 имеет ещё roe_incl_nci (в агрегаты не входит) и
    roe под отказом; CA-NOPE — компания без peer set."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)

    def add_company(iid, ticker, name, market):
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", name, market, None, None, "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{iid}", iid, "XNAS", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{iid}", ticker, "2000-01-01", None, None, None)

    for iid, value in zip(MEMBERS, NET_MARGINS):
        add_company(iid, iid[3:], f"Corp {iid[3:]}", "US")
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1,
                                       "2026-09-01", None, "none",
                                       "ready")
        repos.snapshot.insert_measure(
            f"m-nm-{iid}", f"s-{iid}", "issuer", f"i-{iid[3:]}",
            "net_margin", str(value), "ratio", "2024-01-01",
            "2024-12-31", "f", "v1", None, None)
        repos.snapshot.insert_measure(
            f"m-roe-{iid}", f"s-{iid}", "issuer", f"i-{iid[3:]}",
            "roe", None, "ratio", "2024-01-01", "2024-12-31", "f",
            "v1", "missing_prior_period", None)
        if iid == "US-E01":
            repos.snapshot.insert_measure(
                "m-rnci-US-E01", "s-US-E01", "issuer", "i-E01",
                "roe_incl_nci", "0.2581", "ratio", "2024-01-01",
                "2024-12-31", "f", "v1", None, None)
    add_company("CA-NOPE", "NOPE", "No Peer Corp", "CA")

    repos.peer_set.create_peer_set("energy", "industry", "energy")
    repos.peer_set.add_version("psv-energy", "energy", 1,
                               "2026-01-01", None, "manual", "v1",
                               True, None, None)
    for iid in MEMBERS:
        repos.peer_set.add_member("psv-energy", iid, None)
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    for iid in MEMBERS + ["CA-NOPE"]:
        repos.watchlist.add_member(vid, iid, None)
    yield repos, paths
    conn.close()


# ── C3.1: peer set на экране ─────────────────────────────────────────────

def test_peer_screen_names_rule_and_members(env):
    repos, _paths = env
    screen = data.peer_screen(repos, "US-E01")
    assert screen["has_peer_set"]
    assert screen["peer_set_id"] == "energy"
    assert "manual" in screen["rule"]
    assert "перцентиль от 5" in screen["rule"]
    assert "агрегат от 8" in screen["rule"]
    assert screen["verified"] is True
    tickers = [m["ticker"] for m in screen["members"]]
    assert len(tickers) == 8
    self_marked = [m for m in screen["members"] if m["is_self"]]
    assert len(self_marked) == 1
    assert self_marked[0]["instrument_id"] == "US-E01"


def test_peer_screen_without_set_says_words(env):
    repos, _paths = env
    screen = data.peer_screen(repos, "CA-NOPE")
    assert not screen["has_peer_set"]
    assert "нет peer set" in screen["message"]


# ── C3.2/C3.3: отрасль — таблица, диаграмма, радар против группы ────────

def _industry(repos):
    return tui_model.industry_rows(repos, "energy")


def test_industry_table_marks_refusals_not_silently(env):
    repos, _ = env
    rows = {r["concept"]: r for r in
            data.industry_table_rows(_industry(repos))}
    nm = rows["net_margin"]
    assert not nm["refused"]
    assert float(nm["median"]) == pytest.approx(0.21)
    assert nm["n"] == 8
    roe = rows["roe"]
    assert roe["refused"]
    assert roe["median"] == data.NO_DATA
    assert roe["mark"].startswith("отказ:"), "пометка, не тишина"


def test_industry_chart_box_and_refusals(env):
    repos, _ = env
    screen = _industry(repos)
    spec = data.industry_chart_spec(screen, "net_margin")
    assert spec["kind"] == "box"
    assert spec["n"] == 8
    refused = data.industry_chart_spec(screen, "roe")
    assert refused["kind"] == "message"
    assert "нет данных" in refused["text"]
    unknown = data.industry_chart_spec(screen, "not_a_measure")
    assert unknown["kind"] == "message"
    default = data.industry_chart_spec(screen)
    assert default["kind"] == "box", "по умолчанию — первая чистая мера"


def test_industry_chart_without_version_says_words(env):
    screen = {"sector": "energy", "version": None, "rows": [],
              "as_of": "2026-09-19"}
    spec = data.industry_chart_spec(screen)
    assert spec["kind"] == "message"
    assert "нет версии" in spec["text"]


def test_radar_vs_group_excludes_and_counts(env):
    repos, _ = env
    table = data.measure_table_rows(repos, "US-E01")
    spec = data.radar_vs_group_spec(table, _industry(repos))
    assert spec["kind"] == "radar_vs"
    axes = {a["concept"]: a for a in spec["axes"]}
    assert set(axes) == {"net_margin"}
    assert axes["net_margin"]["value"] == pytest.approx(0.30)
    assert axes["net_margin"]["median"] == pytest.approx(0.21)
    # roe: значения нет у компании — исключён и посчитан
    assert spec["excluded_company"] == 1
    # roe_incl_nci: у компании есть, в агрегатах группы нет — исключён
    assert spec["excluded_group"] == 1


def test_radar_vs_group_without_aggregates_says_words(env):
    repos, _ = env
    table = data.measure_table_rows(repos, "US-E01")
    screen = {"sector": "energy", "version": None, "rows": []}
    spec = data.radar_vs_group_spec(table, screen)
    assert spec["kind"] == "message"
    assert "нет данных" in spec["text"]
    assert spec["excluded_company"] == 0
