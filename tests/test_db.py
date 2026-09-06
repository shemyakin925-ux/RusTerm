"""Тесты инкремента И3: база данных SQLite, миграции, единственный писатель."""
from __future__ import annotations

import sqlite3
import tempfile
import time

import pytest

from rusterm.store.db import apply_migrations, writer_transaction, _SCHEMA_VERSION


def test_schema_version_is_32():
    """SCHEMA_VERSION должно совпадать с числом миграций."""
    assert _SCHEMA_VERSION == 32


def test_apply_migrations_creates_all_tables():
    """M3: миграция создаёт все таблицы и устанавливает schema_version = 32."""
    import os
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        apply_migrations(conn)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
        assert row[0] == 32
        # Ключевые таблицы
        tables = ["issuer", "instrument", "listing", "fact", "peer_set", "snapshot",
                  "measure", "coverage", "job", "audit_log"]
        for t in tables:
            ok = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (t,),
            ).fetchone()
            assert ok is not None, f"Таблица {t} не создана"
    finally:
        conn.close()
        import shutil
        shutil.rmtree(tmpdir)


def test_apply_migrations_idempotent():
    """Если применить миграции дважды — таблицы не создадутся заново."""
    import os
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test2.db")
    conn1 = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn1.execute("PRAGMA journal_mode=WAL")
    conn1.execute("PRAGMA foreign_keys=ON")
    try:
        apply_migrations(conn1)
        conn2 = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
        conn2.execute("PRAGMA journal_mode=WAL")
        conn2.execute("PRAGMA foreign_keys=ON")
        try:
            apply_migrations(conn2)
            count1 = conn1.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            count2 = conn2.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            assert count1 == count2 == 32
        finally:
            conn2.close()
    finally:
        conn1.close()
        import shutil
        shutil.rmtree(tmpdir)


def test_writer_transaction_basic():
    """I14: writer_transaction сериализует запись."""
    import os
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test3.db")
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        apply_migrations(conn)
        with writer_transaction(conn) as c:
            c.execute(
                "INSERT INTO issuer(issuer_id, name, jurisdiction, reporting_standard, reporting_currency) VALUES (?, ?, ?, ?, ?)",
                ("test-issuer", "Test Corp", "US", "us_gaap", "USD"),
            )
        row = conn.execute("SELECT * FROM issuer").fetchone()
        assert row is not None
        assert row[1] == "Test Corp"
        with writer_transaction(conn) as c2:
            c2.execute(
                "INSERT INTO issuer(issuer_id, name, jurisdiction, reporting_standard, reporting_currency) VALUES (?, ?, ?, ?, ?)",
                ("test-issuer-2", "Test Corp 2", "UK", "ifrs", "GBP"),
            )
        row2 = conn.execute("SELECT count(*) FROM issuer").fetchone()[0]
        assert row2 == 2
    finally:
        conn.close()
        import shutil
        shutil.rmtree(tmpdir)
