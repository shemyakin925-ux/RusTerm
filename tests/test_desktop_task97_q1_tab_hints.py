"""ТЗ-97 Q1 (ТЗ-73 `T1`, правило P8): ни одна вкладка не пуста без подсказки.

Правило: «экран не показывает раздел, который не может наполниться; он
либо наполняется, либо называет действие, которым наполняется, либо не
рисуется». Страж проверяет каждую из четырёх вкладок окна на базе,
собранной **обычным путём** (`rusterm follow AAPL` на записанных
ответах — тот же путь, что ТЗ-96 R4): вкладка либо несёт данные, либо
несёт **исполнимую подсказку** — строку с командой `rusterm …`, которую
разбирает парсер CLI (тот же критерий, что B26/J3; строка не
исполняется).

Что закреплено здесь отдельно от правила (правки ТЗ-97 к `T1`):
- «Отрасль» на бумаге без набора — `rusterm peers set …` без
  `--approve`; на неподтверждённом наборе — та же строка с `--approve`
  и составом из набора;
- «Качество»: пять серых строк governance называют канал владения
  `rusterm ingest --source ownership` — команда в CLI уже есть;
- `revenue` в таблице отрасли: ни одна мера словаря её не подаёт,
  поэтому в агрегате её больше нет (обоснование и числа — в отчёте).

На дереве до правок страж краснеет ровно на «Отрасли» и «Качестве»;
замер прогона записан в отчёт (Runs), а не обещан.
"""
from __future__ import annotations

import os
import shlex
import sqlite3
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rusterm.cli import _build_parser, main as cli_main  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)
from PySide6.QtWidgets import (QApplication, QComboBox, QLabel,  # noqa: E402
                               QPushButton, QTabWidget, QTableWidget,
                               QTreeWidget, QWidget)
from tests.test_desktop_task96_r4_firsthour import (  # noqa: E402
    FAKE_TWELVEDATA_KEY, _company_item, _edgar_transport,
    _twelvedata_transport, _widget)

# Порядок и имена вкладок — часть контракта окна: новая вкладка обязана
# попасть в страж, а не быть нарисованной мимо правила.
TABS = ("Все компании", "Компания", "Аналоги", "Качество", "Настройки")


def _open(root):
    """Каталог, собранный обычным путём, + реестр репозиториев."""
    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    return paths, conn, RepoRegistry(conn, paths)


def _register_second_company(repos, ticker: str) -> str:
    """Завести в базу второй инструмент, чтобы у набора был состав из
    двух разрешимых бумаг. `rusterm add` для этого не зовём: он резолвит
    тикер в сеть, а сети в тесте нет; строки те же, что у обычного пути
    (тот же приём, что tests/test_desktop_peers.py:38).

    Площадка — «unknown», ровно то, что оставляет обычный путь follow по
    записанным ответам: XNAS/NASDAQ реестр рынков под `--market US` тут
    не пропускает (`rusterm/markets.py:117`).
    """
    iid = f"US-{ticker}"
    repos.instrument.upsert_issuer(
        Issuer(f"i-{ticker}", f"{ticker} Corp", "US", None, None,
               "us-gaap", "USD"))
    repos.instrument.upsert_instrument(
        Instrument(iid, f"i-{ticker}", None, "common", "active", None))
    repos.instrument.upsert_listing(
        Listing(f"l-{iid}", iid, "unknown", "USD", 1, None, None))
    repos.instrument.add_ticker_history(f"l-{iid}", ticker, "2000-01-01",
                                        None, None, None)
    return iid


