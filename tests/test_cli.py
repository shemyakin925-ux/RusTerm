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
        assert "schema_version=33" in out

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

        # verify: manual-факт superseded извлечённый
        assert main(["--root", root, "verify",
                     "--concept", "revenue", "--value", "777"]) == 0
        out = capsys.readouterr().out
        assert "superseded" in out

        # doctor: база в порядке
        assert main(["--root", root, "doctor"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is True
        assert report["schema_version"] == 33
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
