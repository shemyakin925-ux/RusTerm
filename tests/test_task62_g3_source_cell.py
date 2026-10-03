"""ТЗ-62 G3: строка источника — одна реализация, формы поверхностей.

source_cell(facts, shape=...) строит все формы; таблица выгрузки,
компактный экспорт и панель источника называют один и тот же документ
(хэш), один и тот же период. Подпись графика источника не называет —
форма без места для хэша, записано в docstring chart_caption.
"""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from rusterm.desktop import actions as desktop_actions
from rusterm.desktop import data as desktop_data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 SnapshotRepo)


@pytest.fixture()
def measured_catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-s1", "Corp S", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-S1", "i-s1", None, "common", "active", None))
    raw = repos.raw.put(b"saved response bytes", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
    repos.fact.insert_fact(
        "f-s1", "i-s1", None, "Revenues", "2024-01-01", "2024-12-31",
        "duration", "100", "USD", "USD", "as_reported", "extracted",
        raw.sha256, {"endpoint": "companyfacts", "kind": "10-K"},
        "t62-test")
    repos.snapshot.create_snapshot("s-s1", "US-S1", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-s1", "s-s1", "issuer", "i-s1", "revenues_total",
        "100", "USD", "2024-01-01", "2024-12-31", None, "t62-test",
        None, None)
    repos.snapshot.add_lineage("m-s1", "f-s1", None, "input")
    yield repos, paths
    conn.close()


def test_table_panel_caption_name_one_source(measured_catalog, tmp_path):
    repos, paths = measured_catalog
    table = desktop_data.measure_table_rows(repos, "US-S1")
    row = table["measures"][0]

    # лицо 1: колонка источника выгрузки (csv)
    csv_text = desktop_data.export_table_csv(repos, "US-S1")
    source_column = csv_text.rstrip("\n").splitlines()[2].split(",")[-1]
    # лицо 2: панель источника
    panel = desktop_data.source_panel_view(repos, paths, row)["text"]
    sha12 = str(repos.fact.get_fact("f-s1")["source_ref"])[:12]
    period = "2024-12-31"
    assert sha12 in source_column and period in source_column, (
        source_column, sha12, period)
    assert sha12 in panel, (panel, sha12)
    assert period in panel, (panel, period)
    # документ один: 12 знаков ячейки — префикс 16 знаков панели
    panel_sha = [word.strip("…") for line in panel.splitlines()
                 for word in line.split() if len(word.strip("…")) >= 16
                 and all(c in "0123456789abcdef" for c in word.strip("…"))]
    assert any(p.startswith(sha12) for p in panel_sha), (
        panel_sha, sha12)
    # лицо 3: компактная форма экспорта действий — тот же хэш и период
    facts = [repos.fact.get_fact("f-s1")]
    compact = desktop_actions._source_cell(facts)
    assert compact == f"provider:{sha12}@{period}", compact


def test_caption_documented_as_sourceless(measured_catalog, tmp_path):
    """Подпись графика принципиально не называет документ и хэш —
    форма без места для них; зафиксировано в docstring и поведением."""
    repos, _ = measured_catalog
    table = desktop_data.measure_table_rows(repos, "US-S1")
    caption = desktop_data.chart_caption(table, "revenues_total",
                                         "2024-12-31")
    fact = repos.fact.get_fact("f-s1")
    sha12 = str(fact["source_ref"])[:12]
    assert sha12 not in caption
    assert "хэш" in desktop_data.chart_caption.__doc__


def test_both_source_shapes_come_from_one_function(measured_catalog):
    repos, _ = measured_catalog
    facts = [repos.fact.get_fact("f-s1")]
    compact = desktop_data.source_cell(facts, shape="export")
    table = desktop_data.source_cell(facts, shape="table")
    # один документ, один период — разные формы одной строки
    assert compact.split("@")[0].split(":", 1)[1] \
        == table.split("#")[1].split(" ")[0]
    assert compact.split("@")[1] == table.split("#")[1].split(" ")[1]
    assert desktop_actions._source_cell(facts) == compact