def _follow_aapl(root, mp):
    """ТЗ-96 R2: `rusterm follow AAPL` на записанных ответах; сети нет."""
    import rusterm.cli as cli
    from rusterm.providers.edgar import EdgarProvider
    from rusterm.providers.twelvedata import TwelveDataProvider

    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key=FAKE_TWELVEDATA_KEY,
                                      transport=_twelvedata_transport)
        if name == "yahoo":
            # ТЗ-110 B1: цены по умолчанию — yahoo (chart с диска)
            from rusterm.providers.yahoo import YahooProvider
            from pathlib import Path as _P
            chart = _P(__file__).parent / "data/yahoo/chart_AAPL_trimmed.json"
            return YahooProvider(
                gate=gate, transport=lambda url, headers:
                    (200, chart.read_bytes(), {}))
        return real(name, gate=gate)

    mp.setattr(cli, "get_provider", fake)
    mp.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    mp.setenv("RUSTERM_TWELVEDATA_KEY", FAKE_TWELVEDATA_KEY)
    mp.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    assert cli_main(["--root", str(root), "follow", "AAPL"]) == 0, \
        "обычный путь не доехал до снапшота"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module")
def hour(tmp_path_factory, qapp):
    """Одно окно на файл: база обычным путём, AAPL выбрана в дереве.

    Окружение живёт столько же, сколько окно: панель ключей читается при
    перерисовке, а не при старте.
    """
    root = tmp_path_factory.mktemp("q1") / "app"
    mp = pytest.MonkeyPatch()
    conn = None
    try:
        _follow_aapl(root, mp)
        paths, conn, repos = _open(root)
        win = desktop_window._build_window(repos, paths, None)
        tree = _widget(win, QTreeWidget, "tree")
        item = _company_item(tree, "AAPL")
        assert item is not None, "AAPL не появилась в дереве окна"
        tree.setCurrentItem(item)
        yield SimpleNamespace(win=win, repos=repos, paths=paths, root=root)
    finally:
        if conn is not None:
            conn.close()
        mp.undo()
        from rusterm import env as env_module
        env_module._LAST_ORIGINS = None


# ── чтение вкладки ───────────────────────────────────────────────────────

def _tab_page(win, title: str) -> QWidget:
    tabs = _widget(win, QTabWidget, "tabs")
    pages = {tabs.tabText(i): tabs.widget(i) for i in range(tabs.count())}
    assert title in pages, f"в окне нет вкладки {title!r}: {sorted(pages)}"
    return pages[title]


def _table_of(page: QWidget, name: str) -> QTableWidget:
    found = page.findChild(QTableWidget, name)
    assert found is not None, f"на вкладке нет таблицы {name!r}"
    return found


def _table_cells(table: QTableWidget) -> list[str]:
    out = []
    for header in range(table.columnCount()):
        item = table.horizontalHeaderItem(header)
        if item is not None:
            out.append(item.text())
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            cell = table.item(row, column)
            if cell is not None:
                out.append(cell.text())
    return out


def _tab_texts(page: QWidget) -> list[str]:
    """Всё написанное на вкладке словами: надписи, ячейки таблиц,
    позиции списков, подписи кнопок."""
    texts = [w.text() for w in page.findChildren(QLabel)]
    texts += [w.text() for w in page.findChildren(QPushButton)]
    for table in page.findChildren(QTableWidget):
        texts += _table_cells(table)
    for box in page.findChildren(QComboBox):
        texts += [box.itemText(i) for i in range(box.count())]
    return [text for text in texts if text and text.strip()]


def _has_number_in_second_column(table: QTableWidget) -> bool:
    """Хоть одна строка с числом во второй колонке («сейчас» / «медиана»).
    Мера без значения показана словом NO_DATA — она данными не считается:
    иначе серая заглушка прошла бы как наполнение."""
    for row in range(table.rowCount()):
        cell = table.item(row, 1)
        if cell is not None and cell.text() not in ("", desktop_data.NO_DATA):
            return True
    return False


