"""Репозитории: единственный слой с SQL.

Контракт по docs/module-contracts.md §5. Вне rusterm/store/ SQL не пишется.
Все операции записи — через writer_transaction.
"""
from __future__ import annotations

import json
import uuid
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional, List, Dict

import sqlite3

from .db import writer_transaction, apply_migrations
from .paths import AppPaths, ensure_app_dir
from .raw_store import StoredObject, RawIndexEntry, put_object, append_manifest_line, decompress_object, object_path, has_object


@dataclass
class Issuer:
    issuer_id: str
    name: str
    jurisdiction: str
    registry_id: Optional[str]
    fiscal_year_end: Optional[str]
    reporting_standard: str
    reporting_currency: str


@dataclass
class Instrument:
    instrument_id: str
    issuer_id: str
    isin: Optional[str]
    class_: str  # "class" — зарезервировано
    status: str
    superseded_by: Optional[str]


@dataclass
class Listing:
    listing_id: str
    instrument_id: str
    exchange: str
    currency: str
    is_primary: int
    first_trade_date: Optional[str]
    last_trade_date: Optional[str]


class InstrumentRepo:
    """Справочники, история тикеров, разрешение по дате (ADR-0005)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert_issuer(self, issuer: Issuer) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO issuer(issuer_id, name, jurisdiction, registry_id,
                  fiscal_year_end, reporting_standard, reporting_currency)
                  VALUES (?, ?, ?, ?, ?, ?, ?)
                  ON CONFLICT(issuer_id) DO UPDATE SET
                    name=excluded.name,
                    jurisdiction=excluded.jurisdiction,
                    registry_id=excluded.registry_id,
                    fiscal_year_end=excluded.fiscal_year_end,
                    reporting_standard=excluded.reporting_standard,
                    reporting_currency=excluded.reporting_currency""",
                (issuer.issuer_id, issuer.name, issuer.jurisdiction,
                 issuer.registry_id, issuer.fiscal_year_end,
                 issuer.reporting_standard, issuer.reporting_currency),
            )

    def get_issuer(self, issuer_id: str) -> Optional[Issuer]:
        row = self.conn.execute(
            "SELECT * FROM issuer WHERE issuer_id=?", (issuer_id,)
        ).fetchone()
        return Issuer(*row) if row else None

    def upsert_instrument(self, instrument: Instrument) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO instrument(instrument_id, issuer_id, isin, class,
                  status, superseded_by)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(instrument_id) DO UPDATE SET
                    issuer_id=excluded.issuer_id,
                    isin=excluded.isin,
                    class=excluded.class,
                    status=excluded.status,
                    superseded_by=excluded.superseded_by""",
                (instrument.instrument_id, instrument.issuer_id, instrument.isin,
                 instrument.class_, instrument.status, instrument.superseded_by),
            )

    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        row = self.conn.execute(
            "SELECT * FROM instrument WHERE instrument_id=?", (instrument_id,)
        ).fetchone()
        return Instrument(*row) if row else None

    def upsert_listing(self, listing: Listing) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO listing(listing_id, instrument_id, exchange, currency,
                  is_primary, first_trade_date, last_trade_date)
                  VALUES (?, ?, ?, ?, ?, ?, ?)
                  ON CONFLICT(listing_id) DO UPDATE SET
                    instrument_id=excluded.instrument_id,
                    exchange=excluded.exchange,
                    currency=excluded.currency,
                    is_primary=excluded.is_primary,
                    first_trade_date=excluded.first_trade_date,
                    last_trade_date=excluded.last_trade_date""",
                (listing.listing_id, listing.instrument_id, listing.exchange,
                 listing.currency, listing.is_primary,
                 listing.first_trade_date, listing.last_trade_date),
            )

    def add_ticker_history(self, listing_id: str, ticker: str,
                           valid_from: str, valid_to: Optional[str],
                           reason: Optional[str], source_ref: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO ticker_history(listing_id, ticker, valid_from,
                  valid_to, reason, source_ref)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(listing_id, valid_from) DO NOTHING""",
                (listing_id, ticker, valid_from, valid_to, reason, source_ref),
            )

    def resolve_ticker(self, ticker: str, market: str, as_of: str) -> Optional[str]:
        """ADR-0005: разрешение тикера с датой. Возвращает instrument_id или None."""
        row = self.conn.execute(
            """SELECT i.instrument_id
               FROM ticker_history th
               JOIN listing l ON th.listing_id = l.listing_id
               JOIN instrument i ON l.instrument_id = i.instrument_id
               WHERE th.ticker = ? AND l.exchange = ?
                 AND th.valid_from <= ?
                 AND (th.valid_to IS NULL OR th.valid_to >= ?)
               ORDER BY th.valid_from DESC LIMIT 1""",
            (ticker, market, as_of, as_of),
        ).fetchone()
        return row[0] if row else None


class RawRepo:
    """Content-addressed store + манифест. Пишет в raw_object для FK."""

    def __init__(self, paths: AppPaths, conn: sqlite3.Connection):
        self.paths = paths
        self.conn = conn

    def put(self, data: bytes, **kwargs) -> StoredObject:
        ensure_app_dir(self.paths)
        obj = put_object(self.paths.raw_store, data, **kwargs)
        append_manifest_line(self.paths.raw_manifests, obj)
        # Также в индекс raw_object в БД (FK для fact.source_ref)
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO raw_object(sha256, provider, url, fetched_at, bytes,
                  content_type, compression, instrument_id, block, http_status, etag)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                  ON CONFLICT(sha256) DO NOTHING""",
                (obj.sha256, obj.provider, obj.url, obj.fetched_at,
                 obj.bytes_written, obj.content_type, obj.compression,
                 obj.instrument_id, obj.block, obj.http_status, obj.etag),
            )
        return obj

    def has(self, sha256: str) -> bool:
        return has_object(self.paths.raw_store, sha256)

    def get(self, sha256: str) -> bytes:
        return decompress_object(self.paths.raw_store, sha256)

    def get_raw(self, sha256: str) -> bytes:
        """Прочитать как лежит на диске (без декомпрессии)."""
        from .raw_store import read_object
        return read_object(self.paths.raw_store, sha256)


