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
from datetime import date

from rusterm.reasons import is_known_reason
from rusterm.applog import APP_LOG_BACKUP_COUNT, APP_LOG_MAX_BYTES
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

    def issuer_count(self) -> int:
        """Эмитентов в локальной базе (ТЗ-21 H1: markets показывает
        счётчик; SQL живёт в слое хранилища — приёмка, пункт 7)."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM issuer").fetchone()[0]

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

    def resolve_ticker_candidates(self, ticker: str, market: str,
                                  as_of: str) -> List[str]:
        """Все инструмент-id, подходящие под (тикер, рынок, дата).
        Один — однозначно; несколько — неоднозначно; ноль — не найден.
        Рынок сверяется с площадкой листинга через реестр рынков
        (TASK-18 G1/G2): площадка unknown рынку не противоречит."""
        from rusterm.markets import venue_in_market
        rows = self.conn.execute(
            """SELECT DISTINCT i.instrument_id, l.exchange
               FROM ticker_history th
               JOIN listing l ON th.listing_id = l.listing_id
               JOIN instrument i ON l.instrument_id = i.instrument_id
               WHERE th.ticker = ?
                 AND th.valid_from <= ?
                 AND (th.valid_to IS NULL OR th.valid_to >= ?)""",
            (ticker, as_of, as_of),
        ).fetchall()
        return [r[0] for r in rows if venue_in_market(r[1], market)]

    def ticker_for_instrument(self, instrument_id: str,
                              as_of: str) -> Optional[dict]:
        """Действующий (тикер, рынок) инструмента на дату — для
        тикерной адресации экспорта."""
        row = self.conn.execute(
            """SELECT th.ticker, l.exchange
               FROM ticker_history th
               JOIN listing l ON th.listing_id = l.listing_id
               WHERE l.instrument_id = ?
                 AND th.valid_from <= ?
                 AND (th.valid_to IS NULL OR th.valid_to >= ?)
               ORDER BY th.valid_from DESC LIMIT 1""",
            (instrument_id, as_of, as_of),
        ).fetchone()
        if row is None:
            return None
        return {"ticker": row[0], "market": row[1]}


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

    def delete_index_entry(self, sha256: str) -> bool:
        """Убрать объект из индекса БД. Файл и манифест остаются:
        манифест — ведущий, повторная загрузка вернёт объект по sha."""
        from .raw_store import object_path
        with writer_transaction(self.conn) as c:
            cur = c.execute("DELETE FROM raw_object WHERE sha256=?",
                            (sha256,))
        target = object_path(self.paths.raw_store, sha256)
        for p in (target,
                  target.with_suffix(target.suffix + ".gz"),
                  target.with_suffix(target.suffix + ".zst")):
            if p.exists():
                p.unlink()
        return cur.rowcount > 0

    def objects_without_facts(self) -> list:
        """Объекты, на которые не ссылается ни один факт — кандидаты
        очистки (конвейер, policy facts_only)."""
        return self.conn.execute(
            """SELECT ro.sha256, ro.block, ro.instrument_id
               FROM raw_object ro
               LEFT JOIN fact f ON f.source_ref = ro.sha256
               WHERE f.fact_id IS NULL"""
        ).fetchall()


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
                    superseded_by: Optional[str] = None,
                    canonical_concept: Optional[str] = None,
                    concept_map_version: Optional[str] = None,
                    source_kind: str = "provider") -> None:
        """source_kind (миграция 40, ADR-0011): 'provider' | 'manual'.
        Параметр добавлен полосой L6 (ТЗ-20); дефолт сохраняет смысл
        всех прежних вызовов — машинные факты неразличимы как раньше."""
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO fact(fact_id, issuer_id, listing_id, concept,
                  period_start, period_end, period_type, value, unit, currency,
                  basis, origin, source_ref, locator, parser_version,
                  status, superseded_by, ingested_at,
                  canonical_concept, concept_map_version, source_kind)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fact_id, issuer_id, listing_id, concept,
                 period_start, period_end, period_type, value, unit, currency,
                 basis, origin, source_ref, json.dumps(locator, ensure_ascii=False),
                 parser_version, status, superseded_by, time.time(),
                 canonical_concept, concept_map_version, source_kind),
            )

    _FACT_COLUMNS = (
        "fact_id", "issuer_id", "listing_id", "concept", "period_start",
        "period_end", "period_type", "value", "unit", "currency", "basis",
        "origin", "source_ref", "locator", "parser_version", "status",
        "superseded_by", "canonical_concept", "concept_map_version",
        "source_kind",
    )

    def get_fact(self, fact_id: str) -> Optional[dict]:
        """Один факт по id (верификация: что было показано). Словарь,
        чтобы не зависеть от row_factory соединения."""
        cols = ", ".join(self._FACT_COLUMNS)
        row = self.conn.execute(
            f"SELECT {cols} FROM fact WHERE fact_id=?", (fact_id,)).fetchone()
        return dict(zip(self._FACT_COLUMNS, row)) if row else None

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

    def count_for_issuer_concept(self, issuer_id: str, concept: str) -> int:
        """Сколько фактов концепта у эмитента (для flag_parser)."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM fact WHERE issuer_id=? AND concept=?",
            (issuer_id, concept)).fetchone()[0]

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

    def get_measures(self, snapshot_id: str) -> list:
        """Меры снапшота для экспорта: готовые величины, без пересчёта."""
        return self.conn.execute(
            """SELECT measure_id, scope, scope_ref, concept, value, unit,
                      period_start, period_end, formula_id, method_version,
                      null_reason, peer_set_version
               FROM measure WHERE snapshot_id=? ORDER BY concept""",
            (snapshot_id,)).fetchall()

    def get_snapshot(self, snapshot_id: str) -> Optional[dict]:
        row = self.conn.execute(
            """SELECT snapshot_id, instrument_id, version, as_of, built_at,
                      peer_set_version, peer_set_status, status
               FROM snapshot WHERE snapshot_id=?""",
            (snapshot_id,)).fetchone()
        if row is None:
            return None
        return {"snapshot_id": row[0], "instrument_id": row[1],
                "version": row[2], "as_of": row[3], "built_at": row[4],
                "peer_set_version": row[5], "peer_set_status": row[6],
                "status": row[7]}

    def latest_snapshot_id(self, instrument_id: str) -> Optional[str]:
        row = self.conn.execute(
            """SELECT snapshot_id FROM snapshot WHERE instrument_id=?
               ORDER BY version DESC LIMIT 1""",
            (instrument_id,)).fetchone()
        return row[0] if row else None

    def max_version(self, instrument_id: str) -> int:
        row = self.conn.execute(
            "SELECT MAX(version) FROM snapshot WHERE instrument_id=?",
            (instrument_id,)).fetchone()
        return row[0] or 0

    def latest_per_instrument(self) -> list:
        """Последний снапшот каждого инструмента: для rusterm status."""
        rows = self.conn.execute(
            """SELECT instrument_id, snapshot_id, version, as_of
               FROM snapshot s
               WHERE version = (SELECT MAX(version) FROM snapshot
                                WHERE instrument_id = s.instrument_id)
               ORDER BY instrument_id""").fetchall()
        keys = ("instrument_id", "snapshot_id", "version", "as_of")
        return [dict(zip(keys, r)) for r in rows]

    def previous_snapshot(self, instrument_id: str) -> Optional[str]:
        """Предпоследняя версия: база для diff текущей сборки."""
        row = self.conn.execute(
            """SELECT snapshot_id FROM snapshot WHERE instrument_id=?
               ORDER BY version DESC LIMIT 1 OFFSET 1""",
            (instrument_id,)).fetchone()
        return row[0] if row else None

    def restated_revisions(self, issuer_id: str) -> list:
        """Ревизии ОДНОГО эмитента: restated-факты по периодам, где есть
        as_reported (TASK-14 A2: без фильтра diff снапшота показывал
        ревизии всех эмитентов базы; вызовов «по всем» нет и быть не
        должно)."""
        return self.conn.execute(
            """SELECT f.concept, f.period_end FROM fact f
               WHERE f.issuer_id=? AND f.basis='restated' AND EXISTS (
                     SELECT 1 FROM fact a
                     WHERE a.issuer_id=f.issuer_id AND a.concept=f.concept
                       AND a.period_end=f.period_end
                       AND a.basis='as_reported')""",
            (issuer_id,)
        ).fetchall()

    def lineage_fact_ids(self, measure_id: str) -> List[str]:
        """fact_id входов меры — для панели источника в TUI (TASK-8 U11)."""
        rows = self.conn.execute(
            "SELECT fact_id FROM measure_lineage"
            " WHERE measure_id=? AND fact_id IS NOT NULL",
            (measure_id,)).fetchall()
        return [r[0] for r in rows]

    def instruments_for_fact(self, fact_id: str) -> List[str]:
        """Инструменты, чьи снапшоты содержат меры с lineage,
        ссылающимся на факт (процесс 5, узел recompute)."""
        rows = self.conn.execute(
            """SELECT DISTINCT s.instrument_id
               FROM measure_lineage ml
               JOIN measure m ON m.measure_id = ml.measure_id
               JOIN snapshot s ON s.snapshot_id = m.snapshot_id
               WHERE ml.fact_id = ?""",
            (fact_id,)).fetchall()
        return [r[0] for r in rows]

    def as_reported_facts(self, issuer_id: str, concepts: tuple) -> list:
        """Свежие as_reported-факты эмитента по списку КАНОНИЧЕСКИХ
        концептов (TASK-9 V0): тег источника остаётся в concept, а мера
        собирается по canonical_concept. Возвращает unit и периоды, чтобы
        выбор одного периода шёл без второго запроса."""
        placeholders = ",".join("?" * len(concepts))
        return self.conn.execute(
            f"""SELECT concept, value, fact_id, unit, period_start,
                       period_end, canonical_concept
                FROM fact
                WHERE issuer_id=? AND basis='as_reported' AND status='ok'
                  AND canonical_concept IN ({placeholders})
                ORDER BY period_end DESC, ingested_at DESC""",
            (issuer_id, *concepts)).fetchall()

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
        if not is_known_reason(null_reason):
            raise ValueError(
                f"null_reason {null_reason!r} вне словаря"
                "(rusterm/reasons.py, B15)")
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

    def currencies_for_measure(self, measure_id: str) -> set[str]:
        """Валюты входных фактов меры (ТЗ-21 H3): через lineage. С ТЗ-22
        J1.0 пустая валюта приходит пустой строкой, а не отбрасывается:
        решает страж (смешение записанной валюты с пустотой — отказ).
        ТЗ-23 K4/K6: у оценочных мер (market_cap_total, ev) цена не
        факт, валюта живёт в unit меры — трёхбуквенный unit добавляется
        к набору тем же правилом currency_of_unit."""
        rows = self.conn.execute(
            """SELECT DISTINCT f.currency FROM measure_lineage l
               JOIN fact f ON f.fact_id = l.fact_id
               WHERE l.measure_id = ?""", (measure_id,)).fetchall()
        out = {(r[0] or "") for r in rows}
        from rusterm.core.fact import currency_of_unit
        unit = self.conn.execute(
            "SELECT unit FROM measure WHERE measure_id=?",
            (measure_id,)).fetchone()
        if unit and currency_of_unit(unit[0]):
            out.add(unit[0])
        return out

    def fact_currency(self, fact_id: str) -> Optional[str]:
        """Записанная валюта факта (ТЗ-23 K4/K6): проверка валют
        числителя и знаменателя оценочных мер."""
        row = self.conn.execute(
            "SELECT currency FROM fact WHERE fact_id=?", (fact_id,)
        ).fetchone()
        return row[0] if row else None

    def period_ends_for_measures(self, measure_ids: list[str]) -> dict:
        """Концы периодов мер (ТЗ-22 J3): для проверки разрыва
        календарей у пиров; без меры — записи нет."""
        out: dict[str, str] = {}
        for mid in measure_ids:
            row = self.conn.execute(
                "SELECT period_end FROM measure WHERE measure_id=?",
                (mid,)).fetchone()
            if row and row[0]:
                out[mid] = row[0]
        return out

    def measure_currency(self, measure_id: str, concept: str) -> Optional[str]:
        """Валюта, в которой заявлена мера (ТЗ-22 J1): записанная
        валюта входов для абсолютной меры; смешение — строка отказа с
        перечнем; безразмерным мерам и легаси-наборам — None."""
        from rusterm.core.peers import currency_bound, currency_guard
        if not currency_bound(concept):
            return None
        currencies = self.currencies_for_measure(measure_id)
        mismatch = currency_guard(concept, currencies)
        if mismatch is not None:
            return mismatch
        present = sorted({c.strip().upper() for c in currencies
                          if c and c.strip()})
        return present[0] if len(present) == 1 else None

    def add_lineage(self, measure_id: str, fact_id: Optional[str],
                    peer_measure_id: Optional[str], role: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO measure_lineage(measure_id, fact_id, peer_measure_id, role)
                  VALUES (?, ?, ?, ?)""",
                (measure_id, fact_id, peer_measure_id, role),
            )

    def insert_measure_with_lineage(self, measure: dict,
                                    lineage: list[dict]) -> str:
        """I4: measure без measure_lineage не записывается — исключение
        только value IS NULL при отсутствующих входах: тогда lineage пуст,
        а null_reason обязателен и объясняет, чего не хватило (data-model §4).

        measure и lineage пишутся одной транзакцией — полусостояний нет.
        lineage: [{"fact_id": ...}|{"peer_measure_id": ...}, "role": ...}]
        """
        value = measure.get("value")
        null_reason = measure.get("null_reason")
        if value is not None and not lineage:
            raise ValueError("I4: measure без lineage не записывается")
        if value is None and not null_reason:
            raise ValueError("I4: value IS NULL требует null_reason")
        if not is_known_reason(null_reason):
            raise ValueError(
                f"null_reason {null_reason!r} вне словаря"
                "(rusterm/reasons.py, B15)")
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO measure(measure_id, snapshot_id, scope, scope_ref,
                  concept, value, unit, period_start, period_end,
                  formula_id, method_version, null_reason, peer_set_version)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (measure["measure_id"], measure["snapshot_id"],
                 measure["scope"], measure["scope_ref"], measure["concept"],
                 value, measure["unit"], measure["period_start"],
                 measure["period_end"], measure.get("formula_id"),
                 measure.get("method_version"), null_reason,
                 measure.get("peer_set_version")))
            for l in lineage:
                c.execute(
                    """INSERT INTO measure_lineage(measure_id, fact_id,
                      peer_measure_id, role) VALUES (?, ?, ?, ?)""",
                    (measure["measure_id"], l.get("fact_id"),
                     l.get("peer_measure_id"), l["role"]))
        return measure["measure_id"]


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

    def peer_status_for_instrument(self, instrument_id: str) -> Optional[str]:
        """verified/unverified по последней версии peer set, где состоит
        инструмент; None — не состоит ни в одной (TASK-8 U11)."""
        row = self.conn.execute(
            """SELECT psv.approved_by_user
               FROM peer_set_member m
               JOIN peer_set_version psv
                 ON m.peer_set_version_id = psv.peer_set_version_id
               WHERE m.instrument_id = ?
               ORDER BY psv.valid_from DESC, psv.version DESC LIMIT 1""",
            (instrument_id,)).fetchone()
        if row is None:
            return None
        return "verified" if row[0] else "unverified"

    def peer_set_for_instrument(self, instrument_id: str) -> Optional[dict]:
        """Последняя версия peer set инструмента с origin — read-only
        инструмент get_peer_set (TASK-16 D2, docs §2.4)."""
        row = self.conn.execute(
            """SELECT psv.peer_set_version_id, psv.peer_set_id, psv.version,
                      psv.origin, psv.valid_from, psv.approved_by_user
               FROM peer_set_member m
               JOIN peer_set_version psv
                 ON m.peer_set_version_id = psv.peer_set_version_id
               WHERE m.instrument_id = ?
               ORDER BY psv.valid_from DESC, psv.version DESC LIMIT 1""",
            (instrument_id,)).fetchone()
        if row is None:
            return None
        return {"peer_set_version_id": row[0], "peer_set_id": row[1],
                "version": row[2], "origin": row[3],
                "valid_from": row[4],
                "approved": bool(row[5])}


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

    def exists(self, peer_set_id: str) -> bool:
        """Существует ли набор (TASK-17 E5: команда различает
        'не найден' и 'нет версии на дату')."""
        return self.conn.execute(
            "SELECT 1 FROM peer_set WHERE peer_set_id=?",
            (peer_set_id,)).fetchone() is not None

    def composition(self, peer_set_version_id: str) -> dict:
        """Состав набора: рынки и валюты участников (ТЗ-22 J2).

        Информация, не фильтр: пороги I6 не меняются. Рынок — код
        префикса instrument_id, известный реестру; валюта —
        записанная валюта фактов участников. scope называет набор
        single-market или mixed; колонка origin остаётся словарём
        происхождения (manual/catalog/...) — она решает
        верифицированность, и переименование её сломало бы.
        """
        from rusterm.markets import get_market
        members = [r[0] for r in self.conn.execute(
            """SELECT instrument_id FROM peer_set_member
               WHERE peer_set_version_id=? AND excluded_stale=0""",
            (peer_set_version_id,)).fetchall()]
        markets = sorted({m.split("-", 1)[0] for m in members
                          if get_market(m.split("-", 1)[0])})
        currencies = sorted({r[0] for r in self.conn.execute(
            """SELECT DISTINCT f.currency
               FROM peer_set_member m
               JOIN instrument i ON i.instrument_id = m.instrument_id
               JOIN fact f ON f.issuer_id = i.issuer_id
               WHERE m.peer_set_version_id=?
                 AND f.currency IS NOT NULL""",
            (peer_set_version_id,)).fetchall()})
        return {"markets": markets, "currencies": currencies,
                "members": sorted(members),
                "scope": "mixed" if len(markets) > 1
                else "single-market"}

    def latest_compositions(self) -> list[dict]:
        """Состав по каждому набору на его старшую версию — для
        `rusterm status` (ТЗ-22 J2)."""
        out = []
        for (ps_id,) in self.conn.execute(
                "SELECT peer_set_id FROM peer_set ORDER BY peer_set_id"):
            row = self.conn.execute(
                """SELECT peer_set_version_id, version
                   FROM peer_set_version WHERE peer_set_id=?
                   ORDER BY version DESC LIMIT 1""",
                (ps_id,)).fetchone()
            if row is None:
                continue
            entry = {"peer_set_id": ps_id, "version": row[1]}
            entry.update(self.composition(row[0]))
            out.append(entry)
        return out

    def version_at(self, peer_set_id: str, as_of: str) -> Optional[dict]:
        """Версия, чей интервал [valid_from, valid_to) покрывает дату
        (TASK-17 E2, §0.2 ruling 5). Два совпадения — дефект данных:
        ValueError называет оба, выбор не делается."""
        rows = self.conn.execute(
            """SELECT peer_set_version_id, version, origin, approved_by_user
               FROM peer_set_version
               WHERE peer_set_id=? AND valid_from<=?
                 AND (valid_to IS NULL OR ?<valid_to)
               ORDER BY valid_from""",
            (peer_set_id, as_of, as_of)).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise ValueError(
                f"несколько версий набора {peer_set_id!r} покрывают "
                f"{as_of}: {[r[0] for r in rows]}")
        return {"peer_set_version_id": rows[0][0], "version": rows[0][1],
                "origin": rows[0][2], "approved": bool(rows[0][3])}

    def member_snapshots_at(self, peer_set_version_id: str,
                            as_of: str) -> dict:
        """Для каждого участника версии — новейший снапшот с as_of<=даты
        (TASK-17 E2). Нет снапшота на дату — None: участник не вносит
        вклад и попадает в счётчик причин no_snapshot_at_date."""
        out: dict[str, Optional[str]] = {}
        for (iid,) in self.conn.execute(
                "SELECT instrument_id FROM peer_set_member"
                " WHERE peer_set_version_id=?",
                (peer_set_version_id,)).fetchall():
            row = self.conn.execute(
                """SELECT snapshot_id FROM snapshot
                   WHERE instrument_id=? AND as_of<=?
                   ORDER BY as_of DESC, version DESC LIMIT 1""",
                (iid, as_of)).fetchone()
            out[iid] = row[0] if row else None
        return out


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
                    version: int, action: str, note: Optional[str]) -> str:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_version(watchlist_version_id, watchlist_id,
                  version, created_at, action, note)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (watchlist_version_id, watchlist_id, version, time.time(), action, note),
            )
        return watchlist_version_id

    def add_member(self, watchlist_version_id: str, instrument_id: str,
                   note: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id, instrument_id,
                  note, added_at)
                  VALUES (?, ?, ?, ?)""",
                (watchlist_version_id, instrument_id, note, time.time()),
            )

    # ── Чтение и неизменяемое версионирование (TASK-7 T10) ────────────

    def current_version(self, watchlist_id: str) -> Optional[dict]:
        """Максимальная версия списка или None."""
        row = self.conn.execute(
            """SELECT watchlist_version_id, version, created_at, action, note
               FROM watchlist_version WHERE watchlist_id=?
               ORDER BY version DESC LIMIT 1""",
            (watchlist_id,)).fetchone()
        if row is None:
            return None
        return {"watchlist_version_id": row[0], "version": row[1],
                "created_at": row[2], "action": row[3], "note": row[4]}

    def _version_id(self, watchlist_id: str, version: int) -> Optional[str]:
        row = self.conn.execute(
            "SELECT watchlist_version_id FROM watchlist_version"
            " WHERE watchlist_id=? AND version=?",
            (watchlist_id, version)).fetchone()
        return row[0] if row else None

    def _resolve_version(self, watchlist_id: str,
                         version: Optional[int]) -> Optional[str]:
        if version is not None:
            return self._version_id(watchlist_id, version)
        current = self.current_version(watchlist_id)
        return current["watchlist_version_id"] if current else None

    def members(self, watchlist_id: str,
                version: Optional[int] = None) -> List[dict]:
        """Состав версии; без версии — текущей."""
        vid = self._resolve_version(watchlist_id, version)
        if vid is None:
            return []
        rows = self.conn.execute(
            """SELECT instrument_id, note, added_at FROM watchlist_member
               WHERE watchlist_version_id=? ORDER BY instrument_id""",
            (vid,)).fetchall()
        return [{"instrument_id": r[0], "note": r[1], "added_at": r[2]}
                for r in rows]

    def groups(self, watchlist_id: str,
               version: Optional[int] = None) -> List[dict]:
        vid = self._resolve_version(watchlist_id, version)
        if vid is None:
            return []
        rows = self.conn.execute(
            """SELECT g.group_id, g.name FROM watchlist_group g
               WHERE g.watchlist_version_id=? ORDER BY g.name""",
            (vid,)).fetchall()
        result = []
        for group_id, name in rows:
            members = self.conn.execute(
                "SELECT instrument_id FROM watchlist_group_member"
                " WHERE group_id=? ORDER BY instrument_id",
                (group_id,)).fetchall()
            result.append({"group_id": group_id, "name": name,
                           "instrument_ids": [m[0] for m in members]})
        return result

    def filters(self, watchlist_id: str,
                version: Optional[int] = None) -> List[dict]:
        vid = self._resolve_version(watchlist_id, version)
        if vid is None:
            return []
        rows = self.conn.execute(
            "SELECT criteria FROM watchlist_filter"
            " WHERE watchlist_version_id=?", (vid,)).fetchall()
        # criteria_json разбирается при выдаче, в базе лежит текстом
        return [json.loads(r[0]) for r in rows]

    def add_group(self, group_id: str, watchlist_id: str, version: int,
                  name: str) -> None:
        vid = self._version_id(watchlist_id, version)
        if vid is None:
            raise ValueError(f"версия {version} списка {watchlist_id!r} не найдена")
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_group(group_id, watchlist_version_id, name)
                  VALUES (?, ?, ?)""",
                (group_id, vid, name),
            )

    def add_group_member(self, group_id: str, instrument_id: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_group_member(group_id, instrument_id)
                  VALUES (?, ?)
                  ON CONFLICT(group_id, instrument_id) DO NOTHING""",
                (group_id, instrument_id),
            )

    def set_filter(self, watchlist_id: str, version: int,
                   criteria: dict) -> None:
        vid = self._version_id(watchlist_id, version)
        if vid is None:
            raise ValueError(f"версия {version} списка {watchlist_id!r} не найдена")
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_filter(watchlist_version_id, criteria)
                  VALUES (?, ?)
                  ON CONFLICT(watchlist_version_id) DO UPDATE SET
                    criteria=excluded.criteria""",
                (vid, json.dumps(criteria, ensure_ascii=False)),
            )

    def version_action(self, watchlist_id: str, version: int) -> Optional[str]:
        """action строки запрошенной версии; None — версии нет."""
        row = self.conn.execute(
            """SELECT wv.action FROM watchlist_version wv
               WHERE wv.watchlist_id=? AND wv.version=?""",
            (watchlist_id, version)).fetchone()
        return row[0] if row else None

    def copy_members(self, source_version_id: str,
                     target_version_id: str) -> None:
        """Перенести состав одной версии в другую (полный новый состав
        при импорте/откате)."""
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id,
                  instrument_id, note, added_at)
                  SELECT ?, instrument_id, note, added_at
                  FROM watchlist_member WHERE watchlist_version_id=?""",
                (target_version_id, source_version_id))

    def copy_members_except(self, source_version_id: str,
                            target_version_id: str,
                            instrument_id: str) -> int:
        """Полный новый состав без одного инструмента (удаление из
        состава — тоже новая версия). Возвращает число перенесённых."""
        with writer_transaction(self.conn) as c:
            cur = c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id,
                  instrument_id, note, added_at)
                  SELECT ?, instrument_id, note, added_at
                  FROM watchlist_member
                  WHERE watchlist_version_id=? AND instrument_id <> ?""",
                (target_version_id, source_version_id, instrument_id))
            return cur.rowcount

    def create_version_with_members(self, watchlist_id: str,
                                    action: str, note: Optional[str],
                                    members: list[tuple[str, str]]) -> dict:
        """Новая версия + прежний состав + добавленные участники в ОДНОЙ
        транзакции (TASK-16 D5, docs §3.2): сбой любого INSERT откатывает
        версию и участников целиком — полусписка не остаётся. Возвращает
        {watchlist_version_id, version}."""
        current = self.current_version(watchlist_id)
        if current is None:
            raise ValueError(f"список {watchlist_id!r} не найден")
        source_vid = current["watchlist_version_id"]
        new_number = current["version"] + 1
        vid = str(uuid.uuid4())
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_version(watchlist_version_id,
                  watchlist_id, version, created_at, action, note)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (vid, watchlist_id, new_number, time.time(), action, note))
            c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id,
                  instrument_id, note, added_at)
                  SELECT ?, instrument_id, note, added_at
                  FROM watchlist_member WHERE watchlist_version_id=?""",
                (vid, source_vid))
            for instrument_id, note_member in members:
                c.execute(
                    """INSERT INTO watchlist_member(watchlist_version_id,
                      instrument_id, note, added_at) VALUES (?, ?, ?, ?)""",
                    (vid, instrument_id, note_member, time.time()))
        return {"watchlist_version_id": vid, "version": new_number}

    def rollback_to(self, watchlist_id: str, version: int) -> dict:
        """Откат — НОВАЯ версия, копирующая состав указанной: состав
        (members), группы и фильтры. Ничего не удаляется и не переписывается;
        action='rollback:<n>' (TASK-7 T10)."""
        source_vid = self._version_id(watchlist_id, version)
        if source_vid is None:
            raise ValueError(f"версия {version} списка {watchlist_id!r} не найдена")
        new_number = self.current_version(watchlist_id)["version"] + 1
        new_vid = str(uuid.uuid4())
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO watchlist_version(watchlist_version_id,
                  watchlist_id, version, created_at, action, note)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (new_vid, watchlist_id, new_number, time.time(),
                 f"rollback:{version}", None))
            c.execute(
                """INSERT INTO watchlist_member(watchlist_version_id,
                  instrument_id, note, added_at)
                  SELECT ?, instrument_id, note, added_at
                  FROM watchlist_member WHERE watchlist_version_id=?""",
                (new_vid, source_vid))
            # group_id — глобальный PK: группа в новой версии получает
            # новый id, участники переносятся по карте старый->новый
            for old_gid, name in c.execute(
                    """SELECT group_id, name FROM watchlist_group
                       WHERE watchlist_version_id=?""",
                    (source_vid,)).fetchall():
                new_gid = str(uuid.uuid4())
                c.execute(
                    """INSERT INTO watchlist_group(group_id,
                      watchlist_version_id, name) VALUES (?, ?, ?)""",
                    (new_gid, new_vid, name))
                c.execute(
                    """INSERT INTO watchlist_group_member(group_id, instrument_id)
                       SELECT ?, instrument_id FROM watchlist_group_member
                       WHERE group_id=?""",
                    (new_gid, old_gid))
            c.execute(
                """INSERT INTO watchlist_filter(watchlist_version_id, criteria)
                  SELECT ?, criteria FROM watchlist_filter
                  WHERE watchlist_version_id=?""",
                (new_vid, source_vid))
        return {"watchlist_version_id": new_vid, "version": new_number,
                "action": f"rollback:{version}"}

    def list_watchlists(self) -> List[dict]:
        """Все списки: id, имя, текущая версия, число участников."""
        rows = self.conn.execute(
            """SELECT w.watchlist_id, w.name, MAX(wv.version),
                      (SELECT COUNT(*) FROM watchlist_member wm
                       WHERE wm.watchlist_version_id = wv.watchlist_version_id)
               FROM watchlist w
               JOIN watchlist_version wv ON wv.watchlist_id = w.watchlist_id
               GROUP BY w.watchlist_id, w.name
               ORDER BY w.name""",
        ).fetchall()
        return [{"watchlist_id": r[0], "name": r[1], "version": r[2],
                 "member_count": r[3]} for r in rows]


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

    def claim(self, job_id: str) -> None:
        """Взять задание в работу: queued -> running."""
        with writer_transaction(self.conn) as c:
            c.execute("UPDATE job SET status='running' WHERE job_id=?",
                      (job_id,))

    def finish(self, job_id: str) -> None:
        """Закрыть задание успешно."""
        with writer_transaction(self.conn) as c:
            c.execute(
                "UPDATE job SET status='done', finished_at=? WHERE job_id=?",
                (time.time(), job_id))

    def last_poll_date(self, instrument_id: str,
                       block: str = "prices") -> Optional[str]:
        """Дата последнего успешного обхода (ТЗ-23 K5): MAX(target_date)
        по закрытым заданиям обхода. Строка, а не timestamp: каденция
        живёт в днях и дружит с фальшивыми часами тестов."""
        row = self.conn.execute(
            """SELECT MAX(target_date) FROM job
               WHERE instrument_id=? AND block=? AND status='done'""",
            (instrument_id, block)).fetchone()
        return row[0] if row else None

    def fail(self, job_id: str, error: str, retry: bool,
             not_before: Optional[float] = None) -> None:
        """Провал попытки: retry -> снова в очередь с паузой, иначе dead-letter."""
        with writer_transaction(self.conn) as c:
            c.execute(
                """UPDATE job SET
                     attempt = attempt + 1,
                     status = CASE WHEN ? THEN 'queued' ELSE 'dead' END,
                     not_before = ?,
                     last_error = ?
                   WHERE job_id=?""",
                (retry, not_before, error, job_id))

    # ── Курсоры инкрементальности (data-model.md §2: source_cursor) ──

    def get_cursor(self, provider: str, index_kind: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT cursor FROM source_cursor WHERE provider=? AND index_kind=?",
            (provider, index_kind)).fetchone()
        return row[0] if row else None

    def set_cursor(self, provider: str, index_kind: str, cursor: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO source_cursor(provider, index_kind, last_seen_at, cursor, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(provider, index_kind) DO UPDATE SET
                     cursor=excluded.cursor, updated_at=excluded.updated_at""",
                (provider, index_kind, time.time(), cursor, time.time()))

    # ── Coverage (data-model.md §4) ─────────────────────────────────

    def coverage_upsert(self, instrument_id: str, block: str,
                        status: str, reason: Optional[str]) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO coverage(instrument_id, block, status, last_update, reason)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(instrument_id, block) DO UPDATE SET
                     status=excluded.status, last_update=excluded.last_update,
                     reason=excluded.reason""",
                (instrument_id, block, status, time.time(), reason))

    def get_coverage(self, instrument_id: str, block: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT status, reason FROM coverage WHERE instrument_id=? AND block=?",
            (instrument_id, block)).fetchone()
        if row is None:
            return None
        return {"status": row[0], "reason": row[1]}


def persist_ingestion_results(conn: sqlite3.Connection,
                              fact_dicts: list[dict],
                              coverage_rows: list[tuple]) -> None:
    """Узел 8 процесса 1 (processes.md): факты + обновление coverage
    одной транзакцией. Сбой на середине откатывает всё целиком —
    полусостояний не остаётся.

    fact_dicts — словари факта по data-model.md §3 (как их отдаёт парсер,
    с добавленным fact_id). coverage_rows — (instrument_id, block, status, reason).
    """
    with writer_transaction(conn) as c:
        for f in fact_dicts:
            c.execute(
                """INSERT INTO fact(fact_id, issuer_id, listing_id, concept,
                  period_start, period_end, period_type, value, unit, currency,
                  basis, origin, source_ref, locator, parser_version,
                  status, superseded_by, ingested_at,
                  canonical_concept, concept_map_version)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f["fact_id"], f.get("issuer_id"), f.get("listing_id"),
                 f["concept"], f["period_start"], f["period_end"],
                 f["period_type"], f.get("value"), f["unit"],
                 f.get("currency"), f["basis"], f["origin"],
                 f["source_ref"], json.dumps(f["locator"], ensure_ascii=False),
                 f["parser_version"], f.get("status", "ok"),
                 f.get("superseded_by"), time.time(),
                 f.get("canonical_concept"), f.get("concept_map_version")))
        for instrument_id, block, status, reason in coverage_rows:
            c.execute(
                """INSERT INTO coverage(instrument_id, block, status, last_update, reason)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(instrument_id, block) DO UPDATE SET
                     status=excluded.status, last_update=excluded.last_update,
                     reason=excluded.reason""",
                (instrument_id, block, status, time.time(), reason))


# Блоки покрытия и их статусы — ровно эти восемь и пять
# (docs/watchlist-and-llm.md §1.3, TASK-7 T7).
COVERAGE_BLOCKS: tuple = (
    "prices", "fundamentals", "ownership", "corporate_actions",
    "governance", "industry_metrics", "peer_set", "llm_summary",
)
COVERAGE_STATUSES: tuple = (
    "ready", "stale", "processing", "missing", "error",
)


class CoverageRepo:
    """Покрытие по (instrument, блок). Пробел показывается, а не
    замалчивается: missing/error без непустой причины не записываются —
    запрет enforced здесь, а не на совести вызывающего (TASK-7 T7)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, instrument_id: str, block: str, status: str,
               last_update: Optional[float] = None,
               reason: Optional[str] = None) -> None:
        if block not in COVERAGE_BLOCKS:
            raise ValueError(f"I-coverage: неизвестный блок {block!r}")
        if status not in COVERAGE_STATUSES:
            raise ValueError(f"I-coverage: неизвестный статус {status!r}")
        if status in ("missing", "error") and not (reason and reason.strip()):
            raise ValueError(
                f"I-coverage: {status} требует непустую причину")
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO coverage(instrument_id, block, status, last_update, reason)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(instrument_id, block) DO UPDATE SET
                     status=excluded.status, last_update=excluded.last_update,
                     reason=excluded.reason""",
                (instrument_id, block, status,
                 last_update if last_update is not None else time.time(),
                 reason))

    def for_instrument(self, instrument_id: str) -> List[dict]:
        rows = self.conn.execute(
            """SELECT instrument_id, block, status, last_update, reason
               FROM coverage WHERE instrument_id=? ORDER BY block""",
            (instrument_id,)).fetchall()
        return [self._as_dict(r) for r in rows]

    def for_watchlist(self, watchlist_id: str) -> List[dict]:
        """Покрытие всех инструментов текущей версии списка."""
        rows = self.conn.execute(
            """SELECT c.instrument_id, c.block, c.status, c.last_update, c.reason
               FROM coverage c
               WHERE c.instrument_id IN (
                   SELECT wm.instrument_id
                   FROM watchlist_member wm
                   JOIN watchlist_version wv
                     ON wm.watchlist_version_id = wv.watchlist_version_id
                   WHERE wv.watchlist_id = ?
                     AND wv.version = (
                         SELECT MAX(version) FROM watchlist_version
                         WHERE watchlist_id = ?))
               ORDER BY c.instrument_id, c.block""",
            (watchlist_id, watchlist_id)).fetchall()
        return [self._as_dict(r) for r in rows]

    @staticmethod
    def _as_dict(row) -> dict:
        # Словарь, а не sqlite3.Row: репозиторий не зависит от row_factory.
        return {"instrument_id": row[0], "block": row[1], "status": row[2],
                "last_update": row[3], "reason": row[4]}

    def status_summary(self) -> dict:
        """Число блоков покрытия по статусам — для rusterm status."""
        summary = {status: 0 for status in COVERAGE_STATUSES}
        for status, n in self.conn.execute(
                "SELECT status, COUNT(*) FROM coverage GROUP BY status"):
            summary[status] = n
        return summary

    def ensure_all(self, instrument_id: str,
                   known: dict[str, tuple[str, Optional[str]]],
                   source_errors: Optional[dict] = None) -> None:
        """После сборки снапшота у инструмента существуют все восемь строк
        покрытия — пробел не замалчивается (TASK-7 T7).

        known — блоки, статус которых сборка знает сама. source_errors —
        блоки, чей сборщик вернул E1/E2: строка получает error с причиной
        (docs/threat-model-sources.md §2 class A). У остальных блоков
        существующая строка с данными не трогается; отсутствующая —
        создаётся как missing с причиной.
        """
        source_errors = source_errors or {}
        existing = {row["block"] for row in self.for_instrument(instrument_id)}
        for block in COVERAGE_BLOCKS:
            if block in known:
                status, reason = known[block]
            elif block in source_errors:
                status, reason = "error", source_errors[block]
            elif block in existing:
                continue
            else:
                status, reason = "missing", f"no_data:{block}"
            self.upsert(instrument_id, block, status, reason=reason)


class VerificationRepo:
    """Процесс 5 (docs/processes.md §263-284): журнал ручной верификации.
    Только добавление; promote_to_golden — единственная обратная пометка."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def capture(self, fact_id_wrong: str, fact_id_correct: str,
                note: Optional[str]) -> str:
        """Узел 1: что было показано, что должно быть, ссылка на документ
        (общий source_ref пары фактов). Возвращает verification_id."""
        verification_id = str(uuid.uuid4())
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO verification(verification_id, fact_id_wrong,
                  fact_id_correct, reported_at, note, promoted_to_golden)
                  VALUES (?, ?, ?, ?, ?, 0)""",
                (verification_id, fact_id_wrong, fact_id_correct,
                 time.time(), note))
        return verification_id

    def promote_to_golden(self, verification_id: str) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                "UPDATE verification SET promoted_to_golden=1"
                " WHERE verification_id=?",
                (verification_id,))

    def mismatch_counts(self, since: float) -> list:
        """Расхождения по (провайдер, концепт) за окно: [(provider, concept, n)].
        Провайдер — из сырья, на которое ссылается неверный факт."""
        return self.conn.execute(
            """SELECT ro.provider, fw.concept, COUNT(*) AS n
               FROM verification v
               JOIN fact fw ON fw.fact_id = v.fact_id_wrong
               JOIN raw_object ro ON ro.sha256 = fw.source_ref
               WHERE v.reported_at >= ?
               GROUP BY ro.provider, fw.concept
               ORDER BY n DESC""",
            (since,)).fetchall()

    def verification_pair(self, verification_id: str) -> Optional[dict]:
        """Пара (сырьё, показано, ожидается) для propose_golden."""
        row = self.conn.execute(
            """SELECT v.verification_id, fw.source_ref, fw.concept,
                      fw.period_end, fc.value, fw.value
               FROM verification v
               JOIN fact fw ON fw.fact_id = v.fact_id_wrong
               JOIN fact fc ON fc.fact_id = v.fact_id_correct
               WHERE v.verification_id=?""",
            (verification_id,)).fetchone()
        if row is None:
            return None
        return {"verification_id": row[0], "raw_sha256": row[1],
                "concept": row[2], "period_end": row[3],
                "expected": row[4], "shown": row[5]}


class MetricsRepo:
    """Агрегаты для системных метрик (TASK-7 T12). Только выборки;
    смысл метрики и решение «нет данных — не записываем» — в core/metrics."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def job_status_counts(self) -> dict:
        return {status: n for status, n in self.conn.execute(
            "SELECT status, COUNT(*) FROM job GROUP BY status")}

    def last_fetch_ts(self) -> Optional[float]:
        row = self.conn.execute(
            "SELECT MAX(fetched_at) FROM raw_object").fetchone()
        return row[0]

    def fact_status_counts(self) -> dict:
        return {status: n for status, n in self.conn.execute(
            "SELECT status, COUNT(*) FROM fact GROUP BY status")}

    def raw_counts(self) -> dict:
        """Всего сырья и сколько объектов без единого факта."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        unparsed = self.conn.execute(
            """SELECT COUNT(*) FROM raw_object ro
               WHERE NOT EXISTS (SELECT 1 FROM fact f
                                 WHERE f.source_ref = ro.sha256)""").fetchone()[0]
        return {"total": total, "unparsed": unparsed}

    def verification_open_count(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM verification"
            " WHERE promoted_to_golden=0").fetchone()[0]

    def instrument_counts(self) -> dict:
        """Всего инструментов и сколько входят в ТЕКУЩИЕ версии peer set."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM instrument").fetchone()[0]
        with_peers = self.conn.execute(
            """SELECT COUNT(DISTINCT instrument_id) FROM peer_set_member
               WHERE peer_set_version_id IN (
                   SELECT psv.peer_set_version_id
                   FROM peer_set_version psv
                   JOIN (SELECT peer_set_id, MAX(version) AS mv
                         FROM peer_set_version GROUP BY peer_set_id) m
                     ON m.peer_set_id = psv.peer_set_id AND m.mv = psv.version)"""
        ).fetchone()[0]
        return {"total": total, "with_peers": with_peers}

    def last_two_peer_member_sets(self) -> Optional[tuple]:
        """Составы двух последних версий одного peer set: (прошлый, текущий)
        списки instrument_id; None, если версий меньше двух."""
        versions = self.conn.execute(
            """SELECT psv.peer_set_version_id
               FROM peer_set_version psv
               ORDER BY psv.valid_from DESC, psv.version DESC LIMIT 2""",
        ).fetchall()
        if len(versions) < 2:
            return None
        def members(vid):
            return [r[0] for r in self.conn.execute(
                "SELECT instrument_id FROM peer_set_member"
                " WHERE peer_set_version_id=?", (vid,))]
        return members(versions[1][0]), members(versions[0][0])

    def locator_failures_and_total(self) -> dict:
        """Факты с локатором, из которого нельзя разрешить значение:
        нет kind или нет ссылки на документ."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        bad = self.conn.execute(
            """SELECT COUNT(*) FROM fact
               WHERE locator = '' 
                  OR locator NOT LIKE '%kind%'
                  OR locator NOT LIKE '%doc_sha256%'""").fetchone()[0]
        return {"total": total, "failures": bad}

    def record_sample(self, ts: float, name: str, provider: str,
                      value: float) -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO metric_sample(ts, name, provider, value)
                  VALUES (?, ?, ?, ?)
                  ON CONFLICT(ts, name, provider) DO UPDATE SET
                    value=excluded.value""",
                (ts, name, provider, value))

    def samples(self) -> list:
        return self.conn.execute(
            "SELECT ts, name, provider, value FROM metric_sample"
            " ORDER BY name").fetchall()


