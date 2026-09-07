"""Tests for increment I5: Fact, locators, basis, resolve(locator)."""
from __future__ import annotations

import json
import shutil
import tempfile

import pytest

from rusterm.core.fact import (
    Fact, LocatorXBRL, LocatorTable, LocatorPDF, LocatorHTML,
    LocatorAPI, LocatorDerived, ApiRevision,
    locator_to_json, locator_from_json,
    determine_basis, resolve_locator, validate_fact_for_write,
    sha256_bytes,
)
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.raw_store import put_with_manifest, decompress_object


def test_fact_requires_locator():
    with pytest.raises(ValueError, match="locator"):
        Fact(
            issuer_id="issuer-1", concept="revenue",
            period_start="2023-01-01", period_end="2023-12-31",
            period_type="duration", value="100", unit="USD",
            currency="USD", basis="as_reported", origin="extracted",
            source_ref="abc123", locator={}, parser_version="1.0",
        )


def test_fact_requires_one_of_issuer_or_listing():
    with pytest.raises(ValueError, match="exactly one"):
        Fact(
            issuer_id="issuer-1", listing_id="listing-1", concept="revenue",
            period_start="2023-01-01", period_end="2023-12-31",
            period_type="duration", value="100", unit="USD",
            basis="as_reported", origin="extracted", source_ref="abc123",
            locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
            parser_version="1.0",
        )


def test_fact_valid_with_issuer():
    fact = Fact(
        issuer_id="issuer-1", concept="revenue",
        period_start="2023-01-01", period_end="2023-12-31",
        period_type="duration", value="100000000", unit="USD",
        currency="USD", basis="as_reported", origin="extracted",
        source_ref="abc123",
        locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
        parser_version="1.0",
    )
    assert fact.issuer_id == "issuer-1"
    assert fact.listing_id is None


def test_fact_valid_with_listing():
    fact = Fact(
        listing_id="listing-1", concept="price_close",
        period_start="2024-01-15", period_end="2024-01-15",
        period_type="instant", value="150.25", unit="USD",
        currency="USD", basis="as_reported", origin="extracted",
        source_ref="def456",
        locator={"kind": "api", "endpoint": "/price",
                 "request_hash": "x", "json_pointer": "/close",
                 "value_snapshot": "150.25", "retrieved_at": 0.0},
        parser_version="1.0",
    )
    assert fact.listing_id == "listing-1"


def test_locator_xbrl_roundtrip():
    loc = LocatorXBRL(doc_sha256="abc123", fact_id="f1",
                      concept="Revenue", context_ref="FI2023",
                      unit_ref="USD", decimals="-6", taxonomy="us-gaap-2023")
    data = locator_to_json(loc)
    assert data["kind"] == "xbrl"
    loc2 = locator_from_json(data)
    assert isinstance(loc2, LocatorXBRL)
    assert loc2.fact_id == "f1"


def test_locator_table_roundtrip():
    loc = LocatorTable(doc_sha256="d1", table_index=0, row=5, col=2,
                       header_path=["Rev"], text_snippet="Revenue 100M")
    data = locator_to_json(loc)
    assert data["kind"] == "table"
    loc2 = locator_from_json(data)
    assert isinstance(loc2, LocatorTable)


def test_locator_pdf_roundtrip():
    loc = LocatorPDF(doc_sha256="p1", page=3, text_snippet="Revenue $100M",
                     extractor="pdfplumber", extractor_version="0.10",
                     hint_bbox=[100, 200, 300, 250])
    data = locator_to_json(loc)
    assert data["hint_bbox"] == [100, 200, 300, 250]


def test_locator_derived_roundtrip():
    loc = LocatorDerived(inputs=["f1", "f2", "f3"],
                         formula_id="ebitda", method_version="v1")
    data = locator_to_json(loc)
    assert data["kind"] == "derived"
    assert len(data["inputs"]) == 3


def test_determine_basis_as_reported():
    assert determine_basis("2023-12-31", "2023-12-31", "2024-02-15") == "as_reported"


