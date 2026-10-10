"""ТЗ-110 B2: окно обновляется само — старт и каждые 6 часов.

Done-when пункта: offscreen-тест с подменёнными провайдерами — старт
запускает один проход, тик таймера запускает второй, витой цикл жив
во время прохода (интерфейс не мёрзнет), закрытие окна дожидается
воркера. Строка состояния — «обновлено HH:MM · N бумаг · M запросов».

Провайдеры — с диска (`tests/data/edgar`, yahoo chart), сеть не
трогается (B0), счётчик запросов настоящий, каталог `tmp_path` (P7).
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import rusterm.cli as cli  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.providers.edgar import EdgarProvider  # noqa: E402
from rusterm.providers.yahoo import YahooProvider  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)
from tests.test_task96_r2_follow import (_edgar_transport,  # noqa: E402
                                         YAHOO_CHART)

REPO = Path(__file__).resolve().parents[1]


def _yahoo_ok(url, headers):
    return 200, YAHOO_CHART.read_bytes(), {}


@pytest.fixture()
def offline_providers(monkeypatch):
    real = cli.get_provider

    def slow(base):
        """Транспорт с паузой: проход длится ~секунды, и витой цикл
        успевает покрутиться ПОКА воркер работает (не мёрзнет)."""
        def transport(url, headers):
            time.sleep(0.2)
            return base(url, headers)
        return transport

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate,
                                 transport=slow(_edgar_transport))
        if name == "yahoo":
            return YahooProvider(gate=gate, transport=slow(_yahoo_ok))
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_TWELVEDATA_KEY", raising=False)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-US-AAPL", "Apple Inc.", "US", "320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAPL", "i-US-AAPL", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-US-AAPL", "US-AAPL", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history("l-US-AAPL", "AAPL", "2015-01-01",
                                        None, "sandbox", None)
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    version = repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    repos.watchlist.add_member(version, "US-AAPL", None)
    return repos, paths, conn


def _widget(window, cls, name):
    widget = window.findChild(cls, name)
    assert widget is not None, f"{name} не найдено в окне"
    return widget


def _counters(paths):
    db = sqlite3.connect(f"file:{Path(paths.root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        return {name: db.execute(
            f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("price", "snapshot")}
    finally:
        db.close()


def _requests(paths):
    return cli._requests_used(str(paths.root))


def test_window_refreshes_on_start_and_on_tick(qapp, tmp_path,
                                               offline_providers):
    """Старт окна запускает проход (цены и снапшот в базе, строка
    «обновлено …»); тик таймера — второй проход (запросы растут, дублей
    цен нет). Пока проход идёт, витой цикл качается — интерфейс жив."""
    repos, paths, conn = _catalog(tmp_path)
    window = desktop_window._build_window(repos, paths, "wl-1")
    window.show()
    status = _widget(window, QLabel, "refresh_status")

    iterations = 0
    pumps_before_done = 0
    deadline = time.time() + 120
    while time.time() < deadline:
        QApplication.processEvents()
        iterations += 1
        if status.text().startswith("обновлено "):
            break
        pumps_before_done = iterations
        worker = window.findChild(QThread)
        if worker is not None:
            worker.wait(20)
        time.sleep(0.005)
    conn.close()

    text = status.text()
    assert text.startswith("обновлено "), text
    assert re.match(r"обновлено \d\d:\d\d · 1 бумаг · \d+ запросов", text), \
        text
    counters = _counters(paths)
    assert counters["price"] > 0, counters
    assert counters["snapshot"] > 0, counters
    # витой цикл крутился, ПОКА проход ещё не дошёл до итога: интерфейс
    # не мёрзнет (пауза в фейковом транспорте делает это детерминированным)
    assert pumps_before_done >= 3, (pumps_before_done, iterations, text)

    # второй проход по тику таймера: запросы растут (отчётность и цены
    # переспрашиваются), строки цен не дублируются
    requests_before = _requests(paths)
    window.refresh_tick()
    deadline = time.time() + 60
    while time.time() < deadline:
        QApplication.processEvents()
        if _requests(paths) > requests_before:
            break
        worker = window.findChild(QThread)
        if worker is not None:
            worker.wait(20)
        time.sleep(0.005)

    assert _requests(paths) > requests_before, "тиком ничего не сделано"
    assert _counters(paths)["price"] == counters["price"], \
        "второй проход записал дубли цен (I7)"

    # закрытие дожидается воркера: после close() живых потоков нет
    window.close()
    QApplication.processEvents()
    worker = window.findChild(QThread)
    assert worker is None or not worker.isRunning(), \
        "закрытие окна оставило работать фоновый проход"
    assert status.text().startswith(("обновлено", "обновление")), \
        status.text()


def test_refresh_timer_is_six_hours(qapp, tmp_path, offline_providers):
    """Интервал таймера — 6 часов: тик, а не постоянный опрос."""
    repos, paths, conn = _catalog(tmp_path)
    window = desktop_window._build_window(repos, paths, "wl-1")
    timer = window.refresh_timer
    conn.close()

    assert timer.interval() == 6 * 60 * 60 * 1000
    assert timer.isActive()
