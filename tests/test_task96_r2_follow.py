"""ТЗ-96 R2: `rusterm follow` проводит бумагу путь до снапшота одним
вызовом.

Офлайн: провайдеры подменяются в двери `cli.get_provider` теми же
настоящими классами, но с транспортом на записанных ответах
(`tests/data/edgar`, `tests/data/twelvedata`) — сеть не трогается,
счётчик запросов остаётся настоящим. Каталог — `tmp_path`, окружение
не читается (страж `test_no_shared_tmp`, правило P7).

Что здесь проверяется, а не только «не упало»:
- стадии печатаются с числами и в правильном порядке;
- напечатанное «всего запросов» равно числу обращений к транспорту;
- повтор пути не портит данные и стоит заметно меньше запросов;
- каждая строка «совет:» разбирается парсером CLI — обещание чинить
  себя исполнимой строкой не может быть словами;
- измеренный отказ из ТЗ-94 E1 (цена не доехала до снапшота) на этом
  пути не воспроизводится: ценовые меры не подписываются голой
  `missing_data: price_close`.
"""
from __future__ import annotations

import re
import shlex
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.cli import _build_parser
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.twelvedata import TwelveDataProvider

REPO = Path(__file__).resolve().parents[1]
TICKERS = REPO / "tests/data/edgar/company_tickers.json"
FACTS = REPO / "tests/data/edgar/companyfacts_m3_AAPL.json"
TIMES = REPO / "tests/data/twelvedata/time_series_AAPL_1day_trimmed.json"
SPLITS = REPO / "tests/data/twelvedata/splits_AAPL_full.json"
DIVS = REPO / "tests/data/twelvedata/dividends_AAPL_full.json"


def _edgar_transport(url, headers):
    if "company_tickers" in url:
        return 200, TICKERS.read_bytes(), {}
    if "companyfacts" in url:
        return 200, FACTS.read_bytes(), {}
    if "submissions" in url:
        return 200, (REPO / "tests/data/edgar/submissions_aapl.json"
                     ).read_bytes(), {}
    return 404, b'{"ok": false}', {}


def _twelvedata_transport(url, headers):
    if "time_series" in url:
        return 200, TIMES.read_bytes(), {}
    if "/splits" in url:
        return 200, SPLITS.read_bytes(), {}
    if "/dividends" in url:
        return 200, DIVS.read_bytes(), {}
    return 404, b'{"status": "error"}', {}


@pytest.fixture
def offline_providers(monkeypatch):
    """Настоящие провайдеры, но транспорт — с диска. Дверь одна на
    всё: `cli.get_provider`, откуда их берут все стадии пути."""
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_edgar_transport)
        if name == "twelvedata":
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=_twelvedata_transport)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    return fake


def _run(root, **kwargs):
    args = _build_parser().parse_args(
        ["--root", str(root), "follow", kwargs.pop("ticker", "AAPL"),
         "--market", kwargs.pop("market", "US")])
    return cli.cmd_follow(args)


def _measures(root):
    """Меры последнего снапшота — того же, что читает `rusterm export`:
    concept -> (значение, причина отказа)."""
    from rusterm.store.repos import SnapshotRepo
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    db.row_factory = sqlite3.Row
    sid = SnapshotRepo(db).latest_snapshot_id("US-AAPL")
    if sid is None:
        return {}
    return {r["concept"]: (r["value"], r["null_reason"]) for r in db.execute(
        "SELECT concept, value, null_reason FROM measure "
        "WHERE snapshot_id=?", (sid,))}


def _requests(root):
    return cli._requests_used(str(root))


def test_follow_walks_the_path_from_an_empty_catalog(tmp_path,
                                                     offline_providers,
                                                     capsys):
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    out = capsys.readouterr().out

    stages = [l for l in out.splitlines() if "/5 " in l and " — " in l]
    names = [l.split(": ", 1)[1].split(" — ")[0] for l in stages]
    assert names == ["1/5 каталог", "2/5 поиск в SEC", "3/5 отчётность",
                     "4/5 цены", "5/5 снапшот"], out
    for line in stages:
        assert re.search(r"\(запросов \d+\)$", line), line
    assert "US-AAPL: путь пройден" in out
    assert "отрасль и governance в этот путь не входят" in out

    measures = _measures(root)
    assert measures, "снапшота нет"
    valued = [c for c, (v, _) in measures.items() if v is not None]
    assert valued, "ни одной меры со значением"


