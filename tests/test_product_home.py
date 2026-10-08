"""PRODUCT.md С1 (ТЗ-131 H1–H3): окно открывается таблицей всех компаний.

Слой `rusterm/desktop/home.py` и вкладка «Все компании»: строка на
компанию, числа из последнего снапшота теми же правилами прочерков, что
колонка «сейчас» карточки, изменение цены за год из ядра, сортировка по
числу, поиск с первых букв, группы по-русски, двойной клик — карточка.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit,  # noqa: E402
                               QTableWidget, QTabWidget, QTreeWidget)

from rusterm.core.prices import year_change  # noqa: E402
from rusterm.desktop import home  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def base(tmp_path):
    paths = AppPaths.from_root(tmp_path / "home")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.watchlist.create_watchlist("wl-h", "home", None, None)
    version = repos.watchlist.new_version("wlv-h", "wl-h", 1, "seed", None)
    for ticker, cap, pe, price_then, price_now in (
            ("AAA", "5e9", "12.5", 10.0, 12.0),
            ("BBB", "9e10", "-3", 50.0, 40.0),
            ("CCC", "2e9", "900", 7.0, 7.0)):
        issuer, iid = f"i-{ticker}", f"US-{ticker}"
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"{ticker} Holdings", "US", None, None, "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{ticker}", iid, "XNAS", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{ticker}", ticker, "2000-01-01", None, None, None)
        repos.watchlist.add_member(version, iid, None)
        sid = f"s-{ticker}"
        repos.snapshot.create_snapshot(sid, iid, 1, "2026-09-30", None,
                                       None, "ready")
        for concept, value, unit in (("market_cap_total", cap, "USD"),
                                     ("pe", pe, "ratio")):
            repos.snapshot.insert_measure(
                f"m-{ticker}-{concept}", sid, "issuer", issuer, concept,
                value, unit, "2026-09-30", "2026-09-30", "f", "v1", None,
                None)
        repos.price.put_rows(iid, "yahoo", [
            {"date": "2025-09-30", "close": price_then,
             "adjusted": price_then, "currency": "USD", "volume": 1},
            {"date": "2026-09-30", "close": price_now,
             "adjusted": price_now, "currency": "USD", "volume": 1}])
    yield repos, paths
    conn.close()


def test_year_change_uses_the_price_a_year_back(base):
    repos, _ = base
    change = year_change(repos.price, "US-AAA")
    assert change["change"] == pytest.approx(0.2)
    assert change["close"] == 12.0 and change["date"] == "2026-09-30"


def test_home_rows_apply_the_card_dash_rules(base):
    repos, _ = base
    companies = [{"instrument_id": f"US-{t}", "ticker": t,
                  "name": f"{t} Holdings", "sector": "banks",
                  "market": "US"} for t in ("AAA", "BBB", "CCC")]
    rows = {r["instrument_id"]: r["cells"] for r in
            home.home_rows(repos, companies)}
    assert rows["US-AAA"]["market_cap_total"]["text"] == "5,00 млрд USD"
    assert rows["US-AAA"]["pe"]["text"] == "12,50×"
    assert rows["US-BBB"]["pe"]["text"] == "—", "P/E при убытке — прочерк"
    assert rows["US-CCC"]["pe"]["text"] == "—", "P/E 900 — прочерк"
    assert rows["US-AAA"]["change"]["text"] == "+20,0 %"
    assert rows["US-BBB"]["change"]["text"] == "-20,0 %"
    assert rows["US-AAA"]["group"]["text"] == "Банки"


def test_sector_names_are_russian_and_unknown_stays_as_is():
    for code in ("banks", "hardware_electronics", "mining_metals",
                 "software", "telecom"):
        assert "_" not in home.sector_name(code)
    assert home.sector_name("energy") == "energy"


def _home(window):
    return window.findChild(QTableWidget, "home_table")


def test_window_opens_on_the_home_table_and_sorts_by_number(qapp, base):
    repos, paths = base
    window = desktop_window._build_window(repos, paths, "wl-h")
    tabs = window.findChild(QTabWidget, "tabs")
    assert tabs.tabText(tabs.currentIndex()) == "Все компании"
    table = _home(window)
    assert table.rowCount() == 3
    headers = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    cap = headers.index("Капитализация")
    table.sortItems(cap)
    order = [table.item(r, 0).text() for r in range(table.rowCount())]
    assert order == ["CCC", "AAA", "BBB"], "по числу, а не по тексту"
    texts = [table.item(r, c).text() for r in range(table.rowCount())
             for c in range(table.columnCount())]
    assert "нет данных" not in texts
    summary = window.findChild(QLabel, "home_summary").text()
    assert "компаний: 3" in summary


def test_search_filters_the_home_table(qapp, base):
    repos, paths = base
    window = desktop_window._build_window(repos, paths, "wl-h")
    window.findChild(QLineEdit, "search").setText("bb")
    table = _home(window)
    assert [table.item(r, 0).text() for r in range(table.rowCount())] == \
        ["BBB"]
    assert "совпадений: 1" in window.findChild(QLabel, "home_summary").text()


def test_double_click_opens_the_company_card(qapp, base):
    repos, paths = base
    window = desktop_window._build_window(repos, paths, "wl-h")
    table = _home(window)
    row = next(r for r in range(table.rowCount())
               if table.item(r, 0).text() == "AAA")
    table.cellDoubleClicked.emit(row, 0)
    tabs = window.findChild(QTabWidget, "tabs")
    assert tabs.tabText(tabs.currentIndex()) == "Компания"
    assert "AAA" in window.findChild(QLabel, "company_header").text()
    tree = window.findChild(QTreeWidget, "tree")
    assert tree.topLevelItemCount() >= 1
