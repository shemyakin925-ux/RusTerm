"""ТЗ-76 W5: Verizon — shares_outstanding по payload, а не по догадке.

Фикстура `companyfacts_vz_shares.json` — настоящие companyfacts VZ
(CIK 732712), полученные живым запросом 22.09.2026 (бюджет 10,
израсходовано 2: первый на неверный CIK вернул 404, второй — ответ)
и обрезанные до тегов семейства акций в форме companyfacts (10-K,
последние 6 годовых + 6 прочих на единицу, те же поля записи, что у
tools/trim_companyfacts). Всё, что утверждает тест, читается из
файла, а не из отчёта.

Решение W5 (правило 9 — «тег входит только с payload, который его
доказывает»): у словарного тега shares_outstanding,
us-gaap:CommonStockSharesOutstanding, в payload VZ НЕТ. VZ раскрывает
долю иначе: us-gaap:CommonStockSharesIssued (эмитировано) и
dei:EntityCommonStockSharesOutstanding (обложка 10-K), и это НЕ те же
числа: эмитировано минус казначейские = 4 291 433 646 − 74 258 296 =
4 217 175 350 против обложенческих 4 217 684 168 (разные даты
замера). Подставить любой из них в shares_outstanding — нарушение
Z1 («два тега никогда не суммируются», USD/shares-тег чужого смысла
концепт не закрывает). Словарь остаётся честным отказом: карта не
расширена, ни один подменный тег в shares_outstanding не внесён.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.normalize.concepts import CONCEPT_MAP
from rusterm.pipeline import apply_concept_map

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "data" / "edgar" / "companyfacts_vz_shares.json"

# канонический тег shares_outstanding и подмены, которые VZ подаёт вместо
MAP_TAG = "CommonStockSharesOutstanding"
ISSUED = "CommonStockSharesIssued"
TREASURY = "TreasuryStockCommonShares"
DEI_OUT = "EntityCommonStockSharesOutstanding"


@pytest.fixture(scope="module")
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _latest_shares(node: dict, tag: str) -> int:
    """Свежее 10-K значение тега в единице shares по последнему end."""
    units = node["facts"]["us-gaap"].get(tag) or node["facts"]["dei"].get(tag)
    assert units, f"тега {tag} нет в фикстуре — тест бессилен"
    entries = units["units"]["shares"]
    return max(entries, key=lambda e: e["end"])["val"]


def test_fixture_is_real_verizon(payload):
    """Фикстура — настоящий VZ payload: CIK, имя и следы живой сборки."""
    assert payload["cik"] == 732712
    assert "VERIZON" in payload["entityName"].upper()
    assert "live fetch" in payload["source"].lower()
    assert "us-gaap" in payload["facts"] and "dei" in payload["facts"]


def test_the_map_tag_is_absent_from_the_payload(payload):
    """Решающее: us-gaap:CommonStockSharesOutstanding в payload VZ нет.
    Отказ shares_outstanding для VZ — факт данных, а не догадка."""
    assert MAP_TAG not in payload["facts"]["us-gaap"], (
        "VZ стал подавать картычный тег — вывод W5 пора пересматривать")


def test_the_substitutes_are_present_by_number(payload):
    """Чем именно VZ закрывает долю: эмитированные, казначейские и
    обложенческие outstanding — все с реальными числами из payload."""
    issued = _latest_shares(payload, ISSUED)
    treasury = _latest_shares(payload, TREASURY)
    dei = _latest_shares(payload, DEI_OUT)
    assert issued == 4291433646, issued
    assert treasury == 74258296, treasury
    assert dei == 4217684168, dei
    # эмитировано ≠ в обращении: расходятся ровно на казначейские,
    # поэтому подмена Issued вместо Outstanding завысила бы долю
    assert issued - treasury == 4217175350
    assert issued != dei and issued - treasury != dei


def test_concept_map_refuses_every_vz_shares_tag(payload):
    """Ни один тег семейства акций, который реально подаёт VZ, не
    закрывает shares_outstanding: apply_concept_map даёт канон NULL
    (отказ считается, а не выбрасывается)."""
    for tag in (ISSUED, TREASURY):
        fact = {"concept": f"us-gaap:{tag}"}
        assert apply_concept_map(fact) == 1
        assert fact["canonical_concept"] is None, tag
    dei_fact = {"concept": f"dei:{DEI_OUT}"}
    assert apply_concept_map(dei_fact) == 1
    assert dei_fact["canonical_concept"] is None


def test_map_was_not_widened_to_smuggle_a_substitute():
    """Пин против соблазна «починить» VZ подстановкой: кортеж
    shares_outstanding остаётся ровно одним честным тегом. Тест красен,
    если кто-то допишет Issued/казначейские/dei в shares_outstanding —
    это было бы нарушением Z1, а не решением."""
    assert CONCEPT_MAP["shares_outstanding"] == (MAP_TAG,)


def test_the_map_tag_still_closes_where_it_is_filed():
    """Честный отказ — не сломанный словарь: там, где эмитент действительно
    подаёт CommonStockSharesOutstanding (как AAPL в правиле 9), концепт
    по-прежнему закрывается."""
    fact = {"concept": f"us-gaap:{MAP_TAG}"}
    assert apply_concept_map(fact) == 0
    assert fact["canonical_concept"] == "shares_outstanding"
