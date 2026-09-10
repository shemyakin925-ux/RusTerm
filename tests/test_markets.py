"""TASK-18 G1 + TASK-19 F1: реестр рынков — рынок это строка таблицы.

Набор кодов закреплён упорядоченным кортежем шести (US, CA, OTC,
KR, BR, AU); неизвестный --market — exit 1 с перечнем всех шести;
у каждой строки access из трёх слов ADR-0010 §2; литералов рынка
в formulas/core/normalize нет (страж), и проверен его красный исход:
добавленный "CA" в ядро красит suite.
"""
from __future__ import annotations

import subprocess
import sys

from rusterm.markets import MARKET_CODES, MARKETS, get_market, \
    venue_in_market


def test_registry_pins_exactly_six_codes_in_order():
    # сильнее прежней тройки: точный порядок, а не только множество
    assert MARKET_CODES == ("US", "CA", "OTC", "KR", "BR", "AU")
    ca = get_market("CA")
    assert ca.jurisdiction == "CA" and ca.venue_kind == "exchange"
    assert ca.default_taxonomy == "ifrs-full"  # advisory, не приказ
    assert get_market("OTC").venue_kind == "otc"
    assert get_market("XX") is None


def test_every_row_has_access_from_adr_0010_vocabulary():
    # TASK-19 F1: access — поле реестра, а не знание в голове
    allowed = {"auto", "partial", "manual"}
    for market in MARKETS:
        assert market.access in allowed, (market.code, market.access)
    by_code = {m.code: m for m in MARKETS}
    assert by_code["US"].access == "auto"
    assert by_code["CA"].access == "auto"
    assert by_code["KR"].access == "auto"
    assert by_code["BR"].access == "auto"
    assert by_code["OTC"].access == "partial"
    assert by_code["AU"].access == "partial"
    # строки, посаженные в F1: провайдеры ещё не резолвятся (TASK-20)
    assert (by_code["KR"].provider, by_code["KR"].identifier,
            by_code["KR"].default_taxonomy) == ("dart", "corp_code",
                                                "ifrs-full")
    assert (by_code["BR"].provider, by_code["BR"].identifier,
            by_code["BR"].default_taxonomy) == ("cvm", "cvm_code",
                                                "ifrs-full")
    assert (by_code["AU"].provider, by_code["AU"].identifier,
            by_code["AU"].default_taxonomy) == ("asx", "asx_code",
                                                "ifrs-full")


def test_venues_of_new_markets():
    # TASK-19 F1: venue_in_market знает площадки новых рынков
    assert get_market("KR").venue_kind == "exchange"
    for venue in ("KRX", "KOSPI", "KOSDAQ", "KRX-SETAM"):
        assert venue_in_market(venue, "KR"), venue
    for venue in ("B3", "BVMF", "B3 S.A."):
        assert venue_in_market(venue, "BR"), venue
    for venue in ("ASX", "ASX-24"):
        assert venue_in_market(venue, "AU"), venue
    # чужая площадка рынку не подходит
    assert not venue_in_market("KOSPI", "US")
    assert not venue_in_market("ASX", "KR")
    # unknown-правило не изменилось
    assert venue_in_market("unknown", "KR")
    assert venue_in_market("", "AU")
    assert venue_in_market("UNKNOWN", "BR")
    # прежнее поведение US/CA сохранено
    assert venue_in_market("NYSE", "CA")
    assert venue_in_market("NASDAQ", "US")
    assert venue_in_market("OTC Link", "OTC")


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
        # сильнее прежнего: перечень обязан назвать все шесть кодов
        assert all(code in r.stderr
                   for code in ("XX", "US", "CA", "OTC", "KR", "BR",
                                "AU")), r.stderr
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
