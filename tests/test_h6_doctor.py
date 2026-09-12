"""ТЗ-21 H6: doctor знает новые формы — документы в обе стороны,
ручной факт без документа, строки реестра без модуля провайдера,
покрытие по рынкам. Повреждённая база называет все четыре; здоровая
молчит. SQL — в слое хранилища (doctor.py), тесты зовут doctor_report.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pytest

import rusterm.markets as markets_module
from rusterm.markets import Market
from rusterm.store.db import apply_migrations
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (DocumentRepo, Instrument, Issuer,
                                 RawRepo, RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    yield paths, conn
    conn.close()
    shutil.rmtree(str(paths.root), ignore_errors=True)


def _add_issuer_with_manual_fact(conn, paths, issuer_id: str = "cik-1",
                                 instrument_id: str = "US-X",
                                 fact_sha: str = "d" * 64) -> None:
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, "Corp X", "US", "1", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES ('f-1', ?, 'revenue', '2024-01-01', '2024-12-31',
           'duration', '100', 'USD', 'USD', 'as_reported', 'extracted',
           ?, '{}', 'manual.v1', 'ok', 0, 'revenue', 'manual')""",
        (issuer_id, fact_sha))


def test_h6_clean_db_reports_ok(env):
    paths, conn = env
    report = doctor_report(paths, conn)
    assert report["ok"] is True
    assert report["registry_gaps"] == []
    assert report["documents"] == {"rows": 0, "rows_without_file": 0,
                                   "imported_files_without_row": 0}
    assert report["manual_facts_missing_document"] == 0
    assert set(report["market_coverage"]) == {
        "US", "CA", "OTC", "KR", "BR", "AU"}
    for code, cov in report["market_coverage"].items():
        assert cov == {"issuers": 0, "facts": 0, "last_collection": None}, \
            (code, cov)


def _damage(paths, conn, monkeypatch) -> None:
    """Четыре повреждения, по одному на каждую новую форму H6."""
    # 1. строка document без файла на диске
    DocumentRepo(conn).put("c" * 64, "annual.pdf", "pdf", 12, 1000,
                           issuer_id="cik-1")

    # 2. импортированный файл (raw provider='manual-import') без строки
    #    document — RawRepo документ-строку не создаёт
    RawRepo(paths, conn).put(b"manual document body",
                             provider="manual-import", block="manual")

    # 3. ручной факт, чей документ не существует
    _add_issuer_with_manual_fact(conn, paths)

    # 4. строка реестра с отсутствующим модулем провайдера
    fake = Market(code="XX", jurisdiction="XX", venue_kind="exchange",
                  provider="nosuch", identifier="x",
                  default_taxonomy="ifrs-full", access="manual")
    real = markets_module.MARKETS
    monkeypatch.setattr(markets_module, "MARKETS", (*real, fake))


def test_h6_names_all_four_on_damaged_db(env, monkeypatch):
    paths, conn = env
    _damage(paths, conn, monkeypatch)

    report = doctor_report(paths, conn)
    assert report["ok"] is False
    named = " ".join(report["problems"])
    assert "документов в базе без файла в raw-хранилище: 1" in named
    assert "импортированных файлов без строки document: 1" in named
    assert "ручных фактов без документа-источника: 1" in named
    assert "рынков с нереализованным провайдером: XX:nosuch" in named
    assert report["registry_gaps"] == [{"code": "XX",
                                        "provider": "nosuch",
                                        "status":
                                        "provider_not_implemented"}]

    # покрытие по рынкам видит созданный US-эмитент и его факт
    cov = report["market_coverage"]
    assert cov["US"] == {"issuers": 1, "facts": 1,
                         "last_collection": None}
    assert cov["OTC"]["issuers"] == 0, \
        "OTC не должен дублировать счётчик US по юрисдикции"


def test_h6_cli_exit_zero_on_healthy_one(env, capsys, monkeypatch):
    """Через CLI: здоровая база — код 0, отчёт печатается целиком."""
    import rusterm.cli as cli
    paths, conn = env
    conn.close()
    monkeypatch.setattr(cli, "_open", lambda root: (paths,
                                                    sqlite3.connect(
                                                        str(paths.db_path),
                                                        timeout=30,
                                                        isolation_level=None)))
    code = cli.main(["--root", str(paths.root), "doctor"])
    assert code == 0
    import json
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["market_coverage"]["US"]["issuers"] == 0


def test_h6_cli_names_all_four_on_damaged_db(env, capsys, monkeypatch):
    """Через CLI: повреждённая база — код 1 и все четыре формы поимённо
    в отчёте (Done-when H4 требует именно python3 -m rusterm.cli
    doctor)."""
    import json

    import rusterm.cli as cli
    paths, conn = env
    _damage(paths, conn, monkeypatch)
    conn.close()
    monkeypatch.setattr(cli, "_open", lambda root: (paths,
                                                    sqlite3.connect(
                                                        str(paths.db_path),
                                                        timeout=30,
                                                        isolation_level=None)))
    assert cli.main(["--root", str(paths.root), "doctor"]) == 1
    payload = json.loads(capsys.readouterr().out)
    named = " ".join(payload["problems"])
    for phrase in ("документов в базе без файла",
                   "импортированных файлов без строки document",
                   "ручных фактов без документа-источника",
                   "рынков с нереализованным провайдером: XX:nosuch"):
        assert phrase in named, phrase
