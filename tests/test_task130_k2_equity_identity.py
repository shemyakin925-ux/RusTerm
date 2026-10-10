"""ТЗ-130 K2: капитал материнской компании из тождества баланса.

T и AA подают одну колонку «Итого капитал» с НКД
(StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest)
и строку NCI — прямого тега собственного капитала у них нет. Тождество
total_equity = incl_nci − minority_interest точное (это определение
колонки), и это НЕ подстановка ТЗ-56 Z1: та брала incl_nci ЦЕЛИКОМ.
IFRS-эмитентам (ТЗ-56 Z2, Ambev) отказ сохранён.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import make_snapshot_builder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)


def _issuer(tmp_path, taxonomy="us-gaap"):
    paths = AppPaths.from_root(tmp_path / "id")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-ID", "Ident", "US", None, None, taxonomy, "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-ID", "i-ID", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-ID", "US-ID", "XNAS", "USD", 1, None, None))
    return repos


def _fact(repos, taxonomy, concept, value, start, end, kind):
    from rusterm.pipeline import apply_concept_map
    fact = {"concept": f"{taxonomy}:{concept}"}
    apply_concept_map(fact)
    repos.fact.insert_fact(
        f"f-{concept}-{end}", "i-ID", None, f"{taxonomy}:{concept}",
        start, end, kind, value, "USD", "USD", "as_reported", "extracted",
        "sha", {}, "t", "ok",
        canonical_concept=fact.get("canonical_concept"),
        concept_map_version=fact.get("concept_map_version"))


def _equity_block(repos, taxonomy):
    """incl_nci 1000/900, NCI 100/90, прибыль 200 — roe = 200/900."""
    _fact(repos, taxonomy,
          "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
          "1000", "2024-12-31", "2024-12-31", "instant")
    _fact(repos, taxonomy,
          "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
          "900", "2023-12-31", "2023-12-31", "instant")
    _fact(repos, taxonomy, "MinorityInterest",
          "100", "2024-12-31", "2024-12-31", "instant")
    _fact(repos, taxonomy, "MinorityInterest",
          "90", "2023-12-31", "2023-12-31", "instant")
    _fact(repos, taxonomy, "NetIncomeLoss",
          "200", "2024-01-01", "2024-12-31", "duration")
    _fact(repos, taxonomy, "RevenueFromContractWithCustomerExcludingAssessedTax",
          "1200", "2024-01-01", "2024-12-31", "duration")


def test_roe_computes_from_the_balance_identity(tmp_path):
    repos = _issuer(tmp_path)
    _equity_block(repos, "us-gaap")
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-ID", "i-ID", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-ID")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    roe = rows["roe"]
    assert roe["value"] is not None, roe["null_reason"]
    # roe — на среднем капитале (формула словаря): (810 + 900) / 2
    assert float(roe["value"]) == pytest.approx(200 / 855)
    roles = " | ".join(repos.snapshot.lineage_roles(roe["measure_id"]))
    assert "тождество" in roles, roles


def test_invested_capital_uses_identity_and_names_it(tmp_path):
    repos = _issuer(tmp_path)
    _equity_block(repos, "us-gaap")
    _fact(repos, "us-gaap", "LongTermDebt",
          "500", "2024-12-31", "2024-12-31", "instant")
    _fact(repos, "us-gaap", "CashAndCashEquivalentsAtCarryingValue",
          "100", "2024-12-31", "2024-12-31", "instant")
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-ID", "i-ID", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-ID")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    ic = rows["invested_capital"]
    # 900 + 100 (NCI) + 500 − 100 = 1400: NCI прибавлен ОДИН раз
    assert float(ic["value"]) == pytest.approx(1400), ic["null_reason"]
    roles = " | ".join(repos.snapshot.lineage_roles(ic["measure_id"]))
    assert "incl_nci − NCI" in roles, roles


def test_direct_tag_wins_over_the_identity(tmp_path):
    repos = _issuer(tmp_path)
    _equity_block(repos, "us-gaap")
    _fact(repos, "us-gaap", "StockholdersEquity",
          "800", "2024-12-31", "2024-12-31", "instant")
    _fact(repos, "us-gaap", "StockholdersEquity",
          "700", "2023-12-31", "2023-12-31", "instant")
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-ID", "i-ID", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-ID")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    # прямой тег побеждает: (700 + 800) / 2, тождество не применяется
    assert float(rows["roe"]["value"]) == pytest.approx(200 / 750)


def test_ifrs_keeps_the_refusal_of_task56(tmp_path):
    repos = _issuer(tmp_path, taxonomy="ifrs-full")
    _equity_block(repos, "ifrs-full")
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-ID", "i-ID", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-ID")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    assert rows["roe"]["value"] is None
    assert "total_equity" in rows["roe"]["null_reason"]
