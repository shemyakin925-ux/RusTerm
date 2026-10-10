"""ТЗ-97 Q12, строка 2 (вердикт «прав» по Disputed ТЗ-96): «Собрать» на
любой бумаге = `rusterm follow` в рабочем потоке, стадии читаются в окне;
демо-путь остаётся демо-путём.

Done-when пункта: offscreen-тест — кнопка на не-demo бумаге вызывает
`follow`, транспорт — заглушка из `tests/data`. Зубы разведены нарочно:
сам путь проверяется настоящим прогоном без подмены тела (числа в базе),
а «окно зовёт ровно ту команду, что зовёт терминал» — записчиком на
`cli.cmd_follow`: аргумент-вектор обязан разобрать настоящий парсер, иначе
окно незаметно копирует себе тело стадии.

Что закреплено:
1. кнопка на не-demo бумаге зовёт `cli.cmd_follow` с `command="follow"`,
   тикером и рынком из `instrument_id`, явным `--root`, приёмником стадий
   и флагом отмены — и делает это в фоне (отмена доступна во время пути);
2. слово стадии попадает в полосу состояния до итога: вывод `follow` виден
   в окне, а не только в терминале;
3. на заглушке из `tests/data` путь действительно сделан — факты, цены и
   снапшот лежат в базе, `on_stage` получил все шесть стадий по порядку;
4. демо-бумага в `follow` не ходит: у неё свой синтетический конвейер;
5. отмена обрывает путь на границе стадий — между стадиями, не посередине,
   и не оставляет половины снапшота;
6. отказ канала остаётся словами и закрывающей командой: последняя строка
   `follow` разбирается парсером CLI (правило P8).
"""
from __future__ import annotations

import os
import shlex
import sqlite3
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton,  # noqa: E402
                               QTreeWidget)

import rusterm.cli as cli  # noqa: E402
from rusterm.desktop import actions as desktop_actions  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.providers.edgar import EdgarProvider  # noqa: E402
from rusterm.providers.twelvedata import (  # noqa: E402
    TwelveDataProvider)
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


def _edgar_transport(url, headers):
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


def _twelvedata_transport(url, headers):
    if "time_series" in url:
        return 200, TIMES.read_bytes(), {}
    if "/splits" in url:
        return 200, SPLITS.read_bytes(), {}
    if "/dividends" in url:
        return 200, DIVS.read_bytes(), {}
    return 404, b'{"status": "error"}', {}


@pytest.fixture()
def offline_providers(monkeypatch):
    """Настоящие провайдеры, транспорт — с диска. Дверь одна на всё:
    `cli.get_provider`, откуда их берут все стадии пути. Сети нет, а
    счётчик запросов остаётся настоящим."""
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=_twelvedata_transport)
        if name == "yahoo":
            # ТЗ-110 B1: котировки по умолчанию — yahoo (chart с диска)
            from rusterm.providers.yahoo import YahooProvider
            chart = (DATA / "yahoo" / "chart_AAPL_trimmed.json")
            return YahooProvider(
                gate=gate,
                transport=lambda url, headers:
                    (200, chart.read_bytes(), {}))
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_TWELVEDATA_KEY", raising=False)
    return fake


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _catalog(tmp_path, rows):
    """Песочный каталог, собранный дверями репозитория. Тикеры действуют с
    2015-01-01: прогон не должен зависеть от дня, в котором его запустили
    (урок проверки 11 из ТЗ-97 Q4)."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for iid, ticker, name, market, exchange in rows:
        repos.instrument.upsert_issuer(Issuer(
            f"i-{iid}", name, market, None, None, "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{iid}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{iid}", iid, exchange, "USD", 1, None, None))
        repos.instrument.add_ticker_history(f"l-{iid}", ticker, "2015-01-01",
                                            None, "sandbox", None)
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    version = repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    for iid, *_rest in rows:
        repos.watchlist.add_member(version, iid, None)
    return repos, paths, conn


def _demo_row():
    from rusterm.cli import DEMO_INSTRUMENT
    return (DEMO_INSTRUMENT, "DEMO", "CLI Demo Corp (synthetic)", "US",
            "XNAS")


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


def _wait_status(window, status, timeout_s=40.0):
    """Ждать итогового слова, не голодая воркер: блокирующий worker.wait
    чередуется с processEvents — голый qWait-цикл не отдаёт GIL python-
    потоку (замерено в REPORT-C2)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        text = status.text()
        if text.startswith(("готово", "отменено", "сбор не удался")):
            return text
        worker = window.findChild(QThread)
        if worker is not None:
            worker.wait(50)
        QApplication.processEvents()
    return status.text()


