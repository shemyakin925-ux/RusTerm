"""Тесты И7: парсеры — синтетический XBRL-подобный JSON и таблицы.

Ключевая проверка — I12: resolve(locator) == value на всех фикстурах.
Данные синтетические (fixtures/).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from rusterm.core.fact import Fact, locator_from_json, resolve_locator
from rusterm.parsers import (
    ParseResult,
    SyntheticXBRLParser,
    TableParser,
    parse_auto,
    registered_parsers,
)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import FactRepo, RawRepo
from rusterm.store.raw_store import decompress_object

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _paths():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    return paths, tmpdir


def test_can_parse_decides_by_metadata_only():
    xbrl = SyntheticXBRLParser()
    table = TableParser()
    assert xbrl.can_parse({"doc_kind": "xbrl", "provider": "synthetic"})
    assert not xbrl.can_parse({"doc_kind": "table"})
    assert table.can_parse({"doc_kind": "table"})
    assert not table.can_parse({"doc_kind": "xbrl"})


def test_parse_xbrl_facts_with_locators_and_basis():
    raw = _read("synthetic_report_10k.json")
    context = {"issuer_id": "issuer-demo", "source_ref": "sha-fixture"}
    result = SyntheticXBRLParser().parse(raw, context)
    assert isinstance(result, ParseResult)

    by_concept = {}
    for f in result.facts:
        assert f["locator"]["kind"] == "xbrl"
        assert f["locator"]["doc_sha256"] == "sha-fixture"
        assert f["basis"] in ("as_reported", "restated")
        assert f["origin"] == "extracted"
        assert f["source_ref"] == "sha-fixture"
        by_concept.setdefault(f["concept"], []).append(f)

    # выручка за период документа — as_reported
    revenue_current = [f for f in by_concept["revenue"]
                       if f["period_end"] == "2023-12-31"]
    assert revenue_current and revenue_current[0]["basis"] == "as_reported"
    assert revenue_current[0]["value"] == "100000"

    # сравнительная колонка позднего отчёта — restated
    revenue_prev = [f for f in by_concept["revenue"]
                    if f["period_end"] == "2022-12-31"]
    assert revenue_prev and revenue_prev[0]["basis"] == "restated"

    # битая запись не молча выброшена, а посчитана неразобранной
    assert result.unparsed == 1
    assert len(result.facts) == 3


def test_parse_table_facts_with_locators():
    raw = _read("synthetic_prices_table.json")
    context = {"listing_id": "listing-demo-1", "source_ref": "sha-table"}
    result = TableParser().parse(raw, context)
    assert len(result.facts) == 3
    assert result.unparsed == 1  # ячейка без concept
    for f in result.facts:
        assert f["locator"]["kind"] == "table"
        assert f["locator"]["table_index"] == 0
        assert f["period_type"] == "instant"
        assert f["listing_id"] == "listing-demo-1"
        assert f["issuer_id"] is None


def test_parse_auto_dispatches_and_returns_none():
    raw = _read("synthetic_report_10k.json")
    result = parse_auto(raw, {"doc_kind": "xbrl"}, {"issuer_id": "i"})
    assert result is not None and len(result.facts) == 3
    assert parse_auto(raw, {"doc_kind": "unknown-kind"}, {}) is None
    assert len(registered_parsers()) >= 2


def test_i12_resolve_locator_equals_value_on_fixtures():
    """I12: каждый разобранный факт разрешается локатором в то же значение."""
    paths, tmpdir = _paths()
    try:
        conn = None
        from rusterm.store.db import apply_migrations
        import sqlite3
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        raw_repo = RawRepo(paths, conn)
        getter = lambda sha: decompress_object(paths.raw_store, sha)

        cases = [
            ("synthetic_report_10k.json", {"doc_kind": "xbrl"},
             {"issuer_id": "issuer-demo"}),
            ("synthetic_prices_table.json", {"doc_kind": "table"},
             {"listing_id": "listing-demo-1"}),
        ]
        for fixture_name, metadata, ctx in cases:
            raw = _read(fixture_name)
            obj = raw_repo.put(raw, provider="synthetic",
                               block="fundamentals")
            ctx = dict(ctx, source_ref=obj.sha256)
            result = parse_auto(raw, metadata, ctx)
            assert result is not None, fixture_name
            assert result.facts, fixture_name
            for f in result.facts:
                loc = locator_from_json(f["locator"])
                resolved = resolve_locator(loc, getter)
                assert resolved == f["value"], (
                    f"{fixture_name}: {f['concept']} разрешился в {resolved!r}, "
                    f"а значение факта {f['value']!r}"
                )
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_parsed_fact_persists_through_fact_repo():
    """Словарь факта парсера собирается в core.Fact и проходит вставку
    в базу (FK на source_ref, ровно один из issuer/listing)."""
    paths, tmpdir = _paths()
    try:
        import sqlite3
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        raw_repo = RawRepo(paths, conn)
        fact_repo = FactRepo(conn)

        raw = _read("synthetic_report_10k.json")
        obj = raw_repo.put(raw, provider="synthetic", block="fundamentals")
        result = parse_auto(raw, {"doc_kind": "xbrl"},
                            {"issuer_id": "issuer-demo",
                             "source_ref": obj.sha256})
        stored = 0
        for f in result.facts:
            fact = Fact(
                fact_id=str(uuid.uuid4()),
                issuer_id=f["issuer_id"],
                listing_id=f["listing_id"],
                concept=f["concept"],
                period_start=f["period_start"],
                period_end=f["period_end"],
                period_type=f["period_type"],
                value=f["value"],
                unit=f["unit"],
                currency=f["currency"],
                basis=f["basis"],
                origin=f["origin"],
                source_ref=f["source_ref"],
                locator=f["locator"],
                parser_version=f["parser_version"],
                status=f["status"],
            )
            fact_repo.insert_fact(
                fact_id=fact.fact_id,
                issuer_id=fact.issuer_id,
                listing_id=fact.listing_id,
                concept=fact.concept,
                period_start=fact.period_start,
                period_end=fact.period_end,
                period_type=fact.period_type,
                value=fact.value,
                unit=fact.unit,
                currency=fact.currency,
                basis=fact.basis,
                origin=fact.origin,
                source_ref=fact.source_ref,
                locator=fact.locator,
                parser_version=fact.parser_version,
                status=fact.status,
            )
            stored += 1
        assert stored == 3
        rows = fact_repo.get_facts(issuer_id="issuer-demo")
        assert len(rows) == 3
        conn.close()
    finally:
        shutil.rmtree(tmpdir)
