"""ТЗ-95 F1: старая схема — слова, а не падение окна.

Замер на машине пользователя (собранный `.app`, каталог `~/.rusterm` со
схемой 44, запуск двойным щелчком): окно не появилось, терминала рядом
не было, а прямой запуск бинарника показал причину —

    File "rusterm/desktop/window.py", line 1002, in _build_window
        repaint_chat_usage()
    File "rusterm/desktop/data.py", line 913, in llm_usage_line
        totals = repos.chat_transcript.calls_totals()
    sqlite3.OperationalError: no such table: chat_transcript

У запуска из Finder нет окружения терминала, поэтому каталог берётся по
правилу 4 (`~/.rusterm`) и это может быть база, отставшая от кода.
Мигрировать её окно не вправе (ADR-0023: окно только читает), значит оно
обязано сказать словами, какая схема открылась и какой командой её поднять.

Фикстура — НАСТОЯЩАЯ база схемы 44, собранная кодом истории (тот же
файл, что читает test_upgrade_path): 1 инструмент, 1 список с 1
участником, снапшот и 6 фактов. На ней же проверяется «читаемо то, что
читаемо»: боковая панель показывает инструмент, шапка — номер схемы,
молчат словами только те двери, чьей таблицы в схеме ещё нет.
"""
from __future__ import annotations

import gzip
import os
import shlex
import sqlite3
import types
from pathlib import Path

import pytest

from rusterm import env as env_module
from rusterm.desktop import data as desktop_data
from rusterm.store.db import (apply_migrations, current_schema_version,
                              _SCHEMA_VERSION)
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import RepoRegistry

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (QApplication, QComboBox,  # noqa: E402
                               QLabel, QTreeWidget)

FIXTURE = (Path(__file__).resolve().parents[1] / "tests" / "data" /
           "upgrade" / "schema44.sqlite.gz")

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


def _sandbox(tmp_path, monkeypatch) -> None:
    """HOME и env-файл — песочные: ни одно правило не читает то, что
    лежит у разработчика, и ключ модели сюда не заглянет."""
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "empty.env").write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "empty.env"))
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def stale(tmp_path, monkeypatch):
    """Каталог с базой схемы 44 (база отсталась от кода на одну
    миграцию — ровно случай пользователя)."""
    _sandbox(tmp_path, monkeypatch)
    root = tmp_path / "stale44"
    root.mkdir()
    (root / "rusterm.db").write_bytes(gzip.open(FIXTURE, "rb").read())
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = _connect(paths)
    repos = RepoRegistry(conn, paths)
    assert current_schema_version(conn) == 44, "фикстура поехала"
    assert 44 < _SCHEMA_VERSION
    try:
        yield repos, conn, paths
    finally:
        conn.close()


def _label(window, name: str) -> QLabel:
    label = window.findChild(QLabel, name)
    assert label is not None, f"виджет {name} не найден"
    return label


def _argv_of(notice: str) -> list[str]:
    """Хвост строки — команда, как её наберут в терминале. Парсер CLI
    ждёт аргументы без имени программы; разбор здесь — проверка, что
    строка исполнима, а не оформлена красиво."""
    tokens = shlex.split(notice.split("обновите: ", 1)[1])
    assert tokens[0] == "rusterm", tokens
    return tokens[1:]


# ── 1. строка словами ────────────────────────────────────────────────────

def test_the_notice_names_the_catalog_both_versions_and_the_command(
        stale):
    """Одна строка: каталог, заставшая схема, нужная программе и
    исполнимая команда. Числа берутся из fixtures и из store, а не с
    потолка: «44» здесь — схема базы, «_SCHEMA_VERSION» — число, которое
    окно ждёт."""
    repos, _conn, paths = stale
    notice = desktop_data.header_info(repos)["schema_notice"]
    assert notice == (
        f"база в {paths.root} — схема 44, программе нужна "
        f"{_SCHEMA_VERSION}; обновите: rusterm --root "
        f"{shlex.quote(str(paths.root))} init")
    assert _argv_of(notice) == ["--root", str(paths.root), "init"]


def test_a_current_base_has_nothing_to_say(qapp, tmp_path, monkeypatch):
    """Строка — про отставание, а не постоянная подпись шапки: на
    актуальной базе её нет, и ряд под шапкой пуст."""
    _sandbox(tmp_path, monkeypatch)
    root = tmp_path / "fresh"
    root.mkdir()
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    try:
        assert current_schema_version(conn) == _SCHEMA_VERSION
        assert desktop_data.header_info(repos)["schema_notice"] is None
        from rusterm.desktop import window as desktop_window
        window = desktop_window._build_window(repos, paths, None, 1)
        try:
            assert _label(window, "schema_notice").text() == ""
            assert _label(window, "schema_notice").isHidden()
        finally:
            window.close()
    finally:
        conn.close()


# ── 2. окно строится и не мигрирует ─────────────────────────────────────

