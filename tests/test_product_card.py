"""PRODUCT.md С2 (06.10.2026): карточка компании как у аналогов.

Слой `rusterm/desktop/card.py` без Qt: разделы и русские имена, годы от
старых к новым, «—» с причиной, скрытие пустого и неприменимого,
бессмысленные значения прочерком, строки отчётности из фактов, метрика
заполненности. Плюс две правки ядра того же дня: `history --rebuild` и
нулевые краткосрочные вложения у полной us-gaap отчётности.
"""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from rusterm.core.history import build_history
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.desktop import card, data
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)


def _base(tmp_path, sector_reason="missing_data: operating_income"):
    paths = AppPaths.from_root(tmp_path / "card")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-AAA", "US-AAA", "XNAS", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-AAA", "AAA", "2000-01-01", None, None, None)
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts")
    for year, revenue, equity in ((2023, "100", "-5"), (2024, "120", "40")):
        repos.fact.insert_fact(
            f"f-rev-{year}", "i-AAA", None, "us-gaap:Revenues",
            f"{year}-01-01", f"{year}-12-31", "duration", revenue, "USD",
            "USD", "as_reported", "extracted", raw.sha256,
            {"endpoint": "companyfacts", "kind": "10-K"}, "t",
            canonical_concept="revenue")
        repos.fact.insert_fact(
            f"f-eq-{year}", "i-AAA", None, "us-gaap:StockholdersEquity",
            f"{year}-12-31", f"{year}-12-31", "instant", equity, "USD",
            "USD",
            "as_reported", "extracted", raw.sha256,
            {"endpoint": "companyfacts", "kind": "10-K"}, "t",
            canonical_concept="total_equity")
    # квартальный поток — не годовой, в карточку не попадает
    repos.fact.insert_fact(
        "f-rev-q", "i-AAA", None, "us-gaap:Revenues", "2024-10-01",
        "2024-12-31", "duration", "30", "USD", "USD", "as_reported",
        "extracted", raw.sha256, {"endpoint": "companyfacts",
                                  "kind": "10-Q"}, "t",
        canonical_concept="revenue")
    for version, year in ((1, 2023), (2, 2024)):
        sid = f"s-{year}"
        repos.snapshot.create_snapshot(sid, "US-AAA", version,
                                       f"{year}-12-31", None, None, "ready")
        repos.snapshot.insert_measure(
            f"m-nm-{year}", sid, "issuer", "i-AAA", "net_margin",
            "0.2" if year == 2024 else "0.1", "ratio", f"{year}-01-01",
            f"{year}-12-31", "f", "v1", None, None)
        # ROE 2023 при отрицательном капитале — формально число
        repos.snapshot.insert_measure(
            f"m-roe-{year}", sid, "issuer", "i-AAA", "roe",
            "14.0" if year == 2023 else "0.15", "ratio", f"{year}-01-01",
            f"{year}-12-31", "f", "v1", None, None)
        repos.snapshot.insert_measure(
            f"m-pb-{year}", sid, "issuer", "i-AAA", "pb", None, "ratio",
            f"{year}-01-01", f"{year}-12-31", "f", "v1",
            "missing_data: total_equity", None)
        repos.snapshot.insert_measure(
            f"m-hhi-{year}", sid, "issuer", "i-AAA", "hhi", "0.4",
            "index", f"{year}-01-01", f"{year}-12-31", "f", "v1", None,
            None)
        repos.snapshot.insert_measure(
            f"m-ebitda-{year}", sid, "issuer", "i-AAA", "ebitda", None,
            "USD", f"{year}-01-01", f"{year}-12-31", "f", "v1",
            sector_reason, None)
    return repos


def _view(repos, **kw):
    info = data.measure_table_rows(repos, "US-AAA", card.CARD_YEARS)
    return card.card_view(repos, info, **kw)


def _row(view, concept):
    return next(r for r in view["rows"] if r.get("concept") == concept)


def test_years_old_to_new_now_last_sections_and_russian_names(tmp_path):
    view = _view(_base(tmp_path))
    assert view["columns"] == ["2023", "2024", "сейчас"]
    titles = [r["title"] for r in view["rows"] if r["kind"] == "section"]
    assert titles[0] == "Отчётность"
    assert _row(view, "net_margin")["label"] == "Чистая маржа"
    assert [c["text"] for c in _row(view, "net_margin")["cells"]] == \
        ["10,00 %", "20,00 %", "20,00 %"]


def test_statement_row_is_the_annual_fact_not_the_quarter(tmp_path):
    view = _view(_base(tmp_path))
    revenue = _row(view, "revenue")
    assert revenue["kind"] == "fact"
    assert [c["value"] for c in revenue["cells"][:2]] == [100.0, 120.0]
    assert revenue["fact_ids"]["2024"] == "f-rev-2024"


