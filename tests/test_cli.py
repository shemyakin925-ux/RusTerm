"""Тесты И13: CLI — шесть команд на синтетике, фактический вывод."""
from __future__ import annotations

import json
import shutil
import tempfile

import pytest

from rusterm.cli import main


def _root():
    return tempfile.mkdtemp()


def test_cli_full_cycle_init_ingest_snapshot_export_verify_doctor(capsys):
    root = _root()
    try:
        # init: каталог + миграции
        assert main(["--root", root, "init"]) == 0
        out = capsys.readouterr().out
        assert "schema_version=36" in out

        # demo: демо-данные создаются только явно (TASK-8 U3)
        assert main(["--root", root, "demo"]) == 0
        out = capsys.readouterr().out
        assert "синтетические" in out

        # ingest: сбор по селектору инструмента
        assert main(["--root", root, "ingest",
                     "--instrument", "US-CLI-DEMO"]) == 0
        out = capsys.readouterr().out
        assert "фактов: 6" in out

        # snapshot: сборка версии, счётчик значений и пустых раздельно
        assert main(["--root", root, "snapshot",
                     "--instrument", "US-CLI-DEMO"]) == 0
        out = capsys.readouterr().out
        assert "снапшот v1" in out
        assert "со значением 3, пусто 0" in out

        # export json: значения из снапшота
        assert main(["--root", root, "export", "--instrument", "US-CLI-DEMO",
                     "--format", "json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["snapshot"]["instrument_id"] == "US-CLI-DEMO"
        assert payload["measures"], "экспорт пуст"

        # export csv в файл
        import os
        csv_path = os.path.join(root, "export.csv")
        assert main(["--root", root, "export", "--instrument", "US-CLI-DEMO",
                     "--format", "csv", "--out", csv_path]) == 0
        assert "null_reason" in open(csv_path, encoding="utf-8").read()

        # verify: новый интерфейс TASK-7 T14 — по id факта, с документом
        import sqlite3
        db = sqlite3.connect(f"{root}/rusterm.db")
        fact_id = db.execute(
            "SELECT fact_id FROM fact WHERE concept='revenue'"
            " AND status='ok' LIMIT 1").fetchone()[0]
        db.close()
        assert main(["--root", root, "verify",
                     "--fact", fact_id, "--expected", "777",
                     "--document", "https://example.com/filing?token=S3cret"]) == 0
        out = capsys.readouterr().out
        assert "superseded" in out

        # doctor: база в порядке
        assert main(["--root", root, "doctor"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is True
        assert report["schema_version"] == 36
    finally:
        shutil.rmtree(root)


def test_cli_doctor_detects_schema_gap(capsys):
    root = _root()
    try:
        # doctor на неинициализированном каталоге — код возврата 1
        assert main(["--root", root, "doctor"]) == 1
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is False
        assert any("schema_version" in p for p in report["problems"])
    finally:
        shutil.rmtree(root)


def test_cli_doctor_reports_schema_drift(capsys):
    """BACKLOG B6: база, отставшая от кода, видна в doctor с обоими
    числами — применённой версией и ожидаемой."""
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        import sqlite3
        conn = sqlite3.connect(f"{root}/rusterm.db", isolation_level=None)
        conn.execute("DELETE FROM schema_version WHERE version=36")
        conn.close()
        assert main(["--root", root, "doctor"]) == 1
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is False
        # версии 34 не существует, поэтому после удаления 36 максимум — 35
        assert report["schema_version"] == 35
        assert any("schema_version=35" in p and "36" in p
                   for p in report["problems"])
    finally:
        shutil.rmtree(root)


def test_cli_export_without_snapshot_fails_clean(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        assert main(["--root", root, "export",
                     "--instrument", "US-CLI-DEMO"]) == 1
        assert "снапшотов нет" in capsys.readouterr().err
    finally:
        shutil.rmtree(root)


def test_cli_watchlist_lifecycle_and_coverage(capsys):
    root = _root()
    try:
        assert main(["--root", root, "init"]) == 0
        assert main(["--root", root, "demo"]) == 0
        assert main(["--root", root, "ingest",
                     "--instrument", "US-CLI-DEMO"]) == 0
        capsys.readouterr()

        # create / add / show
        assert main(["--root", root, "watchlist", "create", "w-demo",
                     "--name", "Демо"]) == 0
        assert main(["--root", root, "watchlist", "add", "w-demo",
                     "--instrument", "US-CLI-DEMO",
                     "--note", "первый"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "watchlist", "show", "w-demo"]) == 0
        shown = json.loads(capsys.readouterr().out)
        assert shown["current_version"] == 2          # add — новая версия
        assert [m["instrument_id"]
                for m in shown["members"]] == ["US-CLI-DEMO"]

        # snapshot строит покрытие: все восемь блоков существуют
        assert main(["--root", root, "snapshot",
                     "--instrument", "US-CLI-DEMO"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "coverage", "US-CLI-DEMO"]) == 0
        cov_lines = capsys.readouterr().out.strip().splitlines()
        assert len(cov_lines) == 8
        assert any(l.startswith("US-CLI-DEMO\tfundamentals\t")
                   for l in cov_lines)
        assert any("peer_set" in l and "missing" in l for l in cov_lines)

        # coverage по списку
        assert main(["--root", root, "coverage",
                     "--watchlist", "w-demo"]) == 0
        assert len(capsys.readouterr().out.strip().splitlines()) == 8

        # rollback: новая версия, копирующая состав версии 1 (пустой)
        assert main(["--root", root, "watchlist", "rollback", "w-demo",
                     "--to", "1"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "watchlist", "show", "w-demo"]) == 0
        shown = json.loads(capsys.readouterr().out)
        assert shown["current_version"] == 3   # create v1, add v2, rollback v3
        assert shown["action"] == "rollback:1"
        assert shown["members"] == []
    finally:
        shutil.rmtree(root)


def test_cli_metrics_budget_watchlist_import_export(capsys):
    root = _root()
    try:
        assert main(["--root", root, "init"]) == 0
        # demo+ingest создают демо-инструмент, на который ссылается watchlist
        assert main(["--root", root, "demo"]) == 0
        assert main(["--root", root, "ingest",
                     "--instrument", "US-CLI-DEMO"]) == 0
        capsys.readouterr()

        # metrics: пустая база — «нет данных», запись ничего не выдумывает
        assert main(["--root", root, "metrics"]) == 0
        out = capsys.readouterr().out
        assert "provider_success_rate" in out
        assert "нет данных" in out
        assert main(["--root", root, "metrics", "--record"]) == 0

        # budget: провайдер не работал — честный ноль
        assert main(["--root", root, "budget"]) == 0
        out = capsys.readouterr().out
        assert "потолок запросов за ночь: 5000" in out
        assert "использовано 0, отказано 0" in out

        # watchlist export/import через файл
        assert main(["--root", root, "watchlist", "create", "w-io",
                     "--name", "IO"]) == 0
        assert main(["--root", root, "watchlist", "add", "w-io",
                     "--instrument", "US-CLI-DEMO"]) == 0
        capsys.readouterr()
        import os
        csv_path = os.path.join(root, "watchlist.csv")
        assert main(["--root", root, "watchlist", "export", "--list", "w-io",
                     "--format", "csv"]) == 0
        assert "ticker,market,isin,industry,note,added_at" in \
            capsys.readouterr().out

        # import: тикер не разрешается (нет тикерной истории) — отчёт,
        # ничего не добавлено молча
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("ticker,market,isin,industry,note,added_at\n"
                     "ZZZZ,US,,,x,2026-09-08\n")
        assert main(["--root", root, "watchlist", "import", csv_path,
                     "--list", "w-io"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["added"] == []
        assert report["not_found"][0]["ticker"] == "ZZZZ"

        # ingest --source edgar: провайдер существует (U5); у демо-эмитента
        # нет CIK — конвейер честно отрабатывает E1 и не выдумывает данных
        assert main(["--root", root, "ingest", "--instrument", "US-CLI-DEMO",
                     "--source", "edgar"]) == 0
        out = capsys.readouterr().out
        assert "US-CLI-DEMO: заданий закрыто: 0" in out
        capsys.readouterr()
        assert main(["--root", root, "coverage",
                     "--instrument", "US-CLI-DEMO", "--json"]) == 0
        cov = json.loads(capsys.readouterr().out)
        errors = [r for r in cov["rows"] if r["status"] == "error"]
        assert any("E1" in (r["reason"] or "") for r in errors)
    finally:
        shutil.rmtree(root)


def test_cli_verify_triggers_recompute_of_derived_measure(capsys):
    """TASK-8 U2: исправление факта доезжает до производных мер —
    новая версия снапшота, значение изменилось, версия напечатана."""
    import os
    import sqlite3
    import uuid as _uuid

    from rusterm.core.snapshot import SnapshotBuilder
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import (
        Instrument, InstrumentRepo, Issuer, RawRepo, RepoRegistry,
    )

    root = _root()
    try:
        paths = AppPaths.from_root(root)
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))
        obj = repos.raw.put(b'{"synthetic": "seed"}',
                            provider="synthetic", block="fundamentals")
        fact_ids = {}
        for concept, value in (("revenue", "1000"), ("net_income", "100")):
            fid = str(_uuid.uuid4())
            fact_ids[concept] = fid
            repos.fact.insert_fact(
                fact_id=fid, issuer_id="i1", listing_id=None,
                concept=concept, period_start="2024-01-01",
                period_end="2024-12-31", period_type="duration",
                value=value, unit="USD", currency=None,
                basis="as_reported", origin="extracted",
                source_ref=obj.sha256,
                locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                         "fact_id": fid, "concept": concept},
                parser_version="synthetic.v1",
                canonical_concept=concept)
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build("ins1", "i1", "2024-12-31")
        v1 = repos.snapshot.latest_snapshot_id("ins1")
        old_margin = [m[4] for m in repos.snapshot.get_measures(v1)
                      if m[3] == "net_margin"][0]
        conn.close()

        # CLI: verify по факту выручки — питает производную net_margin
        assert main(["--root", root, "verify",
                     "--fact", fact_ids["revenue"],
                     "--expected", "2000",
                     "--document", "https://example.com/filing"]) == 0
        out = capsys.readouterr().out
        assert "superseded" in out
        assert "пересчитано:" in out
        assert "нет мер с lineage" not in out

        # в новой версии снапшота мера изменилась
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        repos2 = RepoRegistry(conn, paths)
        v2 = repos2.snapshot.latest_snapshot_id("ins1")
        assert v2 != v1
        new_margin = [m[4] for m in repos2.snapshot.get_measures(v2)
                      if m[3] == "net_margin"][0]
        assert new_margin != old_margin
        assert new_margin == repr(100.0 / 2000.0)
        conn.close()
    finally:
        shutil.rmtree(root)


def test_u3_demo_flow_yields_non_null_measures(capsys):
    """TASK-8 U3: demo → ingest → snapshot даёт хотя бы одну меру со
    значением, и строка снапшота разделяет значения и пустые."""
    import sqlite3

    root = _root()
    try:
        assert main(["--root", root, "demo"]) == 0
        assert main(["--root", root, "ingest",
                     "--instrument", "US-CLI-DEMO"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "snapshot",
                     "--instrument", "US-CLI-DEMO"]) == 0
        out = capsys.readouterr().out
        assert "со значением" in out and "пусто" in out
        # хотя бы одна мера с непустым значением — в базе
        conn = sqlite3.connect(f"{root}/rusterm.db")
        values = conn.execute(
            "SELECT m.value FROM measure m").fetchall()
        conn.close()
        assert any(v[0] is not None for v in values), \
            "демо-снапшот без единого значения"
    finally:
        shutil.rmtree(root)


def test_u3_no_selector_exits_one(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        assert main(["--root", root, "ingest"]) == 1
        err = capsys.readouterr().err
        assert "--instrument ID" in err
        assert "--ticker T --market M" in err
        assert "--watchlist ID" in err
        assert main(["--root", root, "snapshot"]) == 1
        assert "--instrument ID" in capsys.readouterr().err
    finally:
        shutil.rmtree(root)


def test_u3_unresolved_ticker_exits_one_listing_candidates(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        assert main(["--root", root, "ingest", "--ticker", "NOPE",
                     "--market", "US"]) == 1
        err = capsys.readouterr().err
        assert "NOPE" in err and "не разрешён" in err
    finally:
        shutil.rmtree(root)


def test_u3_two_instruments_two_snapshots_two_exports(capsys):
    """Два разных инструмента в одной базе: сбор, снапшот и экспорт
    каждого по --instrument; снапшоты и файлы разные."""
    import os
    import sqlite3
    import uuid as _uuid

    from rusterm.store.paths import AppPaths
    from rusterm.store.repos import (
        Instrument, InstrumentRepo, Issuer,
    )

    root = _root()
    try:
        main(["--root", root, "init"])
        # второй инструмент добавляем в справочник напрямую
        paths = AppPaths.from_root(root)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        instruments = InstrumentRepo(conn)
        instruments.upsert_issuer(Issuer(
            "i-second", "Second Corp (synthetic)", "US", None, None,
            "us_gaap", "USD"))
        instruments.upsert_instrument(Instrument(
            "US-SECOND", "i-second", None, "common", "active", None))
        conn.close()

        assert main(["--root", root, "demo"]) == 0
        assert main(["--root", root, "ingest",
                     "--instrument", "US-CLI-DEMO"]) == 0
        assert main(["--root", root, "ingest",
                     "--instrument", "US-SECOND"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "snapshot",
                     "--instrument", "US-CLI-DEMO"]) == 0
        assert main(["--root", root, "snapshot",
                     "--instrument", "US-SECOND"]) == 0
        capsys.readouterr()

        conn = sqlite3.connect(f"{root}/rusterm.db")
        ids = [r[0] for r in conn.execute(
            "SELECT DISTINCT snapshot_id FROM snapshot ORDER BY snapshot_id")]
        conn.close()
        assert len(ids) == 2, f"ожидались два разных снапшота, {ids}"

        out_a = os.path.join(root, "export_a.json")
        out_b = os.path.join(root, "export_b.json")
        assert main(["--root", root, "export", "--instrument", "US-CLI-DEMO",
                     "--out", out_a]) == 0
        assert main(["--root", root, "export", "--instrument", "US-SECOND",
                     "--out", out_b]) == 0
        assert os.path.exists(out_a) and os.path.exists(out_b)
        assert open(out_a).read() != open(out_b).read()
    finally:
        shutil.rmtree(root)


def test_u3_watchlist_selector_ingests_current_members(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        main(["--root", root, "demo"])
        main(["--root", root, "watchlist", "create", "w-sel", "--name", "S"])
        main(["--root", root, "watchlist", "add", "w-sel",
              "--instrument", "US-CLI-DEMO"])
        capsys.readouterr()
        assert main(["--root", root, "ingest", "--watchlist", "w-sel"]) == 0
        out = capsys.readouterr().out
        assert "US-CLI-DEMO:" in out, "участник списка не прошёл сбор"
    finally:
        shutil.rmtree(root)


# ── TASK-8 U9: цельная программа — usage, status, коды выхода, --json ──
def test_u9_bare_command_prints_usage_and_data_dir(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Каталог данных" in out
    assert "rusterm init" in out
    assert "rusterm ingest" in out
    assert "rusterm snapshot" in out
    assert "watchlist" in out


def test_u9_status_fresh_db_reports_zero_without_inventing(capsys):
    root = _root()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "status"]) == 0
        out = capsys.readouterr().out
        assert "инструментов: 0" in out
        assert "снапшотов нет" in out
        assert "покрытие: готово 0" in out
    finally:
        shutil.rmtree(root)


def test_u9_status_after_demo_flow_reports_snapshot_and_coverage(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        main(["--root", root, "demo"])
        main(["--root", root, "ingest", "--instrument", "US-CLI-DEMO"])
        main(["--root", root, "snapshot", "--instrument", "US-CLI-DEMO"])
        capsys.readouterr()
        assert main(["--root", root, "status", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["instruments"] == 1
        assert payload["schema_version"] == 36
        assert len(payload["snapshots"]) == 1
        assert payload["snapshots"][0]["version"] == 1
        assert payload["coverage"]["ready"] >= 1
        assert "RUSTERM_SEC_UA" in payload["env"]["vars"]
    finally:
        shutil.rmtree(root)


def test_u9_unresolved_ticker_no_traceback(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        assert main(["--root", root, "snapshot", "--ticker", "NOPE",
                     "--market", "US"]) == 1
        err = capsys.readouterr().err
        assert "Traceback" not in err
        assert "NOPE" in err
    finally:
        shutil.rmtree(root)


def test_u9_json_flag_parses_for_all_four_commands(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        main(["--root", root, "demo"])
        main(["--root", root, "ingest", "--instrument", "US-CLI-DEMO"])
        main(["--root", root, "snapshot", "--instrument", "US-CLI-DEMO"])
        capsys.readouterr()
        for argv in (["status"], ["coverage", "--instrument", "US-CLI-DEMO"],
                     ["metrics"], ["budget"]):
            assert main(["--root", root, *argv, "--json"]) == 0
            payload = json.loads(capsys.readouterr().out)
            assert isinstance(payload, dict)
    finally:
        shutil.rmtree(root)


def test_u10_console_entry_point_as_subprocess(capsys):
    """TASK-8 U10: точка входа работает как процесс — и как модуль,
    и как установленный консольный скрипт."""
    import subprocess
    import sys

    bare = subprocess.run([sys.executable, "-m", "rusterm.cli"],
                          capture_output=True, text=True)
    assert bare.returncode == 0
    assert "Каталог данных" in bare.stdout
    assert "rusterm init" in bare.stdout

    import shutil
    installed = shutil.which("rusterm")
    if installed:  # скрипт появляется после pip install -e .
        run = subprocess.run([installed], capture_output=True, text=True)
        assert run.returncode == 0
        assert "Каталог данных" in run.stdout
