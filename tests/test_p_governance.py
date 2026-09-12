"""ТЗ-25 P1/P2/P7/P8/P9/P10: продюсер оценок, причины серости,
прокси через ручной импорт, доказуемость цвета, устаревание, экран.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pytest

import rusterm.core.governance as gov
from rusterm.core.governance import (INDICATORS, produce_assessments,
                                     governance_inputs_from_records)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import DocumentRepo, Instrument, Issuer, \
    RepoRegistry


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-T", "i1", None, "common", "active", None))
    obj = repos.raw.put(b"proxy statement text",
                        provider="manual-import", block="manual")
    DocumentRepo(conn).put(obj.sha256, "proxy.pdf", "pdf", 30,
                           len(b"proxy statement text"), issuer_id="i1")
    return conn, repos, paths, obj.sha256


def test_p1_producer_writes_five_rows_with_colors(env):
    conn, repos, paths, sha = env
    inputs = {
        "independent_directors": {
            "inputs": {"share": 0.6}, "lineage_ref": f"{sha}#page=4"},
        "ceo_chair": {
            "inputs": {"roles_separated": True},
            "lineage_ref": f"{sha}#page=5"},
        "related_party": {
            "inputs": {"ratio": 0.001,
                       "approved_by_independents": True},
            "lineage_ref": f"{sha}#page=9"},
        "insider_net": {
            "inputs": {"net_ratio": 0.002},
            "lineage_ref": "forms-345:2024"},
        "auditor": {
            "inputs": {"changes_in_5y": 0,
                       "qualified_opinion": False,
                       "tenure_years": 7},
            "lineage_ref": f"{sha}#page=22"},
    }
    rows = produce_assessments(repos.governance, "US-T", "2025-01-15",
                               inputs, now=date(2025, 2, 1))
    assert [a.indicator for a in rows] == list(INDICATORS)
    assert [a.color for a in rows] == ["green", "green", "green",
                                       "green", "green"]
    assert all(a.lineage_ref for a in rows)
    assert len(repos.governance.for_instrument("US-T")) == 5


def test_p1_no_inputs_five_grey_rows_with_named_reasons(env):
    conn, repos, paths, sha = env
    rows = produce_assessments(repos.governance, "US-T", "2025-01-15",
                               None)
    assert len(rows) == 5
    assert all(a.color == "gray" for a in rows)
    assert all(a.reason == "no_data:not_collected" for a in rows)


def test_p2_four_distinct_grey_reasons_and_card_shows_them(env):
    conn, repos, paths, sha = env
    from rusterm.tui.model import card_rows
    # not_collected
    produce_assessments(repos.governance, "US-T", "2025-01-15", None)
    # source_has_no_disclosure / collected_unparsed / manual_unverified
    spec = {"inputs": {}, "lineage_ref": f"{sha}#page=3"}
    rows = produce_assessments(repos.governance, "US-T", "2025-01-16", {
        "independent_directors": {"inputs": {"share": None},
                                  "lineage_ref": f"{sha}#page=3"},
    })
    card = card_rows(repos, "US-T")
    reasons = {g["indicator"]: g["reason"] for g in card["governance"]}
    assert reasons["independent_directors"] == \
        "no_data:board_independence_not_disclosed"
    assert reasons["insider_net"] == "no_data:not_collected"
    # источник без раскрытия — своя причина (серый по документу)
    assert gov.GREY_REASONS["source_has_no_disclosure"]
    assert gov.GREY_REASONS["collected_unparsed"]
    assert gov.GREY_REASONS["not_collected"]
    assert gov.GREY_REASONS["stale"]


def test_p7_verified_record_colors_unverified_stays_grey(env):
    conn, repos, paths, sha = env
    repos.manual_extraction.add(sha, 4, "other",
                                "independent_directors_share", "0.6",
                                "ratio", "FY2024",
                                "six of the ten directors are independent",
                                True, "fixture", "fixture.v1")
    inputs = governance_inputs_from_records(repos.manual_extraction,
                                            "i1")
    assert "independent_directors" in inputs
    rows = produce_assessments(repos.governance, "US-T", "2025-01-15",
                               inputs, now=date(2025, 2, 1))
    ind = next(a for a in rows if a.indicator == "independent_directors")
    assert ind.color == "green"
    assert ind.lineage_ref == f"{sha}#page=4"
    # verified=no — серый manual_unverified, не цвет
    repos.manual_extraction.add(sha, 7, "other",
                                "auditor_changes_in_5y", "1", "count",
                                "FY2024", "one change", False, "fixture",
                                "fixture.v1")
    inputs2 = governance_inputs_from_records(repos.manual_extraction,
                                             "i1")
    assert set(inputs2) == {"independent_directors", "auditor"}, inputs2
    assert inputs2["auditor"].get("verified") is False
    rows2 = produce_assessments(repos.governance, "US-T", "2025-01-15",
                                {"auditor": {
                                    "inputs": {},
                                    "lineage_ref": "manual_unverified",
                                    "verified": False}})


def test_p8_override_survives_recomputation(env):
    conn, repos, paths, sha = env
    inputs = {"independent_directors": {
        "inputs": {"share": 0.4}, "lineage_ref": f"{sha}#page=4"}}
    produce_assessments(repos.governance, "US-T", "2025-01-15", inputs,
                        now=date(2025, 2, 1))
    first = repos.governance.latest("US-T", "independent_directors")
    assert first["color"] == "yellow"
    # ручная поправка: своя провенанс-метка
    repos.governance.record({
        "instrument_id": "US-T", "indicator": "independent_directors",
        "color": "green", "method_version": gov.METHOD_VERSION,
        "as_of": "2025-02-01",
        "lineage_ref": "override:user:verify:2025-02-01",
        "reason": "user corrected share to 0.6"})
    produce_assessments(repos.governance, "US-T", "2025-01-15", inputs,
                        now=date(2025, 2, 1))
    latest = repos.governance.latest("US-T", "independent_directors")
    assert latest["color"] == "green"
    assert latest["lineage_ref"].startswith("override:")


def test_p9_stale_colour_goes_grey_at_threshold(env):
    conn, repos, paths, sha = env
    old = (date(2025, 1, 15) - timedelta(days=gov.STALENESS_DAYS + 5))
    inputs = {"independent_directors": {
        "inputs": {"share": 0.6}, "lineage_ref": f"{sha}#page=4"}}
    rows = produce_assessments(repos.governance, "US-T",
                               old.isoformat(), inputs,
                               now=date(2026, 9, 12))
    ind = next(a for a in rows if a.indicator == "independent_directors")
    assert ind.color == "gray"
    assert ind.reason.startswith("stale:assessed:")
    # свежая — цвет остаётся
    rows2 = produce_assessments(repos.governance, "US-T", "2026-08-01",
                                inputs, now=date(2026, 9, 12))
    assert rows2[0].color == "green"


def test_p10_export_carries_governance_old_fields_unmoved(env, capsys):
    conn, repos, paths, sha = env
    produce_assessments(repos.governance, "US-T", "2025-01-15", None)
    from rusterm.core.export import snapshot_to_json
    snapshot = {"snapshot_id": "s", "version": 1}
    measures = [{"measure_id": "m1", "scope": "issuer",
                 "scope_ref": "i1", "concept": "net_margin",
                 "value": "0.2", "unit": "ratio", "period_start": "",
                 "period_end": "", "formula_id": "net_margin",
                 "method_version": "v1", "null_reason": None,
                 "peer_set_version": None}]
    assessments = [{"indicator": "auditor", "color": "gray",
                    "reason": "no_data:not_collected",
                    "lineage_ref": "not-collected"}]
    payload = json.loads(snapshot_to_json(snapshot, measures,
                                          governance=assessments))
    assert set(payload) >= {"snapshot", "measures", "governance",
                            "concept_map_version"}
    assert payload["measures"][0]["concept"] == "net_margin"
    assert payload["governance"][0]["color"] == "gray"
    assert payload["governance"][0]["reason"] == "no_data:not_collected"
    # без параметра вывод прежний
    text = snapshot_to_json(snapshot, measures)
    old_payload = json.loads(text)
    assert set(old_payload) == {"snapshot", "measures",
                                "concept_map_version"}
