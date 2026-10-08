"""ТЗ-140 S1: машина проверки панели источника — на фикстурной карточке.

Одна клетка проходит (факт с источником и периодом), одна нет — мера со
значением, у которой родословная пуста: панель называет метод, но ни
одного документа. Схема факта не даёт факта без source_ref
(NOT NULL REFERENCES raw_object), поэтому честный отказ — на строке мер;
через двери магазина сироту не собрать (I4 запрещает), состояние старой
или повреждённой базы воспроизведено прямым SQL.
"""
from __future__ import annotations

import sqlite3

from tools.source_check import check_instrument
from rusterm.core.snapshot import make_snapshot_builder
from rusterm.desktop import card, data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)


def _repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "src-base")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-S", "Fixture Source Co", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-SRC", "i-S", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-S", "US-SRC", "XNYS", "USD", 1, None, None))
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts/SRC")
    return repos, paths, conn, raw.sha256


def _annual(repos, sha, year: str) -> None:
    for fid, tag, canonical, value in (
            (f"f-rev-{year}", "us-gaap:Revenues", "revenue", "100.0"),
            (f"f-ni-{year}", "us-gaap:NetIncomeLoss", "net_income", "10.0"),
            (f"f-ocf-{year}", "us-gaap:NetCashProvidedByUsedInOperatingActivities",
             "ocf", "20.0"),
            (f"f-capex-{year}", "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
             "capex", "5.0")):
        repos.fact.insert_fact(
            fid, "i-S", None, tag, f"{year}-01-01", f"{year}-12-31",
            "duration", value, "USD", "USD", "as_reported", "extracted",
            sha, {"endpoint": "companyfacts", "kind": "10-K"}, "t",
            canonical_concept=canonical)


def test_source_check_passes_and_fails_on_a_fixture_card(tmp_path):
    repos, paths, conn, sha = _repos(tmp_path)
    _annual(repos, sha, "2022")
    make_snapshot_builder(repos, "2026-10-08").build("US-SRC", "i-S",
                                                     "2026-10-08")
    # сирота: значение есть, документов в родословной нет; I4 не даёт
    # её дверям, состояние старой базы воспроизводится прямым SQL
    sid = repos.snapshot.latest_snapshot_id("US-SRC")
    conn.execute(
        """INSERT INTO measure(measure_id, snapshot_id, scope, scope_ref,
           concept, value, unit, period_start, period_end, formula_id,
           method_version, null_reason)
           VALUES ('m-orphan', ?, 'issuer', 'i-S', 'pe', '10.0', '',
                   '2026-10-08', '2026-10-08', 'pe', 'v1', NULL)""",
        (sid,))
    result = check_instrument(repos, paths, "US-SRC")
    cells = {(c[1], c[0]): c for c in result["cells"]}
    good = cells[("revenue", "2022")]
    assert good[2] is True and good[4] is True, good
    bad = cells[("pe", "сейчас")]
    assert bad[2] is False, bad
    assert "ни одного документа" in bad[3], bad
    assert result["open_target"], result["open_target"]