def test_determine_basis_restated():
    assert determine_basis("2024-12-31", "2023-12-31", "2025-02-15") == "restated"


def test_determine_basis_restated_quarterly():
    assert determine_basis("2024-09-30", "2023-09-30", "2024-11-01") == "restated"


def _make_raw_store():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    return paths, tmpdir


def test_resolve_locator_xbrl():
    paths, tmpdir = _make_raw_store()
    try:
        xbrl_data = {"facts": {"us-gaap_Revenue_2023": {"value": "100000000", "unit": "USD"}}}
        obj = put_with_manifest(paths, json.dumps(xbrl_data).encode(),
                                provider="sec", block="fundamentals")
        loc = LocatorXBRL(doc_sha256=obj.sha256, fact_id="us-gaap_Revenue_2023",
                          concept="Revenue")
        def getter(sha): return decompress_object(paths.raw_store, sha)
        assert resolve_locator(loc, getter) == "100000000"
    finally:
        shutil.rmtree(tmpdir)


def test_resolve_locator_table():
    paths, tmpdir = _make_raw_store()
    try:
        table_data = {"tables": [{"rows": [
            {"cells": [{"value": "Revenue"}, {"value": "100M"}]},
            {"cells": [{"value": "Cost"}, {"value": "60M"}]},
        ]}]}
        obj = put_with_manifest(paths, json.dumps(table_data).encode(),
                                provider="sec", block="fundamentals")
        loc = LocatorTable(doc_sha256=obj.sha256, table_index=0, row=0, col=1,
                           header_path=["Revenue"], text_snippet="Revenue 100M")
        def getter(sha): return decompress_object(paths.raw_store, sha)
        assert resolve_locator(loc, getter) == "100M"
    finally:
        shutil.rmtree(tmpdir)


def test_resolve_locator_pdf_snippet():
    paths, tmpdir = _make_raw_store()
    try:
        pdf_text = "Annual Report 2023\nTotal Revenue $100,000,000\nNet Income $10M"
        obj = put_with_manifest(paths, pdf_text.encode(), provider="sec", block="fundamentals")
        loc = LocatorPDF(doc_sha256=obj.sha256, page=1,
                         text_snippet="Total Revenue $100,000,000",
                         extractor="pdfplumber", extractor_version="0.10")
        def getter(sha): return decompress_object(paths.raw_store, sha)
        assert resolve_locator(loc, getter) == "100000000"
    finally:
        shutil.rmtree(tmpdir)


def test_resolve_locator_api():
    paths, tmpdir = _make_raw_store()
    try:
        api_data = {"close": 150.25, "volume": 1000000}
        obj = put_with_manifest(paths, json.dumps(api_data).encode(),
                                provider="yahoo", block="prices")
        loc = LocatorAPI(endpoint="/v1/price/AAPL", request_hash=obj.sha256,
                         json_pointer="/close", value_snapshot="150.25",
                         retrieved_at=obj.fetched_at)
        def getter(sha): return decompress_object(paths.raw_store, sha)
        assert resolve_locator(loc, getter) == "150.25"
    finally:
        shutil.rmtree(tmpdir)


def test_resolve_locator_api_revision_on_mismatch():
    """Значение по json_pointer разошлось со снапшотом — возвращается
    событие ревизии, а не ошибка парсера (ADR-0001, kind=api)."""
    paths, tmpdir = _make_raw_store()
    try:
        api_data = {"close": 160.0, "volume": 1000000}
        obj = put_with_manifest(paths, json.dumps(api_data).encode(),
                                provider="yahoo", block="prices")
        loc = LocatorAPI(endpoint="/v1/price/AAPL", request_hash=obj.sha256,
                         json_pointer="/close", value_snapshot="150.25",
                         retrieved_at=123.0)
        def getter(sha): return decompress_object(paths.raw_store, sha)
        result = resolve_locator(loc, getter)
        assert isinstance(result, ApiRevision)
        assert result.expected == "150.25"
        assert result.actual == "160.0"
        assert result.request_hash == obj.sha256
        assert result.json_pointer == "/close"
    finally:
        shutil.rmtree(tmpdir)


