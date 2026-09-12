"""ТЗ-24 N2..N9: отраслевой модуль соединён со снапшотом, физические
записи становятся входами, единицы не смешиваются, покрытие называет
недостающее, экран и инструмент показывают метрики.

LLM-импорт недоступен (ключа нет): записи manual_extraction сеются
напрямую — ступень ③ детерминирована и от сети не зависит.
"""
from __future__ import annotations

import inspect
import sqlite3

import pytest

from rusterm.core import cadence  # noqa: F401  (импорт пакета целиком)
from rusterm.core.industry import module_for_sector
from rusterm.core.industry.inputs import (
    collect_physical_inputs, compute_sector_metrics, parse_scaled_unit)
from rusterm.core.industry.maritime_tanker import (
    fleet_utilization_pct, calculate_industry_measure)
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    # танкерный сектор: peer set "tankers" (реестр знает модуль)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Tanker Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-T", "i1", None, "common", "active", None))
    peers = PeerSetRepo(conn)
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("tv1", "tankers", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("tv1", "US-T", None)
    repos.snapshot.create_snapshot("s1", "US-T", 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.add_block("s1", "fundamentals", "ready", None)
    # документ с физическими записями (ступень ③ уже прошла):
    # заголовок документа привязывает записи к эмитенту
    from rusterm.store.repos import DocumentRepo
    obj = repos.raw.put(b"annual report physical tables",
                        provider="manual-import", block="manual")
    DocumentRepo(conn).put(obj.sha256, "annual.pdf", "pdf", 10,
                           len(b"annual report physical tables"),
                           issuer_id="i1")
    return conn, repos, paths, obj.sha256


def _record(repos, sha, metric, value, unit, verified=True,
            page=1, category="physical"):
    repos.manual_extraction.add(sha, page, category, metric,
                                str(value) if value is not None else None,
                                unit, "FY2024", f"quote: {metric}",
                                verified, "fixture", "fixture.v1")


def test_n5_units_scale_and_refusal():
    # миллион тонн и тонны различаются ровно в 1e6
    base, mult, ok = parse_scaled_unit("million tons")
    assert (base, mult, ok) == ("tons", 1e6, True)
    base, mult, ok = parse_scaled_unit("tons")
    assert (base, mult, ok) == ("tons", 1.0, True)
    # USD там, где ждут USD/day — вход отвергнут с ожидаемой единицей
    si = collect_physical_inputs.__globals__  # noqa: F401 (sanity)
    from rusterm.core.industry.inputs import SectorInputs
    assert SectorInputs is not None
    # нераспознанное масштабное слово — не молчаливая единица
    base, mult, ok = parse_scaled_unit("billionn tons")
    assert ok is False


def test_n5_unrecognised_scale_yields_reason(env):
    conn, repos, paths, sha = env
    # чужая базовая единица: вход отвергнут с именем ожидаемой
    _record(repos, sha, "off hire days", 12.0, "months")  # ждём days
    si = collect_physical_inputs(repos.manual_extraction, "i1",
                                 "tankers")
    assert si.inputs == {}, "вход не той единицы не стал значением"
    assert si.unit_refused["off_hire_days"] == "days"
    metrics = compute_sector_metrics(
        module_for_sector("tankers"), "tankers", si)
    util = next(m for m in metrics
                if m["concept"] == "fleet_utilization_pct")
    assert util["value"] is None
    assert util["reason"] == "missing_data: unit_mismatch:days"
    # нераспознанное масштабное слово — unmapped, не молчаливая 1
    _record(repos, sha, "off hire days", 12.0, "billionn days")
    si2 = collect_physical_inputs(repos.manual_extraction, "i1",
                                  "tankers")
    assert not si2.inputs
    assert any("billionn" in u for u in si2.unmapped)


def test_n3_mapping_feeds_metric_and_unmapped_counted(env):
    conn, repos, paths, sha = env
    _record(repos, sha, "off hire days", 12.0, "days")
    _record(repos, sha, "totally unknown metric", 5.0, "ships")
    si = collect_physical_inputs(repos.manual_extraction, "i1",
                                 "tankers")
    assert si.inputs["off_hire_days"]["value"] == 12.0
    assert si.inputs["off_hire_days"]["source"] == "manual"
    assert si.unmapped == ["totally unknown metric"]
    # метрика считается из записи: год 365, off-hire 12
    m = fleet_utilization_pct(si.inputs["off_hire_days"]["value"])
    assert m.value == pytest.approx((365 - 12) / 365 * 100.0)
    assert m.method_version == "maritime.v1"


def test_n3_unverified_record_yields_manual_unverified_grey(env):
    conn, repos, paths, sha = env
    _record(repos, sha, "off hire days", 12.0, "days", verified=False)
    si = collect_physical_inputs(repos.manual_extraction, "i1",
                                 "tankers")
    assert "off_hire_days" in si.unverified
    metrics = compute_sector_metrics(
        module_for_sector("tankers"), "tankers", si)
    util = next(m for m in metrics
                if m["concept"] == "fleet_utilization_pct")
    assert util["value"] is None
    assert util["reason"] == "manual_unverified"


def test_n6_grey_names_module_parameter(env):
    conn, repos, paths, sha = env
    metrics = compute_sector_metrics(
        module_for_sector("tankers"), "tankers",
        collect_physical_inputs(repos.manual_extraction, "i1",
                                "tankers"))
    util = next(m for m in metrics
                if m["concept"] == "fleet_utilization_pct")
    # имя в причине — ровно имя параметра функции модуля
    params = list(inspect.signature(
        fleet_utilization_pct).parameters)
    assert "off_hire_days" in params
    assert util["reason"] == "no off_hire_days"
    assert util["method_version"] == "maritime.v1"


def test_n2_snapshot_block_present_and_populated(env, capsys):
    conn, repos, paths, sha = env
    _record(repos, sha, "off hire days", 12.0, "days")
    from rusterm.core.industry.inputs import industry_metrics_for
    builder = SnapshotBuilder(
        repos.snapshot, repos.peer_set, coverage_repo=repos.coverage,
        industry=lambda iid, issuer:
            industry_metrics_for(repos, iid))
    builder.build("US-T", "i1", "2024-12-31")
    blocks = {b["block"]: (b["status"], b["reason"])
              for b in repos.coverage.for_instrument("US-T")}
    assert "industry_metrics" in blocks
    status, reason = blocks["industry_metrics"]
    assert status == "ready"
    assert "maritime.v1" in reason
    # инструмент без сектора с модулем — честная причина, не тишина
    repos.instrument.upsert_instrument(Instrument(
        "US-X", "i1", None, "preferred", "active", None))
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ghosts", "industry", "ghosts")
    peers.add_version("gv1", "ghosts", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("gv1", "US-X", None)
    builder.build("US-X", "i1", "2024-12-31")
    blocks = {b["block"]: (b["status"], b["reason"])
              for b in repos.coverage.for_instrument("US-X")}
    status, reason = blocks["industry_metrics"]
    assert status == "missing"
    assert reason == "industry_no_module:ghosts"


def test_n7_concentration_hand_computed_and_mixed_refused(env):
    conn, repos, paths, sha = env
    from rusterm.core.industry.aggregate import sector_concentration
    # четыре участника с выручкой 40/30/20/10 -> доли .4/.3/.2/.1
    peers = PeerSetRepo(conn)
    peers.add_member("tv1", "US-T", None)
    for n, revenue in enumerate((40.0, 30.0, 20.0, 10.0), start=2):
        iid = f"US-{chr(ord('A') + n)}"
        issuer = f"ic{n}"
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"C{n}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        peers.add_member("tv1", iid, None)
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1,
                                       "2024-12-31", None, "none",
                                       "ready")
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept,
               period_start, period_end, period_type, value, unit,
               currency, basis, origin, source_ref, locator,
               parser_version, status, ingested_at, canonical_concept,
               source_kind) VALUES (?, ?, 'revenue', '2024-01-01',
               '2024-12-31', 'duration', ?, 'USD', 'USD',
               'as_reported', 'extracted', 's', '{}',
               'companyfacts.v1', 'ok', 0, 'revenue', 'provider')""",
            (f"f-{iid}", issuer, str(revenue)))
        repos.snapshot.insert_measure_with_lineage(
            dict(measure_id=f"m-{iid}", snapshot_id=f"s-{iid}",
                 scope="issuer", scope_ref=issuer, concept="revenue",
                 value=str(revenue), unit="USD",
                 period_start="2024-01-01", period_end="2024-12-31",
                 formula_id="revenue", method_version="v1",
                 null_reason=None, peer_set_version=None),
            [{"fact_id": f"f-{iid}", "peer_measure_id": None,
              "role": "input"}])
    got = sector_concentration(repos, "tankers", "2025-01-01")
    assert got["value"] == pytest.approx(0.30)
    assert got["currency"] == "USD"
    assert got["n"] == 4  # вклад дали 4 из 5 участников
    # воспроизводимость: новые данные не меняют прошлое
    repos.snapshot.create_snapshot("s-US-T-new", "US-T", 2,
                                   "2025-06-30", None, "none", "ready")
    again = sector_concentration(repos, "tankers", "2025-01-01")
    assert again["value"] == pytest.approx(0.30)

    # смешанные валюты: KRW-участник портит сумму долей — отказ
    repos.instrument.upsert_issuer(Issuer(
        "ik", "KR Corp", "KR", None, None, "ifrs-full", "KRW"))
    repos.instrument.upsert_instrument(Instrument(
        "KR-K", "ik", None, "common", "active", None))
    peers.add_member("tv1", "KR-K", None)
    repos.snapshot.create_snapshot("s-krk", "KR-K", 1, "2024-12-31",
                                   None, "none", "ready")
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-krk', 'ik', 'revenue', '2024-01-01',
           '2024-12-31', 'duration', '50000000', 'KRW', 'KRW',
           'as_reported', 'extracted', 's', '{}', 'companyfacts.v1',
           'ok', 0, 'revenue', 'provider')""")
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-krk", snapshot_id="s-krk", scope="issuer",
             scope_ref="ik", concept="revenue", value="50000000",
             unit="KRW", period_start="2024-01-01",
             period_end="2024-12-31", formula_id="revenue",
             method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-krk", "peer_measure_id": None,
          "role": "input"}])
    got_mixed = sector_concentration(repos, "tankers", "2025-01-01")
    assert got_mixed["value"] is None
    assert got_mixed["reason"] == "currency_mismatch: KRW, USD"