# Параметры запроса, которые никогда не попадают в журнал (T13):
# URL с ключом или токеном не логируется ни в каком виде.
SECRET_QUERY_PARAMS = {"key", "token", "apikey", "api_key",
                        "access_token", "password"}


def scrub_secret_url(value):
    """Убрать из URL строку запроса секретные параметры; остальное оставить."""
    if not isinstance(value, str) or "?" not in value:
        return value
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    parts = urlsplit(value)
    if not parts.query:
        return value
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in SECRET_QUERY_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def scrub_payload(payload):
    if not isinstance(payload, dict):
        return payload
    return {k: scrub_secret_url(v) if isinstance(v, str) else v
            for k, v in payload.items()}


class LlmSummaryRepo:
    """Хранение LLM-summary (watchlist-and-llm.md §2.6). Только добавление."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, instrument_id: str, model: str, prompt_hash: str,
               snapshot_version: int, summary: str,
               highlights: list, risks: list, citations: list) -> float:
        created_at = time.time()
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO llm_summary(instrument_id, created_at, model,
                  prompt_hash, snapshot_version, summary, highlights, risks, citations)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (instrument_id, created_at, model, prompt_hash,
                 snapshot_version, summary,
                 json.dumps(highlights, ensure_ascii=False),
                 json.dumps(risks, ensure_ascii=False),
                 json.dumps(citations, ensure_ascii=False)))
        return created_at

    def for_instrument(self, instrument_id: str) -> list:
        rows = self.conn.execute(
            """SELECT created_at, model, prompt_hash, snapshot_version,
                      summary, highlights, risks, citations
               FROM llm_summary WHERE instrument_id=?
               ORDER BY created_at DESC""",
            (instrument_id,)).fetchall()
        keys = ("created_at", "model", "prompt_hash", "snapshot_version",
                "summary", "highlights", "risks", "citations")
        return [dict(zip(keys, r)) for r in rows]


class GovernanceRepo:
    """Светофор управления: только добавление, история не переписывается
    (TASK-7 T17, docs/governance-thresholds.md)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def record(self, assessment) -> str:
        """Оценка — словарь или dataclass Assessment с полями строки
        governance_assessment."""
        if not isinstance(assessment, dict):
            from dataclasses import asdict
            assessment = asdict(assessment)
        assessment_id = str(uuid.uuid4())
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO governance_assessment(assessment_id,
                  instrument_id, indicator, color, method_version, as_of,
                  lineage_ref, reason, assessed_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (assessment_id, assessment["instrument_id"],
                 assessment["indicator"], assessment["color"],
                 assessment["method_version"], assessment["as_of"],
                 assessment["lineage_ref"], assessment["reason"],
                 time.time()))
        return assessment_id

    def for_instrument(self, instrument_id: str) -> list:
        rows = self.conn.execute(
            """SELECT assessment_id, instrument_id, indicator, color,
                      method_version, as_of, lineage_ref, reason, assessed_at
               FROM governance_assessment WHERE instrument_id=?
               ORDER BY assessed_at""",
            (instrument_id,)).fetchall()
        keys = ("assessment_id", "instrument_id", "indicator", "color",
                "method_version", "as_of", "lineage_ref", "reason",
                "assessed_at")
        return [dict(zip(keys, r)) for r in rows]

    def latest(self, instrument_id: str, indicator: str) -> Optional[dict]:
        """Последняя по времени оценка индикатора или None."""
        rows = [r for r in self.for_instrument(instrument_id)
                if r["indicator"] == indicator]
        return rows[-1] if rows else None


