"""ТЗ-144: «Добавить аналоги» для компании из новой отрасли (С4).

G1 — кандидаты: компании той же SIC из EDGAR, на бирже США, по выручке
frames (первый тег сильнее). G2 — кнопка окна: подсказка и сбор группы в
рабочих потоках, выбор через подменяемый `QInputDialog.getText`.
Сети нет: транспорт и двери ядра подменены.
"""
from __future__ import annotations

import urllib.error

import pytest

from rusterm.core.peers_suggest import rank_candidates, suggest
from rusterm.providers.budget import RequestGate
from rusterm.providers.edgar import EdgarProvider

LISTED = {
    1: ("NVDA", "NVIDIA CORP", "Nasdaq"),
    2: ("INTC", "INTEL CORP", "Nasdaq"),
    3: ("AVGO", "Broadcom Inc.", "Nasdaq"),
    4: ("TYGO", "Tigo Energy, Inc.", "Nasdaq"),
    5: ("OTCX", "Otc Chip", "OTC"),
    6: ("AMD", "ADVANCED MICRO DEVICES INC", "Nasdaq"),
}


def test_rank_orders_by_revenue_and_first_tag_wins():
    """Tigo: в Revenues 54 млн, в ASC-606 подано ×1000 — берётся первый
    тег; компания вне биржи США, без тикера и сама бумага — мимо."""
    revenues = {1: 130e9, 2: 53e9, 3: 52e9, 4: 54e6, 5: 9e9}
    asc606 = {4: 54e9, 6: 26e9}
    out = rank_candidates([1, 2, 3, 4, 5, 6, 7], [revenues, asc606],
                          LISTED, exclude={1})
    assert [c["ticker"] for c in out] == ["INTC", "AVGO", "AMD", "TYGO"]
    assert out[-1]["revenue"] == 54e6


def test_rank_is_deterministic_and_limited():
    revenues = {2: 10.0, 3: 10.0, 6: 30.0}
    first = rank_candidates([3, 2, 6], [revenues], LISTED, limit=2)
    again = rank_candidates([6, 2, 3, 3], [revenues], LISTED, limit=2)
    assert first == again
    assert [c["ticker"] for c in first] == ["AMD", "AVGO"]


class _FakeProvider:
    cik = 1

    def __init__(self, frames_by_year):
        self.frames_by_year = frames_by_year
        self.years = []

    def sic_code(self):
        return 3674, "SEMICONDUCTORS & RELATED DEVICES"

    def sic_ciks(self, sic):
        return [1, 2, 3, 6]

    def listed_companies(self):
        return LISTED

    def revenue_frame(self, tag, year):
        self.years.append(year)
        return self.frames_by_year.get(year, {}).get(tag, {})


def test_suggest_falls_back_a_year_when_the_frame_is_empty():
    provider = _FakeProvider({2024: {"Revenues": {2: 5.0, 6: 7.0}}})
    out = suggest(provider, {1}, 2025)
    assert out["year"] == 2024 and out["sic"] == 3674
    assert [c["ticker"] for c in out["candidates"]] == ["AMD", "INTC"]
    assert 2025 in provider.years


def _atom(ciks):
    return ("<feed>" + "".join(f"<entry><cik>{c:010d}</cik></entry>"
                               for c in ciks) + "</feed>").encode("latin-1")


def test_sic_ciks_pages_until_a_short_page(monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    seen = []

    def transport(url, headers):
        seen.append(url)
        start = int(url.split("start=")[1].split("&")[0])
        return 200, _atom(range(start, start + (100 if start < 100 else 3))), {}

    provider = EdgarProvider(gate=RequestGate(), transport=transport)
    ciks = provider.sic_ciks(3674)
    assert len(ciks) == 103 and len(seen) == 2


def test_revenue_frame_404_is_an_empty_frame(monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")

    def transport(url, headers):
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)

    provider = EdgarProvider(gate=RequestGate(), transport=transport,
                             sleeper=lambda _s: None)
    assert provider.revenue_frame("Revenues", 2030) == {}


def test_bank_sic_group_is_the_banks_sector():
    from rusterm.core.snapshot import _sector_of

    class _Repo:
        def __init__(self, sid):
            self.sid = sid

        def peer_set_for_instrument(self, _iid):
            return {"peer_set_id": self.sid}

    assert _sector_of(_Repo("sic-6021"), "US-X") == "banks"
    assert _sector_of(_Repo("sic-3674"), "US-X") == "sic-3674"


def test_sector_name_of_a_sic_group():
    from rusterm.desktop import home
    assert home.sector_name("sic-3674") == "Отрасль SIC 3674"
    assert home.sector_name("banks") == "Банки"


# ── G2: кнопка окна ──────────────────────────────────────────────────────

def test_build_peer_group_follows_new_and_writes_the_group(tmp_path,
                                                           monkeypatch):
    from rusterm.desktop import actions
    from tests.test_desktop_task110_b2_refresh import _catalog

    repos, paths, conn = _catalog(tmp_path)
    conn.close()
    followed, commands = [], []
    monkeypatch.setattr(actions, "follow_instrument",
                        lambda root, iid, cancel=None: (
                            followed.append(iid)
                            or actions.CollectOutcome(
                                ok=iid != "US-BAD", reason="follow_failed")))
    monkeypatch.setattr(actions, "run_core_command",
                        lambda root, argv: (commands.append(argv)
                                            or actions.CollectOutcome(ok=True)))
    out = actions.build_peer_group(paths.root, "US-AAPL",
                                   ["msft", "BAD", "AAPL", "DELL"], 3571,
                                   "ELECTRONIC COMPUTERS")
    assert out.ok, out
    assert followed == ["US-MSFT", "US-BAD", "US-DELL"]
    argv = commands[0]
    assert argv[:3] == ["peers", "set", "sic-3571"]
    assert argv[argv.index("--tickers") + 1] == "AAPL,MSFT,DELL"
    assert "--approve" in argv and argv[argv.index("--origin") + 1] \
        == "classifier"
    assert "BAD" in out.detail
