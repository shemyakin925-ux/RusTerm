"""Нулевые краткосрочные вложения — только с положительным
свидетельством (правило D7 для NCI, перенесённое на st_investments).

Осмотр окна 01.10.2026: у DELL строка ShortTermInvestments последний
раз в 2019, и шесть мер (ev, ev_ebitda, net_debt, net_debt_ebitda,
invested_capital, roic) стояли отказом stale_data."""
from __future__ import annotations

from rusterm.core.snapshot import SnapshotBuilder


class _Facts:
    def __init__(self, ends):
        self._ends = ends

    def as_reported_facts(self, issuer_id, concepts):
        return [("us-gaap:ShortTermInvestments", "1", f"f-{e}", "USD",
                 None, e, "st_investments") for e in self._ends]


def _why(ends, cash_end):
    builder = SnapshotBuilder.__new__(SnapshotBuilder)
    builder._snapshots = _Facts(ends)
    return builder._stinv_absent_from_balance("i", cash_end)


def test_discontinued_line_with_fresh_cash_is_zero_with_named_reason():
    assert (_why(["2018-02-02", "2019-02-01"], "2026-07-31")
            == "st_investments_discontinued: last 2019-02-01")


def test_never_reported_with_cash_is_zero():
    assert _why([], "2026-07-31") == "st_investments_never_reported"


def test_line_present_in_the_same_balance_is_not_replaced():
    assert _why(["2026-07-31"], "2026-07-31") is None


def test_no_cash_block_no_evidence_no_zero():
    assert _why([], None) is None


class _NciFacts:
    def __init__(self, ends):
        self._ends = ends

    def as_reported_facts(self, issuer_id, concepts):
        return [("us-gaap:MinorityInterest", "1", f"f-{e}", "USD", None, e,
                 "minority_interest") for e in self._ends]


def _nci(ends, equity_end):
    builder = SnapshotBuilder.__new__(SnapshotBuilder)
    builder._snapshots = _NciFacts(ends)
    return builder._nci_discontinued("i", equity_end)


def test_nci_discontinued_before_fresh_equity_is_named_zero():
    assert (_nci(["2009-07-31", "2010-07-31"], "2026-07-31")
            == "nci_discontinued: last 2010-07-31")


def test_nci_in_the_same_equity_block_or_no_equity_is_not_zero():
    assert _nci(["2026-07-31"], "2026-07-31") is None
    assert _nci(["2010-07-31"], None) is None
    assert _nci([], "2026-07-31") is None   # «никогда» — правило D7