class FactRepo:
    """Запись и выборка фактов. Только вставка; исправление — новый факт + superseded_by."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert_fact(self,
                    fact_id: str,
                    issuer_id: Optional[str],
                    listing_id: Optional[str],
                    concept: str,
                    period_start: str,
                    period_end: str,
                    period_type: str,
                    value: Optional[str],
                    unit: str,
                    currency: Optional[str],
                    basis: str,  # as_reported | restated
                    origin: str,  # extracted | manual
                    source_ref: str,
                    locator: dict,
                    parser_version: str,
                    status: str = "ok",
                    superseded_by: Optional[str] = None) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO fact(fact_id, issuer_id, listing_id, concept,
                  period_start, period_end, period_type, value, unit, currency,
                  basis, origin, source_ref, locator, parser_version,
                  status, superseded_by, ingested_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fact_id, issuer_id, listing_id, concept,
                 period_start, period_end, period_type, value, unit, currency,
                 basis, origin, source_ref, json.dumps(locator, ensure_ascii=False),
                 parser_version, status, superseded_by, time.time()),
            )

    def get_facts(self, issuer_id: Optional[str] = None,
                  listing_id: Optional[str] = None,
                  concept: Optional[str] = None,
                  period_end: Optional[str] = None) -> List[sqlite3.Row]:
        """Гибкая выборка. Все условия — AND."""
        where = []
        params = []
        if issuer_id:
            where.append("issuer_id = ?")
            params.append(issuer_id)
        if listing_id:
            where.append("listing_id = ?")
            params.append(listing_id)
        if concept:
            where.append("concept = ?")
            params.append(concept)
        if period_end:
            where.append("period_end = ?")
            params.append(period_end)
        sql = "SELECT * FROM fact"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY period_end DESC, ingested_at DESC"
        return self.conn.execute(sql, params).fetchall()

    def mark_superseded(self, old_fact_id: str, new_fact_id: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                "UPDATE fact SET superseded_by = ? WHERE fact_id = ?",
                (new_fact_id, old_fact_id),
            )


class SnapshotRepo:
    """Версии снапшотов, блоки, measure, lineage."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_snapshot(self, snapshot_id: str, instrument_id: str,
                        version: int, as_of: str,
                        peer_set_version: Optional[str],
                        peer_set_status: Optional[str],
                        status: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO snapshot(snapshot_id, instrument_id, version,
                  as_of, built_at, peer_set_version, peer_set_status, status)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (snapshot_id, instrument_id, version, as_of,
                 time.time(), peer_set_version, peer_set_status, status),
            )

    def add_block(self, snapshot_id: str, block: str,
                  status: str, reason: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO snapshot_block(snapshot_id, block, status, reason)
                  VALUES (?, ?, ?, ?)""",
                (snapshot_id, block, status, reason),
            )

    def insert_measure(self,
                       measure_id: str,
                       snapshot_id: str,
                       scope: str,
                       scope_ref: str,
                       concept: str,
                       value: Optional[str],
                       unit: str,
                       period_start: str,
                       period_end: str,
                       formula_id: Optional[str],
                       method_version: Optional[str],
                       null_reason: Optional[str],
                       peer_set_version: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO measure(measure_id, snapshot_id, scope, scope_ref,
                  concept, value, unit, period_start, period_end,
                  formula_id, method_version, null_reason, peer_set_version)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (measure_id, snapshot_id, scope, scope_ref, concept,
                 value, unit, period_start, period_end,
                 formula_id, method_version, null_reason, peer_set_version),
            )

    def add_lineage(self, measure_id: str, fact_id: Optional[str],
                    peer_measure_id: Optional[str], role: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO measure_lineage(measure_id, fact_id, peer_measure_id, role)
                  VALUES (?, ?, ?, ?)""",
                (measure_id, fact_id, peer_measure_id, role),
            )