def test_locator_api_roundtrip_v2():
    loc = LocatorAPI(endpoint="/v1/price/AAPL", request_hash="req123",
                     json_pointer="/close", value_snapshot="150.25",
                     retrieved_at=1700000000.0)
    assert loc.schema == "api.v2"
    data = locator_to_json(loc)
    assert "response_sha256" not in data
    loc2 = locator_from_json(data)
    assert isinstance(loc2, LocatorAPI)
    assert loc2.value_snapshot == "150.25"
    assert loc2.retrieved_at == 1700000000.0
    assert loc2.schema == "api.v2"


def test_validate_fact_ok():
    fact = Fact(issuer_id="i1", concept="revenue",
                period_start="2023-01-01", period_end="2023-12-31",
                period_type="duration", value="100", unit="USD",
                currency="USD", basis="as_reported", origin="extracted",
                source_ref="abc",
                locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
                parser_version="1.0")
    assert validate_fact_for_write(fact) == []


def test_validate_fact_missing_source_ref():
    fact = Fact(issuer_id="i1", concept="revenue",
                period_start="2023-01-01", period_end="2023-12-31",
                period_type="duration", value="100", unit="USD",
                basis="as_reported", origin="extracted", source_ref="",
                locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
                parser_version="1.0")
    errors = validate_fact_for_write(fact)
    assert any("source_ref" in e for e in errors)


def test_locator_all_have_schema_version():
    expected = {
        LocatorXBRL: ".v1", LocatorTable: ".v1", LocatorPDF: ".v1",
        LocatorHTML: ".v1",
        LocatorAPI: ".v2",  # api.v2: без response_sha256, со снапшотом
        LocatorDerived: ".v1",
    }
    for cls, version in expected.items():
        assert cls().schema.endswith(version), (
            f"{cls.__name__}: ожидалась схема *{version}, получена {cls().schema}"
        )


def test_fact_basis_validation():
    with pytest.raises(ValueError, match="basis"):
        Fact(issuer_id="i1", concept="r", period_start="2023-01-01",
             period_end="2023-12-31", period_type="duration", value="100",
             unit="USD", basis="bad", origin="extracted", source_ref="x",
             locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
             parser_version="1.0")


def test_fact_origin_validation():
    with pytest.raises(ValueError, match="origin"):
        Fact(issuer_id="i1", concept="r", period_start="2023-01-01",
             period_end="2023-12-31", period_type="duration", value="100",
             unit="USD", basis="as_reported", origin="bad", source_ref="x",
             locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
             parser_version="1.0")


def test_fact_status_validation():
    with pytest.raises(ValueError, match="status"):
        Fact(issuer_id="i1", concept="r", period_start="2023-01-01",
             period_end="2023-12-31", period_type="duration", value="100",
             unit="USD", basis="as_reported", origin="extracted",
             source_ref="x",
             locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
             parser_version="1.0", status="bad")


def test_fact_period_type_validation():
    with pytest.raises(ValueError, match="period_type"):
        Fact(issuer_id="i1", concept="r", period_start="2023-01-01",
             period_end="2023-12-31", period_type="bad", value="100",
             unit="USD", basis="as_reported", origin="extracted",
             source_ref="x",
             locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
             parser_version="1.0")


def test_fact_to_db_tuple():
    fact = Fact(issuer_id="i1", concept="revenue",
                period_start="2023-01-01", period_end="2023-12-31",
                period_type="duration", value="100", unit="USD",
                currency="USD", basis="as_reported", origin="extracted",
                source_ref="abc",
                locator={"kind": "xbrl", "doc_sha256": "x", "fact_id": "f1"},
                parser_version="1.0")
    tup = fact.to_db_tuple()
    assert len(tup) == 18
    assert tup[0] == fact.fact_id
    assert tup[1] == "i1"


def test_sha256_known():
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_bytes(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
