"""ТЗ-108 W4: сбор companyfacts вне refresh оставляет состояние
эмитента; первый refresh после него не планирует «первый сбор»."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rusterm.core.refresh import (companyfacts_last_filed, refresh_watchlist,
                                  remember_ingest)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

EDGAR = Path(__file__).resolve().parent / "data" / "edgar"


def _repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer("cik-320193", "Apple", "US",
                                          "320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAPL", "cik-320193", None, "common", "active", None))
    repos.watchlist.create_watchlist("wl", "w", None, None)
    v = repos.watchlist.new_version("wlv", "wl", 1, "seed", None)
    repos.watchlist.add_member(v, "US-AAPL", None)
    return repos


def test_last_filed_is_the_max_filed_date():
    raw = (EDGAR / "companyfacts_aapl.json").read_bytes()
    filed = [r["filed"] for t in json.loads(raw)["facts"].values()
             for c in t.values() for rows in c["units"].values()
             for r in rows if "filed" in r]
    assert companyfacts_last_filed(raw) == max(filed)
    assert companyfacts_last_filed(b"not json") is None


def test_refresh_after_ingest_is_not_a_first_collection(tmp_path):
    repos = _repos(tmp_path)
    raw = (EDGAR / "companyfacts_aapl.json").read_bytes()
    before = refresh_watchlist(repos, lambda cik: None, "wl",
                               "2026-10-01", dry_run=True)
    assert before[0].reason.startswith("первый сбор")
    assert remember_ingest(repos, "cik-320193", raw) is True
    assert remember_ingest(repos, "cik-320193", raw) is False  # не перезапись
    after = refresh_watchlist(repos, lambda cik: None, "wl",
                              "2026-10-01", dry_run=True)
    assert not after[0].reason.startswith("первый сбор")
    assert after[0].calls["companyfacts"] == 0
