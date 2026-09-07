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
        assert "schema_version=35" in out

        # ingest: сбор по синтетическому провайдеру
        assert main(["--root", root, "ingest"]) == 0
        out = capsys.readouterr().out
        assert "фактов: 4" in out

        # snapshot: сборка версии
        assert main(["--root", root, "snapshot"]) == 0
        out = capsys.readouterr().out
        assert "снапшот v1" in out
        assert "мер:" in out

        # export json: значения из снапшота
        assert main(["--root", root, "export", "--format", "json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["snapshot"]["instrument_id"] == "US-CLI-DEMO"
        assert payload["measures"], "экспорт пуст"

        # export csv в файл
        import os
        csv_path = os.path.join(root, "export.csv")
        assert main(["--root", root, "export", "--format", "csv",
                     "--out", csv_path]) == 0
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
        assert report["schema_version"] == 35
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


def test_cli_export_without_snapshot_fails_clean(capsys):
    root = _root()
    try:
        main(["--root", root, "init"])
        capsys.readouterr()
        assert main(["--root", root, "export"]) == 1
        assert "снапшотов нет" in capsys.readouterr().err
    finally:
        shutil.rmtree(root)


def test_cli_watchlist_lifecycle_and_coverage(capsys):
    root = _root()
    try:
        assert main(["--root", root, "init"]) == 0
        assert main(["--root", root, "ingest"]) == 0
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
        assert main(["--root", root, "snapshot"]) == 0
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
        # ingest создаёт демо-инструмент, на которого ссылается watchlist
        assert main(["--root", root, "ingest"]) == 0
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

        # ingest --source edgar: провайдера нет, честная ошибка
        assert main(["--root", root, "ingest", "--source", "edgar"]) == 1
        assert "edgar-провайдер недоступен" in capsys.readouterr().err
    finally:
        shutil.rmtree(root)
