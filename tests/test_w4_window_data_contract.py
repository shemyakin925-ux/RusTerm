"""ТЗ-76 W4: V3 из ТЗ-75 — окно читает то, что отдаёт data.py.

Страж проверяет surface между `rusterm/desktop/window.py` и
`rusterm/desktop/data.py` на НАСТОЯЩИХ данных: база собирается из
EDGAR-фикстур тем же конвейером, что CLI (add → ingest → snapshot),
список наблюдения и peer set — через двери store. Ни одна дверь не
проверяется на выдуманном словаре: форма ключей утверждается на том,
что возвращает дверь, и сверяется с тем, что окно индексирует
(`_repaint_table`, `_repaint_measures`, `_repaint_industry`,
`repaint_settings`, `show_source_panel`, `ChartArea.set_spec`).

Зубы V1-породы: клетка года обязана совпадать со значением двери
measure_history по форме ``{год: {концепт: значение}}``. Стоит вернуть
в measure_table_rows чтение ``history[мера][год]`` — клетки молча
станут «нет данных», без исключения, и
test_history_cells_agree_with_the_history_door краснеет первым.

Вторые зубы — покрытие: множество ``data.<fn>(``-вызовов окна сверяется
с пин-таблицей. Новый вызов без контракта красен, как и пин на дверь,
которую окно уже не зовёт.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
import rusterm.providers.edgar as edgar_module
from rusterm.desktop import data
from rusterm.markets import MARKET_CODES
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry
from rusterm.tui import model as tui_model

REPO = Path(__file__).resolve().parents[1]
WINDOW_SRC = (REPO / "rusterm" / "desktop" /
              "window.py").read_text(encoding="utf-8")
FIXTURES = Path(__file__).resolve().parent / "data" / "edgar"
TICKERS = ("AAPL", "MSFT", "KO")
PEER_SET = "tech"

def window_calls() -> set[str]:
    """Имена дверей data., которые окно зовёт — из исходника окна, не
    из списка, который кто-то переписывает по памяти."""
    return set(re.findall(r"\bdata\.([a-z_][a-z_0-9]*)\s*\(", WINDOW_SRC))


# ── настоящая база ───────────────────────────────────────────────────────

def _transport(url: str, headers: dict):
    """Подменный транспорт, как в H4: сеть нулевая, файлы записанные."""
    manifest = json.loads(
        (FIXTURES / "m3_manifest.json").read_text(encoding="utf-8"))
    if "company_tickers.json" in url:
        tickers = {str(index): {"cik_str": entry["cik"], "ticker": ticker,
                                "title": f"{ticker} synthetic"}
                   for index, (ticker, entry) in enumerate(
                       manifest.items())}
        return 200, json.dumps(tickers).encode(), {}
    for ticker, entry in manifest.items():
        path = FIXTURES / f"companyfacts_m3_{ticker}.json"
        if f"CIK{entry['cik']:010d}" in url and path.is_file():
            return 200, path.read_bytes(), {}
    return 404, b"{}", {}


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """add → ingest → snapshot по трём US-эмитентам из фикстур, список
    наблюдения и peer set — дверями store. Окно читает именно это."""
    root = tmp_path_factory.mktemp("w4-base")
    scratch = root / "scratch"
    scratch.mkdir()
    saved = {key: os.environ.get(key) for key in
             ("RUSTERM_SEC_UA", "RUSTERM_ENV_FILE", "RUSTERM_DART_KEY")}
    os.environ["RUSTERM_SEC_UA"] = "Synthetic Test w4.invalid"
    os.environ["RUSTERM_ENV_FILE"] = "/nonexistent/rusterm-env-w4"
    os.environ.pop("RUSTERM_DART_KEY", None)
    original = edgar_module.EdgarProvider

    class _Patched(original):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", _transport)
            super().__init__(*args, **kwargs)

    edgar_module.EdgarProvider = _Patched
    conn = None
    try:
        assert cli.main(["--root", str(root), "init"]) == 0
        for ticker in TICKERS:
            assert cli.main(["--root", str(root), "add", "--ticker",
                             ticker, "--market", "US"]) == 0
            assert cli.main(["--root", str(root), "ingest",
                             "--instrument", f"US-{ticker}",
                             "--source", "edgar"]) == 0
            assert cli.main(["--root", str(root), "snapshot",
                             "--instrument", f"US-{ticker}"]) == 0
        paths = AppPaths.from_root(root)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        conn.row_factory = sqlite3.Row
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        repos.peer_set.create_peer_set(PEER_SET, "industry", PEER_SET)
        repos.peer_set.add_version(
            "psv-w4", PEER_SET, 1, "2020-01-01", None, "manual", "v1",
            True, None, None)
        repos.watchlist.create_watchlist("wl-w4", "main", None, None)
        watchlist_version = repos.watchlist.new_version(
            "wlv-w4", "wl-w4", 1, "seed", None)
        for ticker in TICKERS:
            repos.peer_set.add_member("psv-w4", f"US-{ticker}", None)
            repos.watchlist.add_member(watchlist_version,
                                       f"US-{ticker}", None)
        yield {"root": root, "paths": paths, "repos": repos,
               "scratch": scratch, "watchlist_id": "wl-w4",
               "instrument_id": "US-AAPL"}
    finally:
        if conn is not None:
            conn.close()
        edgar_module.EdgarProvider = original
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _companies(ctx):
    return data.sidebar_companies(ctx["repos"], ctx["watchlist_id"])


def _table(ctx):
    return data.measure_table_rows(ctx["repos"], ctx["instrument_id"])


def _screen(ctx):
    return tui_model.industry_rows(ctx["repos"], PEER_SET)


def _scratch_paths(ctx):
    """Правки — по отдельному каталогу: contract-прогоны не должны
    менять ни базу, ни конфиг читаемой базы."""
    return AppPaths.from_root(ctx["scratch"])


# ── пин-таблица: форма, которую окно умеет читать ────────────────────────

def _check_str(value):
    assert isinstance(value, str) and value, value


def _check_company_rows(rows):
    assert rows, "на настоящей базе строки боковой панели пустые"
    for row in rows:
        for key in ("instrument_id", "ticker", "market", "name", "sector"):
            assert key in row, (key, sorted(row))


def _check_spec(spec):
    """ChartArea.set_spec читает kind, а по kind — свои ключи."""
    assert isinstance(spec, dict) and "kind" in spec, spec
    if spec["kind"] == "message":
        _check_str(spec["text"])
    elif spec["kind"] in ("line", "bars"):
        _check_str(spec["concept"])
        assert len(spec["years"]) == len(spec["values"])
        assert all(isinstance(year, int) for year in spec["years"])
        assert all(value is None or isinstance(value, float)
                   for value in spec["values"])
    elif spec["kind"] == "box":
        for key in ("concept", "p25", "median", "p75", "n"):
            assert key in spec, (key, spec)
    elif spec["kind"] in ("radar", "radar_vs"):
        for axis in spec["axes"]:
            assert "concept" in axis and "value" in axis, axis
        if spec["kind"] == "radar_vs":
            assert "excluded_company" in spec and "excluded_group" in spec
    else:
        raise AssertionError(f"окно не знает такого kind: {spec['kind']}")


CONTRACTS: dict[str, list] = {
    "add_instrument": (
        lambda c: data.add_instrument(c["repos"], c["watchlist_id"],
                                      "NOPE", "US"),
        ["ok", "message"]),
    "all_instruments": (lambda c: data.all_instruments(c["repos"]),
                        "companies"),
    "catalog_switch_decision": (
        lambda c: data.catalog_switch_decision(str(c["scratch"] / "nope")),
        ["candidate_root", "exists"]),
    "catalog_view": (lambda c: data.catalog_view(c["paths"]), "catalog"),
    "channel_degrees": (lambda c: data.channel_degrees(c["repos"]),
                        "degrees"),
    "chart_caption": (
        lambda c: data.chart_caption(_table(c), "net_margin", ""), "str"),
    "chart_spec": (
        lambda c: data.chart_spec("line", _table(c), _screen(c),
                                  "net_margin"), "spec"),
    "chat_sessions": (lambda c: data.chat_sessions(c["repos"]),
                      "sessions_are_listed"),
    "chat_transcript_lines": (
        lambda c: data.chat_transcript_lines(c["repos"], "no-such"),
        "lines"),
    "chat_unavailable_reason": (
        lambda c: data.chat_unavailable_reason(object()), "reason"),
    "empty_base_instruments_message": (
        lambda c: data.empty_base_instruments_message(), "str"),
    "empty_base_message": (lambda c: data.empty_base_message(c["paths"]),
                           "str"),
    "expanded_sectors": (
        lambda c: data.expanded_sectors(
            data.sector_tree(_companies(c), ""), "", set()), "set"),
    "export_table_csv": (
        lambda c: data.export_table_csv(c["repos"], c["instrument_id"]),
        "text_or_none"),
    "export_table_md": (
        lambda c: data.export_table_md(c["repos"], c["instrument_id"]),
        "text_or_none"),
    "governance_view": (
        lambda c: data.governance_view(_table(c)["card"]), ["rows"]),
    "header_info": (lambda c: data.header_info(c["repos"]),
                    ["schema_version", "requests_today"]),
    "host_limits_view": (lambda c: data.host_limits_view(c["paths"]),
                         "limit_rows"),
    "industry_chart_spec": (
        lambda c: data.industry_chart_spec(_screen(c), "net_margin"),
        "spec"),
    "industry_table_rows": (lambda c: data.industry_table_rows(_screen(c)),
                            "industry_rows"),
    "keys_view": (lambda c: data.keys_view(), "keys"),
    "llm_usage_line": (lambda c: data.llm_usage_line(c["repos"]), "str"),
    "measure_coverage": (
        lambda c: data.measure_coverage(c["repos"], c["instrument_id"]),
        ["has_snapshot", "green", "total", "reasons"]),
    "measure_table_rows": (lambda c: _table(c), "table"),
    "open_readonly": (lambda c: data.open_readonly(str(c["root"])),
                      "readonly"),
    "peer_screen": (
        lambda c: data.peer_screen(c["repos"], c["instrument_id"]),
        "peer"),
    "radar_vs_group_spec": (
        lambda c: data.radar_vs_group_spec(_table(c), _screen(c)), "spec"),
    "remove_instruments": (
        lambda c: data.remove_instruments(c["repos"],
                                          c["watchlist_id"], []),
        ["ok", "message"]),
    "sector_tree": (lambda c: data.sector_tree(_companies(c), ""), "tree"),
    "set_host_rate_limit": (
        lambda c: data.set_host_rate_limit(
            _scratch_paths(c),
            data.host_limits_view(_scratch_paths(c))["rows"][0]["host"],
            0.5),
        ["ok"]),
    "sidebar_companies": (lambda c: _companies(c), "companies"),
    "source_panel_view": (
        lambda c: data.source_panel_view(c["repos"], c["paths"],
                                         _table(c)["measures"][0],
                                         instrument_id=c["instrument_id"]),
        ["text", "open_target", "stale_count"]),
    "watchlist_choices": (lambda c: data.watchlist_choices(c["repos"]),
                          "watchlists"),
}


def _assert_shape(kind, value):
    if kind == "str":
        _check_str(value)
    elif kind == "spec":
        _check_spec(value)
    elif kind == "companies":
        _check_company_rows(value)
    elif kind == "table":
        for key in ("instrument_id", "ticker", "name", "measures", "years",
                    "card", "suggestion", "summary", "summary_line"):
            assert key in value, key
        for row in value["measures"]:
            for key in ("concept", "current", "years", "has_value",
                        "null_reason", "unit", "measure", "stale_mark"):
                assert key in row, (key, sorted(row))
            for year in value["years"]:
                assert year in row["years"], (year, sorted(row["years"]))
            assert isinstance(row["measure"], dict)
    elif kind == "tree":
        assert value
        for node in value:
            assert "sector" in node and "companies" in node, node
            _check_company_rows(node["companies"])
    elif kind == "set":
        assert isinstance(value, set), value
        assert all(isinstance(item, str) for item in value)
    elif kind == "degrees":
        assert isinstance(value, dict)
        for code in MARKET_CODES:
            assert isinstance(value.get(code, "—"), str), code
    elif kind == "watchlists":
        assert value
        for choice in value:
            for key in ("watchlist_id", "name", "version", "member_count"):
                assert key in choice, key
    elif kind == "peer":
        assert "has_peer_set" in value, value
        if value["has_peer_set"]:
            for key in ("peer_set_id", "version", "scope", "markets",
                        "rule", "members"):
                assert key in value, key
            for member in value["members"]:
                assert "ticker" in member and "is_self" in member, member
        else:
            assert "message" in value, value
    elif kind == "industry_rows":
        assert value, "на настоящей базе с peer set мер отрасли нет"
        for row in value:
            for key in ("concept", "p25", "median", "p75", "n", "mark",
                        "refused"):
                assert key in row, key
    elif kind == "keys":
        for key in ("file", "exists", "rows"):
            assert key in value, key
        for row in value["rows"]:
            for key in ("name", "origin", "found", "purpose"):
                assert key in row, key
            assert "value" not in row and "secret" not in row, row
    elif kind == "limit_rows":
        assert "config_path" in value
        assert value["rows"], "реестр лимитов пуст — проверять нечего"
        for entry in value["rows"]:
            for key in ("host", "nightly_max", "per_second", "override"):
                assert key in entry, key
    elif kind == "catalog":
        for key in ("root", "db_path", "exists"):
            assert key in value, key
        if value["exists"]:
            for key in ("size_bytes", "updated_at"):
                assert key in value, key
    elif kind == "readonly":
        paths, conn = value
        for attr in ("root", "db_path", "config_path"):
            assert hasattr(paths, attr), attr
        assert conn is not None
    elif kind == "sessions_are_listed":
        # ТЗ-81 B1: дверь list_sessions есть, заглушки None больше нет —
        # перечень обязан быть списком, а не «списком или отказом»
        assert isinstance(value, list), value
        for entry in value:
            for key in ("session_id", "model", "started_at", "calls"):
                assert key in entry, (key, entry)
    elif kind == "lines":
        assert isinstance(value, list) and value
        assert all(isinstance(line, str) for line in value), value
    elif kind == "reason":
        assert value is None or isinstance(value, str), value
    elif kind == "text_or_none":
        assert value is None or isinstance(value, str), value
    elif isinstance(kind, list):
        assert isinstance(value, dict), (kind, value)
        for key in kind:
            assert key in value, (key, sorted(value))
    else:  # pragma: no cover
        raise AssertionError(f"неизвестная форма пина: {kind}")


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_window_contract_on_real_base(base, name):
    """Дверь отвечает формой, которую окно индексирует — на настоящей
    базе из фикстур, не на выдуманном словаре."""
    call, kind = CONTRACTS[name]
    _assert_shape(kind, call(base))


def test_pin_table_covers_every_window_call(base):
    """Покрытие: множество вызовов ``data.fn(`` в окне равно пин-таблице
    — новый вызов без контракта красен, как и пин на мёртвую дверь."""
    calls = window_calls()
    assert calls, "в окне не нашлось ни одного вызова data."
    missing = sorted(calls - set(CONTRACTS))
    extra = sorted(set(CONTRACTS) - calls)
    assert not missing, f"двери окна без контракта: {missing}"
    assert not extra, f"пины, которых окно не зовёт: {extra}"


def test_history_cells_agree_with_the_history_door(base):
    """Зубы V1-породы: клетка года равна значению двери measure_history
    по (год, концепт). Чтение history[мера][год] даёт «нет данных» в
    каждой клетке без всякого исключения — ловится здесь, по числам."""
    repos, instrument_id = base["repos"], base["instrument_id"]
    history = data.measure_history(repos, instrument_id)
    table = data.measure_table_rows(repos, instrument_id)
    assert history, "на настоящей базе истории нет вовсе — тест бессилен"
    checked = 0
    for year, concepts in history.items():
        assert year in table["years"], (year, table["years"])
        for concept, value in concepts.items():
            row = data.chosen_measure_table_row(table, concept)
            assert row is not None, concept
            cell = row["years"][year]
            expected = data.format_value(value)
            if cell.endswith(data.RUN_YEAR_MARK):
                expected += data.RUN_YEAR_MARK
            assert cell == expected, (year, concept, cell, expected)
            checked += 1
    assert checked, "ни одной клетки не сверено"
