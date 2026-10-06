"""ТЗ-96 R4: первый час — тест утверждает содержимое вкладок окна.

Путь — ровно R2: `rusterm follow AAPL` на записанных ответах
(`tests/data/edgar`, `tests/data/twelvedata`) в каталог `tmp_path`,
сеть не трогается (правило P7), Qt offscreen, окно собирается настоящей
дверью `_build_window`, бумага выбирается в дереве — после этого
вкладки проверяются по тексту, а не по «не упало».

Маркера `firsthour` здесь нет умышленно: `pyproject addopts` снимает
этот маркер с обычного прогона, а пункт требует, чтобы тесты «Отрасли»
и «Качества» **сами** покраснели, когда ТЗ-73 их наполнит. Значит бегать
они обязаны в обычном наборе приёмки, иначе `strict=True` не сработает
никогда. (См. об этом в отчёте — вопрос координатору.)

Что закреплено числами из реального прогона:
- «Компания»: 29 строк мер, 11 из них с числом в колонке «сейчас»,
  «нет данных» — где меры нет; клик по ячейке отдаёт панель источника с
  именем меры, значением и путём к сырью, который есть на диске;
- «Настройки»: ключи именем и происхождением без значений (подставной
  ключ не попадает ни в одну надпись окна), лимиты = реестр
  провайдеров, каталог называет файл базы;
- «Отрасль» (ТЗ-73 T2) — наполнения ещё нет, её зуб под
  `xfail(strict=True)`; «Качество» (ТЗ-73 T3) — маркер снят ТЗ-97 Q2,
  потому что канал владения стал стадией 4/6 обычного пути и строки
  governance показывают цвет, слово причины и команду закрытия.
"""
from __future__ import annotations

import os
import sqlite3
from types import SimpleNamespace

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS = os.path.join(REPO, "tests/data/edgar/company_tickers.json")
FACTS = os.path.join(REPO, "tests/data/edgar/companyfacts_m3_AAPL.json")
SUBS = os.path.join(REPO, "tests/data/edgar/submissions_aapl.json")
TIMES = os.path.join(REPO, "tests/data/twelvedata/"
                           "time_series_AAPL_1day_trimmed.json")
SPLITS = os.path.join(REPO, "tests/data/twelvedata/splits_AAPL_full.json")
DIVS = os.path.join(REPO, "tests/data/twelvedata/dividends_AAPL_full.json")

# Значение-сенinel: если оно появится в надписи окна — утечка.
FAKE_TWELVEDATA_KEY = "R4-SENTINEL-KEY-9f2c"

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import rusterm.cli as cli  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.desktop import window as desktop_window  # noqa: E402
from rusterm.providers.edgar import EdgarProvider  # noqa: E402
from rusterm.providers.twelvedata import TwelveDataProvider  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths  # noqa: E402
from rusterm.store.repos import RepoRegistry  # noqa: E402
from tests.edgar_fixtures import ownership_body  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (QApplication, QComboBox,  # noqa: E402
                               QLabel, QTableWidget, QTreeWidget, QWidget)

# Числа этого прогона — зафиксированы прогоном R3/R4 (тот же путь, те же
# ответы); расхождение means кто-то изменил разбор или снапшот.
# ТЗ-97 Q7: валовая прибыль стала мерой словаря — строк 28 → 29, и у AAPL
# подан GrossProfit, поэтому мер со значением 10 → 11 (замер прогона).
MEASURE_ROWS = 29
VALUED_NOW = 20


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _edgar_transport(url, headers):
    if "company_tickers" in url:
        return 200, _read(TICKERS), {}
    if "companyfacts" in url:
        return 200, _read(FACTS), {}
    if "submissions" in url:
        return 200, _read(SUBS), {}
    if "/Archives/edgar/data/" in url:
        # ТЗ-97 Q2: стадия 4/6 тянет тела Forms 3/4/5 с диска; нет
        # записи = честный 404 (tests/edgar_fixtures.py).
        body = ownership_body(url)
        return (200, body, {}) if body is not None \
            else (404, b'{"ok": false}', {})
    return 404, b'{"ok": false}', {}


