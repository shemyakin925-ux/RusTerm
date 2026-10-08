"""PRODUCT.md С4 (ТЗ-132): вкладка «Аналоги» — компании группы рядом.

`rusterm/desktop/peers.py`: строки — участники peer set, числа из
последнего снапшота с правилами прочерков карточки, медиана последней
строкой, колонка только при ≥ 3 числах; график — место компании в группе
(0–100, медиана 50), а не проценты к медиане, которые взрываются у нуля.
"""
from __future__ import annotations

import pytest

from rusterm.desktop import peers


def _row(ticker, me=False, **values):
    cells = {c: {"text": "—" if values.get(c) is None else str(values[c]),
                 "value": values.get(c), "tooltip": ""}
             for c, _t in peers.PEER_COLUMNS}
    return {"instrument_id": f"US-{ticker}", "ticker": ticker, "name": "",
            "is_self": me, "cells": cells}


def _table(rows):
    columns = [(c, t) for c, t in peers.PEER_COLUMNS
               if sum(r["cells"][c]["value"] is not None for r in rows)
               >= peers.MIN_VALUES]
    import statistics
    median = {c: {"value": statistics.median(
        [r["cells"][c]["value"] for r in rows
         if r["cells"][c]["value"] is not None])} for c, _t in columns}
    return {"rows": rows, "columns": columns, "median": median}


def test_compare_is_the_place_in_group_not_percent_to_median():
    rows = [_row("ME", True, net_debt_ebitda=2.05, roe=0.30),
            _row("A", net_debt_ebitda=0.10, roe=0.10),
            _row("B", net_debt_ebitda=0.14, roe=0.20),
            _row("C", net_debt_ebitda=3.00, roe=0.40)]
    spec = peers.compare_spec(_table(rows))
    assert spec["kind"] == "hbars"
    values = dict(zip(spec["labels"], spec["values"]))
    # обходит двух из трёх: 66,7, а не «+1 364 % к медиане»
    assert values["Чистый долг / EBITDA"] == pytest.approx(200 / 3)
    assert values["ROE"] == pytest.approx(200 / 3)
    assert spec["range"] == (0.0, 100.0) and spec["center"] == 50.0


def test_column_needs_three_numbers():
    rows = [_row("ME", True, gross_margin=0.7, roe=0.1),
            _row("A", roe=0.2), _row("B", roe=0.3)]
    concepts = [c for c, _t in _table(rows)["columns"]]
    assert concepts == ["roe"], "одно число валовой маржи — не колонка"


def test_no_peer_set_says_words():
    assert peers.peer_table(None, "US-X", {"has_peer_set": False}) is None
    assert peers.compare_spec(None)["kind"] == "message"
