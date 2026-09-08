"""Тесты инкремента И3: база данных SQLite, миграции, единственный писатель."""
from __future__ import annotations

import sqlite3
import tempfile
import time

import pytest

from rusterm.store.db import apply_migrations, writer_transaction, _SCHEMA_VERSION


def test_schema_version_is_36():
    """SCHEMA_VERSION: 32 таблицы + 33 (gzip) + 35 (governance)
    + 36 (canonical_concept; 34 не существует, TASK-9 V0)."""
    assert _SCHEMA_VERSION == 36


def test_apply_migrations_creates_all_tables():
    """M3: миграция создаёт все таблицы и устанавливает schema_version = 36."""
    import os
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        apply_migrations(conn)
        # Берём максимальную версию (последняя применённая)
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row is not None
        assert row[0] == 36
        # Ключевые таблицы
        tables = ["issuer", "instrument", "listing", "fact", "peer_set", "snapshot",
                  "measure", "coverage", "job", "audit_log",
                  "governance_assessment"]
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
            # 32 таблицы миграций (включая schema_version) + governance_assessment
            assert count1 == count2 == 33
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


# ── Миграция 33: gzip в CHECK raw_object.competition ───────────────────

_OLD_RAW_OBJECT_DDL = """CREATE TABLE raw_object (
        sha256 TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        url TEXT,
        fetched_at REAL NOT NULL,
        bytes INTEGER NOT NULL,
        content_type TEXT NOT NULL,
        compression TEXT NOT NULL CHECK (compression IN ('none','zstd')),
        instrument_id TEXT,
        block TEXT,
        http_status INTEGER,
        etag TEXT)"""


def _make_v32_db_with_data(conn: sqlite3.Connection) -> None:
    """База версии 32: все версии отмечены применёнными, raw_object —
    со старым CHECK ('none','zstd') и двумя строками данных."""
    conn.execute(
        "CREATE TABLE schema_version ("
        " version INTEGER PRIMARY KEY,"
        " applied_at REAL NOT NULL,"
        " checksum TEXT NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO schema_version(version, applied_at, checksum) VALUES (?, ?, ?)",
        [(v, 0.0, "seed") for v in range(1, 33)],
    )
    conn.execute(_OLD_RAW_OBJECT_DDL)
    # настоящая база v32 содержит и fact (создаётся миграцией 11);
    # без него миграция 36 (ALTER TABLE fact) не имеет смысла
    conn.execute(
        "CREATE TABLE fact (fact_id TEXT PRIMARY KEY, source_ref TEXT)")
    conn.executemany(
        "INSERT INTO raw_object(sha256, provider, fetched_at, bytes,"
        " content_type, compression) VALUES (?, 'synthetic', 0.0, 3,"
        " 'application/json', ?)",
        [("a" * 64, "none"), ("b" * 64, "zstd")],
    )


def test_migration_33_keeps_data_and_allows_gzip():
    """Миграция 33 на базе С данными: строки переживают перестройку таблицы,
    gzip после неё принимается, посторонняя метка — нет (TASK-3 §A1)."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _make_v32_db_with_data(conn)
        newly = apply_migrations(conn)
        # v32-база получает 33 (gzip), 35 (governance) и 36 (canonical)
        assert newly == [33, 35, 36], f"ожидались [33, 35, 36], получили {newly}"
        rows = dict(conn.execute(
            "SELECT sha256, compression FROM raw_object").fetchall())
        assert rows == {"a" * 64: "none", "b" * 64: "zstd"}, (
            "перестройка таблицы потеряла или исказила данные"
        )
        conn.execute(
            "INSERT INTO raw_object(sha256, provider, fetched_at, bytes,"
            " content_type, compression) VALUES (?, 'synthetic', 0.0, 1,"
            " 'application/json', 'gzip')",
            ("c" * 64,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO raw_object(sha256, provider, fetched_at, bytes,"
                " content_type, compression) VALUES (?, 'synthetic', 0.0, 1,"
                " 'application/json', 'br')",
                ("d" * 64,),
            )
        assert apply_migrations(conn) == [], "повторное применение — no-op"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_fresh_db_raw_object_check_allows_gzip():
    """На чистой базе после всех миграций CHECK raw_object допускает gzip."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        apply_migrations(conn)
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='raw_object'"
        ).fetchone()[0]
        assert "'gzip'" in ddl, "в итоговом CHECK нет 'gzip'"
        conn.execute(
            "INSERT INTO raw_object(sha256, provider, fetched_at, bytes,"
            " content_type, compression) VALUES (?, 'synthetic', 0.0, 1,"
            " 'application/json', 'gzip')",
            ("e" * 64,),
        )
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
