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


def test_year_cell_panel_reads_the_year_measure(tmp_path):
    repos, paths, conn, sha = _repos(tmp_path)
    _annual(repos, sha, "2022")
    make_snapshot_builder(repos, "2022-12-31").build("US-SRC", "i-S",
                                                     "2022-12-31")
    _annual(repos, sha, "2023")
    make_snapshot_builder(repos, "2023-12-31").build("US-SRC", "i-S",
                                                     "2023-12-31")
    info = data.measure_table_rows(repos, "US-SRC", card.CARD_YEARS)
    view = card.card_view(repos, info)
    years = view["columns"][:-1]
    row = next(r for r in view["rows"]
               if r.get("concept") == "net_margin")
    column = years.index("2022")
    panel = data.panel_for_cell(repos, paths, view, row, column,
                                instrument_id="US-SRC")
    assert "2022-12-31" in panel["text"], panel["text"]
    now = data.panel_for_cell(repos, paths, view, row,
                              len(view["columns"]) - 1,
                              instrument_id="US-SRC")
    assert "2023-12-31" in now["text"], now["text"]
    assert now["text"] != panel["text"]


def test_fact_now_without_facts_answers_with_the_row_measure(tmp_path):
    repos, paths, conn, sha = _repos(tmp_path)
    measure_row = {
        "measure": {"measure_id": "m-td", "concept": "total_debt",
                    "value": "40.0", "null_reason": None,
                    "issuer_id": "i-S"},
        "current": "40.0", "unit": "", "null_reason": None}
    view = {"columns": ["2025", "сейчас"]}
    row = {"kind": "fact", "concept": "total_debt", "fact_ids": {},
           "measure_row": measure_row}
    panel = data.panel_for_cell(repos, paths, view, row, 1,
                                instrument_id="US-SRC")
    assert panel["cell_kind"] == "measure_fallback", panel
    assert "источник" in panel["text"]


def test_price_only_measure_names_its_series(tmp_path):
    repos, paths, conn, sha = _repos(tmp_path)
    _annual(repos, sha, "2022")
    make_snapshot_builder(repos, "2026-10-08").build("US-SRC", "i-S",
                                                     "2026-10-08")
    sid = repos.snapshot.latest_snapshot_id("US-SRC")
    conn.execute(
        """INSERT INTO measure(measure_id, snapshot_id, scope, scope_ref,
           concept, value, unit, period_start, period_end, formula_id,
           method_version, null_reason)
           VALUES ('m-tr', ?, 'issuer', 'i-S', 'total_return', '0.1', '',
                   '2026-10-08', '2026-10-08', 'total_return', 'v1',
                   NULL)""", (sid,))
    conn.execute(
        """INSERT INTO measure_lineage_price(measure_id, instrument_id,
           date_from, date_to, role)
           VALUES ('m-tr', 'US-SRC', '2025-10-03', '2026-09-30',
                   'price_series_total_return')""")
    measure_row = {"measure": dict(conn.execute(
        "SELECT * FROM measure WHERE measure_id='m-tr'").fetchone()),
        "current": "0.1", "unit": "", "null_reason": None}
    panel = data.source_panel_view(repos, paths, measure_row,
                                   instrument_id="US-SRC")
    assert "ценовой ряд" in panel["text"], panel["text"]
    assert "2025-10-03 — 2026-09-30" in panel["text"], panel["text"]


def test_measure_of_measure_names_the_input_documents(tmp_path):
    """fcf_yield из fcf (роль from_fcf, peer_measure_id): панель называет
    документы входов той меры — выручку и инвестиции из её родословной."""
    repos, paths, conn, sha = _repos(tmp_path)
    _annual(repos, sha, "2022")
    make_snapshot_builder(repos, "2026-10-08").build("US-SRC", "i-S",
                                                     "2026-10-08")
    sid = repos.snapshot.latest_snapshot_id("US-SRC")
    inner = dict(conn.execute(
        "SELECT measure_id FROM measure WHERE snapshot_id=? AND "
        "concept='fcf'", (sid,)).fetchone())
    conn.execute(
        """INSERT INTO measure(measure_id, snapshot_id, scope, scope_ref,
           concept, value, unit, period_start, period_end, formula_id,
           method_version, null_reason)
           VALUES ('m-fy', ?, 'issuer', 'i-S', 'fcf_yield', '0.1', '',
                   '2026-10-08', '2026-10-08', 'fcf_yield', 'v1', NULL)""",
        (sid,))
    conn.execute(
        """INSERT INTO measure_lineage(measure_id, fact_id,
           peer_measure_id, role)
           VALUES ('m-fy', NULL, ?, 'from_fcf')""", (inner["measure_id"],))
    measure_row = {"measure": dict(conn.execute(
        "SELECT * FROM measure WHERE measure_id='m-fy'").fetchone()),
        "current": "0.1", "unit": "", "null_reason": None}
    panel = data.source_panel_view(repos, paths, measure_row,
                                   instrument_id="US-SRC")
    assert panel["panel"]["sources"], panel["text"]
    assert all(s.get("via_measure") == "fcf"
               for s in panel["panel"]["sources"])
    assert "через меру fcf" in panel["text"], panel["text"]