def _twelvedata_transport(url, headers):
    if "time_series" in url:
        return 200, _read(TIMES), {}
    if "/splits" in url:
        return 200, _read(SPLITS), {}
    if "/dividends" in url:
        return 200, _read(DIVS), {}
    return 404, b'{"status": "error"}', {}


def _widget(win, kind, name):
    found = win.findChild(kind, name)
    assert found is not None, f"в окне нет виджета {name!r}"
    return found


def _company_item(tree, ticker):
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        for j in range(top.childCount()):
            child = top.child(j)
            payload = child.data(0, Qt.ItemDataRole.UserRole)
            if payload and payload[0] == "company" \
                    and ticker in child.text(0):
                return child
    return None


@pytest.fixture(scope="module")
def hour(tmp_path_factory, qapp):
    """Час пользователя один на файл: путь R2, затем открытое окно с
    выбранной бумагой. Тесты читают содержимое, не пересобирая базу.

    Окружение живёт столько же, сколько окно: панель ключей читается при
    перерисовке, а не при старте пути, — снять переменные раньше значило
    бы проверять окно, открытое без ключей.
    """
    root = tmp_path_factory.mktemp("hour") / "app"
    mp = pytest.MonkeyPatch()

    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate,
                                      api_key=FAKE_TWELVEDATA_KEY,
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

    conn = None
    try:
        assert cli.main(["--root", str(root), "follow", "AAPL"]) == 0, \
            "путь R2 не доехал до снапшота"
        paths = AppPaths.from_root(root)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        conn.row_factory = sqlite3.Row
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
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


# ── «Компания» ──────────────────────────────────────────────────────────

def _data_role():
    """UserRole, в котором колонка 0 хранит сырой концепт (ТЗ-111 U2)."""
    from PySide6.QtCore import Qt as _Qt
    return _Qt.ItemDataRole.UserRole


def _data_rows(table):
    """ТЗ-111 U2: строки данных таблицы — те, у кого колонка 0 несёт
    UserRole с сырым концептом; шапки разделов пропускаются."""
    role = _data_role()
    return [r for r in range(table.rowCount())
            if table.item(r, 0) is not None
            and table.item(r, 0).data(role) is not None]


def test_company_tab_shows_the_snapshot_numbers(hour):
    table = _widget(hour.win, QTableWidget, "table")
    data_rows = _data_rows(table)
    assert len(data_rows) == MEASURE_ROWS
    headers = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    assert headers[0] == "мера" and headers[1] == "сейчас"
    texts = {(table.item(r, 0).text() if table.item(r, 0) else "")
             for r in data_rows}
    assert {"Оборачиваемость активов", "Дивидендная доходность",
            "EBITDA"} <= texts

    empty = desktop_data.NO_DATA
    # ТЗ-111 U1: пустые меры показывают фразы словаря причин — считаем
    # ценными только строки, чья ячейка не «нет данных» и не фраза
    from rusterm.reasons_ru import REASONS_RU
    phrases = set(REASONS_RU.values())
    valued = [r for r in data_rows
              if table.item(r, 1)
              and table.item(r, 1).text() != empty
              and table.item(r, 1).text() not in phrases]
    assert len(valued) == VALUED_NOW
    # пустая мера показана словом, а не нулём и не молчанием (ТЗ-110 B1:
    # div_yield с дивидендами yahoo теперь считает — 0,32 %, не «нет»)
    assert table.item(next(
        r for r in data_rows
        if table.item(r, 0).text() == "Дивидендная доходность"),
        1).text() == "0,32 %"
    # ТЗ-111 U1: пустых мер нет как «нет данных» — они со фразами
    from rusterm.reasons_ru import REASONS_RU
    phrases = set(REASONS_RU.values())
    row = next(r for r in data_rows
               if table.item(r, 1) and table.item(r, 1).text() in phrases)
    assert table.item(row, 0).text(), "пустых мер нет — зуб не сработал"
    row = next(r for r in data_rows
               if table.item(r, 0).text() == "Оборачиваемость активов")
    assert table.item(row, 1).text() == "1,15×"


