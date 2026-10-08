"""ТЗ-139 B2: тег-преемник дивиденда на акцию (KO).

Payload-доказательство — замер на копии базы 08.10 (REPORT-139): KO подаёт
`CommonStockDividendsPerShareDeclared` только до 2018-09-28, дальше в XBRL
живёт `CommonStockDividendsPerShareCashPaid` (2025 год = 2,04 USD, 2024 =
1,94), и строка «Дивиденд на акцию» карточки пуста весь период. Тег-преемник
в карте рангом НИЖЕ объявленного: подающий оба (BAC) получает прежнее.
"""
from __future__ import annotations

import pytest

from rusterm.desktop import card
from rusterm.normalize.concepts import canonical_for, priority_rank
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)


def test_paid_per_share_is_the_ranked_successor_of_declared():
    assert canonical_for("CommonStockDividendsPerShareCashPaid") == "dps"
    order = [priority_rank("dps", t) for t in (
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid")]
    assert order == sorted(order), order
    assert len(set(order)) == len(order), order


def _repos(tmp_path, issuer_id="i-KO", instrument_id="US-KO"):
    paths = AppPaths.from_root(tmp_path / "dps-base")
    ensure_app_dir(paths)
    import sqlite3
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, "Fixture Card Co", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-KO", instrument_id, "XNYS", "USD", 1, None, None))
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts/KO")
    return repos, raw.sha256, issuer_id, instrument_id


def _dps_fact(repos, sha, issuer_id, tag, value):
    repos.fact.insert_fact(
        f"f-{tag.split(':')[-1]}", issuer_id, None, tag,
        "2025-01-01", "2025-12-31", "duration", str(value),
        "USD/shares", "USD", "as_reported", "extracted", sha,
        {"endpoint": "companyfacts", "kind": "10-K"}, "t",
        canonical_concept="dps")


def _dps_of(repos, issuer_id):
    """Клетка года из той же двери, что строка карточки (card.py)."""
    series = card.statement_series(repos, issuer_id, "dps", "flow")
    return None if "2025" not in series else float(series["2025"][0])


def test_declared_wins_when_the_issuer_files_both(tmp_path):
    repos, sha, issuer_id, instrument_id = _repos(tmp_path)
    _dps_fact(repos, sha, issuer_id,
              "us-gaap:CommonStockDividendsPerShareDeclared", 1.94)
    _dps_fact(repos, sha, issuer_id,
              "us-gaap:CommonStockDividendsPerShareCashPaid", 2.04)
    assert _dps_of(repos, issuer_id) == pytest.approx(1.94)


def test_paid_fills_the_row_when_declared_stopped(tmp_path):
    repos, sha, issuer_id, instrument_id = _repos(tmp_path)
    _dps_fact(repos, sha, issuer_id,
              "us-gaap:CommonStockDividendsPerShareCashPaid", 2.04)
    assert _dps_of(repos, issuer_id) == pytest.approx(2.04)
