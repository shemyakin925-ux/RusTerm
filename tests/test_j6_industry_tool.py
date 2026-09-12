"""ТЗ-22 J6: инструмент отрасли перестаёт врать пустотой.

list_industry_instruments разрешает сектор через peer set (источник
M7): непустой список для сектора с участниками, документированные
пустые ответы для сектора без участников; версия набора и as_of — в
ответе. Read-only: тест байт-идентичности базы из test_tools
продолжает проходить.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core import tools
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, PeerSetRepo, \
    RepoRegistry


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for i, iid in enumerate(("ins1", "ins2", "ins3")):
        repos.instrument.upsert_issuer(Issuer(
            f"i{i}", f"Issuer {i}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i{i}", None, "common", "active", None))
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, "2024-12-31",
                                       None, "none", "ready")
    peers = PeerSetRepo(conn)
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("tv1", "tankers", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for iid in ("ins1", "ins2", "ins3"):
        peers.add_member("tv1", iid, None)
    peers.create_peer_set("empty", "industry", "empty-sector")
    peers.add_version("ev1", "empty", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    yield repos
    conn.close()


def test_sector_with_members_returns_real_instruments(env):
    answer = tools.list_industry_instruments(
        env, industry="tankers", filters={"as_of": "2025-01-01"})
    assert answer["outcome"] == "resolved"
    assert answer["instrument_ids"] == ["ins1", "ins2", "ins3"]
    assert answer["version"] == 1
    assert answer["peer_set_version_id"] == "tv1"
    assert answer["as_of"] == "2025-01-01"
    assert answer["snapshots"]["ins1"] == "s-ins1"


def test_unknown_sector_is_not_found(env):
    answer = tools.list_industry_instruments(
        env, industry="ghosts", filters={"as_of": "2025-01-01"})
    assert answer["outcome"] == "not_found"
    assert answer["instrument_ids"] == []


def test_known_sector_without_version_at_date_resolves_empty(env):
    answer = tools.list_industry_instruments(
        env, industry="tankers", filters={"as_of": "2020-01-01"})
    assert answer["outcome"] == "resolved"
    assert answer["instrument_ids"] == []
    assert answer["note"] == "no_version_at_date"
    assert answer["version"] is None


def test_no_industry_source_constant_is_gone():
    """NO_INDUSTRY_SOURCE исчез из кода: источник отрасли существует
    с M7; выжившей ветки, которую надо объяснять, тоже нет."""
    assert not hasattr(tools, "NO_INDUSTRY_SOURCE")
    assert "NO_INDUSTRY_SOURCE" not in __import__("inspect").getsource(
        tools)
