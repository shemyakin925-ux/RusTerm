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


def test_ifrs_filer_gets_no_market_cap_without_the_ads_ratio(tmp_path):
    """Сверка 08.10: AMX — 60 млрд обыкновенных акций × цена расписки
    (1 ADS = 20 акций) давали 1,34 трлн против 67 млрд у Yahoo. Пока
    коэффициента нет (ТЗ-138 A2), капитализация — честный отказ."""
    repos, sha = _repos(tmp_path)
    for i in range(3):
        repos.fact.insert_fact(
            f"ifrs-{i}", "i-F", None, f"ifrs-full:Revenue{i}", "2024-01-01",
            "2024-12-31", "duration", "1", "USD", "USD", "as_reported",
            "extracted", sha, {"endpoint": "companyfacts", "kind": "20-F"},
            "t")
    assert repos.snapshot.files_mainly_ifrs("i-F") is True
    _fact(repos, sha, "a", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 1)
    _fact(repos, sha, "b", "Revenues", "revenue", "2023-01-01",
          "2023-12-31", 1)
    _fact(repos, sha, "c", "Revenues", "revenue", "2022-01-01",
          "2022-12-31", 1)
    _fact(repos, sha, "d", "Revenues", "revenue", "2021-01-01",
          "2021-12-31", 1)
    assert repos.snapshot.files_mainly_ifrs("i-F") is False


@pytest.mark.parametrize("cover, ratio", [
    (b"<td>American Depositary Shares, each representing 20 B Shares, "
     b"without par value</td>", 20.0),
    (b"American Depositary Shares (ADSs), with each ADS representing "
     b"<b>two</b> ordinary shares of BHP Group Limited.", 2.0),
    (b"American Depositary Shares (evidenced by American Depositary "
     b"Receipts) each representing&#160;ten ordinary shares", 10.0),
    (b"The ADRs evidence Rio Tinto plc ADSs, each representing one "
     b"ordinary share.", 1.0),
])
def test_ads_ratio_is_read_from_the_20f_cover(cover, ratio):
    """Фразы с настоящих обложек 20-F (AMX, BHP, VOD, RIO; 08.10)."""
    from rusterm.core.ads import parse_ads_ratio
    parsed = parse_ads_ratio(cover)
    assert parsed is not None and parsed[0] == ratio
    assert "each" in parsed[1]


def test_no_ads_phrase_means_no_ratio():
    from rusterm.core.ads import parse_ads_ratio
    assert parse_ads_ratio(b"Class B subordinate voting shares, NYSE") is None
    assert parse_ads_ratio(b"ADSs, each representing zero shares") is None


def test_latest_ads_ratio_door_reads_the_fresh_fact(tmp_path):
    from rusterm.core import ads
    repos, sha = _repos(tmp_path)
    assert repos.snapshot.latest_ads_ratio("i-F") is None
    for fid, day, value in (("r-old", "2024-04-01", "10"),
                            ("r-new", "2026-04-28", "20")):
        repos.fact.insert_fact(
            fid, "i-F", None, ads.CONCEPT, day, day, "instant", value,
            "pure", None, "as_reported", "extracted", sha,
            {"kind": "20-F", "quote": "each representing 20"},
            ads.PARSER_VERSION, canonical_concept=ads.CANONICAL)
    assert repos.snapshot.latest_ads_ratio("i-F") == (20.0, "r-new")


def _stock(repos, sha, fid, tag, canonical, end, value):
    _fact(repos, sha, fid, tag, canonical, end, end, value, kind="instant")


def test_commercial_paper_is_added_to_long_term_debt(tmp_path):
    """BACKLOG P5: AAPL 96,66 (LongTermDebt) + 9,97 (CommercialPaper) =
    106,63 млрд, как в 10-K и у Yahoo; чистый долг считает всё."""
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    _stock(repos, sha, "ltd", "LongTermDebt", "total_debt", "2024-12-31", 90)
    _stock(repos, sha, "cp", "CommercialPaper", None, "2024-12-31", 10)
    _stock(repos, sha, "cash", "CashAndCashEquivalentsAtCarryingValue",
           "cash", "2024-12-31", 30)
    make_snapshot_builder(repos, "2024-12-31").build("US-F", "i-F",
                                                     "2024-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    net_debt = next(m for m in repos.snapshot.get_measures(sid)
                    if m[3] == "net_debt")
    assert float(net_debt[4]) == pytest.approx(70.0), \
        "долг 90 + бумаги 10 − деньги 30 (краткосрочных вложений нет)"
    assert "cp" in repos.snapshot.lineage_fact_ids(net_debt[0])


