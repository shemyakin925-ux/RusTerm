"""ТЗ-130 K2: страж нулевых вложений не должен пугаться НЕтекущих статей.

Дефект (REPORT-130 K1): средняя ветка SQL `LIKE '%MarketableSecurities%
Current%'` без исключения Noncurrent, а LIKE в SQLite не различает регистр
— «Noncurrent» кончается «current», и Alcoa с 2024 (строка «Marketable
securities» в необоротных) выгоняла правило нулевых вложений: ev,
net_debt, invested_capital у AA 2024–2026 отказывали missing_data.
"""
from __future__ import annotations

import sqlite3

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Issuer, RepoRegistry,
                                 SnapshotRepo)


def _repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "guard")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AA", "Alcoa", "US", None, None, "us-gaap", "USD"))
    return repos


def _fact(repos, tag, day="2024-12-31"):
    repos.fact.insert_fact(
        f"f-{tag}", "i-AA", None, f"us-gaap:{tag}", day, day,
        "instant", "1000000", "USD", "USD", "as_reported", "extracted",
        "sha", {}, "t", "ok")


def test_noncurrent_marketable_securities_do_not_block_the_zero(tmp_path):
    repos = _repos(tmp_path)
    _fact(repos, "MarketableSecuritiesNoncurrent")
    _fact(repos, "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent")
    _fact(repos, "InvestmentsNoncurrent")
    guard = SnapshotRepo(repos.conn)
    assert guard.unmapped_current_investments("i-AA", "2024-12-31") == []


def test_current_lines_still_block_the_zero(tmp_path):
    repos = _repos(tmp_path)
    _fact(repos, "MarketableSecuritiesCurrent")
    _fact(repos, "AvailableForSaleSecuritiesDebtSecuritiesCurrent")
    _fact(repos, "InvestmentsCurrent")
    guard = SnapshotRepo(repos.conn)
    tags = guard.unmapped_current_investments("i-AA", "2024-12-31")
    assert "us-gaap:MarketableSecuritiesCurrent" in tags
    assert ("us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent"
            in tags)
    assert "us-gaap:InvestmentsCurrent" in tags


def test_generic_noncurrent_tag_stays_invisible(tmp_path):
    """us-gaap:Investments без Current вообще не статья вложений-текущих:
    у Alcoa это доли в аффилированных компаниях (необоротные)."""
    repos = _repos(tmp_path)
    _fact(repos, "Investments")
    guard = SnapshotRepo(repos.conn)
    assert guard.unmapped_current_investments("i-AA", "2024-12-31") == []
