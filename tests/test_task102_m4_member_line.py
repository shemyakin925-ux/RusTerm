"""ТЗ-102 M4: отказ «мало участников» различает две причины.

Зачем (решение координатора 26.09, строка 6 таблицы, вариант (b)):
строка `peer_set_too_small` означает сегодня и «в наборе столько всех»,
и «в наборе десять бумаг, а значение доехало до одной». На копии базы
27.09 так отказывают почти все 20 отраслевых ячеек, и по словам отказ
неотличим от тощего набора. Порог `AGGREGATE_MIN_PEERS` не меняется
(запрет круга) — меняется только фраза: когда участников столько,
сколько нужно, а мера есть не у всех, строка говорит
«участников N, значение меры есть у K».

K — это не `n` отказа (у отказа `n` всегда 0) и не счётчик `no_value`
(он считает выпавших, а не оставшихся). Внеоконные участники (ТЗ-97 Q8)
в `N` не входят: до расчёта этой меры они не дошли.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from rusterm.core.industry.aggregate import (build_sector_aggregates,
                                             sector_aggregate,
                                             shortfall_note)
from rusterm.core.peers import AGGREGATE_MIN_PEERS
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

AS_OF = "2026-06-30"
BASE = "2025-12-31"
PHRASE = "участников 8, значение меры есть у 1"


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths), paths


def _sector(repos, n: int, with_value: int, sector: str = "tankers",
            snapshots: bool = True, odd: dict[int, str] | None = None) -> str:
    """Набор из `n` участников net_margin: значение есть у первых
    `with_value`. `snapshots=False` — остальные вовсе без снапшота на
    дату (это тоже «нет значения», но другим путём); `odd` — конец
    периода конкретного участника, для окна ТЗ-97 Q8."""
    odd = odd or {}
    peers = repos.peer_set
    peers.create_peer_set(sector, "industry", sector)
    peers.add_version(f"psv-{sector}", sector, 1, "2025-01-01", None,
                      "manual", "v1", True, None, None)
    for k in range(n):
        iid = f"in-{k}"
        end = odd.get(k, BASE)
        peers.add_member(f"psv-{sector}", iid, None)
        repos.instrument.upsert_issuer(Issuer(
            f"i-{iid}", f"Corp {k}", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, f"i-{iid}", None, "common", "active", None))
        if not snapshots and k >= with_value:
            continue
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, end, None,
                                       "none", "ready")
        repos.snapshot.add_block(f"s-{iid}", "fundamentals", "ready", None)
        repos.snapshot.insert_measure(
            measure_id=f"m-{iid}", snapshot_id=f"s-{iid}", scope="issuer",
            scope_ref=f"i-{iid}", concept="net_margin",
            value=repr(float(k + 1)) if k < with_value else None,
            unit="ratio", period_start="2025-06-01", period_end=end,
            formula_id="net_margin", method_version="v1",
            null_reason=None if k < with_value else "missing_data",
            peer_set_version=None)
    return sector


def _net_margin(repos, sector):
    built = build_sector_aggregates(repos, sector, AS_OF, ("net_margin",))
    assert built["outcome"] == "resolved"
    return built["aggregates"][0]


def test_threshold_is_eight_and_this_item_does_not_move_it():
    """Pinned: M4 меняет фразу, а не порог (запрет круга)."""
    assert AGGREGATE_MIN_PEERS == 8


def test_missing_values_are_named_by_both_numbers():
    """Зуб 1 (Done when): 8 участников, значение у одного — строка
    называет оба числа."""
    agg = sector_aggregate("roe", [(f"m{i}", 1.0 if i == 0 else None)
                                   for i in range(8)])
    assert agg.null_reason == "peer_set_too_small"
    assert (agg.members_seen, agg.with_value) == (8, 1)
    assert shortfall_note(agg) == PHRASE


def test_thin_membership_keeps_the_old_line():
    """Зуб 2: участников меньше порога — нехватка в составе набора,
    прежней строки фраза не касается."""
    agg = sector_aggregate("roe", [(f"m{i}", 1.0) for i in range(3)])
    assert agg.null_reason == "peer_set_too_small"
    assert (agg.members_seen, agg.with_value) == (3, 3)
    assert shortfall_note(agg) == ""


def test_computed_measure_gets_no_note():
    """Зуб 3: посчитанная мера фразы не получает, даже когда у части
    участников значения нет (8 из 9 — считается)."""
    agg = sector_aggregate("roe", [(f"m{i}", 1.0 if i < 8 else None)
                                   for i in range(9)])
    assert agg.null_reason is None
    assert shortfall_note(agg) == ""


def test_other_refusal_is_not_relabelled():
    """Зуб 4: отказ не по этому поводу — фразы нет (в частности
    `peer_set_not_confirmed`, где участников тоже может быть много)."""
    agg = sector_aggregate("roe", [(f"m{i}", 1.0 if i == 0 else None)
                                   for i in range(8)], verified=False)
    assert agg.null_reason == "peer_set_not_confirmed"
    assert shortfall_note(agg) == ""


def test_numbers_survive_the_rebuild_for_missing_snapshots(env):
    """Зуб 5: строка агрегата пересобирается при отказе по валюте и при
    отсутствии снапшота — числа не должны обнулиться по дороге."""
    _conn, repos, _paths = env
    agg = _net_margin(repos, _sector(repos, 9, 1, snapshots=False))
    assert agg.null_reason == "peer_set_too_small"
    assert (agg.members_seen, agg.with_value) == (9, 1)
    assert shortfall_note(agg) == "участников 9, значение меры есть у 1"
    # участники без снапшота названы и прежним счётчиком: фраза
    # добавляется к отчётности причин, а не заменяет её
    assert agg.reason_counts.get("no_snapshot_at_date") == 8


def test_members_outside_the_window_are_not_counted(env):
    """Зуб 6: внеоконный участник (ТЗ-97 Q8) до расчёта меры не дошёл —
    в «участников N» он не входит."""
    _conn, repos, _paths = env
    sector = _sector(repos, 10, 1, odd={9: "2022-12-31"})
    agg = _net_margin(repos, sector)
    assert agg.null_reason == "peer_set_too_small"
    assert (agg.members_seen, agg.with_value) == (9, 1)
    assert agg.excluded == {"in-9": "2022-12-31"}
    note = shortfall_note(agg)
    assert note == "участников 9, значение меры есть у 1", note
    assert "участников 10" not in note


def test_cli_industry_line_reads_both_numbers(env):
    """Зуб 7: `rusterm industry`."""
    conn, repos, paths = env
    _sector(repos, 8, 1)
    conn.close()
    repo = Path(__file__).resolve().parents[1]
    env_vars = {**os.environ,
                "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
                "PYTHONPATH": os.pathsep.join(
                    [str(repo), os.environ.get("PYTHONPATH", "")]),
                "TERM": "xterm"}
    r = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(paths.root),
         "industry", "--sector", "tankers", "--as-of", AS_OF],
        capture_output=True, text=True, env=env_vars)
    assert r.returncode == 0, r.stderr
    assert PHRASE in r.stdout, r.stdout
    assert "нет причин" not in r.stdout, r.stdout


def test_tui_and_qt_tab_say_the_same(env):
    """Зуб 8: экран «Отрасль» (TUI) и вкладка Qt — одна формулировка:
    пользователь не выбирает, где ему поверят (ТЗ-97 Q8 тот же закон)."""
    from rusterm.desktop import data
    from rusterm.tui.model import industry_rows, render_industry
    _conn, repos, _paths = env
    screen = industry_rows(repos, _sector(repos, 8, 1), AS_OF)
    tui = "\n".join(render_industry(screen))
    assert PHRASE in tui, tui
    mark = {r["concept"]: r["mark"]
            for r in data.industry_table_rows(screen)}["net_margin"]
    assert PHRASE in mark, mark


def test_period_note_still_shown_with_the_shortfall(env):
    """Зуб 9: новая фраза не вытесняет старую — обе в одной строке
    экрана и в пометке вкладки."""
    from rusterm.tui.model import industry_rows, render_industry
    _conn, repos, _paths = env
    screen = industry_rows(repos, _sector(repos, 10, 1,
                                          odd={9: "2022-12-31"}), AS_OF)
    line = next(l for l in render_industry(screen) if "net_margin" in l)
    assert PHRASE.replace("8", "9") in line, line
    assert "вне окна: in-9 (2022-12-31)" in line, line
