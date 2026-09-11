"""TASK-18 G2+G5: площадка из файла SEC и честный ответ эмитента без
 filings.

Свой hermetic-стаб в tmp: company_tickers.json (три тикера),
company_tickers_exchange.json (две строки: NYSE и OTC), companyfacts
для AAPL из записанного payload и 404 для NOFILE. G2: площадки
NYSE/OTC/unknown попадают в listing.exchange. G5: ingest для 404 —
exit 0, coverage missing no_sec_filings, ноль raw_object и fact,
сообщение на stdout.
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

REPO = Path(__file__).resolve().parents[1]


def _write_stub(stub_dir: Path) -> None:
    aapl = json.loads(
        (REPO / "tests" / "data" / "edgar"
         / "companyfacts_m3_AAPL.json").read_bytes())
    aapl_cik = aapl["cik"]                       # 320193
    nofile_cik = 9999999

    # формат настоящего company_tickers.json: {"0": {cik_str, ticker,
    # title}, "1": {...}, ...}
    tickers = {str(i): row for i, row in enumerate([
        {"cik_str": aapl_cik, "ticker": "AAPL", "title": "Apple Inc."},
        {"cik_str": nofile_cik, "ticker": "NOFILE",
         "title": "No Filings Corp"},
        {"cik_str": 8888888, "ticker": "ABSENT",
         "title": "Absent From Exchange File Corp"},
    ])}
    exchanges = {"fields": ["cik", "name", "ticker", "exchange"],
                 "data": [
        [aapl_cik, "Apple Inc.", "AAPL", "NasdaqGS"],
        [8888888, "OTC Listed Corp", "ABSENT", "OTC"],
    ]}  # NOFILE в файле бирж нет -> venue unknown

    aapl_path = (REPO / "tests" / "data" / "edgar"
                 / "companyfacts_m3_AAPL.json").resolve()
    code = """
import json
from pathlib import Path

_TICKERS = json.loads(%(tickers)r)
_EXCHANGES = json.loads(%(exchanges)r)
_AAPL = Path(%(aapl_path)r).read_bytes()
_NOFILE_KEY = "CIK%(nofile_cik)010d"
_AAPL_KEY = "CIK%(aapl_cik)010d"


def _transport(url, headers):
    if "company_tickers.json" in url:
        return 200, json.dumps(_TICKERS).encode(), {}
    if "company_tickers_exchange.json" in url:
        return 200, json.dumps(_EXCHANGES).encode(), {}
    if "companyfacts" in url:
        if _NOFILE_KEY in url:
            return 404, b"<html>404 not found</html>", {}
        if _AAPL_KEY in url:
            return 200, _AAPL, {}
    return 404, b"{}", {}


import rusterm.providers.edgar as _edgar


class _P(_edgar.EdgarProvider):
    def __init__(self, *a, **kw):
        kw.setdefault("transport", _transport)
        super().__init__(*a, **kw)


_edgar.EdgarProvider = _P
""" % {"tickers": json.dumps(tickers), "exchanges": json.dumps(exchanges),
       "aapl_path": str(aapl_path), "nofile_cik": nofile_cik,
       "aapl_cik": aapl_cik}
    (stub_dir / "sitecustomize.py").write_text(code, encoding="utf-8")


def test_g2_g5_venue_from_exchange_file_and_404_is_an_answer():
    env = {**os.environ,
           "RUSTERM_SEC_UA": "Synthetic Test e2e.invalid",
           "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
           "TERM": "xterm"}

    def run(root, *argv, stub=None):
        e = dict(env)
        e["PYTHONPATH"] = os.pathsep.join(
            [str(stub), str(REPO), os.environ.get("PYTHONPATH", "")])
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=e)

    tmpdir = tempfile.mkdtemp()
    stub = Path(tmpdir) / "stub"
    stub.mkdir()
    _write_stub(stub)
    root = str(Path(tmpdir) / "root")
    try:
        assert run(root, "init", stub=stub).returncode == 0
        for ticker in ("AAPL", "NOFILE", "ABSENT"):
            r = run(root, "add", "--ticker", ticker, "--market", "US",
                    stub=stub)
            assert r.returncode == 0, (ticker, r.stderr)

        db = sqlite3.connect(f"{root}/rusterm.db")
        try:
            listings = dict(db.execute(
                "SELECT i.instrument_id, l.exchange FROM listing l"
                " JOIN instrument i ON i.instrument_id = l.instrument_id"
            ).fetchall())
            assert listings["US-AAPL"] == "NasdaqGS"
            assert listings["US-ABSENT"] == "OTC"
            # NOFILE отсутствует в файле бирж: venue unknown, без исключения
            assert listings["US-NOFILE"] == "unknown"

            # G5: ingest NOFILE — companyfacts 404, exit 0, coverage
            # missing no_sec_filings, ни raw_object, ни fact
            r = run(root, "ingest", "--instrument", "US-NOFILE",
                    "--source", "edgar", stub=stub)
            assert r.returncode == 0, (r.returncode, r.stderr)
            assert "не подаёт XBRL" in r.stdout, r.stdout
            assert db.execute(
                "SELECT status, reason FROM coverage"
                " WHERE instrument_id='US-NOFILE'"
                " AND block='fundamentals'").fetchone() == \
                ("missing", "no_sec_filings")
            assert db.execute("SELECT COUNT(*) FROM raw_object"
                              ).fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM fact"
                              ).fetchone()[0] == 0
        finally:
            db.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
