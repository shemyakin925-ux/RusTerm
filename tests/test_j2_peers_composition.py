"""ТЗ-22 J2: peer set знает, кого он держит — рынки, валюты и
single-market/mixed видны в composition, в `rusterm status` и в
инструменте get_peer_set. Пороги I6 не тронуты: это информация,
не фильтр. Члены набора и версии не меняются (golden не двигается).
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import rusterm.cli as cli
from rusterm.core.tools import get_peer_set
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    import os
    os.environ["RUSTERM_SEC_UA"] = "Synthetic Test j2.invalid"
    os.environ["RUSTERM_ENV_FILE"] = "/nonexistent/rusterm.env-for-tests"
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    # шесть участников: три US (USD) и три KR (KRW), у каждого факты
    for i, (iid, issuer, cur) in enumerate([
            ("US-A", "i0", "USD"), ("US-B", "i1", "USD"),
            ("US-C", "i2", "USD"), ("KR-D", "i3", "KRW"),
            ("KR-E", "i4", "KRW"), ("KR-F", "i5", "KRW")]):
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"Corp {i}", "US" if cur == "USD" else "KR", None,
            None, "us_gaap", cur))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, 'revenue', '2024-01-01',
               '2024-12-31', 'duration', '100', 'USD', ?,
               'as_reported', 'extracted', 's', '{}',
               'companyfacts.v1', 'ok', 0, 'revenue', 'provider')""",
            (f"f-{iid}", issuer, cur))
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps-mixed", "industry", "mixed")
    peers.add_version("v-mixed", "ps-mixed", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for iid in ("US-A", "US-B", "US-C", "KR-D", "KR-E", "KR-F"):
        peers.add_member("v-mixed", iid, None)
    peers.create_peer_set("ps-us", "industry", "us-only")
    peers.add_version("v-us", "ps-us", 1, "2024-01-01", None, "manual",
                      "v1", True, None, None)
    for iid in ("US-A", "US-B", "US-C"):
        peers.add_member("v-us", iid, None)
    return conn, repos, peers


def test_mixed_peer_set_reports_markets_and_currencies(env):
    conn, repos, peers = env
    comp = peers.composition("v-mixed")
    assert comp["markets"] == ["KR", "US"]
    assert comp["currencies"] == ["KRW", "USD"]
    assert comp["scope"] == "mixed"
    assert comp["members"] == ["KR-D", "KR-E", "KR-F",
                               "US-A", "US-B", "US-C"]


def test_single_market_set_unchanged_and_named(env):
    conn, repos, peers = env
    comp = peers.composition("v-us")
    assert comp["scope"] == "single-market"
    assert comp["markets"] == ["US"]
    assert comp["currencies"] == ["USD"]
    # члены и версия нетронуты: у версии тот же состав, что задан
    rows = conn.execute(
        """SELECT instrument_id FROM peer_set_member
           WHERE peer_set_version_id='v-us' ORDER BY instrument_id"""
    ).fetchall()
    assert [r[0] for r in rows] == ["US-A", "US-B", "US-C"]


def test_status_shows_composition(env, capsys, tmp_path, monkeypatch):
    conn, repos, peers = env
    # _open в cmd_status ожидает (paths, conn); подменяем целиком
    paths = AppPaths.from_root(tmp_path / "app")
    monkeypatch.setattr(cli, "_open", lambda root: (paths, conn))
    assert cli.main(["--root", str(paths.root), "status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_id = {p["peer_set_id"]: p for p in payload["peer_sets"]}
    assert by_id["ps-mixed"]["scope"] == "mixed"
    assert by_id["ps-mixed"]["markets"] == ["KR", "US"]
    assert by_id["ps-mixed"]["currencies"] == ["KRW", "USD"]
    assert by_id["ps-us"]["scope"] == "single-market"


def test_get_peer_set_tool_exposes_composition(env):
    conn, repos, peers = env
    answer = get_peer_set(repos, "US-A")
    assert answer["outcome"] == "resolved"
    assert answer["composition"]["scope"] == "mixed"
    assert answer["composition"]["markets"] == ["KR", "US"]
    # инструмент по-прежнему только читает: тот же состав при повторе
    again = get_peer_set(repos, "US-A")
    assert again["composition"] == answer["composition"]
