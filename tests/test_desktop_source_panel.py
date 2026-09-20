"""TASK-C6: панель источника целиком — документ, период входа, хэш,
путь к сырью, открытие сохранённого ответа, отказ словами.

Прогон на живом CNQ из переписи (tests/data/edgar/companyfacts_m6_CNQ):
raw кладётся в хранилище тем же RawRepo.put, снапшот строится тем же
SnapshotBuilder, что у ценза, — панель показывает ровно то, что отдаёт
source_panel модели, плюс путь к сырью из хранилища. CNQ roe под
отказом «missing_data: total_equity» — панель называет концепт по
имени. Оконный тест: offscreen, QDesktopServices заглушен.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid

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

DATA = (__file__.replace("\\", "/").split("/rusterm/")[0]
        + "/rusterm")  # не используется; путь к фикстуре ниже


def _fixture(name: str) -> str:
    from pathlib import Path
    return str(Path(__file__).resolve().parents[1] / "tests" / "data"
               / "edgar" / name)


@pytest.fixture()
def cnq_env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    payload = open(_fixture("companyfacts_m6_CNQ.json"), "rb").read()
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
    repos.watchlist.create_watchlist("wl-c6", "c6", None, None)
    vid = repos.watchlist.new_version("wlv-c6", "wl-c6", 1, "seed",
                                      None)
    repos.watchlist.add_member(vid, "in-CNQ", None)
    yield repos, paths, conn, obj.sha256
    conn.close()


def _measure_row(repos, concept):
    sid = repos.snapshot.latest_snapshot_id("in-CNQ")
    row = next(m for m in repos.snapshot.get_measures(sid)
               if m[3] == concept)
    return {"measure_id": row[0], "concept": row[3], "value": row[4],
            "unit": row[5], "null_reason": row[10], "measure_id_raw": row[0],
            "measure": {"measure_id": row[0], "concept": row[3],
                        "value": row[4], "unit": row[5],
                        "issuer_id": "i-CNQ"}}


# ── C6.1: панель по клику ────────────────────────────────────────────────

def test_panel_view_names_document_hash_unit_and_period(cnq_env):
    repos, paths, _conn, sha = cnq_env
    row = _measure_row(repos, "effective_tax")
    view = desktop_data.source_panel_view(repos, paths, row)
    assert "источник effective_tax" in view["text"]
    assert "единица: ratio" in view["text"]
    assert sha[:16] in view["text"]
    assert "сырье: " in view["text"]
    assert "2025-12-31" in view["text"] or "период входа" in view["text"]
    assert view["open_target"] and view["open_target"].endswith(sha)


def test_raw_location_exists_and_missing(cnq_env):
    repos, paths, _conn, sha = cnq_env
    hit = desktop_data.raw_object_location(paths, sha)
    assert hit["exists"] is True
    miss = desktop_data.raw_object_location(paths, "f" * 64)
    assert miss["exists"] is False
    assert "f" * 64 in miss["path"]


# ── C6.3: отказ объясняется здесь (CNQ roe) ─────────────────────────────

def test_refusal_panel_names_missing_concept(cnq_env):
    repos, paths, _conn, _sha = cnq_env
    row = _measure_row(repos, "roe")
    assert row["null_reason"] == "missing_data: total_equity"
    view = desktop_data.source_panel_view(repos, paths, row)
    assert "причина: missing_data: total_equity" in view["text"]
    assert "не подан: total_equity" in view["text"]
    assert "подстановки нет" in view["text"]


# ── C6.2: открыть сохранённый ответ ─────────────────────────────────────

def test_window_open_raw_button_opens_existing_file(cnq_env,
                                                    monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import (QApplication, QPushButton,
                                   QTableWidget, QTreeWidget)
    from rusterm.desktop import window as desktop_window

    QApplication.instance() or QApplication([])
    repos, paths, _conn, sha = cnq_env
    window = desktop_window._build_window(repos, paths, "wl-c6")
    tree = window.findChild(QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    table = window.findChild(QTableWidget, "table")
    valued = next(r for r in range(table.rowCount())
                  if table.item(r, 1) is not None
                  and table.item(r, 1).text() != "нет данных")
    table.cellClicked.emit(valued, 1)
    button = window.findChild(QPushButton, "open_raw_button")
    assert button is not None and button.isEnabled()

    opened = {}
    monkeypatch.setattr(
        desktop_window.QDesktopServices, "openUrl",
        staticmethod(lambda url: opened.setdefault("url", url)))
    button.click()
    assert opened["url"].toString().endswith(sha)
    window.close()
