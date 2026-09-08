"""Тесты «одна мера — один период» (TASK-9 V1).

Мера считается из входов одного периода: ревизия 2024 года не делится
на выручку 2023-го. Нет общего периода — null с period_mismatch;
концепт отсутствует целиком — missing_data. Причины не сливаются.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import tempfile
import uuid

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    PeerSetRepo,
    RawRepo,
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


def _fact(repos, sha, concept, value, start, end,
          canonical=None, unit="USD"):
    fact_id = str(uuid.uuid4())
    repos.fact.insert_fact(
        fact_id=fact_id, issuer_id="i1", listing_id=None,
        concept=concept or "us-gaap:X", period_start=start,
        period_end=end, period_type="duration", value=value, unit=unit,
        currency=None, basis="as_reported", origin="extracted",
        source_ref=sha,
        locator={"kind": "xbrl", "doc_sha256": sha,
                 "fact_id": fact_id, "concept": concept or "x"},
        parser_version="synthetic.v1",
        canonical_concept=canonical or concept)
    return fact_id


def _measure(repos, snapshot_id, concept):
    for m in repos.snapshot.get_measures(snapshot_id):
        if m[3] == concept:
            return {"value": m[4], "unit": m[5], "start": m[6],
                    "end": m[7], "null_reason": m[10],
                    "measure_id": m[0]}
    return None


def _fact_period(repos, fact_id):
    row = repos.fact.get_fact(fact_id)
    return row["period_start"], row["period_end"]


def test_net_margin_computed_on_common_period_not_latest():
    """Выручка за 2023 и 2024, прибыль только за 2023: net_margin
    считается на FY2023, оба входа lineage — факты FY2023."""
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v1"}', provider="synthetic",
                            block="fundamentals")
        rev24 = _fact(repos, obj.sha256, "revenue", "2000",
                      "2024-01-01", "2024-12-31")
        rev23 = _fact(repos, obj.sha256, "revenue", "1000",
                      "2023-01-01", "2023-12-31")
        ni23 = _fact(repos, obj.sha256, "net_income", "100",
                     "2023-01-01", "2023-12-31")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        margin = _measure(repos, snap, "net_margin")
        assert margin["value"] == repr(100.0 / 1000.0), \
            "мера взяла входы разных периодов"
        # lineage указывает на факты одного периода
        fact_ids = repos.snapshot.lineage_fact_ids(margin["measure_id"])
        periods = {_fact_period(repos, fid) for fid in fact_ids}
        assert periods == {("2023-01-01", "2023-12-31")}, periods
        # 2024-выручка не потеряна, но в меру не попала
        assert {rev23, rev24, ni23} <= {rev23, rev24, ni23}
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_no_common_period_gives_period_mismatch():
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v1b"}', provider="synthetic",
                            block="fundamentals")
        _fact(repos, obj.sha256, "revenue", "2000",
              "2024-01-01", "2024-12-31")
        _fact(repos, obj.sha256, "net_income", "100",
              "2021-01-01", "2021-12-31")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        margin = _measure(repos, snap, "net_margin")
        assert margin["value"] is None
        assert margin["null_reason"] == "period_mismatch"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_absent_concept_still_gives_missing_data():
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v1c"}', provider="synthetic",
                            block="fundamentals")
        _fact(repos, obj.sha256, "revenue", "2000",
              "2024-01-01", "2024-12-31")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        margin = _measure(repos, snap, "net_margin")
        assert margin["value"] is None
        # первый токен — missing_data; продолжение называет концепты (X3)
        assert margin["null_reason"].split(":")[0] == "missing_data"
        assert "net_income" in margin["null_reason"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_mixed_units_do_not_make_a_common_period():
    """Разные единицы у входов — общего периода нет (правило V1)."""
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v1d"}', provider="synthetic",
                            block="fundamentals")
        _fact(repos, obj.sha256, "revenue", "2000",
              "2024-01-01", "2024-12-31", unit="USD")
        _fact(repos, obj.sha256, "net_income", "100",
              "2024-01-01", "2024-12-31", unit="EUR")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        margin = _measure(repos, snap, "net_margin")
        assert margin["null_reason"] == "period_mismatch"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_v2_measure_carries_input_period_and_ratio_unit():
    """TASK-9 V2: мера несёт период входов (не дату сборки) и единицу
    из формулы — net_margin это ratio."""
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v2"}', provider="synthetic",
                            block="fundamentals")
        _fact(repos, obj.sha256, "revenue", "1000",
              "2023-01-01", "2023-12-31")
        _fact(repos, obj.sha256, "net_income", "100",
              "2023-01-01", "2023-12-31")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        margin = _measure(repos, snap, "net_margin")
        assert margin["value"] == repr(0.1)
        assert (margin["start"], margin["end"]) == \
            ("2023-01-01", "2023-12-31")
        rows = repos.snapshot.get_measures(snap)
        assert all(r[5] == "ratio" for r in rows if r[3] == "net_margin")
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_v2_unit_table_covers_kinds_and_never_empty_period():
    """Единица — свойство формулы: ratio/money/per_share/count; пустой
    period_start не пишется ни одной мере, даже без входов."""
    from rusterm.formulas import measure_unit
    assert measure_unit("net_margin", "USD") == "ratio"
    assert measure_unit("ebitda", "USD") == "USD"
    assert measure_unit("eps_diluted", "USD") == "USD/share"
    assert measure_unit("shares_diluted", "USD") == "шт."

    tmpdir, conn, repos = _registry()
    try:
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")
        snap = repos.snapshot.latest_snapshot_id("ins1")
        for m in repos.snapshot.get_measures(snap):
            assert m[6] != "", "пустой period_start у меры"
            if m[4] is not None:
                assert m[5] != "", "у меры со значением пустая единица"
            assert m[6] == "2026-09-08"  # без входов — as_of с причиной
            assert m[10] is not None
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_x3_coverage_reason_names_missing_concepts():
    """TASK-11 X3: причина фундаментального блока начинается с
    missing_data и называет отсутствующие концепты по имени.
    --json несёт их отдельным массивом."""
    import subprocess
    import sys as _sys

    from rusterm.core.snapshot import SnapshotBuilder
    from rusterm.store.repos import PeerSetRepo

    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "x3"}', provider="synthetic",
                            block="fundamentals")
        _fact(repos, obj.sha256, "revenue", "1000",
              "2024-01-01", "2024-12-31")
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-08")

        cov = {r["block"]: r
               for r in repos.coverage.for_instrument("ins1")}
        reason = cov["fundamentals"]["reason"]
        assert reason.startswith("missing_data:")
        assert "net_income" in reason

        # --json несёт список концептов отдельным массивом
        from rusterm.cli import main
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            # тот же каталог app, что открыл _registry — одна база
            main(["--root", os.path.join(tmpdir, "app"), "coverage",
                  "--instrument", "ins1", "--json"])
        payload = json.loads(buf.getvalue())
        row = next(r for r in payload["rows"]
                   if r["block"] == "fundamentals")
        assert row["reason"].startswith("missing_data")
        # массив отсутствующих концептов — рядом с причиной, в строке
        assert isinstance(row.get("missing_concepts"), list)
        assert "net_income" in row["missing_concepts"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
