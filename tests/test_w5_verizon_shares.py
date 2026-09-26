"""ТЗ-76 W5 (данные) + ТЗ-78 Y2 (маршрут): Verizon — shares_outstanding.

Фикстура `companyfacts_vz_shares.json` — настоящие companyfacts VZ
(CIK 732712), полученные живым запросом 22.09.2026 (бюджет 10,
израсходовано 2) и обрезанные до тегов семейства акций (10-K, последние
6 годовых + 6 прочих на единицу, те же поля записи, что у
tools/trim_companyfacts). Всё, что утверждает тест, читается из файла.

W5 закрылся честным отказом: us-gaap:CommonStockSharesOutstanding в
payload VZ нет, карта не расширена, shares_outstanding остаётся
missing_data. Y2 переписывает вывод на новый: поднимается вопрос
маршрута. VZ раскрывает долю через dei:EntityCommonStockSharesOutstanding
(обложка 10-K) и пару us-gaap:CommonStockSharesIssued /
us-gaap:TreasuryStockCommonShares. Оба кандидата — не тот же концепт,
что us-gaap:CommonStockSharesOutstanding, поэтому:

Правило маршрута (не вкус, см. докстроку concepts.py):
  1. us-gaap:CommonStockSharesOutstanding (строка баланса по классу) —
     основной источник, приоритет 0.
  2. dei:EntityCommonStockSharesOutstanding (обложка 10-K, сущность в
     целом) — дополнительный источник, приоритет 1000 (см.
     _DEI_RANK_OFFSET в concepts.py). Если эмитент подаёт оба —
     snapshot берёт min(rank), то есть us-gaap.
  3. us-gaap:CommonStockSharesIssued и us-gaap:TreasuryStockCommonShares
     в shares_outstanding НЕ входят: Issued − Treasury — арифметика двух
     тегов, а карта несёт только одно-теговые соответствия (Z1: «два
     тега никогда не суммируются»). Формула требует own provenance-слой
     в formulas.py, которого нет, и на фикстуре VZ она расходится с
     обложкой ровно на 508 818 shares (см. test_route_divergence):
     Issued/Treasury замерены на end=2025-12-31, dei — на end=2026-01-30,
     это разные даты отсчёта одного и того же года.

Тесты-стражи W5, которые были «карта отказывает VZ», переписаны под
новое поведение: карта принимает dei как shares_outstanding, но по-
прежнему отказывает Issued/Treasury. Страж против smuggle остаётся —
теперь он красен, если кто-то допишет dei в кортеж CONCEPT_MAP us-gaap
(обход приоритета вместо отдельной таблицы).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rusterm.normalize.concepts import (
    CONCEPT_MAP,
    CONCEPT_MAP_DEI,
    _DEI_RANK_OFFSET,
    canonical_for,
    map_version,
    priority_rank,
)
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "data" / "edgar" / "companyfacts_vz_shares.json"

# канонический тег shares_outstanding в основной карте и подмены,
# которые VZ подаёт вместо него
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
    """W5-решение остаётся фактом данных: us-gaap:CommonStockSharesOutstanding
    в payload VZ нет — без Y2 shares_outstanding для VZ был бы missing."""
    assert MAP_TAG not in payload["facts"]["us-gaap"], (
        "VZ стал подавать картычный тег — приоритет маршрута пора "
        "пересматривать: us-gaap снова становится главным источником")


def test_the_substitutes_are_present_by_number(payload):
    """Что именно подаёт VZ вместо map-тега: эмитировано, казначейские,
    обложенческие outstanding — все с реальными числами из payload."""
    issued = _latest_shares(payload, ISSUED)
    treasury = _latest_shares(payload, TREASURY)
    dei = _latest_shares(payload, DEI_OUT)
    assert issued == 4291433646, issued
    assert treasury == 74258296, treasury
    assert dei == 4217684168, dei
    # эмитировано ≠ в обращении: разница ровно в казначейских, и она
    # не равна обложенческому outstanding — подмена Issued или
    # Issued−Treasury вместо dei завысила/занизила бы долю
    assert issued - treasury == 4217175350
    assert issued != dei and issued - treasury != dei


def test_route_divergence_measured_on_the_fixture(payload):
    """Y2 требует измерить расхождение двух маршрутов числом.
    dei (обложка) минус Issued−Treasury (баланс на иную дату) на
    последней паре записей VZ: 4 217 684 168 − 4 217 175 350 =
    508 818 акций (0.012 %). Это не шум: у пар разная end-дата
    (2025-12-31 vs 2026-01-30), то есть арифметика двух тегов и
    прямая обложка — РАЗНЫЕ экономические величины. Формула
    Issued−Treasury в shares_outstanding не идёт."""
    issued = _latest_shares(payload, ISSUED)
    treasury = _latest_shares(payload, TREASURY)
    dei = _latest_shares(payload, DEI_OUT)
    assert (issued - treasury, dei, dei - (issued - treasury)) == (
        4217175350, 4217684168, 508818)
    # расхождение — не нулевое: два маршрута дают разные числа на
    # одних данных, значит выбор между ними обязан быть правилом
    assert dei - (issued - treasury) != 0


def test_dei_tag_closes_shares_outstanding(payload):
    """Новое поведение Y2: dei-факт VZ закрывает shares_outstanding."""
    dei_fact = {"concept": f"dei:{DEI_OUT}"}
    assert apply_concept_map(dei_fact) == 0
    assert dei_fact["canonical_concept"] == "shares_outstanding"
    assert dei_fact["concept_map_version"] == "dei.v1"


def test_us_gaap_substitutes_still_refuse(payload):
    """Карта не распускается: Issued и TreasuryStockCommonShares
    по-прежнему вне shares_outstanding — подмена двумя тегами или
    арифметикой между ними остаётся нарушением Z1."""
    for tag in (ISSUED, TREASURY):
        fact = {"concept": f"us-gaap:{tag}"}
        assert apply_concept_map(fact) == 1, tag
        assert fact["canonical_concept"] is None, tag


def test_map_was_not_widened_to_smuggle_a_substitute():
    """Пин smuggle (W5): кортеж shares_outstanding в us-gaap остаётся
    ровно одним честным тегом — ни Issued, ни Treasury, ни dei-тег в
    us-gaap-таблицу не заносятся. Если future правка допишет их —
    обход приоритета; отдельная таблица CONCEPT_MAP_DEI обязана
    оставаться единственным домом dei-тега."""
    assert CONCEPT_MAP["shares_outstanding"] == (MAP_TAG,)
    assert DEI_OUT not in CONCEPT_MAP["shares_outstanding"]


def test_priority_rule_us_gaap_beats_dei_when_both_present():
    """Правило, не вкус: если эмитент подаёт ОБА, priority_rank обязан
    вернуть us-gaap ранг, меньший любого dei ранга, поэтому snapshot
    выберет us-gaap через min(rank)."""
    us_rank = priority_rank("shares_outstanding", MAP_TAG, "us-gaap")
    dei_rank = priority_rank("shares_outstanding", DEI_OUT, "dei")
    assert us_rank == 0
    assert dei_rank == _DEI_RANK_OFFSET
    assert us_rank < dei_rank, (
        f"us-gaap обязан иметь приоритет: us={us_rank} dei={dei_rank}")


def test_dei_map_is_only_the_cover_page_fact():
    """CONCEPT_MAP_DEI несёт единственный тег, доказанный фикстурой:
    никаких Issued/Treasury/PreferredStockSharesOutstanding сюда не
    кладётся — они либо другие концепты, либо вне карты."""
    assert CONCEPT_MAP_DEI == {"shares_outstanding": (DEI_OUT,)}
    assert map_version("dei") == "dei.v1"


def test_canonical_for_routes_taxonomies_independently():
    """canonical_for не путает таксономии: тот же локальный тег,
    поданный в чужой таксономии, не закрывает концепт."""
    assert canonical_for(DEI_OUT, "us-gaap") is None
    assert canonical_for(MAP_TAG, "dei") is None
    assert canonical_for(DEI_OUT, "dei") == "shares_outstanding"
    assert canonical_for(MAP_TAG, "us-gaap") == "shares_outstanding"


def test_parser_emits_dei_alongside_us_gaap(payload):
    """End-to-end без БД: CompanyFactsParser обязан выдавать dei-факты,
    если они есть в payload, РЯДОМ с us-gaap (иначе фикстура VZ не
    доживает до apply_concept_map и whole path остаётся missing)."""
    raw = FIXTURE.read_bytes()
    result = CompanyFactsParser().parse(
        raw, {"issuer_id": "i-VZ", "source_ref": "sha256:demo"})
    dei_facts = [f for f in result.facts
                 if f["concept"] == f"dei:{DEI_OUT}"]
    assert dei_facts, "parcer не выбросил dei-факт VZ: " \
        f"{sorted({f['concept'] for f in result.facts})}"
    # us-gaap Issued и Treasury тоже обязаны остаться
    tags = {f["concept"] for f in result.facts}
    assert f"us-gaap:{ISSUED}" in tags
    assert f"us-gaap:{TREASURY}" in tags
    # и именно dei проходит apply_concept_map в shares_outstanding
    dei = dei_facts[0]
    assert apply_concept_map(dei) == 0
    assert dei["canonical_concept"] == "shares_outstanding"


def test_the_map_tag_still_closes_where_it_is_filed():
    """Честный отказ W5 не сломан: там, где эмитент действительно
    подаёт CommonStockSharesOutstanding (AAPL, правило 9), концепт
    по-прежнему закрывается через us-gaap."""
    fact = {"concept": f"us-gaap:{MAP_TAG}"}
    assert apply_concept_map(fact) == 0
    assert fact["canonical_concept"] == "shares_outstanding"
    assert fact["concept_map_version"] == "us-gaap.v4"


def test_shares_outstanding_facts_on_vz_go_from_zero_to_six(payload):
    """Y2 «что оживает»: сколько фактов на канон shares_outstanding
    даёт фикстура VZ. До Y2 парсер не выдавал dei-раздел, поэтому
    ни один факт не канонизировался в shares_outstanding; после Y2
    обложка 10-K даёт шесть instants (FY2020..FY2025), все с тем же
    4 217 684 168 на последней дате. Это число — вход для мер, а не
    сами меры: сами меры (см. REPORT-78 Y2) требуют price_close,
    которого в фикстуре нет."""
    raw = FIXTURE.read_bytes()
    result = CompanyFactsParser().parse(
        raw, {"issuer_id": "i-VZ", "source_ref": "sha256:demo"})
    closed = []
    for fact in result.facts:
        apply_concept_map(fact)
        if fact.get("canonical_concept") == "shares_outstanding":
            closed.append(fact)
    assert len(closed) == 6, [f["concept"] for f in closed]
    latest = max(closed, key=lambda f: f["period_end"])
    assert latest["value"] == "4217684168"
    assert latest["period_end"] == "2026-01-30"
