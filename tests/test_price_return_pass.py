"""total_return и drawdown за год по ряду цены (осмотр окна 01.10.2026:
цены за годы в базе, а меры стояли concept_not_mapped)."""
from __future__ import annotations

import pytest

from rusterm.core.snapshot import SnapshotBuilder


class _Prices:
    def __init__(self, rows):
        self._rows = rows

    def series(self, instrument_id, source=None):
        return [{"date": d, "close": c, "adjusted": None,
                 "currency": "USD", "volume": None} for d, c in self._rows]


class _Actions:
    def __init__(self, events):
        self._events = events

    def all(self, instrument_id):
        return self._events


class _Sink:
    def __init__(self):
        self.rows = {}

    def insert_measure_with_lineage(self, measure, lineage):
        self.rows[measure["concept"]] = measure


class _Result:
    measures = 0


def _run(prices, events=()):
    builder = SnapshotBuilder.__new__(SnapshotBuilder)
    builder._prices = _Prices(prices)
    builder._corp_actions = _Actions(list(events))
    builder._snapshots = _Sink()
    written = set()
    builder._price_return_pass("s", "i", "US-X", "2026-10-01", written,
                               _Result())
    return builder._snapshots.rows, written


def test_year_window_return_and_drawdown():
    rows, written = _run([("2024-01-02", 10.0),    # вне окна 365 дней
                          ("2025-10-10", 100.0),
                          ("2026-03-01", 150.0),
                          ("2026-06-01", 120.0),
                          ("2026-09-30", 200.0),
                          ("2026-10-02", 999.0)])  # позже as_of
    assert written == {"total_return", "drawdown"}
    assert float(rows["total_return"]["value"]) == pytest.approx(1.0)
    assert float(rows["drawdown"]["value"]) == pytest.approx(-0.2)
    assert rows["total_return"]["period_start"] == "2025-10-10"
    assert rows["total_return"]["period_end"] == "2026-09-30"


def test_dividend_adds_to_return_split_is_not_applied_twice():
    prices = [("2025-10-10", 100.0), ("2026-05-01", 100.0),
              ("2026-05-04", 98.0), ("2026-09-30", 98.0)]
    rows, _ = _run(prices, [
        {"kind": "dividend", "ex_date": "2026-05-04", "amount": 2.0,
         "factor": None},
        {"kind": "split", "ex_date": "2026-06-01", "amount": None,
         "factor": 4.0}])
    # цена упала на дивиденд: полная доходность ~0, а не -2 %
    assert float(rows["total_return"]["value"]) == pytest.approx(0.0,
                                                                abs=1e-9)


def test_short_series_refuses_with_named_input():
    rows, _ = _run([("2026-09-30", 50.0)])
    for concept in ("total_return", "drawdown"):
        assert rows[concept]["value"] is None
        assert rows[concept]["null_reason"] == "missing_data: price_close"