def test_follow_is_idempotent_and_clearly_cheaper(tmp_path,
                                                  offline_providers,
                                                  capsys):
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    capsys.readouterr()
    first = _requests(root)
    before = _measures(root)

    assert _run(root, ticker="AAPL") == 0
    out = capsys.readouterr().out
    second = _requests(root) - first
    after = _measures(root)

    assert first > 0
    assert second < first, f"повтор стоит не дешевле: {first} -> {second}"
    assert "поиск пропущен" in out, "второй прогон ищет тикер заново"
    assert before == after, "повтор пути изменил значения мер"


def test_price_fed_measures_are_not_census_style_refusals(
        tmp_path, offline_providers, capsys):
    """ТЗ-94 E1: `census --rebuild` пишет снапшот без ценового репозитория,
    и ценовые меры там отказываются голой причиной `price_close`, хотя
    цены в базе есть. Путь R2 обязан так не делать."""
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    capsys.readouterr()
    measures = _measures(root)
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    prices = db.execute("SELECT COUNT(*) FROM price").fetchone()[0]
    db.close()
    assert prices > 0, "фикстура не привезла цен"
    for concept in ("market_cap", "div_yield", "pe"):
        value, reason = measures[concept]
        assert not (value is None and reason == "missing_data: price_close"), (
            f"{concept}: отказ как у census --rebuild — ценовой репозиторий "
            f"в сборку не передан")


def test_the_printed_total_is_the_number_of_calls_made(tmp_path, monkeypatch,
                                                      capsys):
    """Число «всего запросов» обязано быть правдой: сравнено с реальным
    числом обращений к транспорту, а не с тем, что записал CLI. До ТЗ-96
    R2 ценовой стадий в metric_sample не было вовсе — `rusterm budget`
    называл живые запросы вендора нулём, и `follow` унаследовал бы этот
    ноль."""
    served = {"edgar": 0, "twelvedata": 0}
    real = cli.get_provider

    def counting(name, gate=None):
        if name == "edgar":
            def transport(url, headers):
                served["edgar"] += 1
                return _edgar_transport(url, headers)
            return EdgarProvider(gate=gate, transport=transport)
        if name == "twelvedata":
            def transport(url, headers):
                served["twelvedata"] += 1
                return _twelvedata_transport(url, headers)
            return TwelveDataProvider(gate=gate, api_key="TESTONLY",
                                      transport=transport)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", counting)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")

    root = tmp_path / "app"
    assert _run(root, ticker="AAPL") == 0
    out = capsys.readouterr().out
    total = int(re.search(r"путь пройден; всего запросов: (\d+)", out)[1])

    assert served["twelvedata"] > 0, "фикстура не дошла до вендора"
    assert cli._requests_used(str(root)) == sum(served.values())
    assert total == sum(served.values()), (total, served)


def test_every_advice_line_parses_as_a_command(tmp_path, monkeypatch,
                                               capsys):
    """Совет обязан быть исполнимой строкой, а не прозой: разбирается
    тем же парсером, что и настоящий запуск."""
    root = tmp_path / "app"

    def no_contact(name, gate=None):
        from rusterm.providers.budget import ConfigError
        return ConfigError(reason="sec_contact_unset")

    monkeypatch.setattr(cli, "get_provider", no_contact)
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    assert _run(root, ticker="AAPL") != 0
    err = capsys.readouterr().err

    advice = [l for l in err.splitlines() if l.startswith("совет: ")]
    assert advice, "отказ без исполнимого совета"
    for line in advice:
        words = shlex.split(line[len("совет: "):])
        assert words[0] == "rusterm", line
        parsed = _build_parser().parse_args(words[1:])
        assert parsed.command in {"add", "ingest", "snapshot", "markets",
                                  "init", "doctor"}, line


def test_unknown_market_is_refused_before_any_write(tmp_path,
                                                    offline_providers,
                                                    capsys):
    root = tmp_path / "app"
    assert _run(root, ticker="AAPL", market="ZZ") == 1
    err = capsys.readouterr().err
    assert "неизвестный рынок 'ZZ'" in err
    assert not (root / "rusterm.db").exists(), \
        "отказ по рынку создал каталог данных"