def test_the_window_builds_on_the_stale_base_and_shows_the_notice(
        qapp, stale):
    """Окно строится (offscreen), строка про схему видна, исключений нет.
    На нынешнем коде тест краснеет в repaint_chat_usage —
    `sqlite3.OperationalError: no such table: chat_transcript`."""
    from rusterm.desktop import window as desktop_window
    repos, _conn, paths = stale
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    try:
        label = _label(window, "schema_notice")
        assert not label.isHidden(), "строка спрятана — её не видно"
        assert label.text() == \
            desktop_data.header_info(repos)["schema_notice"]
        # читаемо то, что читаемо: боковая панель показала инструмент
        assert window.findChild(QTreeWidget, "tree").topLevelItemCount() \
            >= 1, "на отставшей базе не показался ни один инструмент"
    finally:
        window.close()


def test_the_window_does_not_migrate_the_base(qapp, stale):
    """Окно только называет команду (ADR-0023): после постройки окна на
    отставшей базе схема остаётся 44."""
    from rusterm.desktop import window as desktop_window
    repos, conn, paths = stale
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    window.close()
    assert current_schema_version(conn) == 44


# ── 3. ни одна стартовая дверь не бросает ───────────────────────────────

def test_every_door_the_window_calls_at_startup_answers_without_raising(
        qapp, stale, monkeypatch):
    """Список дверей не переписывается по памяти: каждая функция слоя
    данных обёрнута, окно построено, и отчёт называет то, что окно
    действительно позвало. Обёртка обязана была заметить обе двери
    разговоров — иначе тест бессилен."""
    from rusterm.desktop import window as desktop_window
    repos, _conn, paths = stale
    called: list[str] = []
    raised: list[str] = []

    def wrap(name: str, fn):
        def door(*args, **kwargs):
            try:
                out = fn(*args, **kwargs)
            except Exception as exc:
                raised.append(f"{name} — {type(exc).__name__}: {exc}")
                raise
            called.append(name)
            return out
        return door

    for name in dir(desktop_data):
        attr = getattr(desktop_data, name)
        if not isinstance(attr, types.FunctionType) or \
                name.startswith("_"):
            continue
        monkeypatch.setattr(desktop_data, name, wrap(name, attr))
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    window.close()
    seen = sorted(set(called))
    assert not raised, f"двери стартового пути бросают: {raised}"
    assert {"llm_usage_line", "chat_sessions", "header_info"} <= set(seen), \
        f"обёртка не увидела двери разговоров: {seen}"


# ── 4. команда из строки исполнима и поднимает схему ────────────────────

def test_the_command_the_window_names_is_parseable_and_updates_the_base(
        stale, capsys):
    """Строка ведёт себя как инструкция: команда разбирается парсером
    CLI, её исполнение поднимает схему до нужной — и строка уходит."""
    from rusterm.cli import _build_parser, main as cli_main
    repos, conn, paths = stale
    argv = _argv_of(desktop_data.header_info(repos)["schema_notice"])
    parsed = _build_parser().parse_args(argv)
    assert (parsed.root, parsed.command) == (str(paths.root), "init")
    assert cli_main(argv) == 0, capsys.readouterr().out
    assert current_schema_version(conn) == _SCHEMA_VERSION
    assert desktop_data.header_info(repos)["schema_notice"] is None


def test_after_the_update_the_same_doors_read_transcripts(stale):
    """Зубья: «нет таблицы» и «таблица есть» — разные ответы. После
    команды из строки записанный разговор виден обеим дверям, т. е.
    гвард отставшей схемы не превратился в вечное «—»."""
    from rusterm.cli import main as cli_main
    repos, _conn, paths = stale
    assert cli_main(_argv_of(
        desktop_data.header_info(repos)["schema_notice"])) == 0
    repos.chat_transcript.create_session("s-f1", "fake-model", None,
                                         1000.0, 2)
    assert [s["session_id"] for s in desktop_data.chat_sessions(repos)] == \
        ["s-f1"]
    assert "вызовы: 2" in desktop_data.llm_usage_line(repos)


# ── 5. что именно молчит словами ─────────────────────────────────────────

def test_the_transcript_doors_say_words_and_the_rest_still_reads(stale):
    """Двери разговоров на схеме 44 отвечают словами (пустой перечень и
    «вызовы: —»), остальные двери отдают настоящие строки базы."""
    repos, _conn, _paths = stale
    assert desktop_data.chat_sessions(repos) == []
    assert desktop_data.llm_usage_line(repos) == "вызовы: —"
    assert [c["ticker"] for c in
            desktop_data.sidebar_companies(repos, "wl1")] == ["DEMO"]
    assert desktop_data.watchlist_choices(repos)[0]["member_count"] == 1


def test_the_chat_box_offers_nothing_to_open_on_a_stale_base(qapp, stale):
    """Окно на отставшей базе не обещает разговоры, которых в схеме нет:
    в переключателе один заголовок, счётчик — словами, и при этом
    открыт."""
    from rusterm.desktop import window as desktop_window
    repos, _conn, paths = stale
    window = desktop_window._build_window(repos, paths, "wl1", 1)
    try:
        box = window.findChild(QComboBox, "chat_sessions_box")
        assert [box.itemText(i) for i in range(box.count())] == \
            ["прошлые разговоры"]
        assert _label(window, "llm_usage_label").text() == "вызовы: —"
    finally:
        window.close()
