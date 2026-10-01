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
                 "currency": "USD", "volume": None, "source": "twelvedata"}
                for d, c in self._rows]


class _Actions:
    def __init__(self, events):
        self._events = events

    def all(self, instrument_id):
        return self._events


class _Sink:
    def __init__(self):
        self.rows = {}
        self.lineage = {}

    def insert_measure_with_lineage(self, measure, lineage):
        self.rows[measure["concept"]] = measure
        self.lineage[measure["concept"]] = lineage


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
    _run.lineage = builder._snapshots.lineage
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
    window = _run.lineage["total_return"][0]
    assert window == {"price_instrument_id": "US-X",
                      "date_from": "2025-10-10", "date_to": "2026-09-30",
                      "source": "twelvedata", "points": 4,
                      "role": "input: price_close window"}


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
    kinds = [l.get("ca_kind") for l in _run.lineage["total_return"]]
    assert kinds == [None, "dividend"]     # окно цен + дивиденд, без сплита


def test_short_series_refuses_with_named_input():
    rows, _ = _run([("2026-09-30", 50.0)])
    for concept in ("total_return", "drawdown"):
        assert rows[concept]["value"] is None
        assert rows[concept]["null_reason"] == "missing_data: price_close"
        assert _run.lineage[concept] == []


def test_price_lineage_is_written_and_satisfies_i4(tmp_path):
    """Миграция 48: строка окна цен ложится в measure_lineage_price, и
    doctor не считает меру «со значением, но без lineage»."""
    import sqlite3

    from rusterm.store.db import apply_migrations
    from rusterm.store.doctor import doctor_report
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import Instrument, Issuer, RepoRegistry

    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer("i", "X", "US", "1", None,
                                          "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument("US-X", "i", None,
                                                  "common", "active", None))
    repos.snapshot.create_snapshot("s", "US-X", 1, "2026-10-01", None,
                                   "none", "ready")
    builder = SnapshotBuilder.__new__(SnapshotBuilder)
    builder._prices = _Prices([("2025-10-10", 100.0), ("2026-09-30", 120.0)])
    builder._corp_actions = _Actions([])
    builder._snapshots = repos.snapshot
    builder._price_return_pass("s", "i", "US-X", "2026-10-01", set(),
                               _Result())
    tr = [m for m in repos.snapshot.get_measures("s")
          if m[3] == "total_return"][0]
    assert float(tr[4]) == pytest.approx(0.2)
    assert repos.snapshot.lineage_price(tr[0])[0]["points"] == 2
    report = doctor_report(paths, conn)
    assert not any("без lineage" in p for p in report["problems"])
