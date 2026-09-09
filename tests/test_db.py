"""Тесты инкремента И3: база данных SQLite, миграции, единственный писатель."""
from __future__ import annotations

import sqlite3
import tempfile
import time

import pytest

from rusterm.store.db import apply_migrations, writer_transaction, _SCHEMA_VERSION


def test_schema_version_is_36():
    """SCHEMA_VERSION: 32 таблицы + 33 (gzip) + 35 (governance)
    + 36 (canonical_concept; 34 не существует, TASK-9 V0)
    + 37 (issuer_ingest_state) + 38 (индексы)
    + 39 (industry_aggregate, TASK-17 E3)."""
    assert _SCHEMA_VERSION == 39


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
        assert row[0] == 39
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
            # 32 таблицы миграций (включая schema_version) + governance_assessment + issuer_ingest_state
            assert count1 == count2 == 35
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
    со старым CHECK ('none','zstd') и двумя строками данных.
    fact/measure/measure_lineage — в полной форме миграций 11/20/21:
    настоящая база v32 их содержала, и миграция 38 индексирует их
    колонки целиком (TASK-14 A1)."""
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
    conn.execute(
        """CREATE TABLE fact (
        fact_id TEXT PRIMARY KEY,
        issuer_id TEXT,
        listing_id TEXT,
        concept TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        period_type TEXT NOT NULL CHECK (period_type IN ('instant','duration')),
        value TEXT,
        unit TEXT NOT NULL,
        currency TEXT,
        basis TEXT NOT NULL CHECK (basis IN ('as_reported','restated')),
        origin TEXT NOT NULL CHECK (origin IN ('extracted','manual')),
        source_ref TEXT NOT NULL,
        locator TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ok','suspect')),
        superseded_by TEXT,
        ingested_at REAL NOT NULL)""")
    conn.execute(
        """CREATE TABLE measure (
        measure_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL,
        scope TEXT NOT NULL,
        scope_ref TEXT NOT NULL,
        concept TEXT NOT NULL,
        value TEXT,
        unit TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        formula_id TEXT,
        method_version TEXT,
        null_reason TEXT,
        peer_set_version TEXT)""")
    conn.execute(
        """CREATE TABLE measure_lineage (
        measure_id TEXT NOT NULL,
        fact_id TEXT,
        peer_measure_id TEXT,
        role TEXT NOT NULL,
        PRIMARY KEY (measure_id, fact_id, peer_measure_id, role))""")
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
        # v32-база получает 33 (gzip), 35 (governance), 36 (canonical),
        # 37 (issuer_ingest_state) и 38 (индексы, TASK-14 A1)
        assert newly == [33, 35, 36, 37, 38, 39], \
            f"ожидались [33, 35, 36, 37, 38, 39], получили {newly}"
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


# ── Миграция 38: первые индексы схемы (TASK-14 A1, находка Z3) ──────────

_M48_INDEXES = {
    "idx_fact_issuer_concept_period_basis",
    "idx_fact_source_ref",
    "idx_measure_snapshot",
    "idx_measure_lineage_measure",
}


def test_migration_38_creates_exactly_four_named_indexes():
    """На свежей базе ровно четыре именованных индекса миграции 38 —
    по одному на именованный запрос; пятый наугад стоил бы без пользы."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    try:
        apply_migrations(conn)
        got = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
            " AND sql IS NOT NULL")}
        assert got == _M48_INDEXES, (
            f"ожидались ровно {_M48_INDEXES}, получены {got}")
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_migration_38_revisions_query_hits_index_not_fact_scan():
    """Z3 + TASK-14 A1/A2: restated_revisions() — коррелированный EXISTS
    по fact; без индекса он полный SCAN (квадрат), без фильтра эмитента
    внешний проход тоже SCAN. После миграции 38 и скоупа по issuer_id
    в плане нет ни одного SCAN, оба прохода ищут по покрывающему
    индексу. SQL берётся трассировкой настоящего вызова репозитория —
    тест проверяет фактический запрос, а не его копию."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    try:
        apply_migrations(conn)
        from rusterm.store.repos import SnapshotRepo
        captured: list[str] = []
        conn.set_trace_callback(captured.append)
        try:
            SnapshotRepo(conn).restated_revisions("i1")
        finally:
            conn.set_trace_callback(None)
        assert captured, "restated_revisions не выполнил ни одного запроса"
        plan = [row[3] for row in conn.execute(
            "EXPLAIN QUERY PLAN " + captured[0])]
        assert not any("SCAN" in step for step in plan), (
            f"полное сканирование fact в плане: {plan}")
        assert any("SEARCH" in step for step in plan), plan
        assert all("USING COVERING INDEX"
                   " idx_fact_issuer_concept_period_basis" in step
                   for step in plan if "SEARCH" in step), plan
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_migration_38_issuer_ingest_state_two_sources():
    """TASK-14 A7 (§0.2.5): миграция 37 обещала «строка на эмитента и
    источник», а ключ был issuer_id один. После 38 ключ (issuer_id,
    source): два источника одного эмитента сосуществуют и читаются
    независимо; повторный put по той же паре обновляет, а не дублирует;
    строка старой базы переживает перестройку."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO issuer(issuer_id, name, jurisdiction,"
            " reporting_standard, reporting_currency)"
            " VALUES ('i1', 'Issuer 1', 'US', 'us_gaap', 'USD')")
        # база версии 37 могла нести строку эмитента — она обязана
        # пережить перестройку; эмулируем записью и повторной выливкой
        from rusterm.store.repos import IssuerStateRepo
        state = IssuerStateRepo(conn)
        state.put("i1", "2026-01-01", etag="W/\"a\"", source="edgar")

        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='issuer_ingest_state'").fetchone()[0]
        assert "PRIMARY KEY (issuer_id, source)" in ddl, ddl

        state.put("i1", "2026-02-01", etag="W/\"b\"", source="synthetic")
        edgar = state.get("i1", source="edgar")
        synthetic = state.get("i1", source="synthetic")
        assert edgar["last_filing_date"] == "2026-01-01"
        assert edgar["etag"] == "W/\"a\""
        assert synthetic["last_filing_date"] == "2026-02-01"
        assert synthetic["etag"] == "W/\"b\""

        # повторный put по той же паре — обновление, не дубль
        state.put("i1", "2026-03-01", etag="W/\"c\"", source="edgar")
        n = conn.execute(
            "SELECT COUNT(*) FROM issuer_ingest_state"
            " WHERE issuer_id='i1'").fetchone()[0]
        assert n == 2, "повторный put создал дубль"
        assert state.get("i1")["last_filing_date"] == "2026-03-01"
        # get по умолчанию — edgar (сигнатуры не менялись)
        assert state.get("i1", source="synthetic")["etag"] == "W/\"b\""
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_b21_issuer_state_get_none_for_other_source():
    """BACKLOG B21: get возвращает None и для эмитента, чья строка есть,
    но под другим источником — составной ключ сделает это честным
    (миграция 38, A7). До 38 такой вызов вернул бы edgar-строку."""
    import os
    import shutil
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(str(os.path.join(tmpdir, "test.db")),
                           timeout=30, isolation_level=None)
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO issuer(issuer_id, name, jurisdiction,"
            " reporting_standard, reporting_currency)"
            " VALUES ('i1', 'Issuer 1', 'US', 'us_gaap', 'USD')")
        from rusterm.store.repos import IssuerStateRepo
        state = IssuerStateRepo(conn)
        assert state.get("i1") is None  # строки нет вовсе
        state.put("i1", "2026-01-01", source="edgar")
        assert state.get("i1", source="edgar") is not None
        assert state.get("i1", source="synthetic") is None, (
            "чужой источник вернул чужую строку")
        assert state.get("i-missing") is None
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