def test_combined_debt_tag_does_not_get_paper_twice(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2024-01-01",
          "2024-12-31", 100)
    _stock(repos, sha, "all", "DebtLongtermAndShorttermCombinedAmount",
           "total_debt", "2024-12-31", 100)
    _stock(repos, sha, "cp", "CommercialPaper", None, "2024-12-31", 10)
    _stock(repos, sha, "cash", "CashAndCashEquivalentsAtCarryingValue",
           "cash", "2024-12-31", 30)
    make_snapshot_builder(repos, "2024-12-31").build("US-F", "i-F",
                                                     "2024-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    net_debt = next(m for m in repos.snapshot.get_measures(sid)
                    if m[3] == "net_debt")
    assert float(net_debt[4]) == pytest.approx(70.0), \
        "объединённый тег уже содержит бумаги"


def test_stale_cover_shares_fall_back_to_fresh_diluted_count(tmp_path):
    """BACKLOG P7: у CMCSA обложка подаётся по классам, число акций
    застряло в 2009-м; капитализация берёт свежее разводнённое число
    акций, и lineage называет подмену."""
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2025-01-01",
          "2025-12-31", 100)
    repos.fact.insert_fact(
        "dei-old", "i-F", None, "dei:EntityCommonStockSharesOutstanding",
        "2009-12-31", "2009-12-31", "instant", "1000", "shares", None,
        "as_reported", "extracted", sha, {"endpoint": "companyfacts"},
        "t", canonical_concept="shares_outstanding")
    for fid, start, value in (("dil-h", "2026-01-01", "40"),
                              ("dil-q", "2026-04-01", "50")):
        repos.fact.insert_fact(
            fid, "i-F", None,
            "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
            start, "2026-06-30", "duration", value, "shares", None,
            "as_reported", "extracted", sha, {"endpoint": "companyfacts"},
            "t", canonical_concept="shares_diluted")
    repos.price.put_rows("US-F", "yahoo", [
        {"date": "2026-09-29", "close": 10.0, "adjusted": 10.0,
         "currency": "USD", "volume": 1}])
    make_snapshot_builder(repos, "2026-09-30").build("US-F", "i-F",
                                                     "2026-09-30")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    cap = next(m for m in repos.snapshot.get_measures(sid)
               if m[3] == "market_cap")
    assert float(cap[4]) == pytest.approx(500.0), \
        "квартальное разводнённое число (50) × цена 10"
    assert repos.snapshot.lineage_fact_ids(cap[0]) == ["dil-q"]


def test_split_factor_after_counts_each_date_once():
    """BACKLOG P4: AAPL 2019 — цена ряда 73,41 при фактических 293,6
    (сплит 4:1 в 2020); событие двух источников не умножается дважды."""
    from rusterm.core.prices import split_factor_after
    events = [
        {"kind": "split", "ex_date": "2014-06-09", "factor": 7.0},
        {"kind": "split", "ex_date": "2020-08-31", "factor": 4.0},
        {"kind": "split", "ex_date": "2020-08-31", "factor": 4.0},
        {"kind": "dividend", "ex_date": "2021-01-01", "factor": None},
    ]
    assert split_factor_after(events, "2019-12-31") == 4.0
    assert split_factor_after(events, "2013-12-31") == 28.0
    assert split_factor_after(events, "2021-01-01") == 1.0


def test_price_as_of_prefers_the_yahoo_row_of_the_same_day(tmp_path):
    repos, _sha = _repos(tmp_path)
    repos.price.put_rows("US-F", "twelvedata", [
        {"date": "2024-12-31", "close": 9.5, "currency": "USD"}])
    repos.price.put_rows("US-F", "yahoo", [
        {"date": "2024-12-31", "close": 10.0, "currency": "USD"}])
    assert repos.price.price_as_of("US-F", "2025-01-02")["close"] == 10.0


