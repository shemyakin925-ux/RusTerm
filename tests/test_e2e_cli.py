"""TASK-11 X1: весь путь четырьмя командами в отдельных процессах.

init → add → ingest --source edgar → snapshot на эмитенте из двадцатки.
EDGAR ходит через подменный транспорт (sitecustomize на PYTHONPATH),
настоящая сеть не трогается. Повторный проход не создаёт ничего нового.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STUB = REPO / "tests" / "e2e_stub"

TICKER = "AAPL"
ENV = {
    **os.environ,
    "RUSTERM_SEC_UA": "Synthetic Test e2e.invalid",
    "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
    "PYTHONPATH": os.pathsep.join([str(STUB), str(REPO),
                                   os.environ.get("PYTHONPATH", "")]),
    "TERM": "xterm",
}


def _make_run(root):
    def _run(*argv):
        return subprocess.run([sys.executable, "-m", "rusterm.cli",
                               "--root", root, *argv],
                              capture_output=True, text=True, env=ENV)
    return _run


def test_x1_four_commands_end_to_end_twice():
    tmpdir = tempfile.mkdtemp()
    root = tmpdir
    _run = _make_run(root)
    try:
        # 1. init
        assert _run("init").returncode == 0
        # 2. add — эмитент называется настоящим именем
        r = _run("add", "--ticker", TICKER, "--market", "US")
        assert r.returncode == 0, r.stderr
        assert "Apple Inc." in r.stdout
        # 3. ingest --source edgar — факты есть, неотображённых нет
        r = _run("ingest", "--ticker", TICKER, "--market", "US",
                 "--source", "edgar")
        assert r.returncode == 0, r.stderr
        assert "фактов: 0" not in r.stdout
        assert "неотображённых концептов: 0" in r.stdout
        # 4. snapshot — не меньше восьми мер со значением
        r = _run("snapshot", "--ticker", TICKER, "--market", "US")
        assert r.returncode == 0, r.stderr
        values_line = next(line for line in r.stdout.splitlines()
                           if "со значением" in line)
        count = int(values_line.split("со значением")[1].split(",")[0]
                    .strip())
        assert count >= 8, f"мер со значением {count}, ожидалось >= 8"

        # весь путь без трейсбеков в журнале
        log = (Path(tmpdir) / "logs" / "app.log")
        if log.exists():
            assert "Traceback" not in log.read_text(encoding="utf-8")

        # повтор всего пути: ничего нового, все коды 0
        db = str(Path(tmpdir) / "rusterm.db")
        import sqlite3
        conn = sqlite3.connect(db)
        before = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("issuer", "instrument", "fact", "raw_object")
        }
        conn.close()
        assert _run("add", "--ticker", TICKER, "--market", "US").returncode == 0
        assert _run("ingest", "--ticker", TICKER, "--market", "US",
                    "--source", "edgar").returncode == 0
        assert _run("snapshot", "--ticker", TICKER, "--market", "US"
                    ).returncode == 0
        conn = sqlite3.connect(db)
        after = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("issuer", "instrument", "fact", "raw_object")
        }
        conn.close()
        assert before == after, "повторный путь что-то создал"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_y5_ingest_with_known_cik_makes_exactly_one_request():
    """TASK-12 Y5: ingest --source edgar при известном CIK делает ровно
    один запрос — companyfacts. Тёплого прогона карты тикеров больше
    нет: CIK приходит из issuer.registry_id, а resolve тянул всю карту
    и выбрасывал результат. Счётчик — подменный транспорт, каждый
    прошедший запрос дописывает URL в лог (эквивалент gate.calls_made
    для подпроцесса: gate считает те же запросы, что проходит
    транспорт)."""
    tmpdir = tempfile.mkdtemp()
    root = tmpdir
    _run = _make_run(root)
    call_log = Path(tmpdir) / "edgar_calls.txt"
    try:
        assert _run("init").returncode == 0
        # add создаёт эмитента с CIK (из карты тикеров) — сам считает
        # один запрос, до старта счётчика
        r = _run("add", "--ticker", TICKER, "--market", "US")
        assert r.returncode == 0, r.stderr
        env = dict(ENV)
        env["RUSTERM_EDGAR_CALL_LOG"] = str(call_log)
        r = subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root,
             "ingest", "--ticker", TICKER, "--market", "US",
             "--source", "edgar"],
            capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
        calls = [line for line in
                 call_log.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        assert len(calls) == 1, (
            f"ingest сделал {len(calls)} запросов: {calls}")
        assert "companyfacts" in calls[0], calls
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
