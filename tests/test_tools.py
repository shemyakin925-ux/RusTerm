"""TASK-16 D2: четыре read-only инструмента и страж реестра.

Страж — суть пункта: набор имён реестра закреплён РОВНО четырьмя;
добавление пятого инструмента без_TASK-пункта красит suite. После
вызова каждого инструмента по очереди sha256 файла базы не меняется —
read-only проверяется механически, а не обещанием.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
import uuid

from rusterm.core import tools
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    Listing,
    PeerSetRepo,
    RepoRegistry,
)


def _registry():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Issuer 1", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "ins1", "i1", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l1", "ins1", "US", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l1", "TEST", "2020-01-01", None, None, None)
    peers = PeerSetRepo(conn)
    # ТЗ-22 J6: инструмент разрешает сектор по id peer set — как и
    # cmd_industry; раньше ответ был захардкоженной пустотой
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("psv1", "ins1", None)
    repos.snapshot.create_snapshot("s1", "ins1", 1, "2024-12-31",
                                   None, "none", "ready")
    return tmpdir, conn, paths, repos


def test_registry_key_set_is_exactly_the_four_tools():
    assert set(tools.TOOLS) == {
        "resolve_ticker", "list_industry_instruments",
        "get_peer_set", "get_snapshot_block"}


def test_calling_every_tool_leaves_the_database_byte_identical():
    tmpdir, conn, paths, repos = _registry()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        db_path = str(paths.db_path)

        def sha() -> str:
            return hashlib.sha256(open(db_path, "rb").read()).hexdigest()

        before = sha()
        calls = [
            ("resolve_ticker",
             dict(ticker="TEST", market="US", as_of="2026-09-09")),
            ("list_industry_instruments",
             dict(industry="tankers", filters=None)),
            ("get_peer_set", dict(instrument_id="ins1")),
            ("get_snapshot_block",
             dict(instrument_id="ins1", block="fundamentals")),
        ]
        conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        repos = RepoRegistry(conn, paths)
        for name, kwargs in calls:
            outcome = tools.TOOLS[name](repos, **kwargs)
            assert outcome["outcome"] == "resolved", (name, outcome)
        after = sha()
        assert before == after, (
            "вызов read-only инструмента изменил файл базы")

        # негативные ветки отвечают значениями, не исключениями
        assert tools.TOOLS["resolve_ticker"](
            repos, ticker="nope", market="US",
            as_of="2026-09-09")["outcome"] == "not_found"
        assert tools.TOOLS["get_peer_set"](
            repos, instrument_id="ghost")["outcome"] == "not_found"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_guard_is_mechanical_not_a_promise():
    """Страж держит ровно четыре имени: шестая запись в реестре —
    провал suite. Проверяется подменой копии реестра, мутация модуля
    не нужна."""
    extra = dict(tools.TOOLS)
    extra["delete_everything"] = lambda repos, **kw: {}
    # симуляция будущего нарушения: набор из пяти имён не равен пину
    pinned = {"resolve_ticker", "list_industry_instruments",
              "get_peer_set", "get_snapshot_block"}
    assert set(extra) != pinned
    assert set(tools.TOOLS) == pinned
