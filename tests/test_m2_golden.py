"""M2 golden-file (TASK-8 U7): пять эмитентов × пять завершённых
фискальных лет, значения — настоящие, из companyfacts SEC EDGAR
(обрезанные payload'ы в tests/data/edgar/companyfacts_<тикер>.json,
эталон ожидаемых значений — tests/data/golden_m2.json).

Тест полностью офлайн: каждый number из golden разрешается локатором
в то же значение на сохранённом сырье. Живого запроса нет и не нужно —
сырьё уже в git (записанные ответы, не синтетика).

Ручная сверка заголовочных значений с общеизвестными цифрами сделана
при сборке (AAPL FY25 416.2 млрд, MSFT FY25 281.7 млрд, JNJ FY24
88.8 млрд, KO FY24 47.1 млрд, XOM FY24 349.6 млрд — сходятся);
остальные 120 значений помечены «требуют проверки» пользователем.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rusterm.core.fact import locator_from_json, resolve_locator
from rusterm.formulas import calculate_measure
from rusterm.parsers import CompanyFactsParser

DATA = Path(__file__).resolve().parents[1] / "tests" / "data"
GOLDEN = json.loads((DATA / "golden_m2.json").read_text(encoding="utf-8"))
ISSUERS = sorted({entry["issuer"] for entry in GOLDEN})


def _issuer_facts(issuer: str):
    raw = (DATA / "edgar" / f"companyfacts_m2_{issuer}.json").read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    result = CompanyFactsParser().parse(
        raw, {"issuer_id": f"i-{issuer}", "source_ref": sha})
    index = {(f["concept"], f["period_start"], f["period_end"]): f
             for f in result.facts}
    return raw, sha, index


def test_m2_every_golden_value_resolves_to_fact():
    """Каждое число golden-файла разрешается локатором в то же значение."""
    assert len(ISSUERS) == 5, "пять эмитентов"
    checked = 0
    for issuer in ISSUERS:
        raw, sha, index = _issuer_facts(issuer)
        getter = lambda request_hash: raw  # noqa: E731
        entries = [g for g in GOLDEN if g["issuer"] == issuer]
        assert len(entries) == 25, f"{issuer}: ожидалось 5 метрик × 5 лет"
        for entry in entries:
            # instant-факты парсер хранит с period_start = period_end
            start = entry["period_start"] or entry["period_end"]
            key = (entry["concept"], start, entry["period_end"])
            fact = index.get(key)
            assert fact is not None, f"{issuer}: нет факта {key}"
            assert fact["value"] == entry["expected"], (
                f"{issuer} {entry['metric']} {entry['period_end']}: "
                f"{fact['value']} != {entry['expected']}")
            locator = locator_from_json(fact["locator"])
            resolved = resolve_locator(locator, getter)
            assert resolved == entry["expected"], (
                f"{issuer} {entry['metric']} {entry['period_end']}: "
                f"resolve -> {resolved}")
            checked += 1
    assert checked == 125


def test_m2_derived_margins_and_roe_compute_from_golden():
    """Производные меры считаются из golden-фактов: net_margin на всех
    25 парах (год есть выручка и чистая прибыль), roe — там, где есть
    капитализация начала и конца периода."""
    per_issuer: dict = {}
    for entry in GOLDEN:
        per_issuer.setdefault(
            (entry["issuer"], entry["period_end"]), {}
        )[entry["metric"]] = float(entry["expected"])

    margins = 0
    for (_issuer, _period_end), metrics in per_issuer.items():
        if "revenue" in metrics and "net_income" in metrics:
            measure = calculate_measure("net_margin", net_income=metrics["net_income"],
                                        revenue=metrics["revenue"])
            assert measure.value is not None
            assert measure.null_reason is None
            margins += 1
    assert margins == 25

    roe_checked = 0
    by_issuer: dict = {}
    for (issuer, period_end), metrics in per_issuer.items():
        by_issuer.setdefault(issuer, {})[period_end] = metrics
    for issuer, years in by_issuer.items():
        ends = sorted(years)
        for prev_end, cur_end in zip(ends, ends[1:]):
            prev, cur = years[prev_end], years[cur_end]
            if "total_equity" not in prev or "total_equity" not in cur \
                    or "net_income" not in cur:
                continue
            measure = calculate_measure(
                "roe", net_income=cur["net_income"],
                total_equity_begin=prev["total_equity"],
                total_equity_end=cur["total_equity"])
            assert measure.value is not None, (issuer, cur_end)
            assert measure.null_reason is None
            roe_checked += 1
    assert roe_checked >= 20, f"roe посчитан только на {roe_checked} парах"


def test_m2_golden_covers_five_metrics_per_issuer():
    from collections import Counter
    counts = Counter((e["issuer"], e["metric"]) for e in GOLDEN)
    assert len(counts) == 25
    assert all(n == 5 for n in counts.values()), counts
