"""Тесты CoverageRepo и записи покрытия сборкой снапшота (TASK-7 T7).

Пробел показывается, а не замалчивается: ровно восемь блоков, ровно пять
статусов, missing/error — только с непустой причиной, и запрет
проверяется репозиторием, а не совестью вызывающего.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    COVERAGE_BLOCKS,
    COVERAGE_STATUSES,
    CoverageRepo,
    Instrument,
    InstrumentRepo,
    Issuer,
    PeerSetRepo,
    RepoRegistry,
    SnapshotRepo,
    WatchlistRepo,
)


def _registry():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return tmpdir, conn, RepoRegistry(conn, paths)


def test_coverage_blocks_and_statuses_are_exact_eight_and_five():
    assert COVERAGE_BLOCKS == (
        "prices", "fundamentals", "ownership", "corporate_actions",
        "governance", "industry_metrics", "peer_set", "llm_summary")
    assert COVERAGE_STATUSES == (
        "ready", "stale", "processing", "missing", "error")


def test_coverage_rejects_unknown_block_and_status():
    tmpdir, conn, repos = _registry()
    try:
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        cov = repos.coverage
        with pytest.raises(ValueError, match="блок"):
            cov.upsert("ins1", "not_a_block", "ready")
        with pytest.raises(ValueError, match="статус"):
            cov.upsert("ins1", "prices", "fine")
        assert cov.for_instrument("ins1") == []
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_coverage_missing_and_error_require_non_empty_reason():
    tmpdir, conn, repos = _registry()
    try:
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        cov = repos.coverage
        for status in ("missing", "error"):
            with pytest.raises(ValueError, match="причину"):
                cov.upsert("ins1", "prices", status)
            with pytest.raises(ValueError, match="причину"):
                cov.upsert("ins1", "prices", status, reason="   ")
        # легальные записи: missing/error с причиной, остальные без
        cov.upsert("ins1", "prices", "missing", reason="no_source")
        cov.upsert("ins1", "fundamentals", "error", reason="E1:source_down")
        cov.upsert("ins1", "peer_set", "ready")
        rows = {r["block"]: r for r in cov.for_instrument("ins1")}
        assert rows["prices"]["reason"] == "no_source"
        assert rows["fundamentals"]["status"] == "error"
        assert rows["peer_set"]["reason"] is None
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_ensure_all_prices_only_instrument_yields_eight_rows_seven_missing():
    """Контрольный случай ТЗ: инструмент только с котировками — ровно
    8 строк покрытия, 7 missing с непустыми причинами, prices готов."""
    tmpdir, conn, repos = _registry()
    try:
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        cov = repos.coverage
        cov.upsert("ins1", "prices", "ready")
        cov.ensure_all("ins1", {"fundamentals": ("missing",
                                                 "no_as_reported_facts")})
        rows = cov.for_instrument("ins1")
        assert len(rows) == 8
        by_block = {r["block"]: r for r in rows}
        assert by_block["prices"]["status"] == "ready"  # чужие данные не тронуты
        missing = [r for r in rows if r["status"] == "missing"]
        assert len(missing) == 7
        assert all(r["reason"] and r["reason"].strip() for r in missing)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_snapshot_build_writes_all_eight_blocks_and_source_error():
    tmpdir, conn, repos = _registry()
    try:
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        result = builder.build(
            "ins1", "i1", "2024-12-31",
            source_errors={"prices": "E1: index unreachable"})
        rows = {r["block"]: r for r in repos.coverage.for_instrument("ins1")}
        assert len(rows) == 8
        assert rows["fundamentals"]["status"] == "missing"  # фактов нет
        assert rows["fundamentals"]["reason"] == "no_as_reported_facts"
        assert rows["peer_set"]["status"] == "missing"
        assert rows["peer_set"]["reason"] == "peer_set_not_confirmed"
        assert rows["prices"]["status"] == "error"  # E1/E2 виден в покрытии
        assert "E1" in rows["prices"]["reason"]
        assert rows["llm_summary"]["status"] == "missing"
        assert result.snapshot_id == repos.snapshot.latest_snapshot_id("ins1")
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_for_watchlist_returns_coverage_of_current_members():
    tmpdir, conn, repos = _registry()
    try:
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        repos.instrument.upsert_instrument(Instrument(
            "ins2", "i1", None, "common", "active", None))
        wl = WatchlistRepo(conn)
        wl.create_watchlist("w1", "Наблюдение", None, None)
        wl.new_version("wv1", "w1", 1, "create", None)
        wl.add_member("wv1", "ins1", None)
        wl.add_member("wv1", "ins2", None)
        cov = repos.coverage
        cov.upsert("ins1", "prices", "ready")
        cov.upsert("ins2", "prices", "missing", reason="no_source")
        rows = cov.for_watchlist("w1")
        assert {(r["instrument_id"], r["block"], r["status"])
                for r in rows} == {
            ("ins1", "prices", "ready"),
            ("ins2", "prices", "missing"),
        }
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_coverage_blocks_match_documentation():
    """BACKLOG B7: список блоков в коде и в docs/watchlist-and-llm.md §1.3 —
    один и тот же; переименование блока в коде или в документе краснит."""
    import re
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[1] / "docs"
           / "watchlist-and-llm.md").read_text(encoding="utf-8")
    block_rows = [line for line in doc.splitlines()
                  if line.startswith("| `block` |")]
    assert len(block_rows) == 1, "строка блока §1.3 должна быть ровно одна"
    doc_blocks = set(re.findall(r"`([a-z_]+)`", block_rows[0])) - {"block"}
    assert doc_blocks == set(COVERAGE_BLOCKS), (
        f"документ vs код: {doc_blocks ^ set(COVERAGE_BLOCKS)}"
    )


def test_snapshot_builder_requires_coverage_repo():
    """TASK-8 U1: сборка без coverage_repo — TypeError, а не молчаливое
    отсутствие покрытия."""
    tmpdir, conn, repos = _registry()
    try:
        with pytest.raises(TypeError):
            SnapshotBuilder(repos.snapshot, repos.peer_set)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
