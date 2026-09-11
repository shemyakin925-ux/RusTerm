"""Тесты И11-И12: сборка снапшота (два прохода, excluded_stale, три diff)
и экспорт из готовых величин. Данные синтетические."""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import uuid

import pytest

from rusterm.core.export import attach_provenance, snapshot_to_csv, \
    snapshot_to_json, snapshot_to_md
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
          ingested_at=0, issuer_id="i1"):
    fid = fact_id or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, listing_id, concept,
          period_start, period_end, period_type, value, unit, currency,
          basis, origin, source_ref, locator, parser_version,
          status, superseded_by, ingested_at,
          canonical_concept, concept_map_version)
          VALUES (?, ?, NULL, ?, '2024-01-01', '2024-12-31', 'duration',
                  ?, 'USD', NULL, ?, 'extracted', 'src-x', '{}',
                  'synthetic.v1', 'ok', NULL, ?, ?, 'us-gaap.v1')""",
        (fid, issuer_id, concept, value, basis, ingested_at, concept))
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


def test_snapshot_diff_revisions_scoped_to_built_issuer():
    """TASK-14 A2: diff снапшота отвечает за эмитента сборки. Два
    эмитента, у каждого as_reported + restated по СВОЕМУ концепту;
    сборка первого перечисляет в diff.revisions только концепт первого.
    Без фильтра по issuer_id в restated_revisions() тест краснеет —
    чужие ревизии текли в дифф каждого снапшота."""
    tmpdir, conn = _setup()
    try:
        instruments = InstrumentRepo(conn)
        instruments.upsert_issuer(Issuer("i2", "Second Corp (synthetic)",
                                         "US", None, None, "us_gaap", "USD"))
        instruments.upsert_instrument(Instrument("ins2", "i2", None,
                                                 "common", "active", None))
        # i1: ревизия по revenue; i2: ревизия по net_income
        _fact(conn, "revenue", "2000")
        _fact(conn, "revenue", "1900", basis="restated")
        _fact(conn, "net_income", "400", issuer_id="i2")
        _fact(conn, "net_income", "390", basis="restated", issuer_id="i2")

        builder = SnapshotBuilder(SnapshotRepo(conn),
                                  PeerSetRepo(conn), CoverageRepo(conn))
        v1 = builder.build("ins1", "i1", "2024-12-31")
        assert v1.diff.revisions == [("revenue", "2024-12-31")], \
            f"чужие ревизии в диффе: {v1.diff.revisions}"

        v2 = builder.build("ins2", "i2", "2024-12-31")
        assert v2.diff.revisions == [("net_income", "2024-12-31")], \
            f"чужие ревизии в диффе: {v2.diff.revisions}"
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


def test_export_md_nulls_as_footnotes_numbers_with_periods():
    """B13: markdown-экспорт — пустая мера это прочерк со сноской, где
    названа её причина; число не появляется без периода."""
    from rusterm.normalize.concepts import CONCEPT_MAP_VERSION
    tmpdir, conn = _setup()
    try:
        _fact(conn, "net_income", "400")
        _fact(conn, "revenue", "2000")
        builder = SnapshotBuilder(SnapshotRepo(conn), PeerSetRepo(conn),
                                  CoverageRepo(conn))
        built = builder.build("ins1", "i1", "2024-12-31")
        measures = SnapshotRepo(conn).get_measures(built.snapshot_id)

        text = snapshot_to_md(measures)
        lines = text.splitlines()
        assert lines[0] == f"concept_map_version: {CONCEPT_MAP_VERSION}"

        null_rows, valued_rows = [], []
        for line in lines:
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[0] == "concept":
                continue
            if cells[1].startswith("— ["):
                null_rows.append(cells)
            else:
                valued_rows.append(cells)
        assert valued_rows, "величин со значением не оказалось"
        assert null_rows, "пустых мер не оказалось — сноски не проверишь"

        # каждое число несёт оба конца периода
        for cells in valued_rows:
            assert cells[3] and cells[4], \
                f"{cells[0]}: число без периода: {cells}"

        # каждая пустая мера — со сноской, сноска называет её причину
        stored = {m[3]: m for m in measures}
        footnotes = [line for line in lines if line.startswith("- [")]
        assert len(footnotes) == len(null_rows)
        for cells in null_rows:
            concept = cells[0]
            marker = cells[1].split("[", 1)[1].split("]")[0]
            reason = stored[concept][10]
            assert reason, f"{concept}: пустая мера без причины"
            match = next(f for f in footnotes
                         if f.startswith(f"- [{marker}] {concept}:"))
            assert reason in match, (reason, match)
        conn.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir)


# ── ТЗ-20 L9: провенанс переживает выгрузку ────────────────────────────

def _measure(concept="net_margin", value="0.1", mid="m1"):
    return {"measure_id": mid, "scope": "issuer", "scope_ref": "i1",
            "concept": concept, "value": value, "unit": "ratio",
            "period_start": "2024-01-01", "period_end": "2024-12-31",
            "formula_id": "net_margin", "method_version": "v1",
            "null_reason": None, "peer_set_version": None}


def _provider_fact():
    return {"fact_id": "f-p", "source_kind": "provider",
            "concept": "revenue", "source_ref": "a" * 64,
            "locator": '{"kind": "xbrl"}', "status": "ok"}


def _manual_fact(page=3, sha=None):
    sha = sha or ("b" * 64)
    return {"fact_id": "f-m", "source_kind": "manual",
            "concept": "fleet_size", "source_ref": sha,
            "locator": json.dumps(
                {"locator": f"sha256:{sha}#page={page}"}),
            "status": "ok"}


def test_provider_and_manual_measures_are_distinguishable():
    rows = attach_provenance(
        [_measure(mid="mp"), _measure(concept="fleet_ratio", mid="mm")],
        {"mp": [_provider_fact()], "mm": [_manual_fact(page=3)]})
    by_id = {r["measure_id"]: r for r in rows}
    assert by_id["mp"]["provenance"]["source_kind"] == "provider"
    manual = by_id["mm"]["provenance"]
    assert manual["source_kind"] == "manual"
    entry = manual["facts"][0]
    assert entry["document"] == "b" * 64  # хэш документа
    assert entry["page"] == 3             # страница


def test_round_trip_through_json_finds_hash_and_page():
    rows = attach_provenance([_measure(mid="mm")],
                             {"mm": [_manual_fact(page=7,
                                                  sha="c" * 64)]})
    text = snapshot_to_json({"snapshot_id": "s", "version": 1,
                             "as_of": "2024-12-31"}, rows,
                            provenance=None)
    payload = json.loads(text)
    prov = payload["measures"][0]["provenance"]
    assert prov["facts"][0]["document"] == "c" * 64
    assert prov["facts"][0]["page"] == 7
    # потребитель отвечает на вопрос по тексту экспорта, без базы:
    # это файл пользователя, не регулятор
    assert prov["source_kind"] == "manual"


def test_json_without_provenance_is_unchanged():
    """Существующие вызовы: без provenance ключ 'provenance' не
    появляется, все прежние поля на месте."""
    measures = [_measure()]
    text_before = snapshot_to_json({"snapshot_id": "s"}, measures)
    payload = json.loads(text_before)
    assert "provenance" not in payload["measures"][0]
    for key in ("measure_id", "scope", "scope_ref", "concept", "value",
                "unit", "period_start", "period_end", "formula_id",
                "method_version", "null_reason", "peer_set_version"):
        assert key in payload["measures"][0]


def test_existing_csv_and_md_formats_untouched():
    """Порядок и имена полей CSV/MD не меняются (добавление — только в
    JSON через отдельный параметр). Строка меры — кортеж из
    get_measures, как в реальном вызове."""
    row = ("m1", "issuer", "i1", "net_margin", "0.1", "ratio",
           "2024-01-01", "2024-12-31", "net_margin", "v1", None, None)
    csv_text = snapshot_to_csv([row])
    assert csv_text.splitlines()[1] == (
        "scope,scope_ref,concept,value,unit,period_start,period_end,"
        "method_version,null_reason")
    md_text = snapshot_to_md([row])
    assert "| concept | value | unit | period_start | period_end |" \
        in md_text


def test_unverified_manual_fact_is_visible_as_manual():
    """manual + статус suspect: провенанс по-прежнему manual (факт
    виден), недоверие — отдельное поле status, не исчезновение."""
    fact = _manual_fact()
    fact["status"] = "suspect"
    rows = attach_provenance([_measure(mid="mm")], {"mm": [fact]})
    prov = rows[0]["provenance"]
    assert prov["source_kind"] == "manual"
    assert prov["facts"][0]["status"] == "suspect"
