"""ТЗ-65 K4 (BACKLOG B48): первый час пользователя — тестом.

Сценарий ТЗ-63 целиком на записанных ответах (hermetic-стаб EDGAR:
карта тикеров, биржи, companyfacts из tests/data) — без сети.
Печатает тайминги и числа; в обычном наборе не гоняется
(pyproject addopts), явный вызов: pytest -m firsthour.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _write_stub(stub_dir: Path) -> None:
    aapl = json.loads(
        (REPO / "tests" / "data" / "edgar"
         / "companyfacts_m3_AAPL.json").read_bytes())
    times = (REPO / "tests" / "data" / "twelvedata"
             / "time_series_AAPL_1day_trimmed.json").resolve()
    splits = (REPO / "tests" / "data" / "twelvedata"
              / "splits_AAPL_full.json").resolve()
    dividends = (REPO / "tests" / "data" / "twelvedata"
                 / "dividends_AAPL_full.json").resolve()
    code = f"""
import json
from pathlib import Path
_TICKERS = json.loads(json.dumps({{"0": {{"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}}}))
_AAPL = Path({str(REPO / 'tests/data/edgar/companyfacts_m3_AAPL.json')!r}).read_bytes()
_TIMES = json.loads(Path({str(times)!r}).read_text(encoding="utf-8"))
_SPLITS = Path({str(splits)!r}).read_bytes()
_DIVS = Path({str(dividends)!r}).read_bytes()

def _transport(url, headers):
    if "company_tickers.json" in url:
        return 200, json.dumps(_TICKERS).encode(), {{}}
    if "companyfacts" in url:
        return 200, _AAPL, {{}}
    if "time_series" in url:
        return 200, json.dumps(_TIMES).encode(), {{}}
    if "/splits" in url:
        return 200, _SPLITS, {{}}
    if "/dividends" in url:
        return 200, _DIVS, {{}}
    return 404, b"{{}}", {{}}

import rusterm.providers.edgar as _edgar
import rusterm.providers.twelvedata as _tw

class _P(_edgar.EdgarProvider):
    def __init__(self, *a, **kw):
        kw.setdefault("transport", _transport)
        super().__init__(*a, **kw)

class _T(_tw.TwelveDataProvider):
    def __init__(self, *a, **kw):
        kw.setdefault("transport", _transport)
        super().__init__(*a, **kw)

_edgar.EdgarProvider = _P
_tw.TwelveDataProvider = _T
"""
    (stub_dir / "sitecustomize.py").write_text(code, encoding="utf-8")


@pytest.mark.firsthour
def test_first_hour_scenario(tmp_path, capsys):
    stub = tmp_path / "stub"
    stub.mkdir()
    _write_stub(stub)
    root = str(tmp_path / "root")
    env = {**os.environ,
           "RUSTERM_SEC_UA": "Firsthour Test firsthour.invalid",
           "RUSTERM_TWELVEDATA_KEY": "firsthour-stub-dummy",
           "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
           "QT_QPA_PLATFORM": "offscreen",
           "RUSTERM_APP_SMOKE": "1",
           "PYTHONPATH": os.pathsep.join([str(stub), str(REPO),
                                          os.environ.get("PYTHONPATH", "")])}

    def run(*argv):
        t0 = time.perf_counter()
        p = subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root, *argv],
            capture_output=True, text=True, env=env, timeout=300)
        dt = time.perf_counter() - t0
        assert p.returncode == 0, (argv, p.stdout, p.stderr)
        return dt, p.stdout

    t_init, _ = run("init")
    t_add, _ = run("add", "--ticker", "AAPL", "--name", "Apple Inc.",
                   "--market", "US")
    t_ing, out_ing = run("ingest", "--source", "edgar", "--instrument",
                         "US-AAPL")
    t_tw, out_tw = run("ingest", "--source", "twelvedata", "--instrument",
                       "US-AAPL")
    t_snap, out_snap = run("snapshot", "--instrument", "US-AAPL")
    t_win, _ = run("desktop")
    t_exp, out_exp = run("export", "--instrument", "US-AAPL",
                         "--format", "json")
    measures = json.loads(out_exp)["measures"]
    valued = [m for m in measures if m["value"] is not None]
    with_prov = [m for m in valued if m.get("provenance")]

    t0 = time.perf_counter()
    p = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", root, "budget",
         "--json"], capture_output=True, text=True, env=env, timeout=120)
    used = json.loads(p.stdout)["used"]

    with capsys.disabled():
        print(f"\nfirsthour: init {t_init:.1f} с; add {t_add:.1f} с; "
              f"ingest edgar {t_ing:.1f} с; ingest twelvedata "
              f"{t_tw:.1f} с; snapshot {t_snap:.1f} с; окно "
              f"{t_win:.1f} с; export {t_exp:.1f} с; запросов {used}; "
              f"мер со значением {len(valued)} из {len(measures)}; "
              f"с происхождением {len(with_prov)} из {len(valued)}")
    assert len(measures) == 28
    assert used >= 1
    assert t_init < 20 and t_add < 60 and t_ing < 300
    assert t_snap < 60 and t_win < 60 and t_exp < 20
