"""Тесты И11-И12: сборка снапшота (два прохода, excluded_stale, три diff)
и экспорт из готовых величин. Данные синтетические."""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import uuid

import pytest

from rusterm.core.export import snapshot_to_csv, snapshot_to_json
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    CoverageRepo,
    Instrument,
    InstrumentRepo,
    Issuer,
    PeerSetRepo,
    SnapshotRepo,
)


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    instruments = InstrumentRepo(conn)
    instruments.upsert_issuer(Issuer("i1", "Golden Corp (synthetic)", "US",
                                     None, None, "us_gaap", "USD"))
    instruments.upsert_instrument(Instrument("ins1", "i1", None, "common",
                                             "active", None))
    return tmpdir, conn


def _fact(conn, concept, value, basis="as_reported", fact_id=None,
          ingested_at=0):
    fid = fact_id or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, listing_id, concept,
          period_start, period_end, period_type, value, unit, currency,
          basis, origin, source_ref, locator, parser_version,
          status, superseded_by, ingested_at,
          canonical_concept, concept_map_version)
          VALUES (?, 'i1', NULL, ?, '2024-01-01', '2024-12-31', 'duration',
                  ?, 'USD', NULL, ?, 'extracted', 'src-x', '{}',
                  'synthetic.v1', 'ok', NULL, ?, ?, 'us-gaap.v1')""",
        (fid, concept, value, basis, ingested_at, concept))
    return fid


def test_snapshot_two_passes_and_thresholds():
    tmpdir, conn = _setup()
    try:
        _fact(conn, "net_income", "400")
        _fact(conn, "revenue", "2000")
        _fact(conn, "operating_income", "700")

        peers = PeerSetRepo(conn)
        peers.create_peer_set("ps1", "industry", "tankers")
        peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                          "manual", "v1", True, None, None)

        builder = SnapshotBuilder(SnapshotRepo(conn), peers,
                                  CoverageRepo(conn))

        # 4 пира — порог 5 не пройден: перцентилей нет, блок missing
        peer4 = [(f"p{n}", str(uuid.uuid4()), "net_margin", 0.1 + n / 100, True)
                 for n in range(4)]
        r1 = builder.build("ins1", "i1", "2024-12-31",
                           peer_set_version="psv1", peer_measures=peer4,
                           peer_members_previous=[p[0] for p in peer4],
                           peer_members_current=[p[0] for p in peer4])
        assert r1.measures >= 1
        assert r1.percentiles == 0
        blocks = conn.execute(
            "SELECT status, reason FROM snapshot_block WHERE snapshot_id=?",
            (r1.snapshot_id,)).fetchall()
        assert any(b[0] == "missing" and "threshold" in b[1] for b in blocks)

        # 5 пиров — перцентиль net_margin пишется с peer_set_version
        peer5 = [(f"q{n}", str(uuid.uuid4()), "net_margin", 0.1 + n / 100, True)
                 for n in range(5)]
        r2 = builder.build("ins1", "i1", "2024-12-31",
                           peer_set_version="psv1", peer_measures=peer5,
                           peer_members_previous=[p[0] for p in peer5],
                           peer_members_current=[p[0] for p in peer5])
        assert r2.version == 2
        assert r2.percentiles == 1
        pct = conn.execute(
            """SELECT value, peer_set_version FROM measure
               WHERE snapshot_id=? AND concept='percentile'""",
            (r2.snapshot_id,)).fetchone()
        assert pct is not None and pct[1] == "psv1"
        # собственная маржа 400/2000 = 0.2; пиры 0.1..0.14 — все ниже
        assert float(pct[0]) == pytest.approx(1.0)
        conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir)


def test_export_carries_concept_map_version():
    """TASK-11 X4: экспорт несёт версию карты, породившей числа."""
    from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
    tmpdir, conn = _setup()
    try:
        _fact(conn, "net_income", "400")
        _fact(conn, "revenue", "2000")
        builder = SnapshotBuilder(SnapshotRepo(conn), PeerSetRepo(conn),
                                  CoverageRepo(conn))
        built = builder.build("ins1", "i1", "2024-12-31")
        repo = SnapshotRepo(conn)
        snapshot = repo.get_snapshot(built.snapshot_id)
        measures = repo.get_measures(built.snapshot_id)

        js = json.loads(snapshot_to_json(snapshot, measures))
        assert js["concept_map_version"] == CONCEPT_MAP_VERSION

        csv_lines = snapshot_to_csv(measures).splitlines()
        # первая строка CSV — версия карты, породившей числа (X4)
        assert csv_lines[0] == f"concept_map_version,{CONCEPT_MAP_VERSION}"
    finally:
        shutil.rmtree(tmpdir)


def test_snapshot_excludes_stale_peers_with_mark():
    tmpdir, conn = _setup()
    try:
        _fact(conn, "net_income", "400")
        _fact(conn, "revenue", "2000")
        peers = PeerSetRepo(conn)
        peers.create_peer_set("ps1", "industry", "tankers")
        peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                          "manual", "v1", True, None, None)

        # 6 пиров, из них один без свежих данных (fresh=False)
        peer6 = [(f"p{n}", str(uuid.uuid4()), "net_margin", 0.05 + n / 100, True)
                 for n in range(5)]
        peer6.append(("p-stale", str(uuid.uuid4()), "net_margin", 0.99, False))

        builder = SnapshotBuilder(SnapshotRepo(conn), peers,
                                  CoverageRepo(conn))
        result = builder.build("ins1", "i1", "2024-12-31",
                               peer_set_version="psv1", peer_measures=peer6)
        assert result.excluded_stale == ["p-stale"]
        row = conn.execute(
            """SELECT excluded_stale FROM peer_set_member
               WHERE peer_set_version_id='psv1' AND instrument_id='p-stale'"""
        ).fetchone()
        assert row is not None and row[0] == 1
        # перцентиль считается по пяти свежим, не по устаревшему значению
        assert result.percentiles == 1
        conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir)


def test_snapshot_three_diffs_are_separate():
    tmpdir, conn = _setup()
    try:
        fid_rev = _fact(conn, "revenue", "2000")
        _fact(conn, "net_income", "400")
        peers = PeerSetRepo(conn)
        builder = SnapshotBuilder(SnapshotRepo(conn), peers,
                                  CoverageRepo(conn))

        v1 = builder.build("ins1", "i1", "2024-12-31")
        assert v1.diff.metric_changes == []

        # ревизия: restated-факт по периоду, где есть as_reported
        _fact(conn, "revenue", "1900", basis="restated")
        # изменение метрики: новый факт net_income поступил позже —
        # он вытесняет старый в расчёте, сам старый не изменяется
        _fact(conn, "net_income", "440", ingested_at=2)

        v2 = builder.build("ins1", "i1", "2024-12-31",
                           peer_members_previous=["a", "b"],
                           peer_members_current=["b", "c"])
        # 1) изменение метрик
        concepts = [c for c, _o, _n in v2.diff.metric_changes]
        assert "net_margin" in concepts
        # 2) эффект пересостава — отдельным списком
        assert v2.diff.peer_set_changes == [(["c"], ["a"])]
        # 3) появившаяся ревизия
        assert ("revenue", "2024-12-31") in v2.diff.revisions
        conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir)


def test_export_matches_snapshot_without_recompute():
    tmpdir, conn = _setup()
    try:
        _fact(conn, "net_income", "400")
        _fact(conn, "revenue", "2000")
        builder = SnapshotBuilder(SnapshotRepo(conn), PeerSetRepo(conn),
                                  CoverageRepo(conn))
        built = builder.build("ins1", "i1", "2024-12-31")

        snapshot = SnapshotRepo(conn).get_snapshot(built.snapshot_id)
        measures = SnapshotRepo(conn).get_measures(built.snapshot_id)
        assert snapshot["instrument_id"] == "ins1"

        # значения экспорта совпадают с содержимым снапшота
        payload = json.loads(snapshot_to_json(snapshot, measures))
        exported = {m["concept"]: m for m in payload["measures"]}
        stored = {m[3]: m for m in measures}
        assert set(exported) == set(stored)
        assert exported["net_margin"]["value"] == stored["net_margin"][4]

        # CSV: те же строки, null-причина отдельной колонкой
        csv_text = snapshot_to_csv(measures)
        header = csv_text.splitlines()[1].split(",")
        assert "null_reason" in header
        # строка версии карты — не мера: данные идут со второй строки
        rows = [line.split(",") for line in csv_text.splitlines()[2:]]
        assert len(rows) == len(measures)
        # каждая мера с NULL значением обязана иметь причину
        for m in measures:
            if m[4] is None:
                assert m[10], f"{m[3]}: NULL без причины"
        conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir)
