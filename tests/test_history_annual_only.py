"""Годовая колонка истории — только годовой период или остаток.

Осмотр окна 01.10.2026: у BAC клетка «2026» показывала asset_turnover
за квартал (0,009 против 0,03 у всех лет) — старый снапшот посчитал меру
по Q2, и обход истории положил квартал в колонку года."""
from __future__ import annotations

import sqlite3

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry
from rusterm.tui import model


def _repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer("i", "B", "US", "1", None,
                                          "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument("US-B", "i", None,
                                                  "common", "active", None))
    return repos


def test_quarter_never_lands_in_a_year_column(tmp_path):
    repos = _repos(tmp_path)
    repos.snapshot.create_snapshot("s1", "US-B", 1, "2026-09-24", None,
                                   "none", "ready")
    repos.snapshot.insert_measure(
        "m-q", "s1", "issuer", "i", "asset_turnover", "0.009", "ratio",
        "2026-04-01", "2026-06-30", "f", "v1", None, None)
    repos.snapshot.insert_measure(
        "m-cash", "s1", "issuer", "i", "net_debt", "5", "USD",
        "2026-06-30", "2026-06-30", "f", "v1", None, None)
    repos.snapshot.create_snapshot("s2", "US-B", 2, "2026-10-01", None,
                                   "none", "ready")
    repos.snapshot.insert_measure(
        "m-y", "s2", "issuer", "i", "asset_turnover", "0.034", "ratio",
        "2025-01-01", "2025-12-31", "f", "v1", None, None)
    history = model.measure_history_by_year(repos, "US-B")
    assert history["2025"]["asset_turnover"] == 0.034
    assert "asset_turnover" not in history.get("2026", {})
    # остаток баланса (начало = конец) — законная клетка года
    assert history["2026"]["net_debt"] == 5.0
