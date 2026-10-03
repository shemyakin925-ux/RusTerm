"""ТЗ-64 J2: происхождение в экспорте CLI — обещание на обеих
поверхностях. `export --format json` несёт provenance по lineage (та
же реализация ядра, что у десктопного экспорта), `--format md` —
источники в сноске. Ни одна строка со значением не уходит без
происхождения; строка с отказом несёт причину, а не пустоту.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from rusterm.cli import main as cli_main
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 SnapshotRepo)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-j2", "Corp J", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-J2", "i-j2", None, "common", "active", None))
    raw = repos.raw.put(b"saved response", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
    repos.fact.insert_fact(
        "f-j2", "i-j2", None, "Revenues", "2024-01-01", "2024-12-31",
        "duration", "100", "USD", "USD", "as_reported", "extracted",
        raw.sha256, {"endpoint": "companyfacts"}, "t64-test")
    repos.snapshot.create_snapshot("s-j2", "US-J2", 1, "2025-01-01",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-j2-valued", "s-j2", "issuer", "i-j2", "revenues_total",
        "100", "USD", "2024-01-01", "2024-12-31", None, "t64-test",
        None, None)
    repos.snapshot.add_lineage("m-j2-valued", "f-j2", None, "input")
    repos.snapshot.insert_measure(
        "m-j2-ref", "s-j2", "issuer", "i-j2", "total_equity",
        None, "USD", "2024-01-01", "2024-12-31", None, "t64-test",
        "missing_data: total_equity", None)
    yield repos, paths, raw.sha256
    conn.close()


def _export(root: Path, fmt: str):
    env = dict(os.environ, RUSTERM_ENV_FILE=str(root / "empty.env"))
    proc = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(root),
         "export", "--instrument", "US-J2", "--format", fmt],
        capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_json_valued_measures_carry_provenance(catalog, tmp_path):
    repos, _paths, sha = catalog
    out = _export(tmp_path / "app", "json")
    measures = json.loads(out)["measures"]
    valued = [m for m in measures if m["value"] is not None]
    assert valued, "нет мер со значением"
    for m in valued:
        prov = m["provenance"]
        assert prov and prov["facts"], (m["concept"], prov)
        assert prov["facts"][0]["source_ref"] == sha, m
    refused = [m for m in measures if m["value"] is None]
    assert refused[0]["null_reason"] == "missing_data: total_equity"


def test_md_carries_sources_section(catalog, tmp_path):
    repos, _paths, sha = catalog
    out = _export(tmp_path / "app", "md")
    assert "Источники:" in out
    assert "revenues_total:" in out
    assert sha[:12] in out
    assert "total_equity: входов нет" in out