def _counters(paths):
    """Счётчики каталога, которого может и не быть: до первой стадии базы
    нет вовсе, и для теста отмены это тоже ответ."""
    db_path = Path(paths.root) / "rusterm.db"
    if not db_path.exists():
        return {"fact": 0, "price": 0, "snapshot": 0}
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("fact", "price", "snapshot")}
    finally:
        db.close()


def _advice_words(line):
    """«совет: rusterm add …» -> ['add', …] — тот же разбор, что у
    зуба ТЗ-96 R2: совет обязан быть командой, а не описанием."""
    assert line.startswith("совет: "), line
    words = shlex.split(line[len("совет: "):])
    assert words[0] == "rusterm", line
    return words[1:]


# ── 1-2: кнопка на живой бумаге ─────────────────────────────────────────

def test_the_button_on_a_real_paper_calls_the_same_follow_as_the_terminal(
        qapp, tmp_path, monkeypatch):
    """Тело стадии в окно не переезжает: кнопка зовёт `cli.cmd_follow` с
    аргумент-вектором, разобранным настоящим парсером, в рабочем потоке и
    с приёмником стадий + флагом отмены."""
    release = {"done": False}
    calls = []

    def spy(args, emit=None, cancel=None):
        calls.append((args, emit, cancel))
        deadline = time.time() + 10
        while not release["done"] and time.time() < deadline:
            time.sleep(0.01)
        emit("US-AAPL: 6/6 снапшот — готово (запросов 0)")
        return 0

    monkeypatch.setattr(cli, "cmd_follow", spy)
    repos, paths, conn = _catalog(tmp_path, [AAPL])
    window = desktop_window._build_window(repos, paths, "wl-1")
    status = _widget(window, QLabel, "collect_status")
    cancel = _widget(window, QPushButton, "cancel_button")
    _select(window, "AAPL")
    button = _widget(window, QPushButton, "collect_button")
    assert button.isEnabled()
    button.click()
    QApplication.processEvents()
    assert cancel.isEnabled(), "путь обязан идти в фоне: отмена доступна"
    assert status.text().startswith("сбор запущен"), status.text()
    release["done"] = True
    text = _wait_status(window, status)
    conn.close()

    assert len(calls) == 1, calls
    args, emit, flag = calls[0]
    assert args.command == "follow"
    assert args.ticker == "AAPL" and args.market == "US", vars(args)
    assert Path(str(args.root)) == paths.root
    assert callable(emit) and flag is not None
    assert text.startswith("готово:"), text
    assert not cancel.isEnabled(), "по завершении отмена погашена"
    assert button.isEnabled(), "кнопка сбора вернулась"


