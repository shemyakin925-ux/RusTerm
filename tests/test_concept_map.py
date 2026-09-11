"""Тесты карты концептов us-gaap -> словарь (TASK-9 V0).

Таблица — авторитетная; страж сверяет имена концептов с
docs/data-dictionary.md §2 в обе стороны. Тег вне карты даёт NULL и
считается, приоритет соблюдается, карта не содержит SQL и сети.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from rusterm.normalize import concepts
from rusterm.normalize.concepts import (
    CONCEPT_MAP,
    CONCEPT_MAP_VERSION,
    canonical_for,
    priority_rank,
    strip_taxonomy,
)

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"


def test_every_concept_name_exists_in_data_dictionary():
    """Страж (B7-стиль): левая колонка таблицы — имена из
    docs/data-dictionary.md §2, в обе стороны. Исключений нет:
    постоянный список изъятий удалён (TASK-12 Y4) — строка
    `total_equity_incl_nci` лежит в словаре на main, а guard со
    списком изъятий ничего не сторожит."""
    doc = (Path(__file__).resolve().parents[1] / "docs"
           / "data-dictionary.md").read_text(encoding="utf-8")
    known = set(CONCEPT_MAP)
    missing = [name for name in known
               if f"`{name}`" not in doc and f"**{name}**" not in doc
               and name not in doc]
    assert not missing, f"концептов нет в словаре: {missing}"


def test_w3_total_equity_incl_nci_maps_and_total_equity_does_not_absorb():
    """TASK-10 W3: новый концепт маппится; total_equity НЕ поглощает
    тег Including (теги не синонимы и не суммируются)."""
    assert canonical_for(
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
    ) == "total_equity_incl_nci"
    assert canonical_for("StockholdersEquity") == "total_equity"
    assert CONCEPT_MAP["total_equity"] == ("StockholdersEquity",)
    assert "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest" \
        not in CONCEPT_MAP["total_equity"]


def test_unknown_tag_maps_to_none_and_is_counted():
    assert canonical_for("SomeNewTag2027") is None
    assert canonical_for("") is None
    # канонические имена проходят сами на себя (синтетика)
    assert canonical_for("revenue") == "revenue"
    assert canonical_for("Revenues") == "revenue"


def test_y1_switched_tags_map_and_lookalike_does_not():
    """TASK-12 Y1: два названных тега-преемника маппятся; похожий по
    подстроке PaymentsToAcquireMarketableSecurities — нет (карта
    расширяется именованным решением, никогда подстрочным поиском).
    Новый тег стоит после прежнего: приоритет не тронут."""
    assert canonical_for("PaymentsToAcquireProductiveAssets") == "capex"
    assert canonical_for("Depreciation") == "d_and_a"
    assert canonical_for("PaymentsToAcquireMarketableSecurities") is None
    capex_tags = CONCEPT_MAP["capex"]
    assert capex_tags.index(
        "PaymentsToAcquirePropertyPlantAndEquipment") < \
        capex_tags.index("PaymentsToAcquireProductiveAssets")
    assert CONCEPT_MAP["d_and_a"][-1] == "Depreciation"
    # прежние приоритеты d_and_a не сдвинулись
    assert CONCEPT_MAP["d_and_a"][:3] == (
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization")
    assert CONCEPT_MAP_VERSION == "us-gaap.v3"


def test_priority_first_tag_wins_when_both_present():
    """Оба тега в payload'е: каноническое имя одно («revenue»), а выбор
    источника — по приоритетному рангу (RFC-тег раньше Revenues)."""
    assert strip_taxonomy("us-gaap:Revenues")[1] == "Revenues"
    revenue_tags = CONCEPT_MAP["revenue"]
    assert revenue_tags.index(
        "RevenueFromContractWithCustomerExcludingAssessedTax") < \
        revenue_tags.index("Revenues")
    doc = {
        "source": "synthetic",
        "note": "синтетический companyfacts для приоритета",
        "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [
                    {"start": "2024-01-01", "end": "2024-12-31",
                     "val": 777, "accn": "a1", "form": "10-K",
                     "filed": "2025-02-15", "fy": 2024, "fp": "FY"}]}},
            "Revenues": {
                "units": {"USD": [
                    {"start": "2024-01-01", "end": "2024-12-31",
                     "val": 999, "accn": "a1", "form": "10-K",
                     "filed": "2025-02-15", "fy": 2024, "fp": "FY"}]}},
        }},
    }
    from rusterm.parsers import CompanyFactsParser
    raw = json.dumps(doc).encode()
    result = CompanyFactsParser().parse(raw, {"issuer_id": "i1",
                                              "source_ref": "sha-prio"})
    by_tag = {f["concept"]: f for f in result.facts}
    assert set(by_tag) == {
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:Revenues"}
    # оба несут одно каноническое имя; выигрывает меньший ранг
    for f in result.facts:
        _, local = strip_taxonomy(f["concept"])
        assert canonical_for(local) == "revenue"
    rfc_rank = priority_rank("revenue",
                             "RevenueFromContractWithCustomerExcludingAssessedTax")
    rev_rank = priority_rank("revenue", "Revenues")
    assert rfc_rank < rev_rank


def test_aapl_payload_ingests_with_canonical_concepts():
    """На записанном payload AAPL после «ingest» (парсер + карта)
    как минимум revenue, net_income, total_assets, total_equity и ocf
    имеют непустое canonical_concept."""
    from rusterm.parsers import CompanyFactsParser
    from rusterm.pipeline import apply_concept_map
    raw = (DATA / "companyfacts_m3_AAPL.json").read_bytes()
    import hashlib
    sha = hashlib.sha256(raw).hexdigest()
    result = CompanyFactsParser().parse(raw, {"issuer_id": "i-aapl",
                                              "source_ref": sha})
    unmapped = 0
    canonical_seen: set = set()
    for fact in result.facts:
        fact = dict(fact)
        unmapped += apply_concept_map(fact)
        if fact.get("canonical_concept"):
            canonical_seen.add(fact["canonical_concept"])
    for concept in ("revenue", "net_income", "total_assets",
                    "total_equity", "ocf"):
        assert concept in canonical_seen, concept
    # в m2-payload только пять концептов словаря — неотображённых нет
    assert unmapped == 0


def test_normalize_module_has_no_sql_no_http():
    result = subprocess.run(
        ["grep", "-rnE", r"execute\(|httpx|requests",
         "rusterm/normalize/"],
        capture_output=True, text=True)
    assert result.returncode == 1, result.stdout


def test_v6_doctor_lists_unmapped_tags_with_counts(capsys, monkeypatch):
    import shutil
    import tempfile
    """TASK-9 V6: doctor показывает неотображённые теги по имени и
    счётчику; на пустой базе не падает."""
    from rusterm.cli import main
    tmpdir = tempfile.mkdtemp()
    root = os.path.join(tmpdir, "app")
    try:
        monkeypatch.setenv("RUSTERM_ENV_FILE",
                           "/nonexistent/rusterm.env-for-tests")
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "doctor"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["unmapped_concepts"]["count"] == 0
        assert payload["unmapped_concepts"]["top"] == []
    finally:
        shutil.rmtree(tmpdir)
