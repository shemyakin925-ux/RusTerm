"""ТЗ-143 F1: операционная прибыль без своей строки (PFE, XOM).

PFE и XOM не подают OperatingIncomeLoss — вся цепочка мер честно
отказывала. Правило одной функции ядра (core.operating): pretax +
interest_expense − interest_income (не подан — ноль); свой тег на
период всегда сильнее; роль входа в lineage называет вывод. Проверяются
оба лица: снапшот (меры и родословная) и карточка (годы без тега).
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.operating import DERIVED_ROLE, derive_operating_income
from rusterm.core.snapshot import make_snapshot_builder
from rusterm.desktop import card
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)


def _issuer(tmp_path):
    paths = AppPaths.from_root(tmp_path / "oi")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-OI", "No OI Line", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-OI", "i-OI", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-OI", "US-OI", "XNAS", "USD", 1, None, None))
    return repos


def _fact(repos, concept, value, start, end, kind="duration"):
    from rusterm.pipeline import apply_concept_map
    fact = {"concept": f"us-gaap:{concept}"}
    apply_concept_map(fact)
    repos.fact.insert_fact(
        f"f-{concept}-{end}", "i-OI", None, f"us-gaap:{concept}",
        start, end, kind, value, "USD", "USD", "as_reported", "extracted",
        "sha", {}, "t", "ok",
        canonical_concept=fact.get("canonical_concept"),
        concept_map_version=fact.get("concept_map_version"))


def _no_oi_block(repos):
    """pretax 800, расходы 120, доходы 20, выручка 1000, d_and_a 50 —
    вывод: 800 + 120 − 20 = 900; без вывода ebitda/margins отказывали."""
    _fact(repos,
          "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
          "800", "2024-01-01", "2024-12-31")
    _fact(repos, "InterestExpense", "120",
          "2024-01-01", "2024-12-31")
    _fact(repos, "InvestmentIncomeInterest", "20",
          "2024-01-01", "2024-12-31")
    _fact(repos, "RevenueFromContractWithCustomerExcludingAssessedTax",
          "1000", "2024-01-01", "2024-12-31")
    _fact(repos, "DepreciationDepletionAndAmortization",
          "50", "2024-01-01", "2024-12-31")


def test_snapshot_derives_operating_income_when_line_absent(tmp_path):
    repos = _issuer(tmp_path)
    _no_oi_block(repos)
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-OI", "i-OI", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-OI")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    # цепочка оживает: маржа 900/1000, ebitda 900 + 50
    assert float(rows["operating_margin"]["value"]) == \
        pytest.approx(0.9), rows["operating_margin"]["null_reason"]
    assert float(rows["ebitda"]["value"]) == pytest.approx(950), \
        rows["ebitda"]["null_reason"]
    # роль входа называет вывод
    roles = " | ".join(repos.snapshot.lineage_roles(
        rows["operating_margin"]["measure_id"]))
    assert "выведено: pretax_income + interest_expense" in roles, roles


def test_own_tag_wins_over_the_derivation(tmp_path):
    repos = _issuer(tmp_path)
    _no_oi_block(repos)
    _fact(repos, "OperatingIncomeLoss", "700",
          "2024-01-01", "2024-12-31")
    builder = make_snapshot_builder(repos, "2025-06-30")
    builder.build("US-OI", "i-OI", "2025-06-30")
    sid = repos.snapshot.latest_snapshot_id("US-OI")
    rows = {m["concept"]: m for m in repos.snapshot.get_measures(sid)}
    # тег 700 сильнее вывода 900 — и роли не называют вывод
    assert float(rows["operating_margin"]["value"]) == pytest.approx(0.7)
    roles = " | ".join(repos.snapshot.lineage_roles(
        rows["operating_margin"]["measure_id"]))
    assert "выведено" not in roles, roles


def test_derivation_needs_the_expense(tmp_path):
    """Расходы не поданы — вывода нет (None), мера честно отказывает."""
    assert derive_operating_income(800.0, None, 20.0) is None
    assert derive_operating_income(None, 120.0) is None
    assert derive_operating_income(800.0, 120.0) == pytest.approx(920.0)
    assert derive_operating_income(800.0, 120.0, None) == \
        pytest.approx(920.0)


def test_card_fills_only_years_without_the_tag(tmp_path):
    """Карточка: год без тега выводится, год с тегом остаётся тегом."""
    repos = _issuer(tmp_path)
    _no_oi_block(repos)
    _fact(repos, "OperatingIncomeLoss", "700",
          "2023-01-01", "2023-12-31")
    _fact(repos,
          "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
          "750", "2023-01-01", "2023-12-31")
    _fact(repos, "InterestExpense", "100",
          "2023-01-01", "2023-12-31")
    series = card.statement_series(repos, "i-OI", "operating_income",
                                   "flow")
    # 2024: вывод 800 + 120 − 20 = 900; 2023: свой тег 700
    assert series["2024"][0] == pytest.approx(900.0), series
    assert series["2023"][0] == pytest.approx(700.0), series


def test_derived_role_text_names_the_rule():
    assert "pretax_income" in DERIVED_ROLE
    assert "interest_expense" in DERIVED_ROLE
    assert "interest_income" in DERIVED_ROLE