@pytest.mark.usefixtures("hour")
def test_company_tab_count_matches_the_snapshot_in_the_base(hour):
    """Число в таблице — не украшение окна: оно равно тому, что лежит в
    базе по последней мере этой бумаги (окно только рисует, ТЗ-81 B2)."""
    snapshot_id = hour.repos.snapshot.latest_snapshot_id("US-AAPL")
    assert snapshot_id is not None
    measures = hour.repos.snapshot.get_measures(snapshot_id)
    valued = [m for m in measures
              if m["value"] is not None and str(m["value"]) != ""]
    assert len(valued) == VALUED_NOW
    table = _widget(hour.win, QTableWidget, "table")
    # ТЗ-111 U2: строки таблицы = меры + шапки разделов
    from rusterm.measures_ru import measure_section
    sections = {measure_section(m["concept"]) for m in measures}
    assert table.rowCount() == len(measures) + len(sections)


def test_company_tab_source_panel_names_the_row_and_points_at_raw(hour):
    table = _widget(hour.win, QTableWidget, "table")
    panel = _widget(hour.win, QLabel, "source_panel")
    box = _widget(hour.win, QComboBox, "measure_box")
    assert box.count() == MEASURE_ROWS
    assert sum(1 for i in range(box.count())
               if desktop_data.NO_DATA in box.itemText(i)) \
        == MEASURE_ROWS - VALUED_NOW

    # ТЗ-111 U2: строки данных опознаются по UserRole (шапки разделов
    # пропускаются), имя в колонке 0 — русское
    from rusterm.reasons_ru import REASONS_RU
    phrases = set(REASONS_RU.values())
    first_valued = next(r for r in _data_rows(table)
                        if table.item(r, 1)
                        and table.item(r, 1).text() != desktop_data.NO_DATA
                        and table.item(r, 1).text() != "0,32 %"
                        and table.item(r, 1).text() not in phrases)
    measure = table.item(first_valued, 0).text()
    value = table.item(first_valued, 1).text()
    table.cellClicked.emit(first_valued, 1)
    text = panel.text()
    # панель источника зовёт меру сырым концептом (ТЗ-111 U1: сырое
    # живёт в панели), имя в таблице — русское
    raw_concept = table.item(first_valued, 0).data(
        _data_role())
    assert text.startswith(f"источник {raw_concept} "), text
    assert f"значение: {value}" in text
    assert "сырье: " in text
    # путь к сырью из панели существует — обещание «открыть исходник»
    # исполнимо, а не нарисовано (период входа идёт той же строкой)
    raw = text.split("сырье: ", 1)[1].split("\n")[0]
    raw = raw.split(" (период входа ", 1)[0]
    assert os.path.isfile(raw), raw
    assert "период входа " in text


# ── «Настройки» ─────────────────────────────────────────────────────────

def test_settings_tab_shows_keys_without_values(hour):
    keys = _widget(hour.win, QLabel, "keys_label").text()
    assert "RUSTERM_SEC_UA: найден" in keys
    assert "RUSTERM_TWELVEDATA_KEY: найден" in keys
    assert FAKE_TWELVEDATA_KEY not in keys
    # утечка проверяется по всему окну: и по надписям, и по ячейкам
    shown = [widget.text() for widget in hour.win.findChildren(QWidget)
             if hasattr(widget, "text")]
    for table in hour.win.findChildren(QTableWidget):
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                item = table.item(r, c)
                if item is not None:
                    shown.append(item.text())
    for text in shown:
        assert FAKE_TWELVEDATA_KEY not in (text or "")


def test_settings_tab_limits_are_the_provider_registry(hour):
    from rusterm.providers import all_host_limits
    limits = _widget(hour.win, QTableWidget, "limits_table")
    rows = {limits.item(r, 0).text(): (limits.item(r, 1).text(),
                                       limits.item(r, 2).text())
            for r in range(limits.rowCount())}
    registry = {l.host: l for l in all_host_limits().values()}
    assert set(rows) == set(registry)
    for host, limit in registry.items():
        assert rows[host] == (str(limit.nightly_max), str(limit.per_second))


def test_settings_tab_names_the_catalog_and_the_db_file(hour):
    label = _widget(hour.win, QLabel, "catalog_label").text()
    assert str(hour.root) in label
    assert "rusterm.db" in label
    assert "байт" in label


