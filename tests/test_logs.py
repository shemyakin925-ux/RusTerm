"""Тесты журналов (TASK-7 T13): три назначения, никогда не смешиваются.

audit.jsonl — добавление, по JSON-объекту на строку, переживает потерю
базы, никогда не ротируется. app.log — ротация 5 × 1 МБ. В журналах
нет URL с ключом или токеном.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from rusterm.applog import setup_app_logging
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import AuditRepo, RepoRegistry


def _registry():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return tmpdir, conn, paths, repos


def test_audit_line_survives_db_connection_closed():
    tmpdir, conn, paths, repos = _registry()
    try:
        repos.audit.log("snapshot", "ins1", None, True, "ok")
        conn.close()  # база «потерялась» посреди жизни приложения
        with pytest.raises(sqlite3.ProgrammingError):
            repos.audit.log("export", "ins1", None, True, "ok")
        with open(paths.audit_log_path, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh]
        assert [e["action"] for e in lines] == ["snapshot", "export"]
    finally:
        try:
            conn.close()
        except sqlite3.ProgrammingError:
            pass  # соединение уже закрыто тестом
        shutil.rmtree(tmpdir)


def test_audit_file_failure_does_not_lose_the_db_row():
    """B12: logs/ только для чтения — операция не теряется и не падает:
    log() возвращает причину значением, строка попадает в базу."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root игнорирует права каталога")
    tmpdir, conn, paths, repos = _registry()
    readonly = Path(tmpdir) / "readonly"
    readonly.mkdir()
    audit = AuditRepo(conn, audit_log_path=readonly / "logs" / "audit.jsonl")
    try:
        os.chmod(readonly, 0o555)
        outcome = audit.log("add", "US-AAPL", {"cik": 320193}, True, "ok")
        assert isinstance(outcome, str), \
            f"ожидалось значение ошибки, получено {outcome!r}"
        assert outcome.startswith("audit_file_unavailable"), outcome
        rows = conn.execute(
            "SELECT action, target FROM audit_log").fetchall()
        assert rows == [("add", "US-AAPL")], "строка потеряна"
        # рабочий путь по-прежнему пишет файл и возвращает None
        os.chmod(readonly, 0o755)
        assert repos.audit.log("export", "ins1", None, True, "ok") is None
        assert (paths.audit_log_path).exists()
    finally:
        os.chmod(readonly, 0o755)
        conn.close()
        shutil.rmtree(tmpdir)


def test_no_url_with_key_or_token_is_ever_logged():
    tmpdir, conn, paths, repos = _registry()
    try:
        repos.audit.log(
            "fetch",
            "https://api.example.com/data?token=SECRET123&id=7",
            {"url": "https://api.example.com/data?api_key=XYZ&q=a"},
            True, "ok")
        raw = open(paths.audit_log_path, encoding="utf-8").read()
        assert "SECRET123" not in raw and "XYZ" not in raw
        entry = json.loads(raw.splitlines()[0])
        assert entry["target"] == "https://api.example.com/data?id=7"
        assert entry["payload"]["url"] == "https://api.example.com/data?q=a"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_app_log_rotates_past_limit():
    tmpdir, conn, paths, repos = _registry()
    try:
        logger = setup_app_logging(paths.app_log_path)
        payload = "x" * 4096
        for i in range(300):  # 300 × 4 КБ > 1 МБ — ротация обязана случиться
            logger.info("%06d %s", i, payload)
        for handler in logging.getLogger("rusterm").handlers:
            handler.flush()
        assert paths.app_log_path.exists()
        rotated = paths.app_log_path.with_name(paths.app_log_path.name + ".1")
        assert rotated.exists(), "ротация не произошла на 5 × 1 МБ лимите"
        # B19: перерасход капа даёт ровно два файла (app.log + .1),
        # самый свежий (активный) держит последнюю строку
        siblings = sorted(p.name for p in paths.app_log_path.parent.glob(
            paths.app_log_path.name + "*"))
        assert siblings == ["app.log", "app.log.1"], siblings
        with open(paths.app_log_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        assert "000299" in lines[-1], \
            f"последняя строка не в свежем файле: {lines[-1][-40:]!r}"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_destinations_never_mix():
    tmpdir, conn, paths, repos = _registry()
    try:
        setup_app_logging(paths.app_log_path)
        logging.getLogger("rusterm").info("приложение стартовало")
        repos.audit.log("watchlist_import", "w1", {"rows": 4}, True, "ok")

        app_text = open(paths.app_log_path, encoding="utf-8").read()
        assert "приложение стартовало" in app_text
        assert '"action"' not in app_text, "аудит протёк в app.log"

        with open(paths.audit_log_path, encoding="utf-8") as fh:
            audit_lines = fh.read().splitlines()
        assert len(audit_lines) == 1
        entry = json.loads(audit_lines[0])
        assert entry["action"] == "watchlist_import"
        assert "INFO" not in audit_lines[0], "лог приложения протёк в аудит"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
