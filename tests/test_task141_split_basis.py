"""ТЗ-141 D1: база счётчика акций через сплит (WMT 2024 ×3).

Счётчик, поданный ПОСЛЕ сплита о периоде ДО него (10-K WMT за FY2024
подан 2024-03-15, сплит 3:1 — 2024-02-26), уже в новой базе акций:
капитализация на конец периода = фактическая цена × счётчик ÷ фактор.
Даты подачи нет — значение не трогается, роль lineage называет
неизвестность базы.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import make_snapshot_builder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)


def _base(tmp_path, filed):
    paths = AppPaths.from_root(tmp_path / "split-base")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-W", "Fixture Split Co", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-W", "i-W", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-W", "US-W", "XNYS", "USD", 1, None, None))
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts/W")
    repos.fact.insert_fact(
        "f-rev", "i-W", None, "us-gaap:Revenues",
        "2019-01-01", "2019-12-31", "duration", "100.0",
        "USD", "USD", "as_reported", "extracted", raw.sha256,
        {"endpoint": "companyfacts", "kind": "10-K"}, "t",
        canonical_concept="revenue")
    locator = {"endpoint": "companyfacts", "kind": "10-K"}
    if filed:
        locator["filed"] = filed
    repos.fact.insert_fact(
        "f-sh", "i-W", None, "dei:EntityCommonStockSharesOutstanding",
        "2019-12-31", "2019-12-31", "instant", "100", "shares", None,
        "as_reported", "extracted", raw.sha256, locator, "t",
        canonical_concept="shares_outstanding")
    repos.price.put_rows("US-W", "yahoo", [
        {"date": "2019-12-31", "close": 25.0, "currency": "USD"}])
    repos.corp_action.put("US-W", "2020-08-31", "split", 4.0, None,
                          None, "yahoo")
    make_snapshot_builder(repos, "2019-12-31").build("US-W", "i-W",
                                                     "2019-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-W")
    cap = next(m for m in repos.snapshot.get_measures(sid)
               if m[3] == "market_cap")
    roles = [r[0] for r in conn.execute(
        "SELECT role FROM measure_lineage WHERE measure_id=?",
        (cap[0],)).fetchall()]
    return float(cap[4]), " ".join(roles)


def test_cap_divides_the_count_when_filing_crosses_the_split(tmp_path):
    cap, roles = _base(tmp_path, filed="2020-09-15")
    # фактическая цена 25 × 4 (P4) = 100; счётчик 100 подан 2020-09-15 —
    # после сплита 2020-08-31, о периоде 2019-12-31 — делится на 4:
    # 100 × 25 = 2500
    assert cap == pytest.approx(25.0 * 4 * 100 / 4), cap
    assert "divided by split factor 4" in roles, roles


def test_no_filing_date_leaves_the_count_and_names_it(tmp_path):
    cap, roles = _base(tmp_path, filed=None)
    assert cap == pytest.approx(25.0 * 4 * 100), cap
    assert "basis unknown" in roles, roles
