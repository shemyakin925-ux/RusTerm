""" Hermetic EDGAR for the e2e subprocess test (TASK-11 X1).

Автоматически импортируется интерпретатором (PYTHONPATH указывает на
этот каталог): подменяет транспорт EdgarProvider на записи из
tests/data/edgar — настоящая сеть не трогается.
"""
import json
from pathlib import Path

_DATA = Path(__file__).resolve().parents[1] / "data" / "edgar"


def _recorded_transport(url, headers):
    if "company_tickers.json" in url:
        return 200, (_DATA / "company_tickers.json").read_bytes(), {}
    for path in sorted(_DATA.glob("companyfacts_m3_*.json")):
        doc = json.loads(path.read_bytes())
        if f"CIK{doc['cik']:010d}" in url:
            return 200, path.read_bytes(), {}
    return 404, b'{"error": "not recorded"}', {}


import rusterm.providers.edgar as _edgar_module


class _RecordedEdgarProvider(_edgar_module.EdgarProvider):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("transport", _recorded_transport)
        super().__init__(*args, **kwargs)


_edgar_module.EdgarProvider = _RecordedEdgarProvider
