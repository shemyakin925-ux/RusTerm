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
