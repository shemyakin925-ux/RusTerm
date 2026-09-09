"""TASK-18 G1: реестр рынков — рынок это строка таблицы.

Набор кодов закреплён ровно {US, CA, OTC}; неизвестный --market —
exit 1 с перечнем известных; литералов рынка в formulas/core/normalize
нет (страж), и проверен его красный исход: добавленный "CA" в ядро
красит suite.
"""
from __future__ import annotations

import subprocess
import sys

from rusterm.markets import MARKET_CODES, get_market, known_codes


def test_registry_pins_exactly_three_codes():
    assert set(MARKET_CODES) == {"US", "CA", "OTC"}
    assert len(MARKET_CODES) == 3
    ca = get_market("CA")
    assert ca.jurisdiction == "CA" and ca.venue_kind == "exchange"
    assert ca.default_taxonomy == "ifrs-full"  # advisory, не приказ
    assert get_market("OTC").venue_kind == "otc"
    assert get_market("XX") is None


def test_unknown_market_code_exits_1_naming_known_codes():
    import os
    import tempfile
    repo = "/Users/anton/AI agents/RusTerm"
    env = {**os.environ,
           "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
           "TERM": "xterm"}
    root = tempfile.mkdtemp()
    try:
        r = subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root,
             "add", "--ticker", "AAPL", "--market", "XX"],
            capture_output=True, text=True, env=env)
        assert r.returncode == 1
        assert "XX" in r.stderr and "US" in r.stderr \
            and "CA" in r.stderr and "OTC" in r.stderr, r.stderr
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    del repo


def test_no_market_literals_in_core_or_normalize():
    """Страж: рыночные литералы живут только в реестре. Добавление
    "CA" в модуль ядра красит suite — проверено вручную при приёмке
    пункта (добавлено, красный, удалено)."""
    result = subprocess.run(
        ["grep", "-rnE", r'"(US|CA|OTC)"',
         "rusterm/formulas.py", "rusterm/core/", "rusterm/normalize/"],
        capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
