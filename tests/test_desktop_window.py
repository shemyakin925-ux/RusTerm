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
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QComboBox, QLabel,  # noqa: E402
                               QLineEdit, QPushButton, QTableWidget,
                               QTreeWidget)

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
    # демо-инструмент теми же дверями, что rusterm demo: только он
    # честно собирается синтетическим конвейером из окна (C2.1)
    from rusterm.cli import DEMO_INSTRUMENT, DEMO_ISSUER
    repos.instrument.upsert_issuer(Issuer(
        DEMO_ISSUER, "CLI Demo Corp (synthetic)", "US", None, None,
        "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        DEMO_INSTRUMENT, DEMO_ISSUER, None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        f"{DEMO_INSTRUMENT}-listing", DEMO_INSTRUMENT, "XNAS", "USD",
        1, None, None))
    repos.instrument.add_ticker_history(
        f"{DEMO_INSTRUMENT}-listing", "DEMO", "2020-01-01", None,
        None, None)
    repos.watchlist.add_member(version_id, DEMO_INSTRUMENT, None)
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
    assert counter.text() == "компаний: 4"
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


def test_company_without_snapshot_is_offered_one_action_series(qapp, env):
    """ТЗ-75 V1: у бумаги без снапшотов годовых колонок нет, а под
    таблицей — исполнимая строка «посчитать ряд одним действием»."""
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    energy = tree.topLevelItem(0)
    bbb = None
    for i in range(energy.childCount()):
        if "BBB" in energy.child(i).text(0):
            bbb = energy.child(i)
    assert bbb is not None, "BBB нет в дереве"
    tree.setCurrentItem(bbb)
    table = _widget(window, QTableWidget, "table")
    assert table.columnCount() == 2, "пустые годовые колонки запрещены"
    panel = _widget(window, QLabel, "source_panel")
    assert "rusterm snapshot --instrument US-BBB" in panel.text()


def test_watchlist_label_agrees_with_box(qapp, env):
    """ТЗ-75 V2 (Д2): список выбран в переключателе — подпись говорит
    про него, а не «списков нет»."""
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    box = _widget(window, QComboBox, "watchlist_box")
    label = _widget(window, QLabel, "watchlist_label")
    assert box.currentText(), "переключатель пуст при наличии списков"
    assert "main" in box.currentText()
    assert "списков нет" not in label.text()
    assert "v1" in label.text() and "бумаг" in label.text()


def test_watchlist_label_agrees_on_stale_id(qapp, env):
    """ТЗ-75 V2 (Д2): в окно передали id, которого нет в перечне, —
    переключатель показывает первый список, и подпись говорит про
    этот же список."""
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-gone")
    box = _widget(window, QComboBox, "watchlist_box")
    label = _widget(window, QLabel, "watchlist_label")
    assert box.currentIndex() >= 0
    assert "списков нет" not in label.text()


def test_watchlist_window_start_without_id_is_honest(qapp, env):
    """ТЗ-75 V2 (Д2): окно открыто без явного списка — переключатель
    и подпись говорят про один и тот же список, состав слева для него
    и загружен."""
    repos, paths = env
    window = desktop_window._build_window(repos, paths, None)
    box = _widget(window, QComboBox, "watchlist_box")
    label = _widget(window, QLabel, "watchlist_label")
    counter = _widget(window, QLabel, "match_count")
    assert box.count() > 0
    assert box.currentIndex() >= 0
    assert "списков нет" not in label.text()
    assert counter.text() == "компаний: 4"


def test_watchlist_label_says_none_when_truly_none(qapp, tmp_path):
    """ТЗ-75 V2 (Д2): списков действительно нет — подпись честная,
    переключатель пуст."""
    paths = AppPaths.from_root(tmp_path / "nolist")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    window = desktop_window._build_window(repos, paths, None)
    box = _widget(window, QComboBox, "watchlist_box")
    label = _widget(window, QLabel, "watchlist_label")
    assert box.count() == 0
    assert label.text() == "списков нет"
    conn.close()


