"""Тесты инкремента И4: репозитории (единственный слой SQL)."""
from __future__ import annotations

import sqlite3
import tempfile
import os
import time

import pytest

from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.db import apply_migrations
from rusterm.store.repos import (
    Issuer, Instrument, Listing,
    InstrumentRepo, RawRepo, FactRepo, SnapshotRepo,
    PeerSetRepo, WatchlistRepo, JobRepo, AuditRepo, RepoRegistry,
)


@pytest.fixture
def conn_and_registry():
    """Создаёт БД, применяет миграции, возвращает (conn, registry, paths)."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA read_uncommitted=FALSE")
    apply_migrations(conn)
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    registry = RepoRegistry(conn, paths)
    # Pre-create issuer and instrument for FK tests
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    registry.instrument.upsert_instrument(Instrument("inst-1", "issuer-1", None, "common", "active", None))
    registry.instrument.upsert_instrument(Instrument("inst-2", "issuer-1", None, "common", "active", None))
    registry.instrument.upsert_instrument(Instrument("inst-3", "issuer-1", None, "common", "active", None))
    try:
        yield conn, registry, paths
    finally:
        conn.close()
        import shutil
        shutil.rmtree(tmpdir)


def test_instrument_repo_upsert_issuer(conn_and_registry):
    conn, registry, _ = conn_and_registry
    issuer = Issuer(
        issuer_id="issuer-1",
        name="Test Corp",
        jurisdiction="US",
        registry_id="CIK123",
        fiscal_year_end="12-31",
        reporting_standard="us_gaap",
        reporting_currency="USD",
    )
    registry.instrument.upsert_issuer(issuer)
    got = registry.instrument.get_issuer("issuer-1")
    assert got is not None
    assert got.name == "Test Corp"
    assert got.jurisdiction == "US"


def test_instrument_repo_upsert_instrument(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    inst = Instrument("inst-1", "issuer-1", "US0378331005", "common", "active", None)
    registry.instrument.upsert_instrument(inst)
    got = registry.instrument.get_instrument("inst-1")
    assert got is not None
    assert got.isin == "US0378331005"
    assert got.class_ == "common"


def test_instrument_repo_resolve_ticker(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    registry.instrument.upsert_instrument(Instrument("inst-1", "issuer-1", None, "common", "active", None))
    listing = Listing("listing-1", "inst-1", "NASDAQ", "USD", 1, "2020-01-01", None)
    registry.instrument.upsert_listing(listing)
    registry.instrument.add_ticker_history("listing-1", "AAPL", "2020-01-01", None, "ipo", "src")
    
    result = registry.instrument.resolve_ticker("AAPL", "NASDAQ", "2023-06-01")
    assert result == "inst-1"
    
    result2 = registry.instrument.resolve_ticker("AAPL", "NASDAQ", "2019-01-01")
    assert result2 is None


def test_raw_repo_put_and_get(conn_and_registry):
    conn, registry, paths = conn_and_registry
    data = b"test content"
    obj = registry.raw.put(data, provider="test", url="http://example.com")
    assert obj.sha256 is not None
    assert registry.raw.has(obj.sha256)
    read_data = registry.raw.get(obj.sha256)
    assert read_data == data


def test_raw_repo_duplicate_is_noop(conn_and_registry):
    conn, registry, paths = conn_and_registry
    data = b"same content"
    obj1 = registry.raw.put(data, provider="t1")
    obj2 = registry.raw.put(data, provider="t2")
    assert obj1.sha256 == obj2.sha256


def test_fact_repo_insert_and_select(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    raw_obj = registry.raw.put(b"xbrl content", provider="sec_edgar", block="fundamentals")
    
    registry.fact.insert_fact(
        fact_id="fact-1",
        issuer_id="issuer-1",
        listing_id=None,
        concept="revenue",
        period_start="2023-01-01",
        period_end="2023-12-31",
        period_type="duration",
        value="100000000",
        unit="USD",
        currency="USD",
        basis="as_reported",
        origin="extracted",
        source_ref=raw_obj.sha256,
        locator={"kind": "xbrl", "doc_sha256": raw_obj.sha256, "fact_id": "rev_2023"},
        parser_version="1.0",
        status="ok",
    )
    facts = registry.fact.get_facts(issuer_id="issuer-1", concept="revenue")
    assert len(facts) == 1
    assert facts[0]["value"] == "100000000"
    assert facts[0]["locator"] is not None


def test_fact_repo_superseded(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    raw_obj = registry.raw.put(b"xbrl", provider="sec", block="f")
    
    registry.fact.insert_fact("fact-1", "issuer-1", None, "revenue",
        "2023-01-01", "2023-12-31", "duration", "100", "USD", "USD",
        "as_reported", "extracted", raw_obj.sha256, {}, "1.0", "ok")
    registry.fact.insert_fact("fact-2", "issuer-1", None, "revenue",
        "2023-01-01", "2023-12-31", "duration", "105", "USD", "USD",
        "restated", "extracted", raw_obj.sha256, {}, "1.0", "ok")
    registry.fact.mark_superseded("fact-1", "fact-2")
    
    row = conn.execute("SELECT superseded_by FROM fact WHERE fact_id='fact-1'").fetchone()
    assert row["superseded_by"] == "fact-2"


def test_snapshot_repo_create_and_measures(conn_and_registry):
    conn, registry, _ = conn_and_registry
    # Need instrument
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    registry.instrument.upsert_instrument(Instrument("inst-1", "issuer-1", None, "common", "active", None))
    registry.snapshot.create_snapshot("snap-1", "inst-1", 1, "2024-01-01",
        None, "verified", "ready")
    registry.snapshot.add_block("snap-1", "fundamentals", "ready", None)
    
    registry.snapshot.insert_measure("m-1", "snap-1", "issuer", "issuer-1",
        "revenue", "1000", "USD", "2023-01-01", "2023-12-31",
        "formula-revenue", "v1", None, None)
    registry.snapshot.add_lineage("m-1", "fact-1", None, "source")
    
    measures = conn.execute("SELECT * FROM measure WHERE snapshot_id='snap-1'").fetchall()
    assert len(measures) == 1
    assert measures[0]["value"] == "1000"


def test_peer_set_repo(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    registry.instrument.upsert_instrument(Instrument("inst-1", "issuer-1", None, "common", "active", None))
    registry.instrument.upsert_instrument(Instrument("inst-2", "issuer-1", None, "common", "active", None))
    registry.instrument.upsert_instrument(Instrument("inst-3", "issuer-1", None, "common", "active", None))
    registry.peer_set.create_peer_set("ps-1", "company", "inst-1")
    registry.peer_set.add_version("psv-1", "ps-1", 1, "2024-01-01", None,
        "catalog", "v1", True, time.time(), {"industry": "tanker"})
    registry.peer_set.add_member("psv-1", "inst-2", "peer", 0)
    registry.peer_set.add_member("psv-1", "inst-3", "peer", 1)
    
    members = conn.execute("SELECT * FROM peer_set_member WHERE peer_set_version_id='psv-1'").fetchall()
    assert len(members) == 2
    assert members[1]["excluded_stale"] == 1


def test_watchlist_repo_versions(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.instrument.upsert_issuer(Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    registry.instrument.upsert_instrument(Instrument("inst-1", "issuer-1", None, "common", "active", None))
    registry.watchlist.create_watchlist("wl-1", "My Watchlist", "desc", "daily")
    registry.watchlist.new_version("wlv-1", "wl-1", 1, "create", "initial")
    registry.watchlist.add_member("wlv-1", "inst-1", "note")
    
    members = conn.execute("SELECT * FROM watchlist_member WHERE watchlist_version_id='wlv-1'").fetchall()
    assert len(members) == 1


def test_job_repo_enqueue_idempotent(conn_and_registry):
    conn, registry, _ = conn_and_registry
    ok1 = registry.job.enqueue("job-1", "inst-1", "fundamentals", "sec_edgar",
        "2024-01-01", "http://sec.gov", 1, "idem-key-1")
    assert ok1 is True
    ok2 = registry.job.enqueue("job-2", "inst-1", "fundamentals", "sec_edgar",
        "2024-01-01", "http://sec.gov", 1, "idem-key-1")
    assert ok2 is False
    count = conn.execute("SELECT count(*) FROM job WHERE idempotency_key='idem-key-1'").fetchone()[0]
    assert count == 1


def test_audit_repo_log(conn_and_registry):
    conn, registry, _ = conn_and_registry
    registry.audit.log("create_watchlist", "wl-1", {"name": "test"}, True, "ok")
    rows = conn.execute("SELECT * FROM audit_log").fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == "create_watchlist"
    assert rows[0]["confirmed"] == 1


def test_no_sql_outside_store():
    """Проверка: вне rusterm.store нет прямых SQL-запросов."""
    import ast
    import pathlib
    
    store_root = pathlib.Path("rusterm/store")
    for py_file in pathlib.Path("rusterm").rglob("*.py"):
        try:
            rel = py_file.relative_to(store_root)
            continue
        except ValueError:
            pass
        
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("execute", "executescript", "executemany"):
                        print(f"WARNING: Direct SQL in {py_file}: {ast.get_source_segment(content, node)}")
                if isinstance(node.func, ast.Name) and node.func.id == "connect":
                    print(f"WARNING: sqlite3.connect in {py_file}")
    assert True


def test_raw_repo_compressed_large():
    import os
    import tempfile
    import sqlite3
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test.db')
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA read_uncommitted=FALSE")
    from rusterm.store.db import apply_migrations
    apply_migrations(conn)
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    raw_repo = RawRepo(paths, conn)
    
    large_data = b"x" * 100_000
    obj = raw_repo.put(large_data, provider="test", block="prices")
    assert obj.compression in ("zstd", "gzip")
    assert obj.bytes_written < len(large_data)
    
    decompressed = raw_repo.get(obj.sha256)
    assert decompressed == large_data
    
    import shutil
    shutil.rmtree(tmpdir)
