"""Тесты читающей стороны WatchlistRepo (TASK-7 T10).

Версия неизменяема: правка состава — новая версия; откат — тоже новая
версия, копирующая состав указанной. История не переписывается никогда.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pytest

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    WatchlistRepo,
)


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = type("R", (), {})()
    repos.instrument = InstrumentRepo(conn)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "N", "US", None, None, "us_gaap", "USD"))
    for ins in ("ins1", "ins2", "ins3"):
        repos.instrument.upsert_instrument(Instrument(
            ins, "i1", None, "common", "active", None))
    repos.watchlist = WatchlistRepo(conn)
    repos.watchlist.create_watchlist("w1", "Наблюдение", None, None)
    repos.watchlist.new_version("wv1", "w1", 1, "create", None)
    return tmpdir, conn, repos


def test_version_grows_with_each_edit():
    tmpdir, conn, repos = _setup()
    try:
        wl = repos.watchlist
        wl.add_member("wv1", "ins1", None)                       # версия 1
        wl.new_version("wv2", "w1", 2, "edit", None)
        wl.add_member("wv2", "ins2", None)                       # версия 2
        wl.new_version("wv3", "w1", 3, "edit", None)
        wl.add_member("wv3", "ins3", None)                       # версия 3

        current = wl.current_version("w1")
        assert current["version"] == 3
        # текущая версия — только ins3; версия 1 — только ins1
        assert [m["instrument_id"] for m in wl.members("w1")] == ["ins3"]
        assert [m["instrument_id"] for m in wl.members("w1", version=1)] == \
            ["ins1"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_rollback_creates_new_version_copying_old():
    tmpdir, conn, repos = _setup()
    try:
        wl = repos.watchlist
        wl.add_member("wv1", "ins1", "первый")                   # версия 1
        wl.new_version("wv2", "w1", 2, "edit", None)
        wl.add_member("wv2", "ins2", None)                       # версия 2
        wl.new_version("wv3", "w1", 3, "edit", None)
        wl.add_member("wv3", "ins3", None)                       # версия 3

        before_v1 = wl.members("w1", version=1)
        result = wl.rollback_to("w1", 1)
        assert result["version"] == 4
        assert result["action"] == "rollback:1"

        current = wl.current_version("w1")
        assert current["version"] == 4
        # состав версии 4 равен составу версии 1
        assert wl.members("w1") == before_v1 == [
            {"instrument_id": "ins1", "note": "первый",
             "added_at": before_v1[0]["added_at"]}]
        # версия 1 не изменилась до и после отката
        assert wl.members("w1", version=1) == before_v1
        # версия 3 на месте — ничего не удалено
        assert [m["instrument_id"] for m in wl.members("w1", version=3)] == \
            ["ins3"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_groups_and_filters_versioned_and_copied_on_rollback():
    tmpdir, conn, repos = _setup()
    try:
        wl = repos.watchlist
        wl.add_member("wv1", "ins1", None)
        wl.add_group("g1", "w1", 1, "Танкеры")
        wl.add_group_member("g1", "ins1")
        wl.set_filter("w1", 1, {"industry": "Maritime/Tanker"})

        assert wl.groups("w1")[0]["name"] == "Танкеры"
        assert wl.filters("w1") == [{"industry": "Maritime/Tanker"}]

        wl.new_version("wv2", "w1", 2, "edit", None)
        wl.set_filter("w1", 2, {"industry": "BigTech"})
        assert wl.filters("w1")[0]["industry"] == "BigTech"
        # версия 1 не изменилась
        assert wl.filters("w1", version=1) == [
            {"industry": "Maritime/Tanker"}]

        wl.rollback_to("w1", 1)
        assert wl.filters("w1")[0]["industry"] == "Maritime/Tanker"
        assert wl.groups("w1")[0]["instrument_ids"] == ["ins1"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_list_watchlists_reports_current_version_and_count():
    tmpdir, conn, repos = _setup()
    try:
        wl = repos.watchlist
        wl.add_member("wv1", "ins1", None)
        rows = wl.list_watchlists()
        assert rows == [{"watchlist_id": "w1", "name": "Наблюдение",
                         "version": 1, "member_count": 1}]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