class AuditRepo:
    """Журнал операций: только добавление, дублирование в файл.

    JSONL-строка в logs/audit.jsonl пишется ПЕРЕД записью в базу и
    переживает любой сбой базы — в этом смысл файла (TASK-7 T13).
    Отказ файла (каталог только для чтения, полный диск) не роняет
    операцию (B12): log() возвращает причину значением, а строка всё
    равно попадает в базу — потеря одного адресата не отменяет другой.

    Размер файла ограничен ротацией, как у app.log (B24): тот же кап и
    тот же запас копий (RotatingFileHandler-семантика) — доросший файл
    становится .1, старшие копии сдвигаются, лишние уходят за пределом
    backup_count.
    """

    def __init__(self, conn: sqlite3.Connection, audit_log_path=None,
                 max_bytes: int = APP_LOG_MAX_BYTES,
                 backup_count: int = APP_LOG_BACKUP_COUNT):
        self.conn = conn
        self._audit_log_path = audit_log_path
        self._max_bytes = max_bytes
        self._backup_count = backup_count

    def _rotate_if_needed(self, path: Path) -> None:
        if not path.exists() or path.stat().st_size < self._max_bytes:
            return
        for i in range(self._backup_count - 1, 0, -1):
            src = path.with_name(f"{path.name}.{i}")
            if src.exists():
                src.replace(path.with_name(f"{path.name}.{i + 1}"))
        path.replace(path.with_name(f"{path.name}.1"))

    def log(self, action: str, target: Optional[str],
            payload: Optional[dict], confirmed: bool,
            result: Optional[str]) -> Optional[str]:
        """None — обе цели записаны; строка 'audit_file_unavailable: …'
        — файл недоступен, строка при этом записана в базу."""
        entry = {"ts": time.time(), "action": action,
                 "target": scrub_secret_url(target),
                 "payload": scrub_payload(payload),
                 "confirmed": int(confirmed), "result": result}
        file_error: Optional[str] = None
        if self._audit_log_path is not None:
            path = Path(self._audit_log_path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed(path)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as e:
                file_error = f"audit_file_unavailable: {e}"
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO audit_log(ts, action, target, payload, confirmed, result)
                  VALUES (?, ?, ?, ?, ?, ?)""",
                (entry["ts"], action, entry["target"],
                 json.dumps(entry["payload"]) if entry["payload"] else None,
                 int(confirmed), result),
            )
        return file_error


class IssuerStateRepo:
    """Состояние инкрементального сбора по эмитенту (TASK-13 Z2,
    миграция 37): дата последней виденной отчётности + валидаторы кеша
    companyfacts. Живёт в базе, а не в провайдере (I10)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, issuer_id: str, source: str = "edgar") -> Optional[dict]:
        row = self.conn.execute(
            """SELECT issuer_id, source, last_filing_date, etag,
               last_modified, updated_at FROM issuer_ingest_state
               WHERE issuer_id=? AND source=?""",
            (issuer_id, source)).fetchone()
        if row is None:
            return None
        return {"issuer_id": row[0], "source": row[1],
                "last_filing_date": row[2], "etag": row[3],
                "last_modified": row[4], "updated_at": row[5]}

    def put(self, issuer_id: str, last_filing_date: Optional[str],
            etag: Optional[str] = None, last_modified: Optional[str] = None,
            source: str = "edgar") -> None:
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO issuer_ingest_state(issuer_id, source,
                    last_filing_date, etag, last_modified, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(issuer_id, source) DO UPDATE SET
                    last_filing_date=excluded.last_filing_date,
                    etag=excluded.etag,
                    last_modified=excluded.last_modified,
                    updated_at=excluded.updated_at""",
                (issuer_id, source, last_filing_date, etag, last_modified,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
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
        self.coverage = CoverageRepo(conn)
        self.verification = VerificationRepo(conn)
        self.metrics = MetricsRepo(conn)
        self.llm_summary = LlmSummaryRepo(conn)
        self.governance = GovernanceRepo(conn)
        self.issuer_state = IssuerStateRepo(conn)
        self.price = PriceRepo(conn)
        self.corp_action = CorporateActionRepo(conn)
        self.industry = IndustryRepo(conn)
        self.audit = AuditRepo(conn, audit_log_path=paths.audit_log_path)
        self.document = DocumentRepo(conn)
        self.manual_extraction = ManualExtractionRepo(conn)


class IndustryRepo:
    """Хранение отраслевых агрегатов (TASK-17 E3): append-only по сути,
    повторная сборка той же (версия, дата, мера, метод) обновляет строку,
    а не плодит дубли. NULL-тройка обязана нести причину из словаря B15 —
    на уровне таблицы это CHECK, здесь — тот же сторож, что у мер."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def store_aggregates(self, peer_set_version_id: str, as_of: str,
                         aggregates: list) -> int:
        from rusterm.reasons import is_known_reason
        written = 0
        with writer_transaction(self.conn) as c:
            for agg in aggregates:
                if agg.null_reason is not None and \
                        not is_known_reason(agg.null_reason):
                    raise ValueError(
                        f"null_reason {agg.null_reason!r} вне словаря")
                c.execute(
                    """INSERT INTO industry_aggregate(
                      industry_aggregate_id, peer_set_version_id, as_of,
                      concept, p25, median, p75, n, method_version,
                      null_reason, built_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                      ON CONFLICT(peer_set_version_id, as_of, concept,
                                  method_version) DO UPDATE SET
                        p25=excluded.p25, median=excluded.median,
                        p75=excluded.p75, n=excluded.n,
                        null_reason=excluded.null_reason,
                        built_at=excluded.built_at""",
                    (str(uuid.uuid4()), peer_set_version_id, as_of,
                     agg.concept, agg.p25, agg.median, agg.p75, agg.n,
                     agg.method_version, agg.null_reason, time.time()))
                written += 1
        return written

    def get_aggregates(self, peer_set_version_id: str, as_of: str) -> list:
        return self.conn.execute(
            """SELECT concept, p25, median, p75, n, method_version,
                      null_reason, built_at
               FROM industry_aggregate
               WHERE peer_set_version_id=? AND as_of=?
               ORDER BY concept""", (peer_set_version_id, as_of)).fetchall()