def test_a_stage_line_is_visible_in_the_window_before_the_total(
        qapp, tmp_path, monkeypatch):
    """«С выводом стадий в окно»: строка стадии доходит до полосы
    состояния, а не исчезает в воркере. Воркер на время держится на
    границе стадии, чтобы тест успел прочесть промежуточное слово."""
    release = {"done": False}

    def spy(args, emit=None, cancel=None):
        emit("US-AAPL: 3/6 отчётность — готово (запросов 2)")
        deadline = time.time() + 10
        while not release["done"] and time.time() < deadline:
            time.sleep(0.01)
        return 0

    monkeypatch.setattr(cli, "cmd_follow", spy)
    repos, paths, conn = _catalog(tmp_path, [AAPL])
    window = desktop_window._build_window(repos, paths, "wl-1")
    status = _widget(window, QLabel, "collect_status")
    _select(window, "AAPL")
    _widget(window, QPushButton, "collect_button").click()

    seen = None
    deadline = time.time() + 10
    while time.time() < deadline:
        QApplication.processEvents()
        if "/6 " in status.text():
            seen = status.text()
            break
        time.sleep(0.01)
    release["done"] = True
    text = _wait_status(window, status)
    conn.close()

    assert seen == "US-AAPL: 3/6 отчётность — готово (запросов 2)", seen
    assert text.startswith("готово:"), text


def test_the_window_shows_the_follow_advice_when_a_stage_refuses(
        qapp, tmp_path, monkeypatch):
    """Прежняя кнопка на не-demo бумаге печатала список «запертых» команд
    CLI. Теперь она печатает отказ настоящего пути — словами и советом,
    который разбирается парсером CLI (правило P8)."""
    def spy(args, emit=None, cancel=None):
        emit("нет контакта SEC: офлайн-режим требует --cik и --name")
        emit("US-AAPL: 2/6 поиск в SEC — отказ (запросов 0)")
        emit("совет: rusterm add --ticker AAPL --market US")
        return 1

    monkeypatch.setattr(cli, "cmd_follow", spy)
    repos, paths, conn = _catalog(tmp_path, [AAPL])
    window = desktop_window._build_window(repos, paths, "wl-1")
    status = _widget(window, QLabel, "collect_status")
    _select(window, "AAPL")
    _widget(window, QPushButton, "collect_button").click()
    text = _wait_status(window, status)
    conn.close()

    assert text.startswith("сбор не удался: follow_failed — "), text
    parsed = cli._build_parser().parse_args(
        _advice_words(text.split(" — ", 1)[1]))
    assert parsed.command == "add" and parsed.ticker == "AAPL", vars(parsed)


# ── 4: демо-путь не тронут ─────────────────────────────────────────────

def test_the_demo_paper_still_uses_the_synthetic_pipeline(
        qapp, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "cmd_follow",
                        lambda *a, **kw: calls.append(a) or 0)
    repos, paths, conn = _catalog(tmp_path, [AAPL, _demo_row()])
    window = desktop_window._build_window(repos, paths, "wl-1")
    status = _widget(window, QLabel, "collect_status")
    _select(window, "DEMO")
    _widget(window, QPushButton, "collect_button").click()
    text = _wait_status(window, status)
    from rusterm.cli import DEMO_INSTRUMENT
    # снапшот читается до conn.close(): repos сидит на этом же соединении
    demo_snapshot = repos.snapshot.latest_snapshot_id(DEMO_INSTRUMENT)
    conn.close()

    assert calls == [], f"демо ушло бы в реальный путь: {calls}"
    assert text.startswith("готово:"), text
    assert demo_snapshot, "демо-конвейер не оставил снапшота"


# ── 3: настоящий путь на заглушке из tests/data ────────────────────────

def test_a_renamed_paper_is_collected_by_its_living_ticker(tmp_path,
                                                          monkeypatch):
    """Тикер берётся дверью магазина, а не из идентификатора. У
    переименованной бумаги `US-OLD` идентификатор несёт мёртвый тикер, и
    наивный split отправил бы в `follow` его — то есть собрал бы в базу
    пользователя чужую бумагу."""
    calls = []

    def spy(args, emit=None, cancel=None):
        calls.append(args)
        return 0

    monkeypatch.setattr(cli, "cmd_follow", spy)
    repos, paths, conn = _catalog(tmp_path, [("US-OLD", "OLD", "Old Corp",
                                              "US", "XNAS")])
    # та же дверь, что у `rusterm add`: старая строка закрывается,
    # свежая открывается с 2021-01-01
    repos.instrument.add_ticker_history("l-US-OLD", "OLD", "2015-01-01",
                                        "2020-12-31", "rename", None)
    repos.instrument.add_ticker_history("l-US-OLD", "NEW", "2021-01-01",
                                        None, "rename", None)
    conn.close()

    outcome = desktop_actions.follow_instrument(paths.root, "US-OLD")
    assert len(calls) == 1, calls
    assert calls[0].ticker == "NEW", vars(calls[0])
    assert calls[0].market == "US", vars(calls[0])
    assert outcome.ok is True, vars(outcome)