def test_past_market_cap_uses_the_actual_price_of_that_day(tmp_path):
    repos, sha = _repos(tmp_path)
    _fact(repos, sha, "rev", "Revenues", "revenue", "2019-01-01",
          "2019-12-31", 100)
    repos.fact.insert_fact(
        "sh", "i-F", None, "dei:EntityCommonStockSharesOutstanding",
        "2019-12-31", "2019-12-31", "instant", "100", "shares", None,
        "as_reported", "extracted", sha, {"endpoint": "companyfacts"},
        "t", canonical_concept="shares_outstanding")
    repos.price.put_rows("US-F", "yahoo", [
        {"date": "2019-12-31", "close": 25.0, "currency": "USD"}])
    repos.corp_action.put("US-F", "2020-08-31", "split", 4.0, None,
                               None, "yahoo")
    make_snapshot_builder(repos, "2019-12-31").build("US-F", "i-F",
                                                     "2019-12-31")
    sid = repos.snapshot.latest_snapshot_id("US-F")
    cap = next(m for m in repos.snapshot.get_measures(sid)
               if m[3] == "market_cap")
    assert float(cap[4]) == pytest.approx(25.0 * 4 * 100)


def test_statement_row_keeps_the_home_currency_of_the_filer(tmp_path):
    """08.10: в 20-F AMX рядом с песо стоит пересчёт последнего года в
    USD — строка выручки не должна прыгать песо → доллар → песо."""
    repos, sha = _repos(tmp_path)
    for i, (start, end, value) in enumerate((
            ("2022-01-01", "2022-12-31", "844"),
            ("2023-01-01", "2023-12-31", "816"),
            ("2024-01-01", "2024-12-31", "869"))):
        repos.fact.insert_fact(
            f"mxn-{i}", "i-F", None, "ifrs-full:Revenue", start, end,
            "duration", value, "MXN", "MXN", "as_reported", "extracted",
            sha, {"endpoint": "companyfacts"}, "t",
            canonical_concept="revenue")
    repos.fact.insert_fact(
        "usd-24", "i-F", None, "ifrs-full:Revenue", "2024-01-01",
        "2024-12-31", "duration", "43", "USD", "USD", "as_reported",
        "extracted", sha, {"endpoint": "companyfacts"}, "t",
        canonical_concept="revenue")
    series = card.statement_series(repos, "i-F", "revenue", "flow")
    assert series["2024"][:2] == (869.0, "MXN")
    assert {s[1] for s in series.values()} == {"MXN"}


# ── ТЗ-134 W5: подсказка-команда становится кнопкой ─────────────────────

def test_split_hint_moves_window_command_to_argv():
    from rusterm.desktop import actions, data
    words, argv = actions.split_hint(
        data.NO_HISTORY_HINT.format(instrument_id="US-X"))
    assert argv == ["snapshot", "--instrument", "US-X"]
    assert "rusterm" not in words and words.startswith("истории мер нет")
    assert actions.button_title(argv) == "Посчитать ряд"


def test_split_hint_keeps_text_of_commands_window_does_not_run():
    from rusterm.desktop import actions
    text = "что делать: владение — rusterm ingest --source ownership"
    assert actions.split_hint(text) == (text, None)
    assert actions.split_hint(None) == ("", None)


def test_split_hint_approve_has_own_title():
    from rusterm.desktop import actions
    _, argv = actions.split_hint(
        "x\nчто делать: подтвердите — rusterm peers set ps1 --tickers A "
        "--market US --origin manual --approve")
    assert argv[:3] == ["peers", "set", "ps1"]
    assert actions.button_title(argv) == "Подтвердить группу аналогов"


def test_run_core_command_refuses_commands_outside_window(tmp_path):
    from rusterm.desktop import actions
    out = actions.run_core_command(tmp_path, ["ingest", "--source", "edgar"])
    assert not out.ok and out.reason == "not_a_window_command"
    out = actions.run_core_command(tmp_path, ["peers", "--no-such-flag"])
    assert not out.ok and out.reason == "bad_arguments"
