"""Починка basis уже сохранённых фактов (координатор, 24.09.2026).

Регрессия ТЗ-78 Y2 записала у скачанных companyfacts почти все
финансовые факты как restated. Исправленный разборщик уже скачанное не
лечит: сбор пропускает ответ, который лежит в хранилище. rusterm
reparse заново разбирает сохранённые ответы и выравнивает только basis.
На копии базы пользователя: 102 545 фактов вернулись в as_reported, мер
со значением в последних снапшотах 334 -> 592.
"""
from __future__ import annotations

import sqlite3
import uuid

from rusterm.core.reparse import rebasis_companyfacts
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RawRepo, RepoRegistry,
                                 persist_ingestion_results)

from tests.test_basis_cover_date import _payload


def _base(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-ORCL", "ORACLE CORP", "US", "1341439", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-ORCL", "i-ORCL", None, "common", "active", None))
    payload = _payload(with_cover=True)
    obj = RawRepo(paths, conn).put(
        payload, provider="edgar", block="fundamentals",
        url="https://data.sec.gov/api/xbrl/companyfacts/CIK0001341439.json")
    facts = []
    for fact in CompanyFactsParser().parse(
            payload, {"issuer_id": "i-ORCL", "source_ref": obj.sha256}).facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        facts.append(fact)
    persist_ingestion_results(conn, facts, [])
    return repos, conn


def _snapshot_of_facts(conn):
    return {(r["concept"], r["period_end"]): (r["basis"], r["value"])
            for r in conn.execute(
                "SELECT concept, period_end, basis, value FROM fact")}


def _break_like_the_regression(conn):
    """Состояние базы после регрессии: всё restated."""
    conn.execute("UPDATE fact SET basis = 'restated'")


def test_reparse_restores_as_reported(tmp_path):
    repos, conn = _base(tmp_path)
    healthy = _snapshot_of_facts(conn)
    _break_like_the_regression(conn)
    res = rebasis_companyfacts(repos)
    assert res.objects == 1
    assert res.to_as_reported > 0 and res.to_restated == 0
    assert _snapshot_of_facts(conn) == healthy


def test_reparse_changes_only_basis(tmp_path):
    repos, conn = _base(tmp_path)
    values_before = {k: v[1] for k, v in _snapshot_of_facts(conn).items()}
    _break_like_the_regression(conn)
    rebasis_companyfacts(repos)
    values_after = {k: v[1] for k, v in _snapshot_of_facts(conn).items()}
    assert values_after == values_before


def test_reparse_is_idempotent(tmp_path):
    repos, conn = _base(tmp_path)
    _break_like_the_regression(conn)
    rebasis_companyfacts(repos)
    second = rebasis_companyfacts(repos)
    assert second.changed == 0


def test_healthy_base_is_left_alone(tmp_path):
    repos, conn = _base(tmp_path)
    before = _snapshot_of_facts(conn)
    res = rebasis_companyfacts(repos)
    assert res.changed == 0
    assert _snapshot_of_facts(conn) == before
