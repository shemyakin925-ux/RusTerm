"""ТЗ-109 R4: без сети окно говорит «нет сети — данные от <дата>».

Done-when пункта: offscreen-тест с вечно падающим транспортом — окно
построилось, строка «нет сети» на месте, трассировки нет. Кнопка
«Собрать» идёт настоящим `rusterm follow` (дверь `cli.get_provider`
подменена транспортом-обрывом), строки стадий и отказов детей доходят
до окна (ТЗ-109 R4: stderr детей forwarded в emit), и по транспортной
причине окно называет отсутствие сети словами и дату показанных
данных — вместо «сбор не удался» без причины.

Каталог — `tmp_path`, окружение изолировано (P7); PySide6 offscreen.
"""
from __future__ import annotations

import os
import sqlite3
import time
import urllib.error
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, \
    QTreeWidget  # noqa: E402

import rusterm.cli as cli  # noqa: E402
from rusterm.desktop import actions as desktop_actions  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.providers.edgar import EdgarProvider  # noqa: E402
from rusterm.providers.twelvedata import TwelveDataProvider  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)
from tests.edgar_fixtures import ownership_body  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "tests" / "data"
TICKERS = DATA / "edgar" / "company_tickers.json"
FACTS = DATA / "edgar" / "companyfacts_m3_AAPL.json"
SUBMISSIONS = DATA / "edgar" / "submissions_aapl.json"
TIMES = DATA / "twelvedata" / "time_series_AAPL_1day_trimmed.json"
SPLITS = DATA / "twelvedata" / "splits_AAPL_full.json"
DIVS = DATA / "twelvedata" / "dividends_AAPL_full.json"

AAPL = ("US-AAPL", "AAPL", "Apple Inc.", "US", "XNAS")


def _edgar_ok(url, headers):
    if "company_tickers" in url:
        return 200, TICKERS.read_bytes(), {}
    if "companyfacts" in url:
        return 200, FACTS.read_bytes(), {}
    if "submissions" in url:
        return 200, SUBMISSIONS.read_bytes(), {}
    if "/Archives/edgar/data/" in url:
        body = ownership_body(url)
        return (200, body, {}) if body is not None else (404, b"{}", {})
    return 404, b'{"ok": false}', {}


def _twelvedata_ok(url, headers):
    if "time_series" in url:
        return 200, TIMES.read_bytes(), {}
    if "/splits" in url:
        return 200, SPLITS.read_bytes(), {}
    if "/dividends" in url:
        return 200, DIVS.read_bytes(), {}
    return 404, b'{"status": "error"}', {}


def _raise_urllib(url, headers):
    raise urllib.error.URLError(f"network down: {url.rsplit('/', 1)[-1]}")


def _down_everywhere(url, headers):
    raise urllib.error.URLError("no network at all")


@pytest.fixture()
def prices_offline(monkeypatch):
    """SEC — с диска, цены — обрыв связи. Дверь одна: cli.get_provider."""
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_ok)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=_raise_urllib)
        if name == "yahoo":
            # ТЗ-110 B1: цены по умолчанию — yahoo; сценарий offline
            # требует, чтобы их транспорт падал
            from rusterm.providers.yahoo import YahooProvider
            return YahooProvider(gate=gate, transport=_raise_urllib)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_TWELVEDATA_KEY", raising=False)