def _carries_data(tab: str, page: QWidget) -> bool:
    """Данные вкладки — по её назначению, а не по «что-то нарисовано»."""
    if tab == "Все компании":
        # ТЗ-131 H1: хоть одно число в числовых колонках (от
        # «Капитализации» вправо), не «—» и не слова
        table = _table_of(page, "home_table")
        headers = [table.horizontalHeaderItem(c).text()
                   for c in range(table.columnCount())]
        first = headers.index("Капитализация")
        return any(table.item(row, col) is not None
                   and table.item(row, col).text() not in
                   ("", "—", desktop_data.NO_DATA)
                   for row in range(table.rowCount())
                   for col in range(first, table.columnCount()))
    if tab == "Компания":
        return _has_number_in_second_column(_table_of(page, "table"))
    if tab == "Аналоги":
        return _has_number_in_second_column(_table_of(page, "industry_table"))
    if tab == "Качество":
        table = _table_of(page, "governance_table")
        return any(table.item(row, 1) and table.item(row, 1).text() != "gray"
                   for row in range(table.rowCount()))
    if tab == "Настройки":
        keys = page.findChild(QLabel, "keys_label").text()
        return _table_of(page, "limits_table").rowCount() > 0 \
            and "RUSTERM_" in keys
    raise AssertionError(f"не задано, что считается данными для {tab!r}")


# ── подсказка ────────────────────────────────────────────────────────────

def _flags(argv: list[str]) -> dict:
    return {argv[i]: argv[i + 1] for i, token in enumerate(argv)
            if token.startswith("--") and i + 1 < len(argv)
            and not argv[i + 1].startswith("--")}


def _hint_argv(root, texts: list[str]) -> list[list[str]]:
    """Команды, названные вкладкой, разобранные парсером CLI. Разбор —
    без исполнения; не разобралась — тест краснеет с текстом строки."""
    found = []
    for text in texts:
        for line in text.splitlines():
            if "rusterm " not in line:
                continue
            argv = shlex.split(line[line.index("rusterm"):])
            assert argv[0] == "rusterm", line
            try:
                _build_parser().parse_args(
                    ["--root", str(root)] + argv[1:])
            except SystemExit as exc:
                pytest.fail(f"подсказка не разбирается парсером CLI "
                            f"(exit {exc.code}): {line}")
            found.append(argv)
    return found


def _hints_of(hour, tab: str) -> list[list[str]]:
    return _hint_argv(hour.root, _tab_texts(_tab_page(hour.win, tab)))


# ── страж P8 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tab", TABS)
def test_guard_no_tab_is_empty_without_an_executable_hint(hour, tab):
    """Каждая вкладка либо несёт данные, либо несёт исполнимую подсказку.
    Третья ветка правила («не рисуется») стражем не проверяется: все
    четыре вкладки в окне есть."""
    page = _tab_page(hour.win, tab)
    if _carries_data(tab, page):
        return
    assert _hints_of(hour, tab), (
        f"вкладка {tab!r} пуста и не называет действие, которым "
        f"наполняется; на ней написано: {_tab_texts(page)}")


def test_guard_tab_list_covers_the_whole_window(hour):
    """Страж не устаревает молча: список вкладок стража равен вкладкам
    окна, иначе новая вкладка окажется нарисованной мимо правила."""
    tabs = _widget(hour.win, QTabWidget, "tabs")
    titles = tuple(tabs.tabText(i) for i in range(tabs.count()))
    assert titles == TABS, (titles, TABS)


def test_guard_company_and_settings_still_carry_data(hour):
    """Подсказка — не лазейка: наполненные вкладки обязаны оставаться
    наполненными, а не съезжать в текст с командой."""
    for tab in ("Компания", "Настройки"):
        assert _carries_data(tab, _tab_page(hour.win, tab)), tab


# ── «Отрасль»: две развилки подсказки ────────────────────────────────────

def test_industry_hint_for_paper_without_a_set(hour):
    """Бумага без набора: `peers set` без `--approve` — набирать состав
    ещё нечего, подтверждать нечего."""
    argvs = [argv for argv in _hints_of(hour, "Аналоги")
             if argv[1:3] == ["peers", "set"]]
    assert argvs, _tab_texts(_tab_page(hour.win, "Аналоги"))
    argv = argvs[0]
    assert "--approve" not in argv, argv
    flags = _flags(argv)
    assert flags["--origin"] == "manual", argv
    assert flags["--market"] == "US", argv
    assert "AAPL" in flags["--tickers"], argv
    # позиционный сектор на месте: парсер требует его всегда
    positionals = [token for token in argv[3:]
                   if not token.startswith("--")
                   and token not in flags.values()]
    assert len(positionals) == 1, argv