def test_roe_with_negative_equity_is_a_dash_with_the_reason(tmp_path):
    view = _view(_base(tmp_path))
    cell_2023 = _row(view, "roe")["cells"][0]
    assert cell_2023["text"] == card.DASH
    assert "капитал отрицательный" in cell_2023["tooltip"]
    assert "1\u202f400,00 %" in cell_2023["tooltip"], "исходное число в подсказке"
    assert _row(view, "roe")["cells"][1]["text"] == "15,00 %"


def test_empty_row_hidden_but_named_and_toggle_brings_it_back(tmp_path):
    repos = _base(tmp_path)
    view = _view(repos)
    assert "pb" not in [r.get("concept") for r in view["rows"]]
    assert "P/B: нет данных за период (missing_data: total_equity)" in \
        card.hidden_tooltip(view)
    shown = _view(repos, show_empty=True)
    assert [c["text"] for c in _row(shown, "pb")["cells"]] == [card.DASH] * 3


def test_service_measures_never_shown(tmp_path):
    view = _view(_base(tmp_path), show_empty=True)
    assert "hhi" not in [r.get("concept") for r in view["rows"]]


def test_bank_hides_industrial_rows_and_says_so(tmp_path):
    view = _view(_base(tmp_path, sector_reason="not_applicable: banks"),
                 show_empty=True)
    concepts = {r.get("concept") for r in view["rows"]}
    assert not concepts & card.BANK_HIDDEN
    assert "не применимо к банкам" in view["hidden_note"]


def test_fill_rate_skips_meaningless_and_counts_gaps(tmp_path):
    view = _view(_base(tmp_path), show_empty=True)
    filled, applicable, gaps = card.fill_rate(view)
    # ROE 2023 (отрицательный капитал) не в знаменателе; P/B — пробелы
    assert ("roe", "2023") not in gaps
    assert ("pb", "2023") in gaps and ("pb", "2024") in gaps
    assert filled + len(gaps) == applicable
    assert 0 < filled < applicable


def test_chart_table_scales_money_axis(tmp_path):
    repos = _base(tmp_path)
    view = _view(repos)
    info = data.measure_table_rows(repos, "US-AAA", card.CARD_YEARS)
    table = card.chart_table(view, info)
    assert table["years"] == ["2023", "2024"]
    assert card.axis_label(table, "net_margin") == "Чистая маржа, %"
    row = next(m for m in table["measures"] if m["concept"] == "net_margin")
    assert row["year_values"] == {"2023": pytest.approx(10.0),
                                  "2024": pytest.approx(20.0)}


def test_history_rebuild_makes_a_new_version_of_an_existing_year(
        tmp_path, monkeypatch):
    repos = _base(tmp_path)
    built = []

    class FakeBuilder:
        def build(self, instrument_id, issuer_id, end):
            built.append(end)

    import rusterm.core.snapshot as snapshot_module
    monkeypatch.setattr(snapshot_module, "make_snapshot_builder",
                        lambda _repos, _today: FakeBuilder())
    monkeypatch.setattr(repos.snapshot, "annual_period_ends",
                        lambda _issuer: ["2024-12-31", "2023-12-31"])
    plain = build_history(repos, "US-AAA", "i-AAA", today="2025-06-01")
    assert plain.skipped == ["2023-12-31", "2024-12-31"]
    assert built == []
    again = build_history(repos, "US-AAA", "i-AAA", today="2025-06-01",
                          rebuild=True)
    assert again.built == ["2023-12-31", "2024-12-31"]
    assert again.current_rebuilt and built[-1] == "2025-06-01"


def _stinv_self(cash_concepts, unmapped=()):
    snapshots = SimpleNamespace(
        as_reported_facts=lambda _issuer, concepts: (
            [] if concepts == ("st_investments",) else
            [(c, "1", "f", "USD", None, "2024-12-31", "cash")
             for c in cash_concepts]),
        unmapped_current_investments=lambda _issuer, _end: list(unmapped))
    builder = SimpleNamespace(_snapshots=snapshots)
    builder._stinv_never_in_full_balance = (
        lambda issuer, end: SnapshotBuilder._stinv_never_in_full_balance(
            builder, issuer, end))
    return builder


def test_stinv_never_reported_is_zero_only_for_full_us_gaap_balance():
    us = _stinv_self(["us-gaap:CashAndCashEquivalentsAtCarryingValue"])
    assert SnapshotBuilder._stinv_absent_from_balance(
        us, "i", "2024-12-31") == \
        "st_investments_never_reported: us-gaap balance"
    ifrs = _stinv_self(["ifrs-full:CashAndCashEquivalents"])
    assert SnapshotBuilder._stinv_absent_from_balance(
        ifrs, "i", "2024-12-31") is None
    hidden = _stinv_self(["us-gaap:CashAndCashEquivalentsAtCarryingValue"],
                         unmapped=["us-gaap:ShortTermInvestmentsCurrent"])
    assert SnapshotBuilder._stinv_absent_from_balance(
        hidden, "i", "2024-12-31") is None