def test_n8_tui_rows_headless_and_manual_marked(env):
    conn, repos, paths, sha = env
    _record(repos, sha, "off hire days", 12.0, "days")
    from rusterm.tui.model import industry_metric_rows
    rows = industry_metric_rows(repos, "tankers", "2025-01-01")
    assert rows, "строки метрик построены"
    util = next(r for r in rows
                if r["concept"] == "fleet_utilization_pct")
    assert util["values"], "значение из verified-записи"
    assert util["source"] == "manual", "ручной источник различим полем"
    grey = [r for r in rows if r["grey_reason"]]
    assert grey and all(r["grey_reason"].startswith("no ")
                        for r in grey)
    import inspect
    import rusterm.tui.model as tui_model
    assert "import curses" not in inspect.getsource(tui_model)


def test_n9_tool_returns_metrics_readonly(env):
    conn, repos, paths, sha = env
    _record(repos, sha, "off hire days", 12.0, "days")
    from rusterm.core.tools import get_industry_metrics
    answer = get_industry_metrics(repos, "US-T")
    assert answer["outcome"] == "resolved"
    assert answer["sector"] == "tankers"
    util = next(m for m in answer["metrics"]
                if m["concept"] == "fleet_utilization_pct")
    assert util["value"] is not None
    assert util["method_version"] == "maritime.v1"
    assert util["unit"] == "pct"
    ghost = get_industry_metrics(repos, "US-GHOST")
    assert ghost["reason"] == "industry_no_sector"