class PriceRepo:
    """Котировки (ТЗ-23 K1, ADR-0014): close и adjusted хранятся оба —
    diff строится по close, вендорский adjusted служит сверкой нашей
    корректировке (K3). Уникальность (инструмент, дата, источник):
    повторный сбор того же дня — no-op (I7), INSERT OR IGNORE."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def put_rows(self, instrument_id: str, source: str,
                 rows: list[dict]) -> int:
        """rows: [{date, close?, adjusted?, currency?, volume?}].
        Возвращает число РЕАЛЬНО вставленных дней (дубли не считаются)."""
        inserted = 0
        with writer_transaction(self.conn) as c:
            for r in rows:
                cur = c.execute(
                    """INSERT OR IGNORE INTO price(instrument_id, date,
                       source, close, adjusted, currency, volume,
                       retrieved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (instrument_id, r["date"], source, r.get("close"),
                     r.get("adjusted"), r.get("currency"),
                     r.get("volume"), time.time()))
                inserted += cur.rowcount
        return inserted

    def series(self, instrument_id: str,
               source: str | None = None) -> list[dict]:
        sql = """SELECT date, close, adjusted, currency, volume
                 FROM price WHERE instrument_id=?"""
        args: list = [instrument_id]
        if source:
            sql += " AND source=?"
            args.append(source)
        sql += " ORDER BY date"
        return [dict(zip(("date", "close", "adjusted", "currency",
                          "volume"), r))
                for r in self.conn.execute(sql, args)]

    def price_as_of(self, instrument_id: str, as_of: str) -> Optional[dict]:
        """Последняя цена строкой не позже as_of. Переносить вчерашнюю
        цену за сегодняшний день — работа вызывающего стража: здесь
        только факт (дата, age в днях), а не разрешение."""
        row = self.conn.execute(
            """SELECT date, close, adjusted, currency FROM price
               WHERE instrument_id=? AND date<=?
               ORDER BY date DESC LIMIT 1""",
            (instrument_id, as_of)).fetchone()
        if row is None:
            return None
        return {"date": row[0], "close": row[1], "adjusted": row[2],
                "currency": row[3],
                "age_days": (date.fromisoformat(as_of)
                             - date.fromisoformat(row[0])).days}

    def latest_date(self, instrument_id: str) -> Optional[str]:
        row = self.conn.execute(
            """SELECT MAX(date) FROM price WHERE instrument_id=?""",
            (instrument_id,)).fetchone()
        return row[0] if row else None

    def dates(self, instrument_id: str,
              source: str | None = None) -> list[str]:
        return [r["date"] for r in self.series(instrument_id, source)]

    def instruments_with_history(self) -> list[str]:
        """Инструменты, у которых есть хотя бы одна цена (ТЗ-23 K5)."""
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT instrument_id FROM price ORDER BY instrument_id")]

    def count(self, instrument_id: str | None = None) -> int:
        if instrument_id is None:
            return self.conn.execute(
                "SELECT COUNT(*) FROM price").fetchone()[0]
        return self.conn.execute(
            "SELECT COUNT(*) FROM price WHERE instrument_id=?",
            (instrument_id,)).fetchone()[0]