class PeerSetRepo:
    """Версии наборов и состав. Версия неизменяема."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_peer_set(self, peer_set_id: str, scope_kind: str, scope_ref: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO peer_set(peer_set_id, scope_kind, scope_ref)
                  VALUES (?, ?, ?)
                  ON CONFLICT(peer_set_id) DO NOTHING""",
                (peer_set_id, scope_kind, scope_ref),
            )

    def add_version(self,
                    peer_set_version_id: str,
                    peer_set_id: str,
                    version: int,
                    valid_from: str,
                    valid_to: Optional[str],
                    origin: str,
                    method_version: str,
                    approved_by_user: bool,
                    approved_at: Optional[float],
                    criteria: Optional[dict]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO peer_set_version(peer_set_version_id, peer_set_id,
                  version, valid_from, valid_to, origin, method_version,
                  approved_by_user, approved_at, criteria)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (peer_set_version_id, peer_set_id, version, valid_from,
                 valid_to, origin, method_version,
                 int(approved_by_user), approved_at,
                 json.dumps(criteria) if criteria else None),
            )

    def add_member(self, peer_set_version_id: str, instrument_id: str,
                   reason: Optional[str], excluded_stale: int = 0) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO peer_set_member(peer_set_version_id, instrument_id,
                  reason, excluded_stale)
                  VALUES (?, ?, ?, ?)
                  ON CONFLICT(peer_set_version_id, instrument_id) DO UPDATE SET
                    reason=excluded.reason,
                    excluded_stale=excluded.excluded_stale""",
                (peer_set_version_id, instrument_id, reason, excluded_stale),
            )


class WatchlistRepo:
    """Версии списков, групп, фильтров. Изменение — новая версия целиком."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_watchlist(self, watchlist_id: str, name: str,
                         description: Optional[str],
                         update_schedule: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist(watchlist_id, name, description,
                  update_schedule, created_at)
                  VALUES (?, ?, ?, ?, ?)""",
                (watchlist_id, name, description, update_schedule, time.time()),
            )

    def new_version(self, watchlist_version_id: str, watchlist_id: str,
                    version: int, action: str, note: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_version(watchlist_version_id, watchlist_id,
                  version, created_at, action, note)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (watchlist_version_id, watchlist_id, version, time.time(), action, note),
            )

    def add_member(self, watchlist_version_id: str, instrument_id: str,
                   note: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id, instrument_id,
                  note, added_at)
                  VALUES (?, ?, ?, ?)""",
                (watchlist_version_id, instrument_id, note, time.time()),
            )


class JobRepo:
    """Очередь, попытки, отложенные. Постановка идемпотентна по ключу."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def enqueue(self,
                job_id: str,
                instrument_id: str,
                block: str,
                provider: str,
                target_date: Optional[str],
                url: Optional[str],
                priority: int,
                idempotency_key: str,
                not_before: Optional[float] = None) -> bool:
        """Возвращает True если поставлено, False если уже есть с таким ключом."""
        try:
            with writer_transaction(self.conn) as c:
                c.execute(
                    """INSERT INTO job(job_id, instrument_id, block, provider,
                      target_date, url, priority, status, attempt, not_before,
                      created_at, idempotency_key, last_error)
                      VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?, ?, NULL)""",
                    (job_id, instrument_id, block, provider,
                     target_date, url, priority, not_before,
                     time.time(), idempotency_key),
                )
            return True
        except sqlite3.IntegrityError:
            return False  # дубликат idempotency_key


class AuditRepo:
    """Журнал операций: только добавление, дублирование в файл."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def log(self, action: str, target: Optional[str],
            payload: Optional[dict], confirmed: bool, result: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO audit_log(ts, action, target, payload, confirmed, result)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (time.time(), action, target,
                 json.dumps(payload) if payload else None,
                 int(confirmed), result),
            )


# Фабрика для получения всех репозиториев
class RepoRegistry:
    def __init__(self, conn: sqlite3.Connection, paths: AppPaths):
        self.conn = conn
        self.paths = paths
        self.instrument = InstrumentRepo(conn)
        self.raw = RawRepo(paths, conn)
        self.fact = FactRepo(conn)
        self.snapshot = SnapshotRepo(conn)
        self.peer_set = PeerSetRepo(conn)
        self.watchlist = WatchlistRepo(conn)
        self.job = JobRepo(conn)
        self.audit = AuditRepo(conn)
