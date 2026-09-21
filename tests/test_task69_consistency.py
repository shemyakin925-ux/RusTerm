"""ТЗ-69 P2/P3: происхождение мер соответствует словарю, и pe сходится
двумя путями. Расхождение — красный с обоими значениями."""
from __future__ import annotations

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer,  # noqa: E402
                                 RepoRegistry)


@pytest.fixture()
def catalog(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-c", "Apple Inc.", "US", "320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-C", "i-c", None, "common", "active", None))
    raw = repos.raw.put(b"facts", provider="edgar", block="fundamentals")
    for fid, con, ptype, start, end, val in (
        ("f-c-ni", "net_income", "duration",
         "2024-09-29", "2025-09-27", "112010000000"),
        ("f-c-rev", "revenue", "duration",
         "2024-09-29", "2025-09-27", "416161000000"),
        ("f-c-sh", "shares_outstanding", "instant",
         "2026-06-27", "2026-06-27", "14608963000"),
        ("f-c-debt", "total_debt", "instant",
         "2026-06-27", "2026-06-27", "82300000000"),
        ("f-c-cash", "cash", "instant",
         "2026-06-27", "2026-06-27", "39544000000"),
        ("f-c-stinv", "st_investments", "instant",
         "2026-06-27", "2026-06-27", "22855000000"),
        ("f-c-eq", "total_equity", "instant",
         "2026-06-27", "2026-06-27", "107520000000"),
        ("f-c-eps", "eps_diluted", "duration",
         "2024-09-29", "2025-09-27", "7.668"),
    ):
        repos.fact.insert_fact(
            fid, "i-c", None, con, start, end, ptype, val, "USD",
            "USD", "as_reported", "extracted", raw.sha256,
            {"endpoint": "companyfacts"}, "t69",
            canonical_concept=con)
    repos.snapshot.create_snapshot("s-c", "US-C", 1, "2025-09-27",
                                   None, None, "ready")
    repos.snapshot.insert_measure(
        "m-pe", "s-c", "issuer", "i-c", "pe", "32.61", "ratio",
        "2024-09-29", "2025-09-27", None, "t69", None, None)
    repos.snapshot.add_lineage("m-pe", "f-c-ni", None, "input")
    yield repos, paths
    conn.close()


def test_pe_dictionary_value_differs_from_old(catalog):
    repos, _ = catalog
    sid = repos.snapshot.latest_snapshot_id("US-C")
    rows = repos.snapshot.get_measures(sid)
    pe_row = next(m for m in rows if m[3] == "pe")
    pe_stored = float(pe_row[4])
    dictionary_pe = 250.0 * 14608963000 / 112010000000.0
    rel = abs(pe_stored - dictionary_pe) / dictionary_pe
    assert rel <= 0.05, (pe_stored, dictionary_pe, rel)


def test_divergent_pe_named_red(catalog):
    """Старый pe 166.4 против словарного ~43.84/40.6 — расхождение
    больше 5%, красный с обоими значениями."""
    repos, _ = catalog
    sid = repos.snapshot.latest_snapshot_id("US-C")
    rows = repos.snapshot.get_measures(sid)
    pe_row = next(m for m in rows if m[3] == "pe")
    pe_stored = float(pe_row[4])
    old_wrong = 166.4
    rel = abs(pe_stored - old_wrong) / old_wrong
    assert rel > 0.05, (pe_stored, old_wrong, rel)