def test_industry_hint_on_an_unconfirmed_set_asks_to_approve(tmp_path):
    """Неподтверждённый набор: та же команда с `--approve`, сектором,
    рынком и составом из самого набора. Слова берёт слой данных, окно
    рисует их без правки (тот же порядок, что у rule/message)."""
    root = tmp_path / "app"
    mp = pytest.MonkeyPatch()
    conn = None
    try:
        _follow_aapl(root, mp)
        paths, conn, repos = _open(root)
        _register_second_company(repos, "MSFT")
        conn.close()
        conn = None
        assert cli_main(["--root", str(root), "peers", "set", "software",
                         "--tickers", "AAPL,MSFT", "--market", "US",
                         "--origin", "llm_suggested"]) == 0
        paths, conn, repos = _open(root)
        peer = desktop_data.peer_screen(repos, "US-AAPL")
        assert peer["has_peer_set"] and not peer["verified"], peer
        argvs = _hint_argv(root, [peer.get("hint") or peer.get("message")
                                  or ""])
        assert argvs and "--approve" in argvs[0], peer["hint"]
        argv = argvs[0]
        flags = _flags(argv)
        assert argv[1:3] == ["peers", "set"], argv
        assert argv[3] == "software", argv
        assert set(flags["--tickers"].split(",")) == {"AAPL", "MSFT"}, argv
        assert flags["--market"] == "US", argv
        assert flags["--origin"] == "manual", argv
    finally:
        if conn is not None:
            conn.close()
        mp.undo()
        from rusterm import env as env_module
        env_module._LAST_ORIGINS = None


# ── «Качество»: чем закрывается серый governance ─────────────────────────

def test_quality_governance_is_gray_and_names_the_channel(hour):
    """Governance — серые строки, и вкладка обязана назвать канал
    владения, который их наполняет. ТЗ-110 B1: с котировками в базе
    insider_net получает жёлтую оценку §4 — серые строки остаются, и
    их слова обязаны жить в словаре."""
    table = _table_of(_tab_page(hour.win, "Качество"), "governance_table")
    assert table.rowCount() > 0, "governance не показан вовсе"
    colours = {table.item(r, 1).text()
               for r in range(table.rowCount()) if table.item(r, 1)}
    assert "gray" in colours, colours
    assert colours <= {"gray", "yellow"}, (
        f"новый цвет — перенеси слова и этот зуб: {colours}")
    argvs = [argv for argv in _hints_of(hour, "Качество")
             if argv[1:3] == ["ingest", "--source"]]
    assert argvs, _tab_texts(_tab_page(hour.win, "Качество"))
    argv = argvs[0]
    assert argv[3] == "ownership", argv
    assert _flags(argv)["--instrument"] == "US-AAPL", argv


def test_quality_hint_words_are_one_door(hour):
    """Слово подсказки живёт в слое данных, а не в окне: строка
    разбирается парсером, а на вкладке она ровно тогда, когда строки
    серые (governance_needs_hint). ТЗ-110 B1: с котировками insider_net
    жёлтый — подсказки быть не должно, и дверь с вкладкой согласны."""
    hint = desktop_data.governance_hint("US-AAPL")
    assert "rusterm ingest --source ownership --instrument US-AAPL" in hint
    argv = shlex.split(hint[hint.index("rusterm"):])
    _build_parser().parse_args(["--root", str(hour.root)] + argv[1:])
    page = _tab_page(hour.win, "Качество")
    texts = _tab_texts(page)
    table = _table_of(page, "governance_table")
    colours = {table.item(r, 1).text()
               for r in range(table.rowCount()) if table.item(r, 1)}
    on_tab = any(hint in text for text in texts)
    assert on_tab == (colours <= {"gray"}), (on_tab, colours, texts)
