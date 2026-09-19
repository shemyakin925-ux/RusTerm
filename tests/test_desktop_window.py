"""TASK-C1: окно десктопа на PySide6 — offscreen, без сети и модели.

Окно здесь не показывает себя пользователю: QApplication живёт на
платформе offscreen, проверяются реакции — живой поиск, согласование
поиска и дерева, сохранение раскрытости при выборе компании, слова
«нет данных» в ячейках, смена типа диаграммы без перезапуска окна,
пометка мер без данных и причина молчания модели словами. На машине
без PySide6 файл пропускается целиком (importorskip, ADR-0023 №4).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QComboBox, QLabel,  # noqa: E402
                               QLineEdit, QTableWidget, QTreeWidget)

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.desktop.charts import ChartArea  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    plan = [("US-AAA", "AAA", "Alpha Alpha", "US", "energy"),
            ("US-BBB", "BBB", "Beta Beta", "US", "energy"),
            ("CA-CNQ", "CNQ", "Canadian Natural", "CA", None)]
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
    yield repos, paths
    conn.close()


def _widget(window, cls, name):
    widget = window.findChild(cls, name)
    assert widget is not None, f"виджет {name} не найден"
    return widget


def test_window_on_missing_catalog_says_words_not_traceback(
        qapp, tmp_path):
    paths = AppPaths.from_root(tmp_path / "nowhere")
    window = desktop_window._build_window(None, paths, None)
    header = _widget(window, QLabel, "company_header")
    assert "rusterm init" in header.text()


def test_search_filters_live_and_counts(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    search = _widget(window, QLineEdit, "search")
    tree = _widget(window, QTreeWidget, "tree")
    counter = _widget(window, QLabel, "match_count")
    assert counter.text() == "компаний: 3"
    search.setText("cn")
    assert counter.text() == "совпадений: 1"
    top = tree.topLevelItemCount()
    assert top == 1, "сектор без совпадений скрыт поиском"
    search.setText("zzz")
    assert counter.text() == "совпадений: 0"
    assert tree.topLevelItemCount() == 0


def test_expansion_survives_selection_and_search(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    search = _widget(window, QLineEdit, "search")
    energy = tree.topLevelItem(0)
    energy.setExpanded(True)   # закрепили
    # выбор компании внутри раскрытой отрасли
    tree.setCurrentItem(energy.child(0))
    header = _widget(window, QLabel, "company_header")
    assert "AAA" in header.text()
    assert energy.isExpanded()
    # поиск перестроил дерево, поиск ушёл — раскрытость вернулась
    search.setText("beta")
    search.setText("")
    energy_again = tree.topLevelItem(0)
    assert energy_again.text(0).startswith("▾ energy")
    assert energy_again.isExpanded(), "состояние раскрытия пережило выбор"


def test_table_no_data_by_words_and_years(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    table = _widget(window, QTableWidget, "table")
    concepts = [table.item(row, 0).text()
                for row in range(table.rowCount())]
    assert "net_margin" in concepts and "roe" in concepts
    roe_row = concepts.index("roe")
    assert table.item(roe_row, 1).text() == desktop_data.NO_DATA
    for column in range(2, table.columnCount()):
        assert table.item(roe_row, column).text() == desktop_data.NO_DATA
    nm_row = concepts.index("net_margin")
    assert table.item(nm_row, 1).text() == "0.2043"


def test_cell_click_opens_source_panel_with_reason(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    table = _widget(window, QTableWidget, "table")
    concepts = [table.item(row, 0).text()
                for row in range(table.rowCount())]
    table.cellClicked.emit(concepts.index("roe"), 1)
    panel = _widget(window, QLabel, "source_panel")
    assert "причина: missing_prior_period" in panel.text()


def test_chart_kind_switches_without_restart(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    kind_box = _widget(window, QComboBox, "kind_box")
    chart = window.findChild(ChartArea, "chart_area")
    assert chart is not None
    # свечи честно отказывают: close-only, псевдо-OHLC не рисуется
    for index in range(kind_box.count()):
        if kind_box.itemData(index) == "candles":
            kind_box.setCurrentIndex(index)
    assert "close" in chart.current_text()
    # линия без истории — «нет данных», окно не перезапускалось
    for index in range(kind_box.count()):
        if kind_box.itemData(index) == "line":
            kind_box.setCurrentIndex(index)
    assert chart.current_text() == desktop_data.NO_DATA


def test_measure_without_data_marked_in_switcher(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))
    box = _widget(window, QComboBox, "measure_box")
    labels = [box.itemText(i) for i in range(box.count())]
    assert any("roe" in label and "нет данных" in label
               for label in labels)
    assert not any("net_margin" in label and "нет данных" in label
                   for label in labels)


def test_chat_without_key_speaks_reason_in_placeholder(qapp, env,
                                                       monkeypatch):
    repos, paths = env
    for name in ("RUSTERM_LLM_API_KEY", "RUSTERM_LLM_MODEL",
                 "RUSTERM_LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    window = desktop_window._build_window(repos, paths, "wl-1")
    question = _widget(window, QLineEdit, "question_line")
    assert "модель недоступна" in question.placeholderText()
    # ввод не молчит и не падает: спрашивает — получает причину словами
    question.setText("почему roe пустой?")
    question.returnPressed.emit()
    answer = _widget(window, QLabel, "answer_label")
    assert "модель недоступна" in answer.text()


def test_backend_reported_honestly(qapp):
    from rusterm.desktop import charts
    backend = charts.available_backend()
    assert backend in ("pyqtgraph", "qtcharts")
    area = charts.ChartArea()
    assert area.backend() == backend
