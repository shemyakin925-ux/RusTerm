"""ТЗ-109 R1: необязательная стадия пути путь не кончает.

Измеренный повод (03.10, пустая база): `rusterm follow MSFT` — стадии 1–3
прошли, стадия 4 (владение) упала `source_unreachable:transport:URLError`,
и весь путь остановился: ни цен, ни снапшота. Необязательные стадии —
владение и цены; обязательные — каталог, поиск, отчётность, снапшот.

Офлайн: провайдеры подменяются в двери `cli.get_provider` настоящими
классами с транспортом на записанных ответах (`tests/data/edgar`,
`tests/data/twelvedata`); падающий транспорт поднимает URLError, как
живой urllib. Каталог — `tmp_path`, окружение не читается (P7).

Закреплено:
- отказ владения/цен печатает «<стадия>: пропущено — <причина>;
  повтор: <команда>», путь доходит до снапшота, код выхода 0;
- причина в строке «пропущено» — из покрытия, которое стадия пишет о
  себе, а не выдумка;
- строка «повтор:» разбирается настоящим парсером CLI (правило P8);
- отказ обязательной стадии путь по-прежнему кончает (код != 0).
"""
from __future__ import annotations

import shlex
import sqlite3
import urllib.error
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.twelvedata import TwelveDataProvider
from tests.edgar_fixtures import ownership_body

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "tests" / "data"
TICKERS = DATA / "edgar" / "company_tickers.json"
FACTS = DATA / "edgar" / "companyfacts_m3_AAPL.json"
SUBMISSIONS = DATA / "edgar" / "submissions_aapl.json"
TIMES = DATA / "twelvedata" / "time_series_AAPL_1day_trimmed.json"
SPLITS = DATA / "twelvedata" / "splits_AAPL_full.json"
DIVS = DATA / "twelvedata" / "dividends_AAPL_full.json"


def _edgar_ok(url, headers):
    """Записанные ответы SEC: карта тикеров, факты, submissions, тела
    форм владения с диска; нет записи — честный 404."""
    if "company_tickers" in url:
        return 200, TICKERS.read_bytes(), {}
    if "companyfacts" in url:
        return 200, FACTS.read_bytes(), {}
    if "submissions" in url:
        return 200, SUBMISSIONS.read_bytes(), {}
    if "/Archives/edgar/data/" in url:
        body = ownership_body(url)
        return (200, body, {}) if body is not None else (404, b"{}", {})
    return 404, b'{"ok": false}', {}


def _twelvedata_ok(url, headers):
    if "time_series" in url:
        return 200, TIMES.read_bytes(), {}
    if "/splits" in url:
        return 200, SPLITS.read_bytes(), {}
    if "/dividends" in url:
        return 200, DIVS.read_bytes(), {}
    return 404, b'{"status": "error"}', {}


def _raising(base):
    """Транспорт, который на части URL поднимает URLError, как живой
    обрыв связи; остальное — записанные ответы."""

    def transport(url, headers):
        raise urllib.error.URLError(f"down: {url.rsplit('/', 1)[-1]}")

    def mixed(url, headers):
        if base is _edgar_ok and "/Archives/edgar/data/" in url:
            raise urllib.error.URLError("ownership down")
        if base is _twelvedata_ok:
            raise urllib.error.URLError("vendor down")
        return base(url, headers)

    return transport, mixed


def _install_providers(monkeypatch, edgar_transport, td_transport):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=td_transport)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_PRICE_SOURCE", raising=False)
    monkeypatch.delenv("RUSTERM_TWELVEDATA_KEY", raising=False)


def _run(root, ticker="AAPL", market="US"):
    args = _build_parser().parse_args(
        ["--root", str(root), "follow", ticker, "--market", market])
    return cli.cmd_follow(args)


def _snapshots(root):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        return db.execute(
            "SELECT COUNT(*) FROM snapshot WHERE instrument_id='US-AAPL'"
        ).fetchone()[0]
    finally:
        db.close()


def _coverage(root, block):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    try:
        row = db.execute(
            "SELECT status, reason FROM coverage "
            "WHERE instrument_id='US-AAPL' AND block=?", (block,)).fetchone()
    finally:
        db.close()
    return None if row is None else {"status": row[0], "reason": row[1]}


_SKIP_REASONS = ("source_unreachable:transport",)


def test_ownership_transport_error_does_not_stop_the_path(
        tmp_path, monkeypatch, capsys):
    """Стадия 4/6 упала по транспорту — путь дошёл до снапшота, код 0,
    в выводе названы стадия, причина и исполнимый повтор."""
    _, mixed = _raising(_edgar_ok)
    _install_providers(monkeypatch, mixed, _twelvedata_ok)
    root = tmp_path / "app"

    assert _run(root) == 0
    out = capsys.readouterr().out

    assert _snapshots(root) > 0, "снапшота нет — необязательная стадия " \
                                 "остановила путь"
    skip = [l for l in out.splitlines()
            if "4/6 формы владения: пропущено" in l]
    assert skip, out
    line = skip[0]
    reason = line.split("пропущено — ", 1)[1].split(";", 1)[0]
    assert reason.startswith(_SKIP_REASONS), \
        f"причина не из словаря транспорта: {reason!r}"
    assert f"повтор: rusterm ingest --source ownership " \
           f"--instrument US-AAPL" in line, line
    words = shlex.split(line.split("повтор: ", 1)[1])
    assert words[0] == "rusterm"
    parsed = _build_parser().parse_args(words[1:])
    assert parsed.command == "ingest" and parsed.source == "ownership", \
        vars(parsed)
    coverage = _coverage(root, "ownership")
    assert coverage is not None and coverage["status"] == "missing", coverage
    assert coverage["reason"].startswith(_SKIP_REASONS), coverage


