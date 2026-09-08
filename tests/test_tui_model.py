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
