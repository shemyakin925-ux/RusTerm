"""Тесты процесса 5 — верификация факта (TASK-7 T8, processes.md §263-284).

Извлечённый факт не удаляется: он остаётся и получает superseded_by.
Пятый подтверждённый мисматч по (провайдер, концепт) переводит парсер
в деградировавшие, четвёртый — нет. Порог детерминирован: 5 за 30 дней.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import uuid

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.core.verification import (
    DEGRADE_THRESHOLD,
    VerificationService,
)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
)


def _registry():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "N", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "ins1", "i1", None, "common", "active", None))
    return tmpdir, conn, repos


def _fact(repos, sha, concept, value, period="2024-12-31"):
    fact_id = str(uuid.uuid4())
    repos.fact.insert_fact(
        fact_id=fact_id,
        issuer_id="i1", listing_id=None,
        concept=concept, period_start=period.replace("12-31", "01-01"),
        period_end=period, period_type="duration",
        value=value, unit="USD", currency=None,
        basis="as_reported", origin="extracted",
        source_ref=sha, locator={"kind": "xbrl", "doc_sha256": sha,
                                 "fact_id": "f-" + fact_id[:6],
                                 "concept": concept},
        parser_version="synthetic.v1",
    )
    return fact_id


def _seed(repos):
    """Сырьё + извлечённые факты (выручка ошибочна) + снапшот с мерой."""
    obj = repos.raw.put(b'{"synthetic": "report"}', provider="synthetic",
                        block="fundamentals")
    revenue = _fact(repos, obj.sha256, "revenue", "1000")
    net_income = _fact(repos, obj.sha256, "net_income", "100")
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    builder.build("ins1", "i1", "2024-12-31")
    return obj.sha256, revenue, net_income, builder


def _measure_value(repos, snapshot_id, concept):
    for m in repos.snapshot.get_measures(snapshot_id):
        if m[3] == concept:
            return m[4]
    return None


def test_ground_truth_keeps_extracted_fact_and_sets_superseded_by():
    tmpdir, conn, repos = _registry()
    try:
        sha, revenue, net_income, builder = _seed(repos)
        service = VerificationService(
            repos.fact, repos.verification, repos.snapshot,
            repos.instrument, os.path.join(tmpdir, "golden_proposals.jsonl"))
        correct = service.store_ground_truth(
            revenue, "2000", note="проверено по отчёту")

        wrong_row = repos.fact.get_fact(revenue)
        assert wrong_row is not None, "извлечённый факт удалён — запрещено"
        assert wrong_row["superseded_by"] == correct
        manual_row = repos.fact.get_fact(correct)
        assert manual_row["origin"] == "manual"
        assert manual_row["value"] == "2000"
        assert manual_row["source_ref"] == sha, "ссылка на документ потеряна"
        rows = repos.verification.mismatch_counts(0.0)
        assert rows == [("synthetic", "revenue", 1)]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_recompute_changes_derived_measure():
    tmpdir, conn, repos = _registry()
    try:
        sha, revenue, net_income, builder = _seed(repos)
        service = VerificationService(
            repos.fact, repos.verification, repos.snapshot,
            repos.instrument, os.path.join(tmpdir, "golden_proposals.jsonl"))
        service.store_ground_truth(revenue, "2000")

        snap_v1 = repos.snapshot.latest_snapshot_id("ins1")
        before = _measure_value(repos, snap_v1, "net_margin")
        assert before == repr(100.0 / 1000.0)

        results = service.recompute(revenue, builder)
        assert results, "recompute не пересобрал ни одного снапшота"
        snap_v2 = repos.snapshot.latest_snapshot_id("ins1")
        assert snap_v2 != snap_v1
        after = _measure_value(repos, snap_v2, "net_margin")
        assert after == repr(100.0 / 2000.0)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_fifth_mismatch_degrades_parser_fourth_does_not():
    tmpdir, conn, repos = _registry()
    try:
        sha, _, _, builder = _seed(repos)
        service = VerificationService(
            repos.fact, repos.verification, repos.snapshot,
            repos.instrument, os.path.join(tmpdir, "golden_proposals.jsonl"))
        for i in range(DEGRADE_THRESHOLD - 1):
            fid = _fact(repos, sha, "revenue", str(100 + i))
            service.store_ground_truth(fid, "999")
        assert service.degraded_parsers() == [], "4 расхождения — не порог"

        fid = _fact(repos, sha, "revenue", "100+x")
        service.store_ground_truth(fid, "999")
        degraded = service.degraded_parsers()
        assert degraded == [("synthetic", "revenue", DEGRADE_THRESHOLD)]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_degraded_parser_surfaces_through_coverage_reason():
    tmpdir, conn, repos = _registry()
    try:
        sha, _, _, builder = _seed(repos)
        service = VerificationService(
            repos.fact, repos.verification, repos.snapshot,
            repos.instrument, os.path.join(tmpdir, "golden_proposals.jsonl"))
        for i in range(DEGRADE_THRESHOLD):
            fid = _fact(repos, sha, "revenue", str(200 + i))
            service.store_ground_truth(fid, "999")
        reasons = service.surface_coverage("ins1", repos.coverage)
        assert reasons, "деградация не всплыла в покрытии"
        cov = {r["block"]: r for r in repos.coverage.for_instrument("ins1")}
        assert cov["fundamentals"]["status"] == "error"
        assert "parser_degraded:synthetic:revenue" in cov["fundamentals"]["reason"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_propose_golden_appends_pair_and_marks_verification():
    tmpdir, conn, repos = _registry()
    try:
        sha, revenue, _, _ = _seed(repos)
        golden_path = os.path.join(tmpdir, "golden_proposals.jsonl")
        service = VerificationService(
            repos.fact, repos.verification, repos.snapshot,
            repos.instrument, golden_path)
        service.store_ground_truth(revenue, "2000")
        verification_id = conn.execute(
            "SELECT verification_id FROM verification").fetchone()[0]

        proposal = service.propose_golden(verification_id)
        assert proposal["raw_sha256"] == sha
        assert proposal["expected"] == "2000"
        with open(golden_path, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh]
        assert len(lines) == 1 and lines[0]["expected"] == "2000"
        promoted = conn.execute(
            "SELECT promoted_to_golden FROM verification"
            " WHERE verification_id=?",
            (verification_id,)).fetchone()[0]
        assert promoted == 1
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