def test_stale_inputs_collapse_and_expand_on_click(qapp, tmp_path):
    """ТЗ-75 V2 (Д4): в панели по умолчанию одна строка про устаревшие
    входы; кнопка раскрывает перечень, повторное нажатие сворачивает."""
    paths = AppPaths.from_root(tmp_path / "stalewin")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-s9", "Corp Nine", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-S9", "i-s9", None, "common", "active", None))
    repos.watchlist.create_watchlist("wl-9", "nine", None, None)
    version_id = repos.watchlist.new_version("wlv-9", "wl-9", 1,
                                             "seed", None)
    repos.watchlist.add_member(version_id, "US-S9", None)
    repos.snapshot.create_snapshot("s-s9", "US-S9", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-s9", "s-s9", "issuer", "i-s9", "net_margin", None,
        "ratio", "2024-01-01", "2024-12-31", None, "v1",
        "missing_prior_period", None)
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
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

    window = desktop_window._build_window(repos, paths, "wl-9")
    tree = _widget(window, QTreeWidget, "tree")
    target = None
    for top in range(tree.topLevelItemCount()):
        node = tree.topLevelItem(top)
        for child in range(node.childCount()):
            if "S9" in node.child(child).text(0):
                target = node.child(child)
    assert target is not None, "US-S9 нет в дереве"
    tree.setCurrentItem(target)
    table = _widget(window, QTableWidget, "table")
    concepts = [table.item(row, 0).text()
                for row in range(table.rowCount())]
    table.cellClicked.emit(concepts.index("net_margin"), 1)
    panel = _widget(window, QLabel, "source_panel")
    collapsed = [l for l in panel.text().splitlines()
                 if l.startswith("устаревших входов")]
    assert collapsed, panel.text()
    assert "устаревший (последний" not in panel.text()
    stale_button = window.findChild(QPushButton, "stale_button")
    assert stale_button is not None, "кнопка устаревших входов не найдена"
    # окно в тестах не показывается — проверяем isHidden, а не isVisible
    assert not stale_button.isHidden()
    stale_button.click()
    expanded = [l for l in panel.text().splitlines()
                if "устаревший (последний" in l]
    assert len(expanded) == 25, "перечень не раскрылся по кнопке"
    stale_button.click()
    assert "устаревший (последний" not in panel.text()
    conn.close()


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
    for index in range(kind_box.count()):
        if kind_box.itemData(index) == "line":
            kind_box.setCurrentIndex(index)
    # ТЗ-76 W3: net_margin за период 2024 — линия с точкой. До правки
    # год клетки был годом прогона (2026), колонка 2024 стояла пустой и
    # линия скатывалась в «нет данных».
    assert chart.current_text() == ""
    # та же линия для меры без истории вовсе — «нет данных»;
    # окно не перезапускалось между этими двумя состояниями
    measure_box = _widget(window, QComboBox, "measure_box")
    for index in range(measure_box.count()):
        if measure_box.itemData(index) == "roe":
            measure_box.setCurrentIndex(index)
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


# ── C2: кнопка сбора, прогресс, отмена, бюджет ──────────────────────────

def _collect_button(window):
    return _widget(window, desktop_window.QPushButton, "collect_button")


def _wait_for_collect(window, status, timeout_ms=20000):
    """Ждать итога сбора, НЕ голодая воркер: QTest.qWait-цикл в главном
    потоке не отдаёт GIL Python-потоку (замерено: воркер не завершается
    вообще), поэтому чередуем БЛОКИРУЮЩИЙ worker.wait(50) — GIL
    отпускается целиком — с processEvents, который доставляет
    накопленные сигналы. В живом окне этой проблемы нет: app.exec()
    блокируется по-настоящему (воркер завершается за сотые доли
    секунды — замер в REPORT-C2)."""
    import time
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    worker = window.findChild(QThread)
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        text = status.text()
        if text.startswith(("готово", "отменено", "сбор не удался")):
            return text
        if worker is not None:
            worker.wait(50)
        QApplication.processEvents()
    return status.text()


