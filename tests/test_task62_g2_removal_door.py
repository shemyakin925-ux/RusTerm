"""ТЗ-62 G2: массовое удаление ходит той же дверью, что одиночное.

copy_members_except принимает строку или список — дверь одна; десктоп
зовёт её для обоих случаев, CLI — для одиночного. Семантика версий не
изменилась: удалил три из пяти — одна новая версия, одна строка аудита.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.cli import main as cli_main
from rusterm.desktop import data as desktop_data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry,
                                 WatchlistRepo)


@pytest.fixture()
def five_members(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for n in range(5):
        ticker = f"T{n}"
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", f"Corp {ticker}", "US", None, None,
            "us-gaap", "USD"))
        iid = f"US-{ticker}"
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{iid}", iid, "NASDAQ", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{iid}", ticker, "2000-01-01", None, None, None)
    repos.watchlist.create_watchlist("wl-main", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-main", 1, "seed", None)
    for n in range(5):
        repos.watchlist.add_member(vid, f"US-T{n}", None)
    yield repos, conn
    conn.close()


def _audit_rows(conn, action):
    return conn.execute(
        "SELECT payload FROM audit_log WHERE action=?",
        (action,)).fetchall()


def test_bulk_remove_three_of_five_one_version_one_audit_row(
        five_members, capsys):
    repos, conn = five_members
    outcome = desktop_data.remove_instruments(
        repos, "wl-main", ["US-T0", "US-T1", "US-T2"], confirmed=True)
    assert outcome["ok"]
    assert outcome["removed"] == ["US-T0", "US-T1", "US-T2"]
    assert outcome["version"] == 2
    # состав — две оставшиеся
    members = {m["instrument_id"]
               for m in repos.watchlist.members("wl-main")}
    assert members == {"US-T3", "US-T4"}
    # версий всего две, аудит — одна строка массовой операции
    assert conn.execute(
        "SELECT COUNT(*) FROM watchlist_version").fetchone()[0] == 2
    bulk = _audit_rows(conn, "watchlist_bulk_remove")
    assert len(bulk) == 1
    assert not _audit_rows(conn, "watchlist_remove")


def test_single_remove_old_path_unchanged(five_members, capsys):
    """Старый одиночный путь: та же дверь со строкой — версия одна,
    аудит одной строкой watchlist_remove."""
    repos, conn = five_members
    outcome = desktop_data.remove_instruments(
        repos, "wl-main", ["US-T0"], confirmed=True)
    assert outcome["ok"]
    members = {m["instrument_id"]
               for m in repos.watchlist.members("wl-main")}
    assert len(members) == 4
    assert conn.execute(
        "SELECT COUNT(*) FROM watchlist_version").fetchone()[0] == 2
    assert len(_audit_rows(conn, "watchlist_remove")) == 1


def test_cli_single_remove_uses_the_same_door(five_members, capsys, tmp_path):
    """CLI remove — та же дверь copy_members_except: состав и версия
    совпадают с десктопным одиночным случаем."""
    repos, conn = five_members
    assert cli_main(["--root", str(tmp_path / "app"), "watchlist",
                     "remove", "wl-main", "--instrument", "US-T0"]) == 0
    members = {m["instrument_id"]
               for m in repos.watchlist.members("wl-main")}
    assert "US-T0" not in members and len(members) == 4
    assert len(_audit_rows(conn, "watchlist_remove")) == 1
