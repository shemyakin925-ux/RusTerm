"""TASK-C5: списки наблюдения — правка через те же двери, что CLI.

Переключение списков, правка состава новой версией (история не
переписывается), откат как создание версии со старым составом,
строка аудита у каждой правки (читается из таблицы audit_log напрямую
— тестам SQL разрешён, приёмка ограничивает только rusterm/).
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.desktop import actions
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    repos.watchlist.add_member("wlv-1", "US-AAA", None)
    repos.watchlist.add_member("wlv-1", "US-BBB", None)
    repos.watchlist.create_watchlist("wl-2", "spare", None, None)
    repos.watchlist.new_version("wlv-2", "wl-2", 1, "seed", None)
    for iid, ticker in (("US-AAA", "AAA"), ("US-BBB", "BBB")):
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", ticker * 3, "US", None, None, "us-gaap",
            "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{ticker}", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            f"l-{iid}", iid, "NASDAQ", "USD", 1, None, None))
        repos.instrument.add_ticker_history(
            f"l-{iid}", ticker, "2000-01-01", None, None, None)
    yield repos, paths
    conn.close()


def _members(repos, watchlist_id):
    return sorted(m["instrument_id"] for m
                  in repos.watchlist.members(watchlist_id))


def _audit_rows(repos, action):
    return repos.conn.execute(
        "SELECT action, target, confirmed FROM audit_log"
        " WHERE action=?", (action,)).fetchall()


def test_overview_lists_watchlists_with_version(env):
    repos, _ = env
    overview = actions.watchlists_overview(repos)
    names = {o["watchlist_id"]: o for o in overview}
    assert set(names) == {"wl-1", "wl-2"}
    assert names["wl-1"]["version"] == 1
    assert names["wl-1"]["member_count"] == 2


def test_add_creates_new_version_and_audit(env):
    repos, _ = env
    version = actions.watchlist_add(repos, "wl-1", "US-CCC")
    assert version == 2
    assert _members(repos, "wl-1") == ["US-AAA", "US-BBB", "US-CCC"]
    # прежняя версия доступна без изменений (T10/T11)
    assert [m["instrument_id"] for m
            in repos.watchlist.members("wl-1", version=1)] == \
        ["US-AAA", "US-BBB"]
    rows = _audit_rows(repos, "watchlist_add")
    assert len(rows) == 1 and rows[0]["confirmed"] == 1


def test_remove_creates_version_without_instrument(env):
    repos, _ = env
    version = actions.watchlist_remove(repos, "wl-1", "US-BBB")
    assert version == 2
    assert _members(repos, "wl-1") == ["US-AAA"]
    assert _audit_rows(repos, "watchlist_remove")


def test_remove_then_rollback_restores_previous_version(env):
    """«Удалил и вернул прежнюю версию»: откат создаёт НОВУЮ версию
    с составом старой — история не переписывается (C5.2)."""
    repos, _ = env
    actions.watchlist_remove(repos, "wl-1", "US-BBB")
    result = actions.watchlist_rollback(repos, "wl-1", 1)
    assert result["version"] == 3
    assert result["action"] == "rollback:1"
    assert _members(repos, "wl-1") == ["US-AAA", "US-BBB"]
    # все три версии остались на месте
    versions = actions.watchlist_versions(repos, "wl-1")
    assert [v["version"] for v in versions] == [1, 2, 3]
    rows = _audit_rows(repos, "watchlist_rollback")
    assert len(rows) == 1 and rows[0]["confirmed"] == 1


def test_versions_list_known_versions_only(env):
    repos, _ = env
    assert [v["version"] for v
            in actions.watchlist_versions(repos, "wl-1")] == [1]
    assert actions.watchlist_versions(repos, "wl-missing") == []


def test_add_unknown_list_is_words_not_crash(env):
    repos, _ = env
    with pytest.raises(ValueError) as err:
        actions.watchlist_add(repos, "wl-missing", "US-AAA")
    assert "wl-missing" in str(err.value)
