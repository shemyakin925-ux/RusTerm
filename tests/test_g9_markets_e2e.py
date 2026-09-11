"""TASK-18 G9: end to end для новых рынков — add → ingest → snapshot →
export для одного CA (RY, ifrs-full) и одного OTC (CPTP, us-gaap)
эмитента против записанных payload'ов. Сохранённый эмитент несёт
юрисдикцию реестра и площадку файла бирж.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _write_stub(stub_dir: Path) -> None:
    def payload(ticker: str) -> str:
        return (REPO / "tests" / "data" / "edgar"
                / f"companyfacts_m6_{ticker}.json").resolve().as_posix()

    ry_cik = 1000275
    cptp_cik = 202947
    tickers = {str(i): row for i, row in enumerate([
        {"cik_str": ry_cik, "ticker": "RY", "title": "Royal Bank of Canada"},
        {"cik_str": cptp_cik, "ticker": "CPTP",
         "title": "Capital Properties Inc"},
    ])}
    exchanges = {"fields": ["cik", "name", "ticker", "exchange"],
                 "data": [
        [ry_cik, "Royal Bank of Canada", "RY", "NYSE"],
        [cptp_cik, "Capital Properties Inc", "CPTP", "OTC"],
    ]}
    code = """
import json
from pathlib import Path

_TICKERS = json.loads(%(tickers)r)
_EXCHANGES = json.loads(%(exchanges)r)
_RY = Path(%(ry)r).read_bytes()
_CPTP = Path(%(cptp)r).read_bytes()


def _transport(url, headers):
    if "company_tickers.json" in url:
        return 200, json.dumps(_TICKERS).encode(), {}
    if "company_tickers_exchange.json" in url:
        return 200, json.dumps(_EXCHANGES).encode(), {}
    if "companyfacts" in url:
        if "CIK%(ry_cik)010d" in url:
            return 200, _RY, {}
        if "CIK%(cptp_cik)010d" in url:
            return 200, _CPTP, {}
    return 404, b"{}", {}


import rusterm.providers.edgar as _edgar


class _P(_edgar.EdgarProvider):
    def __init__(self, *a, **kw):
        kw.setdefault("transport", _transport)
        super().__init__(*a, **kw)


_edgar.EdgarProvider = _P
""" % {"tickers": json.dumps(tickers), "exchanges": json.dumps(exchanges),
       "ry": payload("RY"), "cptp": payload("CPTP"),
       "ry_cik": ry_cik, "cptp_cik": cptp_cik}
    (stub_dir / "sitecustomize.py").write_text(code, encoding="utf-8")


def test_g9_end_to_end_for_ca_and_otc_markets():
    env = {**os.environ,
           "RUSTERM_SEC_UA": "Synthetic Test e2e.invalid",
           "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
           "TERM": "xterm"}

    def run(root, *argv, stub):
        e = dict(env)
        e["PYTHONPATH"] = os.pathsep.join(
            [str(stub), str(REPO), os.environ.get("PYTHONPATH", "")])
        return subprocess_run(root, argv, e)

    def subprocess_run(root, argv, e):
        import subprocess
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
        for ticker, market in (("RY", "CA"), ("CPTP", "OTC")):
            assert run(root, "add", "--ticker", ticker, "--market", market,
                       stub=stub).returncode == 0
            assert run(root, "ingest", "--instrument",
                       f"{market}-{ticker}", "--source", "edgar",
                       stub=stub).returncode == 0
            assert run(root, "snapshot", "--instrument",
                       f"{market}-{ticker}", stub=stub).returncode == 0
            r = run(root, "export", "--instrument", f"{market}-{ticker}",
                    "--format", "json", stub=stub)
            assert r.returncode == 0, r.stderr
            export = json.loads(r.stdout)
            assert export["measures"], f"{ticker}: экспорт пуст"

        # сохранённый эмитент несёт юрисдикцию реестра и площадку файла
        db = sqlite3.connect(f"{root}/rusterm.db")
        try:
            issuer = db.execute(
                """SELECT i.jurisdiction, l.exchange
                   FROM issuer i
                   JOIN instrument ins ON ins.issuer_id = i.issuer_id
                   JOIN listing l ON l.instrument_id = ins.instrument_id
                   WHERE ins.instrument_id = 'CA-RY'""").fetchone()
            assert issuer == ("CA", "NYSE"), issuer
            issuer = db.execute(
                """SELECT i.jurisdiction, l.exchange
                   FROM issuer i
                   JOIN instrument ins ON ins.issuer_id = i.issuer_id
                   JOIN listing l ON l.instrument_id = ins.instrument_id
                   WHERE ins.instrument_id = 'OTC-CPTP'""").fetchone()
            assert issuer == ("US", "OTC"), issuer
        finally:
            db.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
