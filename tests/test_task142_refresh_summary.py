"""ТЗ-142 E2: строка «что изменилось» — одна функция в ядре, проход
называет приехавшее словами.

PRODUCT.md С5: кнопка «Обновить» «в конце одной строкой пишет, что
изменилось». Строку собирает `refresh_summary_line` (core.refresh);
`rusterm refresh --all` печатает её последней строкой прохода, окно
показывает её же в строке кнопки — ничего не считая само. Фикстура
прохода офлайновая (P7, tmp_path): одна бумага приезжает с новой
отчётностью (10-Q по записанному submissions + companyfacts), одна
отказывает ДО запроса (эмитент чужого рынка, ТЗ-92 C2) — строка
называет обе.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
import rusterm.desktop.actions as desktop_actions
from rusterm.cli import _build_parser
from rusterm.core.refresh import (SUMMARY_LINE_PREFIX, refresh_one,
                                  refresh_summary_line)
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.yahoo import YahooProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Issuer, Instrument, Listing,
                                 RepoRegistry)
from tests.test_task96_r2_follow import (_edgar_transport,  # noqa: F401
                                         YAHOO_CHART)

REPO = Path(__file__).resolve().parents[1]

# submissions с максимумом даты на 10-Q: форма последней подачи —
# та, что строка «что изменилось» называет рядом с тикером
SUBMISSIONS_10Q = {
    "filings": {"recent": {
        "filingDate": ["2026-09-15", "2026-08-01"],
        "form": ["10-Q", "10-K"],
    }},
    "name": "Apple Inc.",
}


def _transport(url, headers):
    if "submissions" in url:
        return 200, json.dumps(SUBMISSIONS_10Q).encode("utf-8"), {}
    return _edgar_transport(url, headers)


def _yahoo_ok(url, headers):
    return 200, YAHOO_CHART.read_bytes(), {}


@pytest.fixture
def offline_providers(monkeypatch):
    real = cli.get_provider

    def fake(name, gate=None):
        if name == "edgar":
            return EdgarProvider(gate=gate, transport=_transport)
        if name == "yahoo":
            return YahooProvider(gate=gate, transport=_yahoo_ok)
        return real(name, gate=gate)

    monkeypatch.setattr(cli, "get_provider", fake)
    monkeypatch.setenv("RUSTERM_SEC_UA", "Rusterm Test r.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_PRICE_SOURCE", raising=False)


def test_summary_line_names_counts_reports_and_refusals():
    """Словами, как в ТЗ-142: цены, новые отчёты с именами и формами,
    меры, отказы."""
    line = refresh_summary_line(
        new_prices=49, new_reports=[("KO", "10-Q"), ("ORCL", "10-K")],
        measures_changed=37, refusals=1)
    assert line == ("цены: 49, новые отчёты: 2 (KO 10-Q, ORCL 10-K), "
                    "мер изменилось: 37, отказов: 1")


def test_summary_line_without_reports_and_truncated_names():
    """Без новых отчётов — ноль словами; длиннее трёх имён — усечение
    с «, …», счётчик называет всех."""
    line = refresh_summary_line(new_prices=0, new_reports=[],
                                measures_changed=0, refusals=0)
    assert line == ("цены: 0, новые отчёты: 0, мер изменилось: 0, "
                    "отказов: 0")
    five = [(t, "10-Q") for t in ("AAA", "BBB", "CCC", "DDD", "EEE")]
    line = refresh_summary_line(new_prices=5, new_reports=five,
                                measures_changed=5, refusals=0)
    assert line == ("цены: 5, новые отчёты: 5 (AAA 10-Q, BBB 10-Q, "
                    "CCC 10-Q, …), мер изменилось: 5, отказов: 0")


def _catalog(tmp_path, with_refusal: bool = True):
    """AAPL (отчётность приедет); с with_refusal — и BR-AMBEV (отказ
    до запроса — эмитент чужого рынка, ТЗ-92 C2)."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "cik-320193", "Apple Inc.", "US", "320193", None, "us-gaap",
        "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAPL", "cik-320193", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-US-AAPL", "US-AAPL", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history("l-US-AAPL", "AAPL",
                                        "2015-01-01", None, "sandbox",
                                        None)
    # отражённая дата подачи старше фида: submissions покажет 10-Q
    repos.issuer_state.put("cik-320193", "2026-08-01")
    if with_refusal:
        repos.instrument.upsert_issuer(Issuer(
            "cvm-23264", "Ambev S.A.", "BR", "23264", None,
            "ifrs-full", "BRL"))
        repos.instrument.upsert_instrument(Instrument(
            "BR-AMBEV", "cvm-23264", None, "common", "active", None))
        repos.instrument.upsert_listing(Listing(
            "l-BR-AMBEV", "BR-AMBEV", "BVMF", "BRL", 1, None, None))
        repos.instrument.add_ticker_history("l-BR-AMBEV", "AMBEV",
                                            "2015-01-01", None,
                                            "sandbox", None)
    conn.close()
    return paths


def test_pass_line_names_a_new_filing_and_a_refusal(
        tmp_path, offline_providers, capsys):
    """Один проход: последняя строка — «что изменилось» — называет
    обе бумаги: приехавший 10-Q по имени и отказ (чужой рынок)."""
    paths = _catalog(tmp_path)
    args = _build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])
    assert cli.cmd_refresh(args) == 1, "отказ чужого рынка — код 1"
    out = capsys.readouterr().out
    summary = out.strip().splitlines()[-1]
    assert summary.startswith(SUMMARY_LINE_PREFIX), out
    assert "новые отчёты: 1 (AAPL 10-Q)" in summary, summary
    assert "отказов: 1" in summary, summary


def test_refresh_one_carries_the_form_of_the_new_filing(
        tmp_path, offline_providers):
    """Форма в результате прохода — от последней подачи фида, без
    нового запроса (тот же кэшированный submissions)."""
    paths = _catalog(tmp_path)
    from rusterm.providers.budget import RequestGate
    gate = RequestGate()
    provider = EdgarProvider(gate=gate, transport=_transport)

    def factory(cik: int):
        provider.cik = cik
        return provider

    opened = cli._open(str(paths.root))
    conn = opened[1]
    apply_migrations(conn)
    repos = RepoRegistry(conn, opened[0])
    try:
        result = refresh_one(repos, factory, "US-AAPL", "2026-09-20")
        assert result.action == "updated", result
        assert result.form == "10-Q", result
    finally:
        conn.close()


def test_window_line_carries_the_counts(tmp_path, offline_providers):
    """Строка кнопки — та же строка прохода рядом с отметкой времени:
    refresh_pass ничего не считает сам (ТЗ-142 E2). Каталог без
    отказа: проход успешен (код 0), и итог несёт счётчики."""
    paths = _catalog(tmp_path, with_refusal=False)
    assert cli.cmd_refresh(_build_parser().parse_args(
        ["--root", str(paths.root), "refresh", "--all"])) == 0
    outcome = desktop_actions.refresh_pass(str(paths.root))
    assert outcome.ok, outcome.detail
    assert outcome.detail.startswith("обновлено "), outcome.detail
    # второй проход: всё уже в базе — нули словами, строка та же
    assert " · цены: " in outcome.detail, outcome.detail
    assert "новые отчёты: 0" in outcome.detail, outcome.detail
