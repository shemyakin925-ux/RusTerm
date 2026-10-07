"""ТЗ-130 K2: теги себестоимости Alcoa и AT&T в карте us-gaap.v6.

Payload-доказательства — в REPORT-130 (K1): CostOfGoodsAndService…
— строка Alcoa «Cost of goods sold (exclusive of expenses shown
separately below)», FY2021 = 9 153 000 000 USD; OtherCostOfOperatingRevenue
— строка AT&T «Operating expenses: Cost of revenues», FY2024 =
27 032 000 000 USD. Оба — в конце приоритета: эмитент, подающий полную
строку, продолжает получать прежний тег.
"""
from __future__ import annotations

from rusterm.normalize.concepts import (CONCEPT_MAP_VERSION, canonical_for,
                                        priority_rank)


def test_v6_maps_the_two_cogs_successors():
    assert CONCEPT_MAP_VERSION == "us-gaap.v6"
    assert canonical_for(
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"
    ) == "cogs"
    assert canonical_for("OtherCostOfOperatingRevenue") == "cogs"


def test_v6_keeps_the_full_lines_first():
    """Полные строки себестоимости приоритетнее усечённых: Alcoa подаёт
    одну строку «exclusive of D&A», AT&T — «Cost of revenues»; эмитент с
    CostOfGoodsAndServicesSold получает её, как и раньше."""
    order = [priority_rank("cogs", t) for t in (
        "CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
        "OtherCostOfOperatingRevenue")]
    assert order == sorted(order)
    assert len(set(order)) == len(order)