def test_header_shows_budget_numbers(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    status = _widget(window, QLabel, "status")
    assert "потолок 5000" in status.text()
    assert "запросов сегодня 0" in status.text()


def test_collect_refuses_non_demo_with_cli_words(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    tree.setCurrentItem(tree.topLevelItem(0).child(0))  # AAA: не демо
    button = _collect_button(window)
    assert button.isEnabled()
    button.click()
    status_line = _widget(window, QLabel, "collect_status")
    assert "rusterm ingest --source edgar" in status_line.text()
    cancel = _widget(window, desktop_window.QPushButton, "cancel_button")
    assert not cancel.isEnabled(), "отмена не могла быть запущена"


def test_collect_runs_pipeline_and_refreshes_window(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    sectorless = tree.topLevelItem(1)
    demo_item = None
    for i in range(sectorless.childCount()):
        if "DEMO" in sectorless.child(i).text(0):
            demo_item = sectorless.child(i)
    assert demo_item is not None, "демо-инструмент в дереве"
    tree.setCurrentItem(demo_item)
    button = _collect_button(window)
    button.click()
    status_line = _widget(window, QLabel, "collect_status")
    text = _wait_for_collect(window, status_line)
    assert text.startswith("готово:"), text
    assert "снапшот" in text
    # снапшот реально в базе; окно перечитало карточку и бюджет
    from rusterm.cli import DEMO_INSTRUMENT
    assert repos.snapshot.latest_snapshot_id(DEMO_INSTRUMENT)
    header = _widget(window, QLabel, "status")
    assert "потолок 5000" in header.text()
    cancel = _widget(window, desktop_window.QPushButton, "cancel_button")
    assert not cancel.isEnabled(), "по завершении отмена погашена"
    assert button.isEnabled(), "кнопка сбора вернулась"


def test_collect_cancel_button_wires_flag(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    tree = _widget(window, QTreeWidget, "tree")
    sectorless = tree.topLevelItem(1)
    demo_item = None
    for i in range(sectorless.childCount()):
        if "DEMO" in sectorless.child(i).text(0):
            demo_item = sectorless.child(i)
    tree.setCurrentItem(demo_item)
    button = _collect_button(window)
    cancel = _widget(window, desktop_window.QPushButton, "cancel_button")
    assert not cancel.isEnabled()
    button.click()
    assert cancel.isEnabled(), "на время сбора отмена доступна"
    cancel.click()  # флаг выставлен; итог придёт сигналом
    status_line = _widget(window, QLabel, "collect_status")
    text = _wait_for_collect(window, status_line)
    assert text.startswith(("отменено", "готово")), text


# ── C3: peer set и отрасль ──────────────────────────────────────────────

def _select(window, ticker):
    tree = _widget(window, QTreeWidget, "tree")
    for g in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(g)
        for i in range(group.childCount()):
            if group.child(i).text(0).startswith(ticker + " "):
                tree.setCurrentItem(group.child(i))
                return
    raise AssertionError(f"{ticker} нет в дереве")


def test_industry_tab_shows_peer_set_with_rule(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    peer_line = _widget(window, QLabel, "peer_line")
    assert "peer set energy" in peer_line.text()
    assert "правило: происхождение manual" in peer_line.text()
    members = _widget(window, QLabel, "members_line")
    assert "AAA" in members.text() and "BBB" in members.text()


def test_industry_tab_without_peer_set_says_words(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "DEMO")
    peer_line = _widget(window, QLabel, "peer_line")
    assert "нет peer set" in peer_line.text()


def test_industry_table_marks_refusals_and_sorts(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    table = _widget(window, QTableWidget, "industry_table")
    assert table.rowCount() > 0
    # отказ помечен словами в своей колонке, а не молча
    marks = [table.item(r, 5).text() for r in range(table.rowCount())]
    assert any(m.startswith("отказ:") for m in marks)
    assert all(m != "" or
               table.item(r, 1).text() != desktop_data.NO_DATA
               for r, m in enumerate(marks))
    # сортировка по любой мере: по имени меры туда-обратно
    table.sortItems(0)
    first_asc = table.item(0, 0).text()
    table.sortItems(0, __import__("PySide6.QtCore", fromlist=["Qt"])
                    .Qt.SortOrder.DescendingOrder)
    first_desc = table.item(0, 0).text()
    assert first_asc != first_desc
    assert first_desc == sorted(
        table.item(r, 0).text() for r in range(table.rowCount()))[-1]


def test_radar_excluded_counts_shown(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    excluded = _widget(window, QLabel, "excluded_label")
    assert "исключены" in excluded.text()
    radar = window.findChild(ChartArea, "radar_chart")
    assert radar is not None
    assert radar.current_text() != "", "без агрегатов радар говорит словами"


# ── ТЗ-75 S1: каждый элемент управления проверен нажатием ────────────────

def _second_watchlist(repos):
    repos.watchlist.create_watchlist("wl-2", "other", None, None)
    vid = repos.watchlist.new_version("wlv-2", "wl-2", 1, "seed", None)
    repos.watchlist.add_member(vid, "CA-CNQ", None)


def test_s1_watchlist_box_switch_reloads_members(qapp, env):
    repos, paths = env
    _second_watchlist(repos)
    window = desktop_window._build_window(repos, paths, "wl-1")
    box = _widget(window, QComboBox, "watchlist_box")
    counter = _widget(window, QLabel, "match_count")
    label = _widget(window, QLabel, "watchlist_label")
    assert counter.text() == "компаний: 4"
    box.setCurrentIndex(1)
    assert box.currentData() == "wl-2"
    assert counter.text() == "компаний: 1", "состав не перечитан"
    assert "1 бумаг" in label.text()


def _fresh_instrument(repos):
    repos.instrument.upsert_issuer(Issuer(
        "i-s1x", "Corp S1X", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-S1X", "i-s1x", None, "common", "active", None))
    # площадка из реестра рынков (NASDAQ), иначе резолвер тикера
    # не найдёт бумагу — venue_in_market("XNAS", "US") ложь
    repos.instrument.upsert_listing(Listing(
        "l-s1x", "US-S1X", "NASDAQ", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-s1x", "S1X", "2000-01-01", None, None, None)


def test_s1_watchlist_add_button_press_adds_paper(qapp, env, monkeypatch):
    repos, paths = env
    _fresh_instrument(repos)
    window = desktop_window._build_window(repos, paths, "wl-1")
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("S1X US", True)))
    _widget(window, QPushButton, "watchlist_add_button").click()
    counter = _widget(window, QLabel, "match_count")
    label = _widget(window, QLabel, "watchlist_label")
    assert counter.text() == "компаний: 5", "бумага не добавилась"
    assert "v2" in label.text(), "правка списка не создала версию"
    assert "5 бумаг" in label.text()


def test_s1_watchlist_remove_button_press_removes_selected(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "CNQ")
    counter = _widget(window, QLabel, "match_count")
    assert counter.text() == "компаний: 4"
    _widget(window, QPushButton, "watchlist_remove_button").click()
    assert counter.text() == "компаний: 3", "бумага не удалилась"


def test_s1_watchlist_clear_button_press_asks_and_clears(qapp, env,
                                                         monkeypatch):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    from PySide6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: asked.append(a) or
                     QMessageBox.StandardButton.Yes))
    _widget(window, QPushButton, "watchlist_clear_button").click()
    counter = _widget(window, QLabel, "match_count")
    label = _widget(window, QLabel, "watchlist_label")
    assert asked, "подтверждение не спрашивалось"
    assert counter.text() == "компаний: 0", "список не очищен"
    assert "0 бумаг" in label.text()


def test_s1_measure_switch_press_changes_chart(qapp, tmp_path):
    repos, paths = _history_window_env(qapp, tmp_path)
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    box = _widget(window, QComboBox, "measure_box")
    chart = window.findChild(ChartArea, "chart_area")
    idx_nm = next(i for i in range(box.count())
                  if box.itemData(i) == "net_margin")
    idx_roe = next(i for i in range(box.count())
                   if box.itemData(i) == "roe")
    box.setCurrentIndex(idx_nm)
    live = chart.current_text()
    box.setCurrentIndex(idx_roe)
    empty = chart.current_text()
    assert live == "", "мера с историей не рисует живую диаграмму"
    assert empty == desktop_data.NO_DATA, (
        "мера без значений не отвечает «нет данных»")


def _history_window_env(qapp, tmp_path):
    """База, где у net_margin заполнены годы 2024 и 2023 (ТЗ-75 V1)."""
    repos, paths = _minimal_base(tmp_path / "hist")
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    version_id = repos.watchlist.new_version("wlv-1", "wl-1", 1,
                                             "seed", None)
    repos.watchlist.add_member(version_id, "US-AAA", None)
    repos.snapshot.create_snapshot("s-2023", "US-AAA", 1, "2023-06-30",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-2023", "s-2023", "issuer", "i-AAA", "net_margin", "0.226",
        "ratio", "2023-01-01", "2023-12-31", "f-2", "v1", None, None)
    repos.snapshot.insert_measure(
        "m-roe-2023", "s-2023", "issuer", "i-AAA", "roe", None,
        "ratio", "2023-01-01", "2023-12-31", "f-3", "v1",
        "missing_prior_period", None)
    repos.snapshot.create_snapshot("s-2024", "US-AAA", 2, "2024-06-30",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-nm-2024", "s-2024", "issuer", "i-AAA", "net_margin", "0.2043",
        "ratio", "2024-01-01", "2024-12-31", "f-1", "v1", None, None)
    repos.snapshot.insert_measure(
        "m-roe-2024", "s-2024", "issuer", "i-AAA", "roe", None,
        "ratio", "2024-01-01", "2024-12-31", "f-4", "v1",
        "missing_prior_period", None)
    return repos, paths


def _minimal_base(root):
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
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
    return repos, paths


def test_s1_industry_measure_switch_changes_chart(qapp, env):
    repos, paths = env
    # AGGREGATE_MIN_PEERS = 8: отрасль собирается только от восьми
    # вкладчиков, иначе экран честно отвечает peer_set_too_small
    for n in range(1, 7):
        iid, tid = f"US-D{n}", f"D{n}"
        repos.instrument.upsert_issuer(Issuer(
            f"i-{tid}", f"Corp {tid}", "US", None, None,
            "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{tid}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{tid}", iid, "NASDAQ", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{tid}", tid, "2000-01-01", None, None, None)
        repos.peer_set.add_member("psv-1", iid, None)
        repos.watchlist.add_member("wlv-1", iid, None)
        repos.snapshot.create_snapshot(f"s-{tid}", iid, 1,
                                       "2026-09-01", "psv-1",
                                       "verified", "ready")
        repos.snapshot.insert_measure(
            f"m-nm-{tid}", f"s-{tid}", "issuer", f"i-{tid}",
            "net_margin", f"0.{10 + n}", "ratio",
            "2024-01-01", "2024-12-31", f"f-{tid}", "v1", None, None)
    repos.snapshot.create_snapshot("s-bbb", "US-BBB", 1, "2026-09-01",
                                   "psv-1", "verified", "ready")
    repos.snapshot.insert_measure(
        "m-nm-bbb", "s-bbb", "issuer", "i-BBB", "net_margin", "0.11",
        "ratio", "2024-01-01", "2024-12-31", "f-bbb", "v1", None, None)
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    box = _widget(window, QComboBox, "industry_measure_box")
    chart = window.findChild(ChartArea, "industry_chart")
    assert box.count() >= 2, "в отраслевом переключателе меньше двух мер"
    idx_nm = next(i for i in range(box.count())
                  if box.itemData(i) == "net_margin")
    idx_other = next(i for i in range(box.count())
                     if box.itemData(i) != "net_margin")
    box.setCurrentIndex(idx_nm)
    live = chart.current_text()
    box.setCurrentIndex(idx_other)
    refused = chart.current_text()
    assert live == "", "box-plot отрасли не нарисован при n=2"
    assert refused != live and "нет данных" in refused, (
        "мера вне агрегата не отказывает словами")


def test_s1_export_buttons_write_files(qapp, env, monkeypatch, tmp_path):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    from PySide6.QtWidgets import QFileDialog
    targets = {}

    def fake_save(_parent, _caption, _dir, filt):
        fmt = filt.lstrip("*")
        path = str(tmp_path / f"out.{fmt}")
        targets[fmt] = path
        return path, filt

    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(fake_save))
    _widget(window, QPushButton, "export_csv_button").click()
    _widget(window, QPushButton, "export_md_button").click()
    assert set(targets) == {".csv", ".md"}, targets
    csv_text = Path(targets[".csv"]).read_text(encoding="utf-8")
    md_text = Path(targets[".md"]).read_text(encoding="utf-8")
    assert "net_margin" in csv_text and "0.2043" in csv_text
    assert "net_margin" in md_text


def test_s1_save_png_button_writes_file(qapp, env, monkeypatch, tmp_path):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    from PySide6.QtWidgets import QFileDialog
    target = tmp_path / "chart.png"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "*.png")))
    _widget(window, QPushButton, "save_png_button").click()
    assert target.exists(), "png не записан"
    assert target.stat().st_size > 0


def test_s1_switch_root_press_cancel_words(qapp, env, monkeypatch,
                                           tmp_path):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    # каталог без данных + отказ в вопросе = ничего не создаётся
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: str(tmp_path / "nowhere")))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    status = _widget(window, QLabel, "status")
    before = status.text()
    _widget(window, QPushButton, "switch_root_button").click()
    assert "смена каталога отменена" in status.text()
    assert status.text() != before or before == ""
    assert (tmp_path / "nowhere").exists() is False, \
        "каталог создан без подтверждения"


def test_s1_chat_sessions_box_honest_empty(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    box = _widget(window, QComboBox, "chat_sessions_box")
    usage = _widget(window, QLabel, "llm_usage_label")
    before = usage.text()
    # двери list_sessions в store нет (Disputed REPORT-C7): переключатель
    # честно называет причину вместо пустоты
    assert box.count() == 1
    assert "ждёт двери list_sessions" in box.itemText(0)
    assert box.itemData(0) is None
    box.setCurrentIndex(0)
    assert usage.text() == before, "пустое переключение меняло счётчики"


def test_s1_tabs_switch_shows_industry(qapp, env):
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    _select(window, "AAA")
    from PySide6.QtWidgets import QTabWidget
    tabs = window.findChild(QTabWidget, "tabs")
    assert tabs is not None and tabs.count() >= 2
    tabs.setCurrentIndex(1)
    assert tabs.currentIndex() == 1
    peer_line = _widget(window, QLabel, "peer_line")
    assert "peer set energy" in peer_line.text()


def test_s2_add_unknown_paper_names_ready_command(qapp, env, monkeypatch):
    """ТЗ-75 S2: бумаги нет в базе — окно называет готовую команду
    rusterm add с подстановкой, а не отмахивается «иди в CLI»."""
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("ZZ US", True)))
    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.append(a[-1])))
    _widget(window, QPushButton, "watchlist_add_button").click()
    assert warned, "отказ не показан"
    assert "rusterm add --ticker ZZ --market US" in warned[0]


