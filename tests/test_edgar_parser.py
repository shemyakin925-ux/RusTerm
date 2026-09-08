"""Тесты реального XBRL-парсера companyfacts (TASK-8 U6).

Парсится настоящий ответ SEC (обрезанный до одного концепта,
tests/data/edgar/companyfacts_aapl.json). Каждый факт обязан
разрешаться локатором в то же значение; basis — по правилу I3;
дубликат периода из более раннего флинга — в superseded со ссылкой
на победителя.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.core.fact import locator_from_json, resolve_locator
from rusterm.parsers import CompanyFactsParser, parse_auto

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"
FAKE_UA = "Synthetic Test synthetic.invalid"


def _raw() -> bytes:
    return (DATA / "companyfacts_aapl.json").read_bytes()


def _sha(raw: bytes) -> str:
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _parse():
    raw = _raw()
    parser = CompanyFactsParser()
    result = parser.parse(raw, {"issuer_id": "i-aapl",
                                "source_ref": _sha(raw)})
    return raw, result


def test_real_companyfacts_facts_all_resolve():
    raw, result = _parse()
    assert result.unparsed == 0
    assert result.facts, "из записанного companyfacts не извлечён ни один факт"
    getter = lambda sha: raw  # request_hash = sha этого же сырья
    for fact in result.facts:
        locator = locator_from_json(fact["locator"])
        resolved = resolve_locator(locator, getter)
        assert resolved == fact["value"], (
            f"{fact['concept']} {fact['period_end']}: {resolved} != "
            f"{fact['value']}")
        assert fact["locator"]["kind"] == "api"
        assert fact["locator"]["request_hash"] == _sha(raw)


def test_real_companyfacts_basis_distribution():
    raw, result = _parse()
    bases = {f["basis"] for f in result.facts}
    # в записи Apple есть и собственные периоды флинга, и сравнительные
    assert "as_reported" in bases
    assert "restated" in bases
    for fact in result.facts:
        assert fact["basis"] in ("as_reported", "restated")
        assert fact["concept"].startswith("us-gaap:")


def test_duplicate_across_filings_newest_filed_wins():
    """Тот же (concept, unit, период) в двух флингах: живой — новейший
    filed; проигравший — в superseded со ссылкой на локатор победителя."""
    doc = {
        "source": "synthetic",
        "note": "синтетический companyfacts для дедупликации",
        "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 900,
             "accn": "0002", "form": "10-K", "filed": "2025-02-15",
             "fy": 2024, "fp": "FY"},
            {"start": "2023-01-01", "end": "2023-12-31", "val": 880,
             "accn": "0001", "form": "10-K", "filed": "2024-02-15",
             "fy": 2023, "fp": "FY"},
        ]}}}},
    }
    raw = json.dumps(doc).encode()
    sha = _sha(raw)
    result = CompanyFactsParser().parse(
        raw, {"issuer_id": "i1", "source_ref": sha})

    live = [f for f in result.facts
            if (f["concept"], f["period_start"], f["period_end"])
            == ("us-gaap:Revenues", "2023-01-01", "2023-12-31")]
    assert len(live) == 1
    assert live[0]["value"] == "900", "новейший filed должен победить"

    assert len(result.superseded) == 1
    loser = result.superseded[0]
    assert loser["value"] == "880"
    assert loser["superseded_by_locator"]["json_pointer"] == \
        live[0]["locator"]["json_pointer"]
    assert loser["superseded_by_filed"] == "2025-02-15"


def test_parse_auto_dispatches_companyfacts_and_every_fact_resolves():
    raw = _raw()
    import hashlib
    sha = hashlib.sha256(raw).hexdigest()
    result = parse_auto(raw, {"doc_kind": "companyfacts"},
                        {"issuer_id": "i-aapl", "source_ref": sha})
    assert result is not None
    assert result.parser_version == "companyfacts.v1"
    getter = lambda request_hash: raw
    for fact in result.facts:
        locator = locator_from_json(fact["locator"])
        assert resolve_locator(locator, getter) == fact["value"]