def test_price_transport_error_does_not_stop_the_path(
        tmp_path, monkeypatch, capsys):
    """Стадия 5/6 упала по транспорту — снапшот построен на отчётности,
    код 0, строка «пропущено» называет причину и повтор."""
    _, mixed = _raising(_twelvedata_ok)
    _install_providers(monkeypatch, _edgar_ok, mixed)
    root = tmp_path / "app"

    assert _run(root) == 0
    out = capsys.readouterr().out

    assert _snapshots(root) > 0, "снапшота нет"
    skip = [l for l in out.splitlines() if "5/6 цены: пропущено" in l]
    assert skip, out
    line = skip[0]
    reason = line.split("пропущено — ", 1)[1].split(";", 1)[0]
    assert reason.startswith(_SKIP_REASONS), f"{reason!r}"
    words = shlex.split(line.split("повтор: ", 1)[1])
    parsed = _build_parser().parse_args(words[1:])
    assert parsed.command == "ingest" and parsed.source == "twelvedata", \
        vars(parsed)
    prices = _coverage(root, "prices")
    assert prices is not None and prices["status"] == "missing", prices
    # цены не доехали — значит, доли владельцев и отчётность доехали:
    # путь обязан был сохранить именно их
    assert _coverage(root, "fundamentals")["status"] == "ready"
    assert _coverage(root, "ownership")["status"] == "ready"


def test_required_stage_failure_still_stops_the_path(
        tmp_path, monkeypatch, capsys):
    """Отчётность — обязательная стадия: её транспортный отказ останавливает
    путь с ненулевым кодом, снапшота нет, строка «стадия не прошла» на
    месте (GUIDE §1.1 не тронут)."""
    _, mixed = _raising(_edgar_ok)

    def facts_down(url, headers):
        if "companyfacts" in url:
            raise urllib.error.URLError("sec down")
        return mixed(url, headers)

    _install_providers(monkeypatch, facts_down, _twelvedata_ok)
    root = tmp_path / "app"

    assert _run(root) != 0
    captured = capsys.readouterr()
    out, err = captured.out, captured.err

    assert _snapshots(root) == 0, "обязательная стадия пропустила отказ"
    combined = out + err
    assert "стадия не прошла" in combined, combined
    assert "пропущено" not in out, "обязательная стадия названа пропущенной"


def test_resume_reruns_only_the_skipped_stage(tmp_path, monkeypatch, capsys):
    """ТЗ-109 R3: повтор пути после пропуска цен запускает только ценовую
    стадию и снапшот — ноль запросов к SEC, вслух названо «повтор: цены».
    Состояние — в покрытии базы, не в памяти процесса."""
    edgar_calls = {"n": 0}
    td_calls = {"n": 0}

    def counting_edgar(url, headers):
        edgar_calls["n"] += 1
        return _edgar_ok(url, headers)

    def counting_td(url, headers):
        td_calls["n"] += 1
        raise urllib.error.URLError("vendor down")

    _install_providers(monkeypatch, counting_edgar, counting_td)
    root = tmp_path / "app"

    assert _run(root) == 0, "первый прогон: цены пропущены, путь дошёл"
    first_out = capsys.readouterr().out
    assert "5/6 цены: пропущено" in first_out, first_out
    assert "повтор: rusterm ingest --source twelvedata" in first_out
    edgar_after_run1 = edgar_calls["n"]

    def serving_td(url, headers):
        td_calls["n"] += 1
        return _twelvedata_ok(url, headers)

    _install_providers(monkeypatch, counting_edgar, serving_td)
    assert _run(root) == 0
    second_out = capsys.readouterr().out

    assert edgar_calls["n"] == edgar_after_run1, \
        "повтор ходил в SEC — должны были быть только цены"
    assert td_calls["n"] > 0, "ценовой вендор не вызван ни разу"
    assert "повтор: цены" in second_out, second_out
    assert "5/6 цены — готово" in second_out, second_out
    assert _coverage(root, "prices")["status"] == "ready"
    assert _snapshots(root) > 0


def test_resume_skips_stages_already_collected(tmp_path, monkeypatch, capsys):
    """Полностью собранная бумага на повторе стоит ноль запросов: стадии
    3–5 пропущены по готовому покрытию, путь кончается снапшотом."""
    _install_providers(monkeypatch, _edgar_ok, _twelvedata_ok)
    root = tmp_path / "app"
    assert _run(root) == 0
    capsys.readouterr()

    assert _run(root) == 0
    out = capsys.readouterr().out

    for stage in ("3/6 отчётность", "4/6 формы владения", "5/6 цены"):
        assert f"{stage} — уже собрано, пропуск (запросов 0)" in out, out
    assert "повтор:" not in out, out