# ── ТЗ-75 S4: пустой список — не пустое окно ────────────────────────────

def test_s4_no_watchlists_shows_all_instruments(qapp, tmp_path):
    """ТЗ-75 S4: списков нет, инструменты в базе есть — окно
    показывает инструменты и предлагает собрать список одной
    командой, а не молчит пустотой."""
    repos, paths = _minimal_base(tmp_path / "nowl")
    repos.instrument.upsert_issuer(Issuer(
        "i-BBB", "Beta Beta", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-BBB", "i-BBB", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-BBB", "US-BBB", "NASDAQ", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-BBB", "BBB", "2000-01-01", None, None, None)
    window = desktop_window._build_window(repos, paths, None)
    counter = _widget(window, QLabel, "match_count")
    header = _widget(window, QLabel, "company_header")
    assert counter.text() == "компаний: 2", "инструменты не показаны"
    assert "rusterm watchlist create main --name main" in header.text()
    tree = _widget(window, QTreeWidget, "tree")
    assert tree.topLevelItemCount() > 0, "дерево пустое"


def test_s4_empty_base_names_first_command(qapp, tmp_path):
    """ТЗ-75 S4: инструментов нет вовсе — окно называет первую
    команду целиком, с подстановкой, без многоточий."""
    paths = AppPaths.from_root(tmp_path / "empty")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    window = desktop_window._build_window(repos, paths, None)
    header = _widget(window, QLabel, "company_header")
    assert "…" not in header.text(), "многоточие вместо команды"
    conn.close()
    assert "rusterm demo" in header.text()
    assert "rusterm add --ticker AAPL --market US" in header.text()


def test_s4_watchlist_ops_without_list_say_words(qapp, tmp_path,
                                                 monkeypatch):
    """ТЗ-75 S4/S1: без списка операции списка не молчат — слова с
    готовой командой создания."""
    repos, paths = _minimal_base(tmp_path / "noops")
    window = desktop_window._build_window(repos, paths, None)
    from PySide6.QtWidgets import QMessageBox
    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.append(a[-1])))
    for name in ("watchlist_add_button", "watchlist_remove_button",
                 "watchlist_clear_button"):
        _widget(window, QPushButton, name).click()
    assert len(warned) == 3, warned
    for message in warned:
        assert "rusterm watchlist create main --name main" in message
