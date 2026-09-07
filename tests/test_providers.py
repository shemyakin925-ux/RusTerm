"""Тесты И6: провайдеры через Protocol, реестр, синтетические фикстуры.

Все данные — синтетические фикстуры из fixtures/ (в имени и содержимом
каждой есть слово synthetic).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.providers import (
    SyntheticDisclosuresProvider,
    SyntheticMarketProvider,
    UnknownProvider,
    available,
    get_provider,
    register,
)
from rusterm.providers.market import (
    Candidates,
    PriceSeries,
    ProfileResult,
    ProviderError,
    ResolveAmbiguous,
    ResolveMatch,
    ResolveNotFound,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fixtures_are_marked_synthetic():
    """Каждый файл фикстур обязан иметь synthetic в имени и в содержимом."""
    files = sorted(f for f in FIXTURES.glob("*") if f.is_file())
    assert files, "каталог fixtures пуст"
    for f in files:
        assert "synthetic" in f.name, f"{f.name}: нет synthetic в имени"
        content = f.read_text(encoding="utf-8")
        assert "synthetic" in content, f"{f.name}: нет synthetic в содержимом"
        if f.suffix == ".json":
            json.loads(content)  # фикстуры валидны как JSON


def test_registry_returns_providers_and_marks_unknown():
    assert "synthetic-market" in available()
    assert "synthetic-disclosures" in available()
    assert isinstance(get_provider("synthetic-market"), SyntheticMarketProvider)
    assert isinstance(get_provider("synthetic-disclosures"),
                      SyntheticDisclosuresProvider)
    result = get_provider("no-such-provider")
    assert isinstance(result, UnknownProvider)


def test_resolve_unique_ambiguous_notfound():
    provider = SyntheticMarketProvider()
    # уникальное разрешение — только с датой (ADR-0005)
    outcome = provider.resolve("DEMO", "US", "2024-05-20")
    assert isinstance(outcome, ResolveMatch)
    assert outcome.instrument_id == "US-DEMO-A"

    # неоднозначность — список кандидатов, не молчаливый выбор первого
    outcome = provider.resolve("DUAL", "US", "2024-05-20")
    assert isinstance(outcome, ResolveAmbiguous)
    assert outcome.candidates == ("US-DUAL-A", "US-DUAL-B")

    # не найдено — значение, не исключение
    outcome = provider.resolve("NOPE", "US", "2024-05-20")
    assert isinstance(outcome, ResolveNotFound)


def test_resolve_without_date_is_rejected():
    provider = SyntheticMarketProvider()
    outcome = provider.resolve("DEMO", "US", "")
    assert isinstance(outcome, ProviderError)
    assert outcome.reason == "resolve_without_date"


def test_prices_have_both_close_and_adjusted():
    provider = SyntheticMarketProvider()
    result = provider.prices("listing-demo-1", "2024-05-20", "2024-05-21")
    assert isinstance(result, PriceSeries)
    assert len(result.rows) == 2
    for row in result.rows:
        assert row.close > 0
        assert row.adjusted > 0
    # фильтр по диапазону
    result = provider.prices("listing-demo-1", "2024-05-21", "2024-05-21")
    assert len(result.rows) == 1
    # неизвестный листинг — ошибка значением
    assert isinstance(provider.prices("nope", "2024-01-01", "2024-12-31"),
                      ProviderError)


def test_profile_found_and_not_found():
    provider = SyntheticMarketProvider()
    result = provider.profile("US-DEMO-A")
    assert isinstance(result, ProfileResult)
    assert result.data["industry"] == "tankers"
    assert isinstance(provider.profile("nope"), ProviderError)


def test_industry_members_are_candidates():
    provider = SyntheticMarketProvider()
    result = provider.industry_members("tankers")
    assert isinstance(result, Candidates)
    assert any(item["instrument_id"] == "US-DEMO-A" for item in result.items)


def test_poll_index_is_incremental():
    """poll_index: один запрос на источник; повторный опрос с новым
    курсором не возвращает старые записи."""
    provider = SyntheticDisclosuresProvider()
    first = provider.poll_index("")
    assert len(first.records) == 2
    assert first.cursor == "0002"

    second = provider.poll_index(first.cursor)
    assert second.records == ()
    assert second.cursor == "0002"

    mid = provider.poll_index("0001")
    assert len(mid.records) == 1
    assert mid.records[0].cursor == "0002"


def test_fetch_document_is_idempotent():
    """Тот же документ — тот же sha256 (module-contracts.md §3)."""
    provider = SyntheticDisclosuresProvider()
    doc1 = provider.fetch_document("synthetic://report-10k")
    doc2 = provider.fetch_document("synthetic://report-10k")
    assert doc1.sha256 == doc2.sha256
    assert doc1.content == doc2.content
    assert b"synthetic" in doc1.content
    # неизвестный url — ошибка значением
    assert isinstance(provider.fetch_document("synthetic://nope"),
                      ProviderError)


def test_list_documents_filters_without_bodies():
    provider = SyntheticDisclosuresProvider()
    all_docs = provider.list_documents("issuer-demo")
    assert len(all_docs.documents) == 2
    tenk = provider.list_documents("issuer-demo", doc_type="10-K")
    assert len(tenk.documents) == 1
    assert tenk.documents[0].url == "synthetic://report-10k"


def test_register_replaces_factory():
    class Probe:
        source_name = "synthetic"

    register("probe-provider", Probe)
    assert isinstance(get_provider("probe-provider"), Probe)
    register("synthetic-market", SyntheticMarketProvider)  # вернуть как было
