"""ТЗ-130 K2: тег себестоимости Alcoa (v6) и отзыв тега AT&T (v7).

Payload-доказательства — в REPORT-130 (K1): CostOfGoodsAndService…
— строка Alcoa «Cost of goods sold (exclusive of expenses shown
separately below)», FY2021 = 9 153 000 000 USD; OtherCostOfOperatingRevenue
— строка AT&T «Operating expenses: Cost of revenues», FY2024 =
27 032 000 000 USD — оказалась ЧАСТЬЮ себестоимости (строку
оборудования AT&T подаёт своим расширением), и в v7 тег отозван: сверка
с Yahoo 08.10 показала валовую прибыль 95 млрд против ~73.
"""
from __future__ import annotations

from rusterm.normalize.concepts import (CONCEPT_MAP_VERSION, WITHDRAWN_TAGS,
                                        canonical_for, priority_rank)


def test_v7_keeps_alcoa_cogs_and_withdraws_the_partial_att_line():
    assert CONCEPT_MAP_VERSION == "us-gaap.v8"
    assert canonical_for(
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"
    ) == "cogs"
    assert canonical_for("OtherCostOfOperatingRevenue") is None
    assert WITHDRAWN_TAGS["us-gaap:OtherCostOfOperatingRevenue"] == "cogs"


def test_v6_keeps_the_full_lines_first():
    """Полные строки себестоимости приоритетнее усечённых: Alcoa подаёт
    одну строку «exclusive of D&A», AT&T — «Cost of revenues»; эмитент с
    CostOfGoodsAndServicesSold получает её, как и раньше."""
    order = [priority_rank("cogs", t) for t in (
        "CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization")]
    assert order == sorted(order)
    assert len(set(order)) == len(order)
