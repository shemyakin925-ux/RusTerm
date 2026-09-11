"""Тесты модели TUI (TASK-8 U11): всё содержимое экранов собирают
чистые функции rusterm/tui/model.py над репозиториями — headless,
без терминала. SQL, сеть и формулы в rusterm/tui/ запрещены.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid

from rusterm.core import governance as gov
from rusterm.tui import model
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    PeerSetRepo,
    RepoRegistry,
    WatchlistRepo,
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

    wl = WatchlistRepo(conn)
    wl.create_watchlist("w1", "Наблюдение", None, None)
    wl.new_version("wv1", "w1", 1, "create", None)
    wl.add_member("wv1", "ins1", None)
    return tmpdir, conn, repos


def _seed_snapshot_with_measures(repos):
    """Снапшот с одной мерой со значением (lineage к факту) и одной
    пустой мерой с причиной."""
    obj = repos.raw.put(b'{"synthetic": "tui"}', provider="synthetic",
                        block="fundamentals")
    fact_id = str(uuid.uuid4())
    repos.fact.insert_fact(
        fact_id=fact_id, issuer_id="i1", listing_id=None,
        concept="revenue", period_start="2024-01-01",
        period_end="2024-12-31", period_type="duration",
        value="1000", unit="USD", currency=None,
        basis="as_reported", origin="extracted",
        source_ref=obj.sha256,
        locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                 "fact_id": fact_id, "concept": "revenue"},
        parser_version="synthetic.v1",
        canonical_concept="revenue")
    repos.snapshot.create_snapshot("s1", "ins1", 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.add_block("s1", "fundamentals", "ready", None)
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-value", snapshot_id="s1", scope="issuer",
             scope_ref="i1", concept="net_margin", value="0.1",
             unit="ratio", period_start="2024-01-01",
             period_end="2024-12-31", formula_id="net_margin",
             method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": fact_id, "peer_measure_id": None, "role": "input"}])
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-null", snapshot_id="s1", scope="issuer",
             scope_ref="i1", concept="roic", value=None, unit="ratio",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="roic", method_version="v1",
             null_reason="missing_data", peer_set_version=None),
        [])


def test_list_screen_one_row_per_member_with_eight_cells():
    tmpdir, conn, repos = _registry()
    try:
        _seed_snapshot_with_measures(repos)
        rows = model.list_rows(repos, "w1")
        assert len(rows) == 1
        row = rows[0]
        assert row["instrument_id"] == "ins1"
        assert len(row["coverage_cells"]) == 8
        assert all(cell in ("ready", "stale", "processing", "missing",
                            "error", "-") for cell in row["coverage_cells"])
        assert row["as_of"] == "2024-12-31"
        lines = model.render_list(rows)
        assert any("ins1" in line for line in lines)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_missing_block_renders_with_reason():
    tmpdir, conn, repos = _registry()
    try:
        repos.coverage.upsert("ins1", "prices", "missing",
                              reason="no_source")
        card = model.card_rows(repos, "ins1")
        price_block = next(b for b in card["coverage"]
                           if b["block"] == "prices")
        assert price_block["status"] == "missing"
        assert price_block["reason"] == "no_source"
        lines = model.render_card(card)
        assert any("prices: missing — no_source" in line
                   for line in lines)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_null_measure_renders_dash_with_null_reason():
    tmpdir, conn, repos = _registry()
    try:
        _seed_snapshot_with_measures(repos)
        card = model.card_rows(repos, "ins1")
        null_measure = next(m for m in card["measures"]
                            if m["concept"] == "roic")
        assert null_measure["value"] == model.NULL_MARK
        assert null_measure["null_reason"] == "missing_data"
        value_measure = next(m for m in card["measures"]
                             if m["concept"] == "net_margin")
        assert value_measure["value"] == "0.1"
        assert value_measure["null_reason"] is None
        lines = model.render_card(card)
        assert any("roic: — ratio (missing_data)" in line
                   for line in lines)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_source_panel_returns_document_locator_and_method_version():
    tmpdir, conn, repos = _registry()
    try:
        _seed_snapshot_with_measures(repos)
        card = model.card_rows(repos, "ins1")
        value_measure = next(m for m in card["measures"]
                             if m["concept"] == "net_margin")
        panel = model.source_panel(repos, value_measure)
        assert panel["method_version"] == "v1"
        assert panel["sources"], "нет источников у меры со значением"
        source = panel["sources"][0]
        assert source["document"].startswith("sha256:") or \
            len(source["document"]) == 64
        assert source["locator"]["kind"] == "xbrl"
        assert source["fact_id"]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_unconfirmed_peer_set_is_marked():
    tmpdir, conn, repos = _registry()
    try:
        peers = PeerSetRepo(conn)
        peers.create_peer_set("ps1", "industry", "tankers")
        peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                          "classifier", "v1", False, None, None)
        peers.add_member("psv1", "ins1", None)

        rows = model.list_rows(repos, "w1")
        assert rows[0]["peer_status"] == "unverified"
        assert "peer не подтверждён" in model.render_list(rows)[0]
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_governance_five_colors_independently():
    tmpdir, conn, repos = _registry()
    try:
        repos.governance.record(gov.independent_directors(
            "ins1", 0.6, "2024-12-31", "doc#p1"))
        repos.governance.record(gov.ceo_chair(
            "ins1", False, False, "2024-12-31", "doc#p2"))
        repos.governance.record(gov.related_party(
            "ins1", None, None, "2024-12-31", "doc#p3"))
        card = model.card_rows(repos, "ins1")
        colors = {g["indicator"]: g["color"] for g in card["governance"]}
        assert colors["independent_directors"] == "green"
        assert colors["ceo_chair"] == "red"
        assert colors["related_party"] == "gray"
        assert len(card["governance"]) == 5
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_tui_has_no_sql_no_http():
    result = subprocess.run(
        ["grep", "-rnE", r"execute\(|httpx|requests", "rusterm/tui/"],
        capture_output=True, text=True)
    assert result.returncode == 1, result.stdout  # 1 = совпадений нет


def test_v6_source_panel_names_source_tag_and_map_version():
    """TASK-9 V6: панель источника показывает, какой тег стал числом
    и по какой версии карты."""
    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "v6"}', provider="synthetic",
                            block="fundamentals")
        fact_id = str(uuid.uuid4())
        repos.fact.insert_fact(
            fact_id=fact_id, issuer_id="i1", listing_id=None,
            concept="us-gaap:Revenues", period_start="2024-01-01",
            period_end="2024-12-31", period_type="duration",
            value="1000", unit="USD", currency=None,
            basis="as_reported", origin="extracted",
            source_ref=obj.sha256,
            locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                     "fact_id": fact_id, "concept": "us-gaap:Revenues"},
            parser_version="synthetic.v1",
            canonical_concept="revenue",
            concept_map_version="us-gaap.v1")
        repos.snapshot.create_snapshot("s1", "ins1", 1, "2024-12-31",
                                       None, "none", "ready")
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id="m1", snapshot_id="s1", scope="issuer",
                 scope_ref="i1", concept="net_margin", value="0.1",
                 unit="ratio", period_start="2024-01-01",
                 period_end="2024-12-31", formula_id="net_margin",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": fact_id, "peer_measure_id": None,
              "role": "input"}])
        card = model.card_rows(repos, "ins1")
        measure = next(m for m in card["measures"]
                       if m["concept"] == "net_margin")
        panel = model.source_panel(repos, measure)
        source = panel["sources"][0]
        assert source["source_tag"] == "us-gaap:Revenues"
        assert source["concept_map_version"] == "us-gaap.v1"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_c5_source_panel_lists_stale_excluded_fact_with_marker():
    """TASK-15 C5: у эмитента с operating_income от 2012 и revenue от
    2025 мера operating_margin пуста с 'missing_data: operating_income';
    панель источника перечисляет факт 2012 с маркером и обеими датами —
    факт видим как устаревший, а не исчез. Причина меры не меняется."""
    from rusterm.core.snapshot import SnapshotBuilder

    tmpdir, conn, repos = _registry()
    try:
        obj = repos.raw.put(b'{"synthetic": "c5"}', provider="synthetic",
                            block="fundamentals")

        def fact(concept, canonical, end, value):
            fid = str(uuid.uuid4())
            repos.fact.insert_fact(
                fact_id=fid, issuer_id="i1", listing_id=None,
                concept=concept, period_start=f"{end[:4]}-01-01",
                period_end=end, period_type="duration", value=value,
                unit="USD", currency=None, basis="as_reported",
                origin="extracted", source_ref=obj.sha256,
                locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                         "fact_id": fid, "concept": concept},
                parser_version="synthetic.v1", canonical_concept=canonical)
            return fid

        stale_id = fact("us-gaap:OperatingIncomeLoss", "operating_income",
                        "2012-12-31", "50000")
        fact("us-gaap:Revenues", "revenue", "2025-12-31", "2000")

        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2026-09-09")

        card = model.card_rows(repos, "ins1")
        measure = next(m for m in card["measures"]
                       if m["concept"] == "operating_margin")
        assert measure["value"] == model.NULL_MARK
        assert measure["null_reason"] == "missing_data: operating_income", \
            measure["null_reason"]

        panel = model.source_panel(repos, measure)
        assert panel["stale"], "исключённый факт не показан"
        entry = panel["stale"][0]
        assert entry["fact_id"] == stale_id
        assert entry["period_end"] == "2012-12-31"
        assert entry["marker"] == ("устаревший (последний 2012-12-31,"
                                   " anchor 2025-12-31)"), entry["marker"]

        # у меры со значением исключённое не показывается
        revenue_measure = next(m for m in card["measures"]
                               if m["concept"] == "net_margin")
        revenue_panel = model.source_panel(repos, revenue_measure)
        if revenue_measure["value"] != model.NULL_MARK:
            assert revenue_panel["stale"] == []
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


# ── ТЗ-20 L8: рынок в списке, source_kind в карточке ───────────────────

def _seed_manual_fact(repos, sha_ref: str, status: str = "ok"):
    fact_id = str(uuid.uuid4())
    repos.fact.insert_fact(
        fact_id=fact_id, issuer_id="i1", listing_id=None,
        concept="fleet_size", period_start="2025-01-01",
        period_end="2025-12-31", period_type="duration",
        value="42", unit="ships", currency=None, basis="as_reported",
        origin="manual", source_ref=sha_ref,
        locator={"locator": f"sha256:{sha_ref}#page=3"},
        parser_version="manual:fake-model:records.v1",
        status=status, source_kind="manual")
    return fact_id


def test_list_row_carries_market_code_from_registry():
    tmpdir, conn, repos = _registry()
    try:
        rows = model.list_rows(repos, "w1")
        # ins1 не начинается с кода рынка — честное «—»
        assert rows[0]["market"] == "—"
        repos.instrument.upsert_instrument(Instrument(
            "US-FLT", "i1", None, "common", "active", None))
        wl = repos.watchlist
        vid = wl.new_version("wv2", "w1", 2, "edit", None)
        wl.copy_members("wv1", "wv2")
        wl.add_member("wv2", "US-FLT", None)
        rows = model.list_rows(repos, "w1")
        by_id = {r["instrument_id"]: r for r in rows}
        assert by_id["US-FLT"]["market"] == "US"
    finally:
        conn.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_render_list_shows_market_column():
    lines = model.render_list([
        {"market": "US", "ticker": "FLT", "instrument_id": "US-FLT",
         "as_of": "2024-12-31",
         "coverage_cells": ["ready"] + ["-"] * 7,
         "peer_status": None, "market_code": "US"}])
    assert lines[0].startswith("US  ")


def test_card_distinguishes_manual_from_provider_and_marks_unverified():
    """Done-when L8: строка модели для manual-непроверенного факта
    отличается от provider-факта в поле, на котором ключается
    отрисовщик; curses для тестов не нужен."""
    tmpdir, conn, repos = _registry()
    try:
        _seed_snapshot_with_measures(repos)
        obj = repos.raw.put(b'{"manual": "doc"}', provider="manual-import",
                            block="manual")
        manual_fact = _seed_manual_fact(repos, obj.sha256, status="ok")
        manual_bad = _seed_manual_fact(repos, obj.sha256, status="suspect")
        repos.snapshot.create_snapshot("s2", "ins1", 2, "2025-12-31",
                                       None, "none", "ready")
        repos.snapshot.add_block("s2", "fundamentals", "ready", None)
        prov_fact = str(uuid.uuid4())
        prov_obj = repos.raw.put(b'{"provider": "doc"}',
                                 provider="synthetic",
                                 block="fundamentals")
        repos.fact.insert_fact(
            fact_id=prov_fact, issuer_id="i1", listing_id=None,
            concept="revenue", period_start="2025-01-01",
            period_end="2025-12-31", period_type="duration",
            value="1000", unit="USD", currency=None,
            basis="as_reported", origin="extracted",
            source_ref=prov_obj.sha256,
            locator={"kind": "xbrl"},
            parser_version="synthetic.v1",
            canonical_concept="revenue")
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id="m-prov", snapshot_id="s2", scope="issuer",
                 scope_ref="i1", concept="revenue_growth", value="0.1",
                 unit="ratio", period_start="2025-01-01",
                 period_end="2025-12-31", formula_id="x",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": prov_fact, "peer_measure_id": None,
              "role": "input"}])
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id="m-manual", snapshot_id="s2", scope="issuer",
                 scope_ref="i1", concept="fleet_ratio", value="0.5",
                 unit="ratio", period_start="2025-01-01",
                 period_end="2025-12-31", formula_id="x",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": manual_fact, "peer_measure_id": None,
              "role": "input"}])
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id="m-manual-bad", snapshot_id="s2",
                 scope="issuer", scope_ref="i1", concept="fleet_bad",
                 value="0.9", unit="ratio", period_start="2025-01-01",
                 period_end="2025-12-31", formula_id="x",
                 method_version="v1", null_reason=None,
                 peer_set_version=None),
            [{"fact_id": manual_bad, "peer_measure_id": None,
              "role": "input"}])
        card = model.card_rows(repos, "ins1")
        by_measure = {m["measure_id"]: m for m in card["measures"]}
        provider_measure = by_measure["m-prov"]
        manual_measure = by_measure["m-manual"]
        manual_bad_measure = by_measure["m-manual-bad"]
        # provider и manual различимы в поле модели
        assert provider_measure["source_kind"] == "provider"
        assert manual_measure["source_kind"] == "manual"
        assert manual_measure["unverified"] is False
        # непроверенное manual помечено отдельно
        assert manual_bad_measure["unverified"] is True
        lines = model.render_card(card)
        manual_line = [line for line in lines
                       if line.strip().startswith("fleet_ratio")][0]
        bad_line = [line for line in lines
                    if line.strip().startswith("fleet_bad")][0]
        assert "[manual]" in manual_line
        assert "[manual · НЕ проверено]" in bad_line
        # панель источника manual-факта: файл и страница вместо URL
        panel = model.source_panel(repos,
                                   dict(by_measure["m-manual"],
                                        issuer_id="i1"))
        kinds = {s["kind"] for s in panel["sources"]}
        assert "manual" in kinds
        labels = [s.get("locator_label") for s in panel["sources"]
                  if s["kind"] == "manual"]
        assert labels and labels[0] == "файл, страница 3"
    finally:
        conn.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