class CorporateActionRepo:
    """Корпоративные действия (ТЗ-23 K1): входы уже написанной и
    протестированной price_adj (сплиты — factor, дивиденды — amount).
    Уникальность (инструмент, ex_date, вид)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def put(self, instrument_id: str, ex_date: str, kind: str,
            factor: Optional[float] = None,
            amount: Optional[float] = None, currency: Optional[str] = None,
            source: str = "twelvedata") -> bool:
        """True — записано; False — такое событие уже есть (I7)."""
        with writer_transaction(self.conn) as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO corporate_action(
                   instrument_id, ex_date, kind, factor, amount,
                   currency, source) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (instrument_id, ex_date, kind, factor, amount, currency,
                 source))
            return cur.rowcount > 0

    def raw_events(self, instrument_id: str) -> list[dict]:
        """События по возрастанию ex_date в сыром виде. Дивидендный
        фактор (вход price_adj) здесь НЕ вычисляется: он требует close
        на ex-date, которым репозиторий не владеет, — расчёт живёт в
        вызывающем (K3), по сохранённому ряду цен."""
        return self.all(instrument_id)

    def all(self, instrument_id: str) -> list[dict]:
        return [dict(zip(("instrument_id", "ex_date", "kind", "factor",
                          "amount", "currency", "source"), r))
                for r in self.conn.execute(
                    """SELECT instrument_id, ex_date, kind, factor,
                       amount, currency, source FROM corporate_action
                       WHERE instrument_id=? ORDER BY ex_date""",
                    (instrument_id,))]


class DocumentRepo:
    """Заголовки импортированных документов (TASK-19 F4, миграция 40,
    ADR-0011). sha256 первичен: тот же файл импортируется один раз,
    повтор — False, а не дубль. Тело документа живёт на диске
    пользователя; база хранит только заголовок и происхождение."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def put(self, sha256: str, filename: str, format: str,
            page_count: int, byte_len: int, issuer_id: Optional[str] = None,
            imported_at: Optional[float] = None) -> bool:
        """Вставить заголовок. True — записан; False — такой sha256 уже
        есть (тот же файл повторно не импортируется)."""
        with writer_transaction(self.conn) as c:
            row = c.execute(
                "SELECT 1 FROM document WHERE sha256=?",
                (sha256,)).fetchone()
            if row is not None:
                return False
            c.execute(
                """INSERT INTO document(sha256, filename, format,
                   page_count, issuer_id, imported_at, bytes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sha256, filename, format, page_count, issuer_id,
                 imported_at if imported_at is not None else time.time(),
                 byte_len))
        return True

    def get(self, sha256: str) -> Optional[dict]:
        row = self.conn.execute(
            """SELECT sha256, filename, format, page_count, issuer_id,
               imported_at, bytes FROM document WHERE sha256=?""",
            (sha256,)).fetchone()
        if row is None:
            return None
        return {"sha256": row[0], "filename": row[1], "format": row[2],
                "page_count": row[3], "issuer_id": row[4],
                "imported_at": row[5], "bytes": row[6]}

    def for_issuer(self, issuer_id: str) -> list:
        return self.conn.execute(
            """SELECT sha256, filename, format, page_count, imported_at
               FROM document WHERE issuer_id=? ORDER BY imported_at""",
            (issuer_id,)).fetchall()


class ManualExtractionRepo:
    """Записи-кандидаты ручного импорта (TASK-19 F4, миграция 40,
    ADR-0011): ступень ② даёт кандидата с дословной цитатой, ступень ③ —
    детерминированный исход verified. Append-only: исход контроля —
    данные, а не правка; запись с verified=no сохраняется и видна, но в
    меры снапшота не попадает (причина manual_unverified)."""

    _CATEGORIES = ("financial", "physical", "other")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, document_sha256: str, page_no: int, category: str,
            metric: str, value: Optional[str], unit: Optional[str],
            period: Optional[str], quote: str, verified: bool,
            model: str, prompt_version: str) -> str:
        """Записать кандидата, вернуть extraction_id. Категория вне трёх
        слов и пустая цитата отклоняются до SQL (тем же стилем, что
        сторож B15 у мер) — CHECK таблицы страховка, не интерфейс."""
        if category not in self._CATEGORIES:
            raise ValueError(
                f"category {category!r} вне словаря"
                "('financial'|'physical'|'other', ADR-0011 ②)")
        if not quote:
            raise ValueError("цитата обязательна (ADR-0011 ②): запись "
                             "без дословной цитаты не хранится")
        extraction_id = str(uuid.uuid4())
        with writer_transaction(self.conn) as c:
            c.execute(
                """INSERT INTO manual_extraction(document_sha256, page_no,
                   category, metric, value, unit, period, quote, verified,
                   model, prompt_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_sha256, page_no, category, metric, value, unit,
                 period, quote, int(bool(verified)), model, prompt_version))
        return extraction_id

    def for_document(self, document_sha256: str) -> list:
        return self.conn.execute(
            """SELECT rowid, document_sha256, page_no, category, metric,
               value, unit, period, quote, verified, model, prompt_version
               FROM manual_extraction WHERE document_sha256=?
               ORDER BY page_no, rowid""", (document_sha256,)).fetchall()

    def counts(self, document_sha256: str) -> dict:
        """Сколько кандидатов всего/подтверждено: карточка источника
        обязана показывать, сколько кандидатов не прошло контроль."""
        rows = self.conn.execute(
            """SELECT verified, COUNT(*) FROM manual_extraction
               WHERE document_sha256=? GROUP BY verified""",
            (document_sha256,)).fetchall()
        by_verified = {r[0]: r[1] for r in rows}
        total = sum(by_verified.values())
        return {"total": total, "verified": by_verified.get(1, 0),
                "unverified": by_verified.get(0, 0)}
