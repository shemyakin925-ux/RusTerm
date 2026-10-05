"""ТЗ-107 V1/V2: история мер по финансовым годам и график по целым годам.

Скриншот пользователя 30.09 (BAC): в таблице только «сейчас» и 2026, на
оси графика 2026.088608 … 2026.088616 с одной точкой. Причина — снапшоты
строились только «на сегодня». Здесь: пересборка по концу каждого года,
повтор ничего не добавляет, «сейчас» остаётся текущим, а ось графика
подписана целыми годами.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.cli import main as cli_main
from rusterm.reasons_ru import reason_phrase
from rusterm.core.history import build_history
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry
from rusterm.tui import model as tui_model

TODAY = "2026-09-30"
YEARS = {"2022": ("1000", "100", "900"),
         "2023": ("1200", "180", "1000"),
         "2024": ("1500", "300", "1100")}


def _fact(conn, issuer_id, concept, start, end, value, kind):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, ?, ?, 'USD',
           'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer_id}-{concept}-{start}-{end}", issuer_id, concept,
         start, end, kind, value, concept))


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Corp", "US", None, "12-31", "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-HIST", "i1", None, "common", "active", None))
    for year, (revenue, net_income, assets) in YEARS.items():
        start, end = f"{year}-01-01", f"{year}-12-31"
        _fact(conn, "i1", "revenue", start, end, revenue, "duration")
        _fact(conn, "i1", "net_income", start, end, net_income, "duration")
        _fact(conn, "i1", "total_assets", end, end, assets, "instant")
    return conn, repos, paths


def test_annual_period_ends_are_fiscal_year_ends(env):
    _, repos, _ = env
    assert repos.snapshot.annual_period_ends("i1") == [
        "2024-12-31", "2023-12-31", "2022-12-31"]


def test_history_builds_one_snapshot_per_year_with_its_own_values(env):
    _, repos, _ = env
    res = build_history(repos, "US-HIST", "i1", today=TODAY)
    assert res.built == ["2022-12-31", "2023-12-31", "2024-12-31"]
    assert res.current_rebuilt
    history = tui_model.measure_history_by_year(repos, "US-HIST")
    margins = {y: history.get(y, {}).get("net_margin") for y in YEARS}
    assert margins == {"2022": 0.1, "2023": 0.15, "2024": 0.2}, margins


def test_rerun_adds_nothing_and_current_stays_last(env):
    _, repos, _ = env
    build_history(repos, "US-HIST", "i1", today=TODAY)
    count = len(repos.snapshot.snapshots_of_instrument("US-HIST"))
    res = build_history(repos, "US-HIST", "i1", today=TODAY)
    assert res.built == [] and not res.current_rebuilt
    assert len(repos.snapshot.snapshots_of_instrument("US-HIST")) == count
    snaps = repos.snapshot.snapshots_of_instrument("US-HIST")
    assert snaps[-1]["as_of"] == TODAY


def test_cli_history_reports_built_years(env, capsys):
    _, _, paths = env
    rc = cli_main(["--root", str(paths.root), "history",
                   "--instrument", "US-HIST"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "собрано лет: 3 (2022, 2023, 2024)" in out, out


def test_bank_measures_without_value_say_not_applicable(env):
    """V4: у банка EBITDA/FCF/EV без числа — not_applicable: banks, в
    окне «не применимо к банкам»; та же мера у небанка — missing_data."""
    _, repos, _ = env
    from rusterm.core.peer_sets import set_industry_peers
    from rusterm.core.snapshot import make_snapshot_builder
    from rusterm.desktop import data
    set_industry_peers(repos, "banks", ["US-HIST"], "manual", True, "2020-01-01")
    make_snapshot_builder(repos, TODAY).build("US-HIST", "i1", TODAY)
    sid = repos.snapshot.latest_snapshot_id("US-HIST")
    reasons = {m[3]: m[-1] for m in repos.snapshot.get_measures(sid)}
    rows = {r["concept"]: r for r in
            data.measure_table_rows(repos, "US-HIST")["measures"]}
    assert rows["ebitda"]["current"] == "не применимо к банкам", rows["ebitda"]
    assert data.not_applicable_text("not_applicable: banks") == \
        "не применимо к банкам"
    assert data.not_applicable_text("missing_data: capex") is None
    assert rows["net_margin"]["has_value"]


def test_non_bank_keeps_missing_data(env):
    _, repos, _ = env
    from rusterm.core.snapshot import make_snapshot_builder
    from rusterm.desktop import data
    make_snapshot_builder(repos, TODAY).build("US-HIST", "i1", TODAY)
    rows = {r["concept"]: r for r in
            data.measure_table_rows(repos, "US-HIST")["measures"]}
    # ТЗ-111 U1 (ЗАМЕНА-БУЛАВКИ: «нет данных» -> фраза словаря причин)
    assert rows["ebitda"]["current"] == reason_phrase("missing_data")
    assert not str(rows["ebitda"]["null_reason"]).startswith("not_applicable")


@pytest.mark.parametrize("suffix", ["", ".gz", ".zst"])
def test_compressed_raw_object_is_found(tmp_path, suffix):
    """V3: сжатый ответ (<sha>.gz) — на месте; окно не пишет «сырья нет»."""
    from rusterm.desktop import data
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    sha = "e7d84368" + "0" * 56
    target = paths.raw_store / sha[:2] / (sha + suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    loc = data.raw_object_location(paths, sha)
    assert loc["exists"] and loc["path"] == str(target)


def test_absent_raw_object_still_says_absent(tmp_path):
    from rusterm.desktop import data
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    assert not data.raw_object_location(paths, "ab" + "0" * 62)["exists"]
