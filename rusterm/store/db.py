"""Открытие БД, миграции, единственный поток-писатель.

Контракт по docs/data-model.md и ADR-0003:
- SQLite, WAL, одна база на каталог данных.
- Миграции только вперёд, пронумерованы, применяются по порядку.
- schema_version хранится в одноимённой таблице.
- Перед каждой миграцией — копия rusterm.db рядом.
- Все SQL-запросы приложения идут отсюда; вне rusterm/store/ SQL не пишем.
- Писатель один: lock-объект гарантирует сериализацию записи.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .paths import AppPaths

# Один писатель на процесс. Читать можно из любого потока.
_writer_lock = threading.Lock()
_SCHEMA_VERSION = 37  # 32 таблицы + 33 (gzip) + 35 (governance) + 36 (canonical_concept) + 37 (issuer_ingest_state)


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Миграции: по одной на таблицу. Каждая версия = одна таблица + обновление schema_version.
# Формат: (create_sql, table_name_for_check)
_MIGRATIONS: list[tuple[str, str]] = [
    ("""CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at REAL NOT NULL,
        checksum TEXT NOT NULL)""", "schema_version"),
    ("""CREATE TABLE IF NOT EXISTS issuer (
        issuer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        jurisdiction TEXT NOT NULL,
        registry_id TEXT,
        fiscal_year_end TEXT,
        reporting_standard TEXT NOT NULL,
        reporting_currency TEXT NOT NULL)""", "issuer"),
    ("""CREATE TABLE IF NOT EXISTS instrument (
        instrument_id TEXT PRIMARY KEY,
        issuer_id TEXT NOT NULL REFERENCES issuer(issuer_id),
        isin TEXT,
        class TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active','delisted','merged')),
        superseded_by TEXT REFERENCES instrument(instrument_id))""", "instrument"),
    ("""CREATE TABLE IF NOT EXISTS listing (
        listing_id TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        exchange TEXT NOT NULL,
        currency TEXT NOT NULL,
        is_primary INTEGER NOT NULL CHECK (is_primary IN (0,1)),
        first_trade_date TEXT,
        last_trade_date TEXT)""", "listing"),
    ("""CREATE TABLE IF NOT EXISTS ticker_history (
        listing_id TEXT NOT NULL REFERENCES listing(listing_id),
        ticker TEXT NOT NULL,
        valid_from TEXT NOT NULL,
        valid_to TEXT,
        reason TEXT,
        source_ref TEXT,
        UNIQUE (listing_id, valid_from))""", "ticker_history"),
    ("""CREATE TABLE IF NOT EXISTS concept (
        concept TEXT PRIMARY KEY,
        period_type TEXT NOT NULL CHECK (period_type IN ('instant','duration')),
        unit_kind TEXT NOT NULL,
        description TEXT NOT NULL)""", "concept"),
    ("""CREATE TABLE IF NOT EXISTS formula (
        formula_id TEXT NOT NULL,
        method_version TEXT NOT NULL,
        definition TEXT NOT NULL,
        definition_hash TEXT NOT NULL,
        introduced_at REAL NOT NULL,
        PRIMARY KEY (formula_id, method_version))""", "formula"),
    ("""CREATE TABLE IF NOT EXISTS fx_rate (
        from_ccy TEXT NOT NULL,
        to_ccy TEXT NOT NULL,
        date TEXT NOT NULL,
        rate REAL NOT NULL,
        source_ref TEXT,
        PRIMARY KEY (from_ccy, to_ccy, date))""", "fx_rate"),
    ("""CREATE TABLE IF NOT EXISTS raw_object (
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
        etag TEXT)""", "raw_object"),
    ("""CREATE TABLE IF NOT EXISTS source_cursor (
        provider TEXT NOT NULL,
        index_kind TEXT NOT NULL,
        last_seen_at REAL,
        cursor TEXT,
        updated_at REAL NOT NULL,
        PRIMARY KEY (provider, index_kind))""", "source_cursor"),
    ("""CREATE TABLE IF NOT EXISTS fact (
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
        source_ref TEXT NOT NULL REFERENCES raw_object(sha256),
        locator TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ok','suspect')),
        superseded_by TEXT REFERENCES fact(fact_id),
        ingested_at REAL NOT NULL,
        CHECK (
            (issuer_id IS NOT NULL AND listing_id IS NULL) OR
            (issuer_id IS NULL AND listing_id IS NOT NULL)
        ),
        CHECK (locator <>''))""", "fact"),
    ("""CREATE TABLE IF NOT EXISTS peer_set (
        peer_set_id TEXT PRIMARY KEY,
        scope_kind TEXT NOT NULL CHECK (scope_kind IN ('company','industry')),
        scope_ref TEXT NOT NULL)""", "peer_set"),
    ("""CREATE TABLE IF NOT EXISTS peer_set_version (
        peer_set_version_id TEXT PRIMARY KEY,
        peer_set_id TEXT NOT NULL REFERENCES peer_set(peer_set_id),
        version INTEGER NOT NULL,
        valid_from TEXT NOT NULL,
        valid_to TEXT,
        origin TEXT NOT NULL CHECK (origin IN ('manual','catalog','classifier','llm_suggested')),
        method_version TEXT NOT NULL,
        approved_by_user INTEGER NOT NULL CHECK (approved_by_user IN (0,1)),
        approved_at REAL,
        criteria TEXT,
        UNIQUE (peer_set_id, version))""", "peer_set_version"),
    ("""CREATE TABLE IF NOT EXISTS peer_set_member (
        peer_set_version_id TEXT NOT NULL REFERENCES peer_set_version(peer_set_version_id),
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        reason TEXT,
        excluded_stale INTEGER NOT NULL DEFAULT 0 CHECK (excluded_stale IN (0,1)),
        PRIMARY KEY (peer_set_version_id, instrument_id))""", "peer_set_member"),
    ("""CREATE TABLE IF NOT EXISTS snapshot (
        snapshot_id TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        version INTEGER NOT NULL,
        as_of TEXT NOT NULL,
        built_at REAL NOT NULL,
        peer_set_version TEXT REFERENCES peer_set_version(peer_set_version_id),
        peer_set_status TEXT CHECK (peer_set_status IN ('verified','unverified','none')),
        status TEXT NOT NULL,
        UNIQUE (instrument_id, version))""", "snapshot"),
    ("""CREATE TABLE IF NOT EXISTS snapshot_block (
        snapshot_id TEXT NOT NULL REFERENCES snapshot(snapshot_id),
        block TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ready','partial','missing','error')),
        reason TEXT,
        PRIMARY KEY (snapshot_id, block))""", "snapshot_block"),
    ("""CREATE TABLE IF NOT EXISTS measure (
        measure_id TEXT PRIMARY KEY,
        snapshot_id TEXT NOT NULL REFERENCES snapshot(snapshot_id),
        scope TEXT NOT NULL CHECK (scope IN ('issuer','instrument')),
        scope_ref TEXT NOT NULL,
        concept TEXT NOT NULL,
        value TEXT,
        unit TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        formula_id TEXT,
        method_version TEXT,
        null_reason TEXT,
        peer_set_version TEXT REFERENCES peer_set_version(peer_set_version_id),
        CHECK (
            (value IS NULL AND null_reason IS NOT NULL) OR
            (value IS NOT NULL)
        ),
        CHECK (
            (concept <> 'percentile' AND peer_set_version IS NULL) OR
            (concept = 'percentile' AND peer_set_version IS NOT NULL)
        ))""", "measure"),
    ("""CREATE TABLE IF NOT EXISTS measure_lineage (
        measure_id TEXT NOT NULL REFERENCES measure(measure_id),
        fact_id TEXT,
        peer_measure_id TEXT,
        role TEXT NOT NULL,
        PRIMARY KEY (measure_id, fact_id, peer_measure_id, role),
        CHECK (fact_id IS NOT NULL OR peer_measure_id IS NOT NULL))""", "measure_lineage"),
    ("""CREATE TABLE IF NOT EXISTS latest_measure (
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        concept TEXT NOT NULL,
        value TEXT,
        unit TEXT NOT NULL,
        period_end TEXT NOT NULL,
        method_version TEXT,
        snapshot_version INTEGER NOT NULL,
        PRIMARY KEY (instrument_id, concept))""", "latest_measure"),
    ("""CREATE TABLE IF NOT EXISTS coverage (
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        block TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('ready','stale','processing','missing','error')),
        last_update REAL,
        reason TEXT,
        PRIMARY KEY (instrument_id, block))""", "coverage"),
    ("""CREATE TABLE IF NOT EXISTS watchlist (
        watchlist_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        update_schedule TEXT,
        created_at REAL NOT NULL)""", "watchlist"),
    ("""CREATE TABLE IF NOT EXISTS watchlist_version (
        watchlist_version_id TEXT PRIMARY KEY,
        watchlist_id TEXT NOT NULL REFERENCES watchlist(watchlist_id),
        version INTEGER NOT NULL,
        created_at REAL NOT NULL,
        action TEXT NOT NULL,
        note TEXT,
        UNIQUE (watchlist_id, version))""", "watchlist_version"),
    ("""CREATE TABLE IF NOT EXISTS watchlist_member (
        watchlist_version_id TEXT NOT NULL REFERENCES watchlist_version(watchlist_version_id),
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        note TEXT,
        added_at REAL NOT NULL,
        PRIMARY KEY (watchlist_version_id, instrument_id))""", "watchlist_member"),
    ("""CREATE TABLE IF NOT EXISTS watchlist_group (
        group_id TEXT PRIMARY KEY,
        watchlist_version_id TEXT NOT NULL REFERENCES watchlist_version(watchlist_version_id),
        name TEXT NOT NULL)""", "watchlist_group"),
    ("""CREATE TABLE IF NOT EXISTS watchlist_group_member (
        group_id TEXT NOT NULL REFERENCES watchlist_group(group_id),
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        PRIMARY KEY (group_id, instrument_id))""", "watchlist_group_member"),
    ("""CREATE TABLE IF NOT EXISTS watchlist_filter (
        watchlist_version_id TEXT NOT NULL REFERENCES watchlist_version(watchlist_version_id),
        criteria TEXT NOT NULL,
        PRIMARY KEY (watchlist_version_id))""", "watchlist_filter"),
    ("""CREATE TABLE IF NOT EXISTS job (
        job_id TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        block TEXT NOT NULL,
        provider TEXT NOT NULL,
        target_date TEXT,
        url TEXT,
        priority INTEGER NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('queued','running','done','failed','dead')),
        attempt INTEGER NOT NULL DEFAULT 0,
        not_before REAL,
        created_at REAL NOT NULL,
        finished_at REAL,
        idempotency_key TEXT NOT NULL UNIQUE,
        last_error TEXT)""", "job"),
    ("""CREATE TABLE IF NOT EXISTS job_attempt (
        job_id TEXT NOT NULL REFERENCES job(job_id),
        attempt INTEGER NOT NULL,
        started_at REAL NOT NULL,
        finished_at REAL,
        result TEXT,
        error TEXT,
        http_status INTEGER,
        PRIMARY KEY (job_id, attempt))""", "job_attempt"),
    ("""CREATE TABLE IF NOT EXISTS audit_log (
        ts REAL NOT NULL,
        action TEXT NOT NULL,
        target TEXT,
        payload TEXT,
        confirmed INTEGER NOT NULL CHECK (confirmed IN (0,1)),
        result TEXT)""", "audit_log"),
    ("""CREATE TABLE IF NOT EXISTS verification (
        verification_id TEXT PRIMARY KEY,
        fact_id_wrong TEXT NOT NULL REFERENCES fact(fact_id),
        fact_id_correct TEXT NOT NULL REFERENCES fact(fact_id),
        reported_at REAL NOT NULL,
        note TEXT,
        promoted_to_golden INTEGER NOT NULL DEFAULT 0 CHECK (promoted_to_golden IN (0,1)))""", "verification"),
    ("""CREATE TABLE IF NOT EXISTS metric_sample (
        ts REAL NOT NULL,
        name TEXT NOT NULL,
        provider TEXT,
        value REAL NOT NULL,
        PRIMARY KEY (ts, name, provider))""", "metric_sample"),
    ("""CREATE TABLE IF NOT EXISTS llm_summary (
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        created_at REAL NOT NULL,
        model TEXT NOT NULL,
        prompt_hash TEXT NOT NULL,
        snapshot_version INTEGER NOT NULL,
        summary TEXT NOT NULL,
        highlights TEXT NOT NULL,
        risks TEXT NOT NULL,
        citations TEXT NOT NULL,
        PRIMARY KEY (instrument_id, created_at))""", "llm_summary"),
]

# Миграция 33: 'gzip' в CHECK raw_object.compression.
# Существующие миграции неприкосновенны (у пользователя уже может лежать
# база), а SQLite не умеет менять CHECK у существующей таблицы через ALTER,
# поэтому — штатная перестройка: новая таблица с нужным ограничением,
# перелив данных, удаление старой, переименование.
_RAW_OBJECT_GZIP_DDL = """CREATE TABLE raw_object_new (
        sha256 TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        url TEXT,
        fetched_at REAL NOT NULL,
        bytes INTEGER NOT NULL,
        content_type TEXT NOT NULL,
        compression TEXT NOT NULL CHECK (compression IN ('none','zstd','gzip')),
        instrument_id TEXT,
        block TEXT,
        http_status INTEGER,
        etag TEXT)"""

_RAW_OBJECT_COLUMNS = (
    "sha256, provider, url, fetched_at, bytes, content_type, "
    "compression, instrument_id, block, http_status, etag"
)


def _migrate_33_raw_object_gzip(conn: sqlite3.Connection) -> None:
    conn.execute(_RAW_OBJECT_GZIP_DDL)
    conn.execute(
        f"INSERT INTO raw_object_new ({_RAW_OBJECT_COLUMNS}) "
        f"SELECT {_RAW_OBJECT_COLUMNS} FROM raw_object"
    )
    conn.execute("DROP TABLE raw_object")
    conn.execute("ALTER TABLE raw_object_new RENAME TO raw_object")


# Процедурные миграции после табличных: версия -> (функция, текст для checksum).
_CUSTOM_MIGRATIONS: dict = {33: (_migrate_33_raw_object_gzip, _RAW_OBJECT_GZIP_DDL)}


# Миграция 35: governance_assessment — светофор управления (TASK-7 T17,
# docs/governance-thresholds.md). Только добавление: оценка истории
# никогда не переписывается, новая строка на каждую оценку.
# Версия 34 не существует: T8 нашёл superseded_by уже в DDL fact,
# нумерация 35 взята из ТЗ дословно.
_GOVERNANCE_ASSESSMENT_DDL = """CREATE TABLE IF NOT EXISTS governance_assessment (
        assessment_id TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instrument(instrument_id),
        indicator TEXT NOT NULL CHECK (indicator IN (
            'independent_directors','ceo_chair','related_party',
            'insider_net','auditor')),
        color TEXT NOT NULL CHECK (color IN ('green','yellow','red','gray')),
        method_version TEXT NOT NULL,
        as_of TEXT NOT NULL,
        lineage_ref TEXT NOT NULL,
        reason TEXT,
        assessed_at REAL NOT NULL)"""


def _migrate_35_governance_assessment(conn: sqlite3.Connection) -> None:
    conn.execute(_GOVERNANCE_ASSESSMENT_DDL)


_CUSTOM_MIGRATIONS[35] = (_migrate_35_governance_assessment,
                          _GOVERNANCE_ASSESSMENT_DDL)


# Миграция 36: тег источника остаётся в fact.concept, каноническое имя
# из карты (rusterm/normalize/concepts.py, us-gaap.v1) пишется рядом —
# NULL для неотображённых тегов, чтобы не врать (TASK-9 V0).
def _migrate_36_canonical_concept(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE fact ADD COLUMN canonical_concept TEXT")
    conn.execute("ALTER TABLE fact ADD COLUMN concept_map_version TEXT")


_CUSTOM_MIGRATIONS[36] = (_migrate_36_canonical_concept,
                          "ALTER TABLE fact ADD canonical_concept,"
                          " concept_map_version")


# Миграция 37: состояние инкрементального сбора по эмитенту (TASK-13 Z2).
# Дата последней виденной отчётности и валидаторы кеша companyfacts —
# единственный источник истины для «не изменилось — не скачивается»;
# хранится снаружи провайдера, потому что провайдер о базе не знает
# (инвариант I10). Одна строка на эмитента и источник.
_ISSUER_INGEST_STATE_DDL = """CREATE TABLE IF NOT EXISTS issuer_ingest_state (
        issuer_id TEXT PRIMARY KEY REFERENCES issuer(issuer_id),
        source TEXT NOT NULL DEFAULT 'edgar',
        last_filing_date TEXT,
        etag TEXT,
        last_modified TEXT,
        updated_at TEXT NOT NULL)"""


def _migrate_37_issuer_ingest_state(conn: sqlite3.Connection) -> None:
    conn.execute(_ISSUER_INGEST_STATE_DDL)


_CUSTOM_MIGRATIONS[37] = (_migrate_37_issuer_ingest_state,
                          _ISSUER_INGEST_STATE_DDL)


def apply_migrations(conn: sqlite3.Connection) -> List[int]:
    """Применить все миграции до SCHEMA_VERSION.

    Idempotent: каждую версию применяем только один раз (фильтруем по applied).
    Возвращает список версий, которые реально применили в этом вызове.
    """
    # Гарантируем наличие таблицы версий
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY,"
        " applied_at REAL NOT NULL,"
        " checksum TEXT NOT NULL)"
    )

    # Узнаем, какие версии уже применены
    try:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        applied_versions: set[int] = {r[0] for r in rows}
    except sqlite3.OperationalError:
        applied_versions = set()

    newly_applied: List[int] = []

    for idx, (create_sql, table_name) in enumerate(_MIGRATIONS):
        version = idx + 1  # версии 1..N

        if version in applied_versions:
            continue
        if version > _SCHEMA_VERSION:
            continue

        # Применяем CREATE TABLE IF NOT EXISTS
        try:
            conn.execute(create_sql)
        except sqlite3.OperationalError as e:
            # Проверим, существует ли таблица
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                ).fetchone()
                if row is None:
                    raise
            except Exception:
                raise

        # Обновляем версию
        conn.execute(
            "INSERT INTO schema_version(version, applied_at, checksum) VALUES (?, ?, ?)",
            (version, time.time(), _checksum(create_sql))
        )
        applied_versions.add(version)
        newly_applied.append(version)

    for version, (migrate, checksum_text) in sorted(_CUSTOM_MIGRATIONS.items()):
        if version in applied_versions or version > _SCHEMA_VERSION:
            continue
        # PRAGMA foreign_keys не действует внутри транзакции, поэтому
        # выключается до BEGIN и возвращается после COMMIT.
        fk_was_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute("BEGIN IMMEDIATE")
            migrate(conn)
            conn.execute(
                "INSERT INTO schema_version(version, applied_at, checksum) VALUES (?, ?, ?)",
                (version, time.time(), _checksum(checksum_text))
            )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=%s" % ("ON" if fk_was_on else "OFF"))
        applied_versions.add(version)
        newly_applied.append(version)

    return newly_applied


def current_schema_version(conn: sqlite3.Connection) -> Optional[int]:
    """Применённая версия схемы; None, если таблицы версий ещё нет."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None


def open_connection(paths: AppPaths) -> sqlite3.Connection:
    """Единая точка открытия соединения приложения: WAL, FK, row_factory."""
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def writer_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Контекст для записи под единым писательским локом (I14).

    Гарантирует сериализацию: только один поток пишет в одну транзакцию.
    При выходе — COMMIT, при исключении — ROLLBACK.
    """
    with _writer_lock:
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
