"""TASK-15 C6: инкрементальный проход против живого фида SEC EDGAR.

Два настоящих эмитента, чьи CIK уже известны из записанных payload
(tests/data/edgar) — эмитенты сеются в базу напрямую, поэтому `add`
и карта тикеров запросов не тратят. Два подряд refresh --watchlist:
первый качает, второй видит «не изменилось» — 2 submissions, 0
companyfacts, ни одной новой строки. Потолок пункта — 8 запросов.
Без RUSTERM_SEC_UA тест пропускается чисто (N2/N7); приложение читает
контакт из ~/.rusterm.env само.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry, WatchlistRepo

REPO = Path(__file__).resolve().parents[1]
# CIK из записанных payload: комиссия эмитента уже зафиксирована в git,
# живая карта тикеров для C6 не нужна
C6_ISSUERS = (("AAPL", json.loads(
    (REPO / "tests" / "data" / "edgar" / "companyfacts_m3_AAPL.json")
    .read_bytes())["cik"]),
    ("MSFT", json.loads(
        (REPO / "tests" / "data" / "edgar" / "companyfacts_m3_MSFT.json")
        .read_bytes())["cik"]))


def _live_ua() -> str | None:
    from rusterm import env as env_module
    env_module.load_env()
    return os.environ.get("RUSTERM_SEC_UA")


@pytest.mark.integration
def test_c6_live_incremental_second_pass_zero_downloads():
    if not _live_ua():
        pytest.skip("SEC_UA UNSET — network path not exercised")

    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join(
               [str(REPO), os.environ.get("PYTHONPATH", "")]),
           "TERM": "xterm"}

    def run(root, *argv):
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=env)

    def counts(root):
        db = sqlite3.connect(f"{root}/rusterm.db")
        try:
            return [db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("raw_object", "fact", "job")]
        finally:
            db.close()

    tmpdir = tempfile.mkdtemp()
    root = tmpdir
    try:
        paths = AppPaths.from_root(root)
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        wl = WatchlistRepo(conn)
        wl.create_watchlist("live", "два эмитента", None, None)
        wl.new_version("wv-live", "live", 1, "create", None)
        vid = wl.current_version("live")["watchlist_version_id"]
        for ticker, cik in C6_ISSUERS:
            repos.instrument.upsert_issuer(Issuer(
                f"i-{ticker}", f"{ticker} Corp (live)", "US", str(cik),
                None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"in-{ticker}", f"i-{ticker}", None, "common", "active",
                None))
            wl.add_member(vid, f"in-{ticker}", None)
        conn.close()

        # проход 1: по submissions и companyfacts на эмитента
        r = run(root, "refresh", "--watchlist", "live", "--json")
        assert r.returncode == 0, r.stderr
        first = json.loads(r.stdout)
        assert all(res["action"] == "updated" for res in first["results"]), \
            first["results"]
        assert first["requests"] == {"submissions": 2, "companyfacts": 2}, \
            first["requests"]

        # проход 2: только submissions, ничего не создаётся
        before = counts(root)
        r = run(root, "refresh", "--watchlist", "live", "--json")
        assert r.returncode == 0, r.stderr
        second = json.loads(r.stdout)
        assert all(res["action"] == "unchanged"
                   for res in second["results"]), second["results"]
        assert second["requests"] == {"submissions": 2, "companyfacts": 0}, \
            second["requests"]
        assert counts(root) == before, "второй проход создал строки"

        total = (first["requests"]["submissions"]
                 + first["requests"]["companyfacts"]
                 + second["requests"]["submissions"]
                 + second["requests"]["companyfacts"])
        print(f"C6 live: {total} requests across two passes")
        assert total <= 8, f"C6 израсходовал {total} запросов из 8"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
