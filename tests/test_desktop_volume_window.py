"""ТЗ-61 F3: окно на настоящем объёме — 500 бумаг, тайминги.

Список наблюдения на 500 бумаг собирается настоящим путём репозиториев
(эмитент + инструмент + листинг + тикер + член списка; синтетика
допустима, воздух — нет), у каждой бумаги снапшот с мерой. Измеряются:
сборка окна (открытие), переключение компании (selectionChanged ->
load_company), построение диаграммы.

Ряд на 2500 точек (ADR-0004) в дереве не существует: единственный ряд
диаграмм окна — история мер, а она пуста по построению (ADR-0009);
крупнейший настоящий пейлоад котировок в дереве — 200 закрытий
(tests/data/twelvedata/time_series_AAPL_1day_trimmed.json). Диаграмма
гоняется по настоящему полотну (ChartArea.set_spec) на этом пейлоаде;
полноценная 2500-точечная проверка ждёт дверь ценового ряда —
координаторский пункт.

Маркер volume: обычный набор тест не гоняет (pyproject addopts),
явный вызов — pytest -m volume.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTreeWidget  # noqa: E402

from rusterm.desktop import charts as desktop_charts  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)

ROOT = Path(__file__).resolve().parents[1]
VOLUME = 500


def _real_closes() -> list[float]:
    payload = json.loads((ROOT / "tests/data/twelvedata/"
                          "time_series_AAPL_1day_trimmed.json").read_text(
                              encoding="utf-8"))
    return [float(row["close"]) for row in payload["values"]]


@pytest.mark.volume
def test_window_timings_at_500_papers(tmp_path, capsys):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    iid = []
    for n in range(VOLUME):
        ticker = f"V{n:03d}"
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", f"Corp {ticker}", "US", None, None,
            "us-gaap", "USD"))
        instrument = f"US-{ticker}"
        repos.instrument.upsert_instrument(Instrument(
            instrument, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{instrument}", instrument, "NASDAQ", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{instrument}", ticker, "2000-01-01", None, None, None)
        iid.append(instrument)
    repos.watchlist.create_watchlist("wl-main", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-main", 1, "seed", None)
    for instrument in iid:
        issuer_id = f"i-{instrument[3:]}"
        repos.watchlist.add_member(vid, instrument, None)
        # снапшот с мерой — настоящая запись, не воздух
        repos.snapshot.create_snapshot(f"s-{instrument}", instrument, 1,
                                       "2025-01-01", None, None, "ready")
        repos.snapshot.insert_measure(
            f"m-{instrument}", f"s-{instrument}", "issuer", issuer_id,
            "revenues_total", "100", "USD",
            "2024-01-01", "2024-12-31", None, "t61-f3", None, None)

    app = QApplication.instance() or QApplication([])

    t0 = time.perf_counter()
    window = desktop_window._build_window(repos, paths, "wl-main")
    window.show()
    app.processEvents()
    open_s = time.perf_counter() - t0

    tree = window.findChild(QTreeWidget, "tree")
    assert tree is not None
    sector_item = tree.topLevelItem(0)
    assert sector_item is not None
    assert sector_item.childCount() == VOLUME
    company_item = sector_item.child(VOLUME // 2)

    t1 = time.perf_counter()
    tree.setCurrentItem(company_item)
    app.processEvents()
    switch_s = time.perf_counter() - t1

    closes = _real_closes()
    spec = {"kind": "line", "concept": "close (реальный пейлоад)",
            "years": list(range(len(closes))), "values": closes}
    chart = window.findChild(desktop_charts.ChartArea, "chart_area")
    assert chart is not None
    t2 = time.perf_counter()
    chart.set_spec(spec)
    app.processEvents()
    chart_s = time.perf_counter() - t2

    window.close()
    with capsys.disabled():
        print(f"\nF3: открытие окна на {VOLUME} бумаг: {open_s:.2f} с; "
              f"переключение компании: {switch_s:.2f} с; диаграмма на "
              f"{len(closes)} реальных точках: {chart_s:.2f} с")
    # потолки отзывчивости заведены щедрыми; числа — в REPORT-61
    assert open_s < 20, open_s
    assert switch_s < 10, switch_s
    assert chart_s < 10, chart_s
