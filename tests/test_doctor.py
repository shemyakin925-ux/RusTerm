"""Тесты дрейфа raw store и базы в doctor (BACKLOG B9)."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

from rusterm.store.db import apply_migrations
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir




# ── BACKLOG B9: дрейф raw store и базы в обе стороны ───────────────────
def test_doctor_names_orphan_row_and_orphan_file():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    try:
        apply_migrations(conn)
        # строка в базе, файла нет
        conn.execute(
            "INSERT INTO raw_object(sha256, provider, fetched_at, bytes,"
            " content_type, compression)"
            " VALUES (?, 'synthetic', 0, 3, 'application/json', 'none')",
            ("a" * 64,))
        # файл в store, строки нет
        store_dir = paths.raw_store / "aa"
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / ("b" * 64)).write_bytes(b"orphan payload")

        report = doctor_report(paths, conn)
        assert report["ok"] is False
        named = " ".join(report["problems"])
        assert "raw_object без файла: 1" in named
        assert "файлов в raw/store без строки в базе: 1" in named
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_doctor_silent_when_store_and_db_agree():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    try:
        apply_migrations(conn)
        from rusterm.store.repos import RawRepo
        RawRepo(paths, conn).put(b'{"synthetic": "ok"}',
                                 provider="synthetic",
                                 block="fundamentals")
        report = doctor_report(paths, conn)
        drift = [p for p in report["problems"]
                 if "raw_object без файла" in p
                 or "raw/store без строки" in p]
        assert drift == []
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_c4_doctor_names_state_orphans_and_dropped_index(capsys):
    """TASK-15 C4: два новых дрейфа видны doctor'у — строка
    issuer_ingest_state без эмитента и уроненный индекс схемы; exit 1,
    в отчёте названы оба."""
    import json
    from rusterm.cli import main
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    try:
        apply_migrations(conn)
        conn.execute(
            "INSERT INTO issuer(issuer_id, name, jurisdiction,"
            " reporting_standard, reporting_currency)"
            " VALUES ('i1', 'Issuer 1', 'US', 'us_gaap', 'USD')")
        conn.execute(
            "INSERT INTO issuer_ingest_state(issuer_id, source,"
            " last_filing_date, updated_at)"
            " VALUES ('i1', 'edgar', '2026-01-01', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO issuer(issuer_id, name, jurisdiction,"
                     " reporting_standard, reporting_currency)"
                     " VALUES ('i2', 'Ghost', 'US', 'us_gaap', 'USD')")
        conn.execute(
            "INSERT INTO issuer_ingest_state(issuer_id, source,"
            " last_filing_date, updated_at)"
            " VALUES ('i2', 'edgar', '2026-02-02', '2026-02-02T00:00:00Z')")
        # осиротить строку состояния: FK отключается только на время
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM issuer WHERE issuer_id='i2'")
        conn.execute("PRAGMA foreign_keys=ON")
        # уронить индекс
        conn.execute("DROP INDEX idx_measure_snapshot")
        assert conn.execute(
            "PRAGMA foreign_keys").fetchone()[0] == 1
        conn.close()

        import io
        assert main(["--root", tmpdir, "doctor"]) == 1
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is False
        named = " ".join(report["problems"])
        assert "строк issuer_ingest_state без эмитента: 1" in named
        assert "idx_measure_snapshot" in named
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── BACKLOG B24: счётчики по хостам видны в doctor ─────────────────────

def test_doctor_shows_per_host_used_and_ceiling_after_fake_run(capsys):
    """B24: после подставного прогона (RequestGate с двумя HostLimit)
    doctor печатает для каждого хоста used и ceiling рядом."""
    import json as _json
    from rusterm import cli as cli_module
    from rusterm.core.metrics import record_host_usage
    from rusterm.providers.budget import (
        BudgetExceeded, HostLimit, NetworkGate, RequestGate)
    from rusterm.store.repos import RepoRegistry

    tmpdir = tempfile.mkdtemp()
    try:
        assert cli_module.main(["--root", tmpdir, "init"]) == 0
        capsys.readouterr()
        paths = AppPaths.from_root(tmpdir)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        repos = RepoRegistry(conn, paths)

        gate = RequestGate(gate=NetworkGate(
            environ={"RUSTERM_SEC_UA": "Synthetic Test b24.invalid"}))
        dart = HostLimit("opendart.fss.or.kr", per_second=1000.0,
                         nightly_max=3)
        sec = HostLimit("data.sec.gov", per_second=1000.0, nightly_max=5)
        send = lambda headers: "ok"
        assert gate.request(send, limit=dart) == "ok"
        assert gate.request(send, limit=dart) == "ok"
        assert gate.request(send, limit=dart) == "ok"
        assert isinstance(gate.request(send, limit=dart), BudgetExceeded)
        assert gate.request(send, limit=sec) == "ok"

        written = record_host_usage(repos.metrics, gate)
        assert written == 2  # оба пула тронуты
        conn.close()

        assert cli_module.main(["--root", tmpdir, "doctor"]) == 0
        report = _json.loads(capsys.readouterr().out)
        budget = report["request_budget"]
        # used — из проб прогона; ceiling — штатный из объявлений
        # реестра (5000/хост), а не сессионный лимит подставного прогона
        assert budget["opendart.fss.or.kr"]["used"] == 3
        assert budget["opendart.fss.or.kr"]["ceiling"] == 5000
        assert budget["data.sec.gov"]["used"] == 1
        assert budget["data.sec.gov"]["ceiling"] == 5000
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
