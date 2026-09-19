"""TASK-C4: экспорт того, что на экране — csv/md тем же кодом ядра,
график в png с подписью, колонка источника у каждой строки со значением.

Слой данных тестируется без Qt (ADR-0023 №4): значения в файле
обязаны совпадать байт-в-байт с выводом snapshot_to_csv/snapshot_to_md
ядра — тех же вызовов, что у rusterm export; desktop-слой только
дописывает колонку/раздел «источник» из lineage фактов. Оконные тесты
живут под importorskip PySide6, offscreen, диалог сохранения
заглушается — ни одного настоящего диалога и записи вне tmp_path.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import csv  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import sqlite3  # noqa: E402
import uuid  # noqa: E402

import pytest  # noqa: E402

from rusterm.core.export import snapshot_to_csv, snapshot_to_md  # noqa: E402
from rusterm.core.snapshot import SnapshotBuilder  # noqa: E402
from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (Instrument, Issuer,  # noqa: E402
                                 RepoRegistry, persist_ingestion_results)


def _fact(issuer_id: str, concept: str, value: str) -> dict:
    return {
        "fact_id": str(uuid.uuid4()),
        "issuer_id": issuer_id,
        "listing_id": None,
        "concept": concept,
        "canonical_concept": concept,
        "concept_map_version": "synthetic.v1",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "period_type": "duration",
        "value": value,
        "unit": "USD",
        "currency": "USD",
        "basis": "as_reported",
        "origin": "extracted",
        "source_ref": "a" * 64,
        "locator": {"kind": "api",
                    "endpoint": "https://example.test/companyfacts"},
        "parser_version": "synthetic.v1",
        "status": "ok",
    }


@pytest.fixture()
def env(tmp_path):
    """Два эмитента: E01 со значениями и E02 без operating_income —
    его nopat под отказом, и отказ в файле обязан звучать теми же
    словами, что на экране."""
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    plans = {
        "E01": {"operating_income": "700", "d_and_a": "100",
                "tax_expense": "20", "pretax_income": "100"},
        "E02": {"d_and_a": "100", "tax_expense": "20",
                "pretax_income": "100"},
    }
    for ticker, facts in plans.items():
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", f"Corp {ticker}", "US", "0000000000", None,
            "us-gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            f"US-{ticker}", f"i-{ticker}", None, "common", "active",
            None))
        fact_dicts = [_fact(f"i-{ticker}", concept, value)
                      for concept, value in facts.items()]
        persist_ingestion_results(repos.conn, fact_dicts, [])
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build(f"US-{ticker}", f"i-{ticker}", "2026-09-19")
    repos.watchlist.create_watchlist("wl-1", "main", None, None)
    vid = repos.watchlist.new_version("wlv-1", "wl-1", 1, "seed", None)
    for ticker in plans:
        repos.watchlist.add_member(vid, f"US-{ticker}", None)
    yield repos, paths
    conn.close()


def test_csv_values_are_byte_identical_to_core(env):
    """C4.1: значения и отказы в csv — байт-в-байт snapshot_to_csv
    ядра (тот же вызов, что у rusterm export); desktop-слой только
    дописывает колонку «источник»."""
    repos, _ = env
    sid = repos.snapshot.latest_snapshot_id("US-E01")
    measures = repos.snapshot.get_measures(sid)
    core_rows = list(csv.reader(io.StringIO(snapshot_to_csv(measures))))
    mine = desktop_data.export_table_csv(repos, "US-E01")
    mine_rows = list(csv.reader(io.StringIO(mine)))
    assert mine_rows[0] == core_rows[0]
    assert mine_rows[1] == core_rows[1] + ["источник"]
    for core_row, mine_row in zip(core_rows[2:], mine_rows[2:]):
        assert mine_row[:-1] == core_row


def test_every_valued_row_carries_a_source(env):
    """C4.3: ни одна строка со значением не уходит без источника:
    канал, локатор, хэш ответа, конец периода."""
    repos, _ = env
    text = desktop_data.export_table_csv(repos, "US-E01")
    rows = list(csv.reader(io.StringIO(text)))
    source_idx = rows[1].index("источник")
    value_idx = rows[1].index("value")
    valued = [r for r in rows[2:] if r[value_idx] not in ("", None)]
    assert valued, "ожидались строки со значениями"
    for row in valued:
        assert row[source_idx], row
        assert "#aaaa" in row[source_idx]
        assert "2025-12-31" in row[source_idx]
        assert "companyfacts" in row[source_idx]


def test_refusal_words_survive_into_files(env):
    """C4.1: отказ в файле — те же слова, что на экране: токен
    null_reason дословно и в csv-колонке, и в md-сноске ядра."""
    repos, _ = env
    sid = repos.snapshot.latest_snapshot_id("US-E02")
    measures = repos.snapshot.get_measures(sid)
    refusal = next(m[10] for m in measures
                   if m[3] == "nopat" and m[10])
    assert refusal == "missing_data: operating_income"
    csv_text = desktop_data.export_table_csv(repos, "US-E02")
    assert refusal in csv_text
    md_text = desktop_data.export_table_md(repos, "US-E02")
    assert refusal in md_text
    assert md_text.startswith(snapshot_to_md(measures).splitlines()[0])


def test_md_keeps_core_text_and_adds_sources(env):
    """C4.1/C4.3: md — текст ядра без изменений плюс раздел
    «Источники» по каждой мере."""
    repos, _ = env
    sid = repos.snapshot.latest_snapshot_id("US-E01")
    measures = repos.snapshot.get_measures(sid)
    core_text = snapshot_to_md(measures)
    mine = desktop_data.export_table_md(repos, "US-E01")
    assert mine.startswith(core_text)
    assert "\nИсточники:\n" in mine
    for m in measures:
        assert f"- {m[3]}:" in mine


def test_export_without_snapshot_is_none_not_empty_file(env):
    repos, _ = env
    assert desktop_data.export_table_csv(repos, "US-NOPE") is None
    assert desktop_data.export_table_md(repos, "US-NOPE") is None


def test_chart_caption_carries_issuer_measure_period_date(env):
    """C4.2: подпись png — эмитент, мера, период, дата выгрузки."""
    repos, _ = env
    table = {"ticker": "E01", "name": "Corp E01"}
    caption = desktop_data.chart_caption(table, "net_margin",
                                         "2024-12-31",
                                         exported_at="2026-09-20")
    assert "E01" in caption and "Corp E01" in caption
    assert "net_margin" in caption
    assert "2024-12-31" in caption
    assert "выгружено 2026-09-20" in caption


def test_window_export_buttons_write_files(env, monkeypatch, tmp_path):
    """Кнопки окна пишут файлы: диалог заглушен, запись — в tmp_path.
    Под PySide6-менее машиной файл пропускается целиком."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from rusterm.desktop import window as desktop_window

    app = QApplication.instance() or QApplication([])
    repos, paths = env
    window = desktop_window._build_window(repos, paths, "wl-1")
    window.close()

    from PySide6.QtWidgets import QPushButton, QTreeWidget

    tree = window.findChild(QTreeWidget, "tree")
    assert tree is not None
    energy = tree.topLevelItem(0)
    assert energy is not None and energy.childCount() > 0
    tree.setCurrentItem(energy.child(0))

    target = tmp_path / "out.csv"
    monkeypatch.setattr(
        desktop_window.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")))
    csv_button = window.findChild(QPushButton, "export_csv_button")
    assert csv_button is not None
    csv_button.click()
    assert target.exists()
    assert "concept_map_version" in target.read_text(encoding="utf-8")

    png_target = tmp_path / "chart.png"
    monkeypatch.setattr(
        desktop_window.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(png_target), "")))
    png_button = window.findChild(QPushButton, "save_png_button")
    assert png_button is not None
    png_button.click()
    assert png_target.exists()
    assert png_target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
