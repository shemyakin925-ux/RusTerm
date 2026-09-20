"""ТЗ-68 N2: отказ учит — что нужно, где взять, в какую переменную.
Подстановка из констант провайдера (тест monkeypatch-ит и проверяет,
что подменённое доехало до сообщения); SEC_UA — контакт, а не секрет."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

ENV_KEYS = ("RUSTERM_SEC_UA", "RUSTERM_TWELVEDATA_KEY",
            "RUSTERM_LLM_API_KEY")


def _app(tmp_path: Path) -> str:
    return str(tmp_path / "app")


def _run(root: str, *argv, env_extra=None):
    env = {**os.environ, "RUSTERM_ENV_FILE": "/nonexistent/n2.env"}
    for k in ENV_KEYS:
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
        capture_output=True, text=True, cwd=REPO, env=env, timeout=300)


def test_sec_ua_refusal_teaches(tmp_path):
    root = _app(tmp_path)
    assert _run(root, "init").returncode == 0
    assert _run(root, "add", "--ticker", "AAPL", "--name", "Apple",
                "--market", "US", "--cik", "320193").returncode == 0
    r = _run(root, "ingest", "--source", "edgar", "--instrument",
             "US-AAPL")
    assert r.returncode != 0
    assert "sec_ua_unset" in r.stderr
    assert "что делать:" in r.stderr
    assert "RUSTERM_SEC_UA" in r.stderr
    assert "не секрет" in r.stderr


def test_twelvedata_refusal_teaches(tmp_path):
    root = _app(tmp_path)
    assert _run(root, "init").returncode == 0
    assert _run(root, "add", "--ticker", "AAPL", "--name", "Apple",
                "--market", "US", "--cik", "320193").returncode == 0
    r = _run(root, "ingest", "--source", "twelvedata", "--instrument",
             "US-AAPL")
    assert r.returncode != 0
    assert "twelvedata_key_unset" in r.stderr
    assert "что делать:" in r.stderr
    assert "RUSTERM_TWELVEDATA_KEY" in r.stderr