# ── «Отрасль» и «Качество»: наполнение за ТЗ-73 ────────────────────────

def test_industry_tab_today_says_why_it_is_empty(hour):
    """Не xfail: сегодня вкладка обязана называть причину словами, а не
    молчать (правило ТЗ-73 T1 уже в силе для этого текста)."""
    peer = _widget(hour.win, QLabel, "peer_line").text()
    assert "нет peer set" in peer
    assert _widget(hour.win, QTableWidget, "industry_table").rowCount() == 0


@pytest.mark.xfail(strict=True,
                   reason="ТЗ-73 T2: сектор и peer set должны появляться "
                          "обычным путём; после него «Отрасль» обязана "
                          "показывать таблицу, а не сообщение")
def test_industry_tab_shows_a_peer_table_after_the_usual_path(hour):
    peer = _widget(hour.win, QLabel, "peer_line").text()
    members = _widget(hour.win, QLabel, "members_line").text()
    table = _widget(hour.win, QTableWidget, "industry_table")
    assert "нет peer set" not in peer
    assert "участники (" in members
    assert table.rowCount() > 0


def test_quality_tab_coverage_is_measured_not_declared(hour):
    label = _widget(hour.win, QLabel, "coverage_label").text()
    truth = desktop_data.measure_coverage(hour.repos, "US-AAPL")
    assert str(truth["green"]) in label.split("из ")[0]
    assert f"из {truth['total']}" in label


def test_governance_rows_carry_words_and_a_door_after_the_usual_path(hour):
    """ТЗ-97 Q2 (ТЗ-73 T3, правило P8): выпускной зуб ТЗ-73 — маркер
    `xfail(strict=True)` снят, канал владения стал стадией 4/6.

    Про обычный путь на записанной ленте AAPL: формы 3/4/5 собраны,
    одна сделка разобрана, поэтому `insider_net` больше НЕ имеет права
    врать «источник ещё не обойдён» — он называет, что собрано и чего
    не хватает. Цвет на этой фикстуре остаётся серым: знаменатель
    `market_cap_total` считается от котировок и числа акций, которых в
    записанном companyfacts нет; что цвет появляется, когда
    знаменатель есть, утверждает
    `tests/test_task97_q2_governance_words.py`.
    """
    from rusterm.core.governance import grey_reason_text

    table = _widget(hour.win, QTableWidget, "governance_table")
    assert table.rowCount() == 5, "governance — пять строк, без свёртки"
    assert table.columnCount() == 4
    not_collected = grey_reason_text("no_data:not_collected")
    for row in range(table.rowCount()):
        indicator = table.item(row, 0).text()
        colour = table.item(row, 1).text()
        note = table.item(row, 2).text()
        closing = table.item(row, 3).text()
        assert indicator and colour, f"строка {row}: пусто"
        # «расшифровка» и «чем закрывается» заполнены словами, а не
        # голым кодом причины: пустая ячейка под запретом (P8)
        assert note and "не описана" not in note, f"{indicator}: {note}"
        assert closing.startswith("rusterm "), f"{indicator}: {closing}"
        argv = closing.split()[1:]
        parsed = cli._build_parser().parse_args(argv)
        assert parsed.command == argv[0], closing
        assert "US-AAPL" in argv, f"дверь не называет бумагу: {closing}"
    # ТЗ-111 U2: колонка «показатель» — имена словами
    from rusterm.measures_ru import GOVERNANCE_RU
    insider = [row for row in range(table.rowCount())
               if table.item(row, 0).text()
               == GOVERNANCE_RU["insider_net"]]
    assert len(insider) == 1
    note = table.item(insider[0], 2).text()
    assert note != not_collected, (
        "канал владения обошёл путь, а строка всё ещё говорит "
        "«источник не обойдён»")
    # ТЗ-110 B1: с котировками yahoo в базе знаменатель market_cap_total
    # считается, и insider_net доезжает до жёлтой оценки §4 (окно около
    # нуля) — слова из того же словаря, «не описана» исключено выше
    assert table.item(insider[0], 1).text() == "yellow", note
    assert note == grey_reason_text("within_pm_0.1pct"), note
