"""TASK-C8: качество данных видно глазом — покрытие мер из тех же
строк, что rusterm coverage, пометки устаревания порогом-константой
ядра, governance пятью цветами с расшифровкой из ядра.

Прогон на живом CNQ из переписи; слой данных без Qt, окно — offscreen.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.desktop import data as desktop_data
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RawRepo,
                                 RepoRegistry,
                                 persist_ingestion_results)

CNQ_PAYLOAD = (Path(__file__).resolve().parents[1] / "tests" / "data"
               / "edgar" / "companyfacts_m6_CNQ.json")


@pytest.fixture()
def cnq_env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    payload = CNQ_PAYLOAD.read_bytes()
    cik = json.loads(payload)["cik"]
    repos.instrument.upsert_issuer(Issuer(
        "i-CNQ", "Canadian Natural", "CA", str(cik), None,
        "ifrs-full", "CAD"))
    repos.instrument.upsert_instrument(Instrument(
        "in-CNQ", "i-CNQ", None, "common", "active", None))
    url = (f"https://data.sec.gov/api/xbrl/companyfacts/"
           f"CIK{cik:010d}.json")
    obj = RawRepo(paths, repos.conn).put(
        payload, provider="edgar", block="fundamentals", url=url)
    parsed = CompanyFactsParser().parse(
        payload, {"issuer_id": "i-CNQ", "source_ref": obj.sha256})
    fact_dicts = []
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        fact_dicts.append(fact)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("in-CNQ", "i-CNQ", "2026-09-09")
    yield repos, paths, conn
    conn.close()


# ── C8.1: покрытие мер ───────────────────────────────────────────────────

def test_measure_coverage_matches_snapshot_rows(cnq_env):
    repos, _paths, _conn = cnq_env
    coverage = desktop_data.measure_coverage(repos, "in-CNQ")
    sid = repos.snapshot.latest_snapshot_id("in-CNQ")
    measures = repos.snapshot.get_measures(sid)
    expected_green = sum(1 for m in measures if m[4] is not None)
    assert coverage["has_snapshot"] is True
    assert coverage["green"] == expected_green
    assert coverage["total"] == len(measures)
    for token, count in coverage["reasons"].items():
        assert count == sum(1 for m in measures
                            if m[4] is None
                            and (m[10] or "missing_data").split(":")[0]
                            == token)


def test_coverage_without_snapshot_is_honest(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-X", "X", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-X", "i-X", None, "common", "active", None))
    coverage = desktop_data.measure_coverage(repos, "US-X")
    assert coverage == {"has_snapshot": False, "green": 0, "total": 0,
                        "reasons": {}}
    conn.close()


# ── C8.2: устаревание порогом-константой ─────────────────────────────────

def test_staleness_mark_uses_core_constant():
    from rusterm.core.snapshot import _STALE_LOOKBACK_DAYS as threshold
    old = desktop_data.staleness_mark("2012-12-31", as_of="2026-09-20")
    assert "устаревшая" in old
    assert str(threshold) in old, "порог назван именем константы ядра"
    assert desktop_data.staleness_mark("2024-12-31",
                                       as_of="2026-09-20") == ""
    assert desktop_data.staleness_mark("", as_of="2026-09-20") == ""


def test_measure_table_rows_carry_stale_marks(cnq_env):
    repos, _paths, _conn = cnq_env
    table = desktop_data.measure_table_rows(repos, "in-CNQ")
    assert table["measures"], "ожидались строки мер"
    marked = [r for r in table["measures"] if r["stale_mark"]]
    for row in marked:
        assert "устаревшая" in row["stale_mark"]
        assert "порог" in row["stale_mark"]


# ── C8.3: governance пятью цветами, расшифровка из ядра ─────────────────

def test_governance_view_five_colors_without_folding():
    card = {"governance": [
        {"indicator": i, "color": color, "reason": reason,
         "lineage_ref": "doc#page=1", "method_version": "v1"}
        for i, (color, reason) in zip(
            ("independent_directors", "ceo_chair", "related_party",
             "insider_net", "auditor"),
            (("green", ""), ("yellow", ""), ("red", ""),
             ("gray", "manual_unverified"),
             ("gray", "not_collected")))]}
    view = desktop_data.governance_view(card)
    assert len(view["rows"]) == 5, "пять показателей без свёртки"
    assert [r["color"] for r in view["rows"]] == \
        ["green", "yellow", "red", "gray", "gray"]
    from rusterm.core.governance import GREY_REASONS
    by_name = {r["indicator"]: r for r in view["rows"]}
    assert by_name["insider_net"]["note"] == \
        GREY_REASONS["manual_unverified"]
    assert by_name["auditor"]["note"] == GREY_REASONS["not_collected"]
    assert by_name["independent_directors"]["note"] == ""


def test_window_quality_tab_shows_coverage_and_governance(cnq_env):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import (QApplication, QLabel, QTabWidget,
                                   QTableWidget, QTreeWidget)
    from rusterm.desktop import window as desktop_window

    QApplication.instance() or QApplication([])
    repos, paths, _conn = cnq_env
    repos.watchlist.create_watchlist("wl-c8", "c8", None, None)
    vid = repos.watchlist.new_version("wlv-c8", "wl-c8", 1, "seed",
                                      None)
    repos.watchlist.add_member(vid, "in-CNQ", None)
    window = desktop_window._build_window(repos, paths, "wl-c8")
    tabs = window.findChild(QTabWidget, "tabs")
    assert tabs.count() == 3
    tree = window.findChild(QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    label = window.findChild(QLabel, "coverage_label")
    assert "покрытие мер:" in label.text()
    assert " из " in label.text()
    gtable = window.findChild(QTableWidget, "governance_table")
    assert gtable.rowCount() == 5
    window.close()