@pytest.fixture()
def everything_offline(monkeypatch):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_down_everywhere)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=_down_everywhere)
        if name == "yahoo":
            from rusterm.providers.yahoo import YahooProvider
            return YahooProvider(gate=gate, transport=_down_everywhere)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")


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
    iid, ticker, name, market, exchange = AAPL
    # registry_id = CIK из записанной карты: без него стадия 3 честно
    # отказывает «нет CIK» ещё до цен, и сценарий offline не достигается
    repos.instrument.upsert_issuer(Issuer(
        f"i-{iid}", name, market, "320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, f"i-{iid}", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        f"l-{iid}", iid, exchange, "USD", 1, None, None))
    repos.instrument.add_ticker_history(f"l-{iid}", ticker, "2015-01-01",
                                        None, "sandbox", None)
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    version = repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    repos.watchlist.add_member(version, iid, None)
    return repos, paths, conn


def _widget(window, cls, name):
    widget = window.findChild(cls, name)
    assert widget is not None, f"{name} не найдено в окне"
    return widget


def _select(window, needle):
    tree = _widget(window, QTreeWidget, "tree")
    for i in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(i)
        for j in range(group.childCount()):
            child = group.child(j)
            if needle in child.text(0):
                tree.setCurrentItem(child)
                return child
    raise AssertionError(f"бумага {needle!r} не найдена в дереве")


def _wait_final_status(window, status, timeout_s=60.0):
    """Ждать итоговое слово, не голодая воркер (урок REPORT-C2):
    worker.wait чередуется с processEvents."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        text = status.text()
        if text.startswith(("готово", "отменено", "сбор не удался",
                            "нет сети")):
            return text
        worker = window.findChild(QThread)
        if worker is not None:
            worker.wait(50)
        QApplication.processEvents()
    return status.text()


def test_offline_collect_shows_banner_with_data_date(
        qapp, tmp_path, prices_offline):
    """Цены за обрывом — путь дошёл до снапшота (R1), окно построилось,
    строка «нет сети — данные от <дата>» в шапке и в полосе сбора,
    трассировки нет: воркер дошёл до итога."""
    repos, paths, conn = _catalog(tmp_path)
    window = desktop_window._build_window(repos, paths, "wl-1")
    window.show()  # offscreen: иначе isVisible() у детей всегда False
    status = _widget(window, QLabel, "collect_status")
    banner = _widget(window, QLabel, "offline_notice")
    assert not banner.isVisible()
    _select(window, "AAPL")
    _widget(window, QPushButton, "collect_button").click()

    text = _wait_final_status(window, status)
    # дата из двери данных читается до close(): repos сидит на соединении
    expected_banner = (f"нет сети — данные от "
                       f"{desktop_data.last_snapshot_date(repos, 'US-AAPL')}")
    conn.close()

    assert banner.text().startswith("нет сети — данные от "), banner.text()
    assert banner.isVisible(), "строка «нет сети» не показана"
    # дата — та же, что отвечает дверь данных окна
    assert banner.text() == expected_banner, banner.text()
    assert text.startswith("готово:"), text
    assert "нет сети — данные от" in text, text


def test_offline_collect_without_any_data_says_so(
        qapp, tmp_path, everything_offline):
    """Сети нет вовсе: путь кончается на поиске в SEC, снапшотов нет —
    строка честно говорит «данных пока нет», окно живо, без трассировки."""
    repos, paths, conn = _catalog(tmp_path)
    window = desktop_window._build_window(repos, paths, "wl-1")
    window.show()  # offscreen: иначе isVisible() у детей всегда False
    status = _widget(window, QLabel, "collect_status")
    banner = _widget(window, QLabel, "offline_notice")
    _select(window, "AAPL")
    _widget(window, QPushButton, "collect_button").click()

    text = _wait_final_status(window, status)
    conn.close()

    assert banner.isVisible()
    assert banner.text() == "нет сети — данных пока нет", banner.text()
    assert text == "нет сети — данных пока нет", text


def test_follow_instrument_marks_transport_refusal_offline(tmp_path,
                                                           prices_offline):
    """Машина слова: у итога сбора есть флаг offline, окно читает его
    getattr-ом — демо-сбор без поля остаётся рабочим."""
    paths = AppPaths.from_root(tmp_path / "app")
    outcome = desktop_actions.follow_instrument(paths.root, "US-AAPL")

    assert outcome.ok is True, vars(outcome)
    assert outcome.offline is True, vars(outcome)
    assert outcome.snapshot_id is not None


def test_follow_instrument_total_outage_is_offline_too(
        tmp_path, everything_offline):
    paths = AppPaths.from_root(tmp_path / "app")
    outcome = desktop_actions.follow_instrument(paths.root, "US-AAPL")

    assert outcome.ok is False, vars(outcome)
    assert outcome.reason == "follow_failed"
    assert outcome.offline is True, vars(outcome)
