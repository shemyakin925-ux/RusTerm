"""Регрессия ТЗ-78 Y2, найденная координатором 24.09.2026.

С тех пор как CompanyFactsParser разбирает раздел ``dei``, проход 1
считал «конец периода подачи» максимумом концов ВСЕХ её фактов. Число
акций с обложки (``dei:EntityCommonStockSharesOutstanding``) датировано
днём подачи — позже конца отчётного года. Конец периода подачи уезжал
на дату обложки, и каждый финансовый факт подачи становился
``restated``. Снапшот берёт только ``as_reported``: на живой выгрузке
Oracle это 13 982 «пересчитанных» против 69 «как поданы», у половины
аналогов пользователя посчитано 4 меры из 28 и меньше.

Правило: конец периода подачи задают финансовые факты; обложка ``dei``
в нём не участвует.
"""
from __future__ import annotations

import json

from rusterm.parsers import CompanyFactsParser

ACCN = "0001564590-22-023675"


def _entry(end: str, val: float, start: str | None = None,
           form: str = "10-K", fy: int = 2022, fp: str = "FY") -> dict:
    e = {"end": end, "val": val, "accn": ACCN, "fy": fy, "fp": fp,
         "form": form, "filed": "2022-06-21"}
    if start:
        e["start"] = start
    return e


def _payload(with_cover: bool) -> bytes:
    us_gaap = {
        "Revenues": {"units": {"USD": [
            _entry("2022-05-31", 42_440e6, start="2021-06-01"),
            # сравнительный год той же подачи — законно restated
            _entry("2021-05-31", 40_479e6, start="2020-06-01"),
        ]}},
        "Assets": {"units": {"USD": [_entry("2022-05-31", 109_297e6)]}},
    }
    facts = {"us-gaap": us_gaap}
    if with_cover:
        facts["dei"] = {"EntityCommonStockSharesOutstanding": {"units": {
            "shares": [_entry("2022-06-13", 2_666_000_000)]}}}
    return json.dumps({"cik": 1341439, "entityName": "ORACLE CORP",
                       "facts": facts}).encode()


def _basis(payload: bytes) -> dict:
    res = CompanyFactsParser().parse(payload, {
        "issuer_id": "i", "listing_id": "l", "source_ref": "sha"})
    return {(f["concept"].split(":")[-1], f["period_end"]): f["basis"]
            for f in res.facts}


def test_cover_date_does_not_restate_the_fiscal_year():
    got = _basis(_payload(with_cover=True))
    assert got[("Revenues", "2022-05-31")] == "as_reported", got
    assert got[("Assets", "2022-05-31")] == "as_reported", got


def test_comparative_year_is_still_restated():
    """Граница не размыта: прошлогодняя цифра той же подачи —
    по-прежнему restated."""
    got = _basis(_payload(with_cover=True))
    assert got[("Revenues", "2021-05-31")] == "restated", got


def test_same_verdict_with_and_without_cover():
    """Наличие обложки не меняет ни одного basis финансовых фактов."""
    with_cover = _basis(_payload(with_cover=True))
    without = _basis(_payload(with_cover=False))
    shared = {k: v for k, v in with_cover.items() if k in without}
    assert shared == without


def test_cover_fact_itself_is_kept():
    """Сам факт обложки не выбрасывается: ТЗ-78 Y2 берёт из него
    число акций Verizon."""
    got = _basis(_payload(with_cover=True))
    assert ("EntityCommonStockSharesOutstanding", "2022-06-13") in got