def test_follow_instrument_walks_the_path_and_streams_its_stages(
        tmp_path, offline_providers):
    paths = AppPaths.from_root(tmp_path / "app")
    stages = []
    outcome = desktop_actions.follow_instrument(
        paths.root, "US-AAPL", on_stage=stages.append)
    counters = _counters(paths)

    assert outcome.ok is True, vars(outcome)
    assert outcome.cancelled is False
    names = [line.split(": ", 1)[1].split(" — ")[0] for line in stages
             if "/6 " in line and " — " in line]
    assert names == ["1/6 каталог", "2/6 поиск в SEC", "3/6 отчётность",
                     "4/6 формы владения", "5/6 цены", "6/6 снапшот"], stages
    assert counters["fact"] > 0 and counters["price"] > 0, counters
    assert counters["snapshot"] > 0, counters
    assert outcome.snapshot_id is not None
    assert outcome.snapshot_version is not None


def test_a_stage_refusal_leaves_the_last_line_as_a_parseable_command(
        tmp_path, offline_providers):
    """Бумаги, которой нет в записанном индексе SEC: путь останавливается
    на 2/6, а окно остаётся с последней строкой `follow` — советом."""
    paths = AppPaths.from_root(tmp_path / "app")
    outcome = desktop_actions.follow_instrument(paths.root, "US-ZZZZ")

    assert outcome.ok is False
    assert outcome.reason == "follow_failed"
    parsed = cli._build_parser().parse_args(_advice_words(outcome.detail))
    assert parsed.command == "add", vars(parsed)
    assert _counters(paths)["snapshot"] == 0


# ── 5: отмена на границе стадий ────────────────────────────────────────

def test_cancel_before_the_first_stage_writes_nothing(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    flag = desktop_actions.CancelFlag()
    flag.cancel()
    outcome = desktop_actions.follow_instrument(paths.root, "US-AAPL",
                                               cancel=flag)

    assert outcome.cancelled is True, vars(outcome)
    assert outcome.ok is False
    assert _counters(paths) == {"fact": 0, "price": 0, "snapshot": 0}
    assert not (Path(paths.root) / "rusterm.db").exists(), \
        "отмена до старта не должна создавать каталог"


class _CancelAfter:
    """Флаг, открывающийся на N-й проверке: граница стадий проверяется без
    гонок со временем."""

    def __init__(self, after):
        self.after = after
        self.checks = 0

    def __bool__(self):
        self.checks += 1
        return self.checks > self.after


def test_cancel_mid_path_stops_at_the_next_stage_boundary(tmp_path,
                                                          offline_providers):
    """Отмена на третьей проверке границы: стадии 1/6 и 2/6 прошли —
    каталог и инструмент уже есть, — а отчётность, цены и снапшота нет.
    Половины пути не бывает: рубёж между запросами, не посередине."""
    paths = AppPaths.from_root(tmp_path / "app")
    outcome = desktop_actions.follow_instrument(
        paths.root, "US-AAPL", cancel=_CancelAfter(2))
    counters = _counters(paths)
    db = sqlite3.connect(f"file:{Path(paths.root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    instruments = db.execute("SELECT COUNT(*) FROM instrument").fetchone()[0]
    db.close()

    assert outcome.cancelled is True, vars(outcome)
    assert counters["fact"] == 0 and counters["snapshot"] == 0, counters
    assert instruments == 1, "поиск в SEC уже прошёл — граница не на границе"
