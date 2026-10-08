"""Правки координатора 08.10.2026 (ТЗ-130 K3/K4, ТЗ-137 Y1) — по
находкам сверки с Yahoo (`tools/yahoo_check.py`):

- смысл тега важнее базиса подачи: NetIncomeLoss из сравнительной
  колонки (restated) побеждает ProfitLoss (с долей меньшинства), поданный
  as_reported, — у FCX маржа, ROE и P/E расходились с 10-K вдвое;
- объявления дивиденда, поданные датами (BAC с 2020), — сумма за 365
  дней и за год;
- карта us-gaap.v7: отзыв частичного тега себестоимости AT&T и преемник
  процентных расходов InterestExpenseNonoperating;
- история: старая версия снапшота на ту же дату не даёт клеток;
  «сейчас» не старше последнего годового отчёта.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import make_snapshot_builder
from rusterm.core.ttm import declared_by_year, declared_window
from rusterm.desktop import card, data
from rusterm.normalize.concepts import (WITHDRAWN_TAGS, canonical_for,
                                        map_version)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing,
                                 RepoRegistry)


def _repos(tmp_path):
    paths = AppPaths.from_root(tmp_path / "c0810")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-F", "Fixture Metals", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-F", "i-F", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-F", "US-F", "XNYS", "USD", 1, None, None))
    repos.instrument.add_ticker_history("l-F", "F", "2000-01-01", None,
                                        None, None)
    raw = repos.raw.put(b"payload", provider="edgar",
                        url="https://data.sec.gov/companyfacts/F")
    return repos, raw.sha256


def _fact(repos, sha, fid, tag, canonical, start, end, value,
          basis="as_reported", kind="duration"):
    repos.fact.insert_fact(
        fid, "i-F", None, f"us-gaap:{tag}", start, end, kind, str(value),
        "USD", "USD", basis, "extracted", sha,
        {"endpoint": "companyfacts", "kind": "10-K"}, "t",
        canonical_concept=canonical)


def test_restated_parent_income_beats_as_reported_profit_with_nci(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    _fact(repos, sha, "pl", "ProfitLoss", "net_income", "2024-01-01",
          "2024-12-31", 40)
    _fact(repos, sha, "nil", "NetIncomeLoss", "net_income", "2024-01-01",
          "2024-12-31", 20, basis="restated")
    make_snapshot_builder(repos, "2024-12-31").build("US-F", "i-F",
                                                     "2024-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    margin = next(m for m in repos.snapshot.get_measures(sid)
                  if m[3] == "net_margin")
    assert float(margin[4]) == pytest.approx(0.2), \
        "прибыль акционеров (NetIncomeLoss), а не с долей меньшинства"
    assert "nil" in repos.snapshot.lineage_fact_ids(margin[0])


def test_restated_never_adds_a_period_missing_from_as_reported(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    _fact(repos, sha, "nil", "NetIncomeLoss", "net_income", "2024-01-01",
          "2024-12-31", 20, basis="restated")
    make_snapshot_builder(repos, "2024-12-31").build("US-F", "i-F",
                                                     "2024-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    margin = next(m for m in repos.snapshot.get_measures(sid)
                  if m[3] == "net_margin")
    assert margin[4] is None and margin["null_reason"], \
        "restated только улучшает тег периода, нового периода не создаёт"


def test_declared_dividends_sum_over_the_trailing_year():
    rows = [(0.24, "2023-10-18", "2023-10-18", "d4"),
            (0.24, "2023-07-19", "2023-07-19", "d3"),
            (0.24, "2023-07-19", "2023-07-19", "dup"),
            (0.22, "2023-04-26", "2023-04-26", "d2"),
            (0.22, "2023-02-01", "2023-02-01", "d1"),
            (0.21, "2022-10-19", "2022-10-19", "old"),
            (0.92, "2023-01-01", "2023-12-31", "fy")]   # не мгновенный
    window = declared_window(rows, "2023-12-31")
    assert window.value == pytest.approx(0.92)
    assert {c.fact_id for c in window.components} == {"d1", "d2", "d3",
                                                      "d4"}
    assert declared_window(rows, "2021-06-30") is None
    by_year = declared_by_year(rows)
    assert by_year["2023"][0] == pytest.approx(0.92)
    assert len(by_year["2023"][1]) == 4 and by_year["2022"][0] == 0.21


def test_map_v7_withdraws_partial_cogs_and_adds_interest_successor():
    assert map_version("us-gaap") == "us-gaap.v7"
    assert canonical_for("OtherCostOfOperatingRevenue") is None
    assert WITHDRAWN_TAGS == {"us-gaap:OtherCostOfOperatingRevenue": "cogs"}
    assert canonical_for("InterestExpenseNonoperating") == "interest_expense"


def test_withdraw_canonical_clears_only_the_withdrawn_pair(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "other", "OtherCostOfOperatingRevenue", "cogs",
          "2024-01-01", "2024-12-31", 27)
    _fact(repos, sha, "full", "CostOfRevenue", "cogs", "2024-01-01",
          "2024-12-31", 47)
    assert repos.fact.withdraw_canonical(WITHDRAWN_TAGS, "us-gaap.v7") == 1
    assert repos.fact.get_fact("other")["canonical_concept"] is None
    assert repos.fact.get_fact("other")["concept_map_version"] == \
        "us-gaap.v7"
    assert repos.fact.get_fact("full")["canonical_concept"] == "cogs"


def test_old_snapshot_version_on_the_same_date_gives_no_cells(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    for version, value, reason in ((1, "0.5", None),
                                   (2, None, "missing_data: cogs")):
        sid = f"s-{version}"
        repos.snapshot.create_snapshot(sid, "US-F", version, "2024-12-31",
                                       None, None, "ready")
        repos.snapshot.insert_measure(
            f"m-{version}", sid, "issuer", "i-F", "gross_margin", value,
            "ratio", "2024-01-01", "2024-12-31", "f", "v1", reason, None)
    history = data.measure_history(repos, "US-F")
    assert "gross_margin" not in history.get("2024", {}), \
        "пересобранная версия честно не считает — старое число не доживает"


def test_now_value_older_than_last_annual_report_is_a_dash(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    repos.snapshot.create_snapshot("s-now", "US-F", 1, "2025-03-01", None,
                                   None, "ready")
    repos.snapshot.insert_measure(
        "m-gp", "s-now", "issuer", "i-F", "gross_profit", "30", "USD",
        "2023-07-01", "2023-09-30", "f", "v1", None, None)
    info = data.measure_table_rows(repos, "US-F", card.CARD_YEARS)
    view = card.card_view(repos, info, show_empty=True)
    row = next(r for r in view["rows"] if r.get("concept") == "gross_profit")
    now = row["cells"][-1]
    assert now["text"] == card.DASH
    assert "старше последнего годового отчёта" in now["tooltip"]
