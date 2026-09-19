"""TASK-C5: списки наблюдения в окне — переключение, правка через
ядро, подтверждение и аудит массовой операции.

Слой данных тестируется без Qt: добавление/удаление ходит теми же
методами репозитория, что CLI watchlist add/remove (новая версия с
полным составом, append-only — прежняя версия остаётся), аудит — та
же таблица audit_log. Оконные тесты — offscreen, диалоги заглушены.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json  # noqa: E402
import sqlite3  # noqa: E402

import pytest  # noqa: E402

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer, Listing,  # noqa: E402
                                 RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for iid, ticker, market in (("US-AAA", "AAA", "NASDAQ"),
                                ("US-BBB", "BBB", "NASDAQ"),
                                ("CA-CNQ", "CNQ", "NASDAQ")):
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", f"Corp {ticker}", market[:2], None, None,
            "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{iid}", iid, market, "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{iid}", ticker, "2000-01-01", None, None, None)
    repos.watchlist.create_watchlist("wl-main", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-main", 1, "seed",
                                      None)
    for iid in ("US-AAA", "US-BBB"):
        repos.watchlist.add_member(vid, iid, None)
    yield repos, conn
    conn.close()


def _audit_rows(conn, action=None):
    rows = conn.execute(
        "SELECT action, payload FROM audit_log ORDER BY rowid"
    ).fetchall()
    if action:
        rows = [r for r in rows if r["action"] == action]
    return rows


# ── C5.1: списки видны и переключаются ──────────────────────────────────

def test_watchlist_choices_carry_version_and_count(env):
    repos, _ = env
    choices = desktop_data.watchlist_choices(repos)
    assert len(choices) == 1
    assert choices[0]["watchlist_id"] == "wl-main"
    assert choices[0]["version"] == 1
    assert choices[0]["member_count"] == 2


# ── C5.2: правка через ядро, старая версия доступна ─────────────────────

def test_add_resolves_ticker_new_version_and_audit(env):
    repos, conn = env
    outcome = desktop_data.add_instrument(repos, "wl-main", "CNQ",
                                          "CA")
    assert outcome["ok"] and outcome["instrument_id"] == "CA-CNQ"
    assert outcome["version"] == 2
    members = {m["instrument_id"]
               for m in repos.watchlist.members("wl-main")}
    assert members == {"US-AAA", "US-BBB", "CA-CNQ"}
    # прежняя версия жива и не изменилась
    old = {m["instrument_id"]
           for m in repos.watchlist.members("wl-main", version=1)}
    assert old == {"US-AAA", "US-BBB"}
    actions = [r["action"] for r in _audit_rows(conn)]
    assert actions.count("watchlist_add") == 1


def test_add_unknown_ticker_says_words_changes_nothing(env):
    repos, conn = env
    outcome = desktop_data.add_instrument(repos, "wl-main", "NOPE",
                                          "XNAS")
    assert not outcome["ok"]
    assert "нет" in outcome["message"]
    assert repos.watchlist.current_version("wl-main")["version"] == 1
    assert _audit_rows(conn, "watchlist_add") == []


def test_remove_then_restore_previous_version(env):
    """Удаление — новая версия без бумаги; прежняя доступна; «вернуть
    прежнюю версию» — новая версия поверх копии старой."""
    repos, conn = env
    outcome = desktop_data.remove_instruments(repos, "wl-main",
                                              ["US-AAA"])
    assert outcome["ok"] and outcome["version"] == 2
    members = {m["instrument_id"]
               for m in repos.watchlist.members("wl-main")}
    assert members == {"US-BBB"}
    previous = {m["instrument_id"]
                for m in repos.watchlist.members("wl-main", version=1)}
    assert previous == {"US-AAA", "US-BBB"}
    # вернуть прежнюю версию: новая версия копией состава версии 1
    current = repos.watchlist.current_version("wl-main")
    restore_id = repos.watchlist.new_version(
        "wlv-restore", "wl-main", current["version"] + 1, "rollback",
        None)
    repos.watchlist.copy_members(
        repos.watchlist._version_id("wl-main", 1), restore_id)
    restored = {m["instrument_id"]
                for m in repos.watchlist.members("wl-main")}
    assert restored == previous
    assert _audit_rows(conn, "watchlist_remove")


# ── C5.3: массовая операция — подтверждение и строка аудита ────────────

def test_bulk_remove_demands_confirmation_first(env):
    repos, conn = env
    outcome = desktop_data.remove_instruments(
        repos, "wl-main", ["US-AAA", "US-BBB"])
    assert not outcome["ok"] and outcome["needs_confirm"]
    assert "подтвердите" in outcome["message"]
    # ничего не изменилось: ни версии, ни состава, ни аудита
    assert repos.watchlist.current_version("wl-main")["version"] == 1
    assert len(repos.watchlist.members("wl-main")) == 2
    assert _audit_rows(conn, "watchlist_bulk_remove") == []


def test_confirmed_bulk_remove_writes_one_audit_line(env):
    repos, conn = env
    outcome = desktop_data.remove_instruments(
        repos, "wl-main", ["US-AAA", "US-BBB"], confirmed=True)
    assert outcome["ok"] and outcome["version"] == 2
    assert repos.watchlist.members("wl-main") == []
    rows = _audit_rows(conn, "watchlist_bulk_remove")
    assert len(rows) == 1
    payload = json.loads(rows[0]["payload"])
    assert payload["count"] == 2
    assert sorted(payload["instruments"]) == ["US-AAA", "US-BBB"]
    assert _audit_rows(conn, "watchlist_remove") == []


def test_single_remove_needs_no_confirmation(env):
    repos, conn = env
    outcome = desktop_data.remove_instruments(repos, "wl-main",
                                              ["US-AAA"])
    assert outcome["ok"]
    assert _audit_rows(conn, "watchlist_bulk_remove") == []


# ── окно: переключатель и версия видны; очистка подтверждается ──────────

def test_window_shows_switcher_version_and_confirm(env, monkeypatch,
                                                   tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import (QApplication, QComboBox, QLabel,
                                   QMessageBox, QPushButton)
    from rusterm.desktop import window as desktop_window

    QApplication.instance() or QApplication([])
    repos, conn = env
    window = desktop_window._build_window(repos, paths := tmp_path / "app",
                                          "wl-main")
    window.close()
    box = window.findChild(QComboBox, "watchlist_box")
    label = window.findChild(QLabel, "watchlist_label")
    assert box is not None and box.count() == 1
    assert "v1" in label.text() and "2 бумаг" in label.text()

    clear_button = window.findChild(QPushButton,
                                    "watchlist_clear_button")
    assert clear_button is not None

    asked = {}

    def fake_question(*a, **k):
        asked["asked"] = True
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(desktop_window.QMessageBox, "question",
                        staticmethod(fake_question))
    clear_button.click()
    assert asked.get("asked")
    assert repos.watchlist.members("wl-main") == []
    assert "v2" in label.text()
    assert len(_audit_rows(conn, "watchlist_bulk_remove")) == 1
