"""ТЗ-95 F3: разрыв в годовом ряду — окно называет пропущенный год.

Форма живой базы пользователя (MSFT): колонки 2026, 2024, 2023, 2022.
Четыре колонки — это потолок, поэтому прежнее объяснение («история за N
лет, потому что колонок меньше запрошенных») молчало: объяснять было
нечего. Молчащий пробел между 2026 и 2024 читается как «данных нет ни у
кого», а на деле этого года просто нет в базе. Строка выводится из
видимых колонок, а не из константы.
"""
from __future__ import annotations

import os
import sqlite3

import pytest

from rusterm.desktop import data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, Listing, RepoRegistry

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QLabel,  # noqa: E402
                               QTreeWidget)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _connect(paths: AppPaths) -> sqlite3.Connection:
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _years(repos, *years: str) -> None:
    """Ряд мер net_margin по годам: период меры — этот год, значит год
    колонки из данных, а не из года прогона (ТЗ-76 W3)."""
    for n, year in enumerate(years, start=1):
        repos.snapshot.create_snapshot(f"s-{year}", "US-MSF", n,
                                       f"{year}-12-31", None, None, "ready")
        repos.snapshot.insert_measure(
            f"m-{year}", f"s-{year}", "issuer", "i-MSF", "net_margin",
            f"0.{20 + n}", "ratio", f"{year}-01-01", f"{year}-12-31",
            f"f-{year}", "v1", None, None)


@pytest.fixture()
def base(tmp_path):
    """Каталог с одной бумагой и списком наблюдения; ряд лет дописывает
    вызывающий через `_years`."""
    paths = AppPaths.from_root(tmp_path / "gap")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-MSF", "Модельная", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-MSF", "i-MSF", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-MSF", "US-MSF", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-MSF", "MSF", "2000-01-01", None, None, None)
    repos.watchlist.create_watchlist("wl-msf", "main", None, None)
    version_id = repos.watchlist.new_version("wlv-msf", "wl-msf", 1,
                                             "seed", None)
    repos.watchlist.add_member(version_id, "US-MSF", None)
    try:
        yield repos
    finally:
        conn.close()


def test_msft_shape_has_a_gap_and_no_apology_yet(base):
    """Сам ряд лет — то, что видит окно: четыре колонки, 2025 среди них
    нет. Это precondition, а не вывод: без него остальное можно
    объяснить кривой фикстурой."""
    _years(base, "2026", "2024", "2023", "2022")
    table = data.measure_table_rows(base, "US-MSF")
    assert table["years"] == ["2026", "2024", "2023", "2022"], table["years"]
    assert len(table["years"]) == data.DEFAULT_YEAR_COLUMNS


def test_the_gap_year_is_named_by_the_line(base):
    """ТЗ-95 F3: колонки идут 2026 → 2022, 2025 пропущен — окно говорит
    про пропущенный год словами, хотя колонок ровно потолок."""
    _years(base, "2026", "2024", "2023", "2022")
    note = data.measure_table_rows(base, "US-MSF")["history_note"]
    assert note is not None, "разрыва не видно — F3 не выполнен"
    assert "пропущен 2025 год" in note, note
    assert "\n" not in note, "одна строка, а не абзац"


def test_the_named_year_comes_from_the_columns_not_a_constant(base):
    """Другой разрыв — другое слово: 2025 тут на месте, нет 2023.
    Константа «нет 2025» на этом же тесте краснеет."""
    _years(base, "2026", "2025", "2024", "2022")
    note = data.measure_table_rows(base, "US-MSF")["history_note"]
    assert "пропущен 2023 год" in note, note
    assert "2025" not in note, note


def test_two_gaps_are_named_in_the_ascending_order(base):
    """Сколько лет потеряно — столько и названо (2026, 2024, 2022)."""
    _years(base, "2026", "2024", "2022")
    note = data.measure_table_rows(base, "US-MSF")["history_note"]
    assert "пропущены 2023, 2025 годы" in note, note


def test_a_contiguous_row_has_nothing_to_say(base):
    """Обратный случай той же правды: 2025 добавился, видимые четыре
    колонки идут подряд — строки про разрыв нет и быть не должно. Год
    вне видимого ряда (2022) не превращается в жалобу."""
    _years(base, "2026", "2025", "2024", "2023", "2022")
    table = data.measure_table_rows(base, "US-MSF")
    assert table["years"] == ["2026", "2025", "2024", "2023"], table["years"]
    assert table["history_note"] is None, table["history_note"]


def test_a_short_row_says_both_facts_in_one_line(base):
    """ТЗ-81 B2 и ТЗ-95 F3 в одной строке: колонок меньше потолка —
    окно говорит и про границы снапшотов, и про дыру между ними."""
    _years(base, "2026", "2024")
    note = data.measure_table_rows(base, "US-MSF")["history_note"]
    assert note.startswith("история за 2 года"), note
    assert "пропущен 2025 год" in note, note
    assert "\n" not in note, note


def test_the_window_shows_the_gap_under_the_table(qapp, base):
    """Слова доходят до пользователя: под таблицей — панель источника,
    и в ней назван пропущенный год."""
    from rusterm.desktop import window as desktop_window
    _years(base, "2026", "2024", "2023", "2022")
    paths = base.paths
    window = desktop_window._build_window(base, paths, "wl-msf", 1)
    tree = window.findChild(QTreeWidget, "tree")
    company = None
    for top in range(tree.topLevelItemCount()):
        node = tree.topLevelItem(top)
        for child in range(node.childCount()):
            if "MSF" in node.child(child).text(0):
                company = node.child(child)
    assert company is not None, "бумага не появилась в боковой панели"
    tree.setCurrentItem(company)
    panel = window.findChild(QLabel, "source_panel")
    assert "пропущен 2025 год" in panel.text(), panel.text()
