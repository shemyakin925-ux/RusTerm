"""ТЗ-105 R3: обложка 10-K доезжает до словаря — и почему этого мало.

Что здесь закреплено (запись расширена ОДНИМ запросом SEC 30.09.2026, raw
сохранён в `/tmp/r3-raw-aapl-companyfacts.json`, обрезка — правилами
`tools/trim_companyfacts.py`, те же поля и те же шесть самых свежих
мгновенных периодов):

- фикстура `tests/data/edgar/companyfacts_m3_AAPL.json` несёт раздел
  `dei`, и он не остаётся мёртвым текстом: обычный путь `rusterm follow`
  кладёт 6 фактов `shares_outstanding` с картой `dei.v1`;
- знаменатель `insider_net` от этого не зелёнеет: `market_cap_total`
  отказывает по цене, а не по числу акций. Причина закреплена префиксом,
  а не датой — зуб переживает полночь (правило P6: дата в пине гниёт).

Зуб выпуска ТЗ-105 R3 («`colours != {"gray"}`») здесь НЕ переносится:
замер — в `agent/REPORT-104.md` (Runs) и в «Спорном» item 30. Лента цен
фикстуры кончается 2026-09-11, сборка идёт на сегодняшнем дне, допуск
свежести цены — 7 дней, поэтому все ценовые меры пусты и вкладка
«Качество» остаётся серой независимо от обложки.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tests.test_task96_r2_follow import (_run, offline_providers,
                                         YAHOO_CHART)  # noqa: F401

TAG = "dei:EntityCommonStockSharesOutstanding"


@pytest.fixture
def stale_providers(monkeypatch):
    """Тот же офлайн-путь, но ценовая лента yahoo устаревшая: записанный
    chart сдвинут на 60 дней назад — снапшот обязан отказывать ценовым
    мерам с price_close_stale (ТЗ-110 B1: источник по умолчанию —
    yahoo, а отказ от старой ленты — то, что этот файл закрепляет)."""
    import rusterm.cli as cli
    from rusterm.providers.edgar import EdgarProvider
    from tests.test_task96_r2_follow import _edgar_transport

    real = cli.get_provider
    shift = 60 * 86400

    def _stale_yahoo(url, headers):
        payload = json.loads(YAHOO_CHART.read_text(encoding="utf-8"))
        result = (payload.get("chart") or {}).get("result") or []
        for r in result:
            r["timestamp"] = [ts - shift for ts in (r.get("timestamp")
                                                    or [])]
        return 200, json.dumps(payload).encode("utf-8"), {}

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "yahoo":
            from rusterm.providers.yahoo import YahooProvider
            return YahooProvider(gate=gate, transport=_stale_yahoo)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")


def _rows(root, sql, params=()):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    db.row_factory = sqlite3.Row
    try:
        return [tuple(r) for r in db.execute(sql, params)]
    finally:
        db.close()


def test_cover_page_share_count_reaches_the_dictionary(tmp_path,
                                                       offline_providers):
    """Раздел dei в фикстуре — не декорация: путь `follow` кладёт его в
    словарь как `shares_outstanding`."""
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    rows = _rows(root, "SELECT concept, canonical_concept, unit, "
                       "concept_map_version, basis, period_end, value "
                       "FROM fact WHERE canonical_concept="
                       "'shares_outstanding' ORDER BY period_end")
    assert len(rows) == 6, rows
    assert {r[0] for r in rows} == {TAG}, rows
    assert {r[2] for r in rows} == {"shares"}, rows
    assert {r[3] for r in rows} == {"dei.v1"}, rows
    assert {r[4] for r in rows} == {"as_reported"}, rows
    assert [r[5] for r in rows] == ["2020-10-16", "2021-10-15",
                                    "2022-10-14", "2023-10-20",
                                    "2024-10-18", "2025-10-17"], rows
    assert int(rows[-1][6]) == 14776353000, rows[-1]


def test_denominator_refuses_on_price_not_on_share_count(tmp_path,
                                                         stale_providers):
    """Знаменатель считан, но пуст: отказ называет цену, а не акции —
    это и есть причина, по которой зуб выпуска не переносится."""
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    rows = _rows(root, "SELECT value, null_reason FROM measure WHERE "
                       "concept='market_cap_total' AND snapshot_id IN "
                       "(SELECT snapshot_id FROM snapshot WHERE "
                       "instrument_id='US-AAPL' ORDER BY as_of DESC "
                       "LIMIT 1)")
    assert len(rows) == 1, rows
    value, reason = rows[0]
    assert value is None, rows
    assert reason and reason.startswith("missing_data: price_close_stale:"), \
        reason
    assert "share" not in reason.lower(), (
        f"отказ должен называть цену, а не число акций: {reason}")


def test_governance_insider_net_still_names_the_missing_denominator(
        tmp_path, stale_providers):
    """Серость не перекрашена записью обложки: `insider_net` остаётся
    серым и указывает на тот же знаменатель."""
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    # ТЗ-133 R3: follow теперь собирает и годовые снапшоты — у каждого
    # своя датированная оценка; проверяется текущая (последняя дата)
    rows = _rows(root, "SELECT color, reason FROM governance_assessment "
                       "WHERE indicator='insider_net' AND "
                       "instrument_id='US-AAPL' AND as_of=(SELECT "
                       "MAX(as_of) FROM governance_assessment WHERE "
                       "indicator='insider_net' AND "
                       "instrument_id='US-AAPL')")
    assert len(rows) == 1, rows
    color, reason = rows[0]
    assert color == "gray", rows
    assert reason == "no_data:ownership_without_market_cap", rows
