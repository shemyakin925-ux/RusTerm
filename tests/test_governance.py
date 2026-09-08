"""Тесты governance-светофора (TASK-7 T17, governance-thresholds.md).

По индикатору — тест, бьющий все четыре цвета; отдельные тесты на
отсутствие агрегата/балла и на обязательность lineage. Пороги — дословно
из документа; серый — для отсутствия данных, никогда не зелёный.
"""
from __future__ import annotations

import inspect
import os
import shutil
import sqlite3
import tempfile

import pytest

from rusterm.core import governance as gov
from rusterm.store.db import _SCHEMA_VERSION, apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
)


# ── Индикатор 1: доля независимых директоров ───────────────────────────
def test_indicator_1_independent_directors_all_four_colors():
    a = gov.independent_directors("ins1", 0.6, "2024-12-31", "doc#p1")
    assert (a.color, a.method_version) == ("green", "governance.v1")
    # граница 50% — уже зелёный (>= 50%)
    assert gov.independent_directors(
        "ins1", 0.5, "2024-12-31", "doc#p1").color == "green"
    assert gov.independent_directors(
        "ins1", 0.4, "2024-12-31", "doc#p1").color == "yellow"
    # граница 33% — жёлтый (33-50)
    assert gov.independent_directors(
        "ins1", 0.33, "2024-12-31", "doc#p1").color == "yellow"
    assert gov.independent_directors(
        "ins1", 0.2, "2024-12-31", "doc#p1").color == "red"
    gray = gov.independent_directors("ins1", None, "2024-12-31", "doc#p1")
    assert gray.color == "gray"
    assert gray.reason.startswith("no_data:")


# ── Индикатор 2: совмещение CEO и председателя ─────────────────────────
def test_indicator_2_ceo_chair_all_four_colors():
    assert gov.ceo_chair("ins1", True, False, "2024-12-31",
                         "doc#p2").color == "green"
    assert gov.ceo_chair("ins1", False, True, "2024-12-31",
                         "doc#p2").color == "yellow"
    assert gov.ceo_chair("ins1", False, False, "2024-12-31",
                         "doc#p2").color == "red"
    # не раскрыто ни то, ни другое — серый
    assert gov.ceo_chair("ins1", None, None, "2024-12-31",
                         "doc#p2").color == "gray"
    # роли разделены — зелёный независимо от lead (он при совмещении)
    assert gov.ceo_chair("ins1", True, None, "2024-12-31",
                         "doc#p2").color == "green"


# ── Индикатор 3: сделки со связанными сторонами ────────────────────────
def test_indicator_3_related_party_all_four_colors():
    assert gov.related_party("ins1", 0.004, None, "2024-12-31",
                             "doc#p3").color == "green"
    assert gov.related_party("ins1", 0.02, None, "2024-12-31",
                             "doc#p3").color == "yellow"
    assert gov.related_party("ins1", 0.04, True, "2024-12-31",
                             "doc#p3").color == "red"
    # без одобрения независимой частью — красный даже при малом объёме
    assert gov.related_party("ins1", 0.001, False, "2024-12-31",
                             "doc#p3").color == "red"
    # раздел отсутствует — серый, а не зелёный
    gray = gov.related_party("ins1", None, None, "2024-12-31", "doc#p3")
    assert gray.color == "gray"


# ── Индикатор 4: чистые операции инсайдеров ────────────────────────────
def test_indicator_4_insider_net_all_four_colors():
    assert gov.insider_net("ins1", 0.002, "2024-12-31",
                           "doc#p4").color == "green"
    assert gov.insider_net("ins1", 0.0, "2024-12-31",
                           "doc#p4").color == "yellow"
    yellow_band = gov.insider_net("ins1", -0.002, "2024-12-31", "doc#p4")
    assert yellow_band.color == "yellow"
    # −0,3% вне ±0,1%: причина показывает реальную полосу, не «в пределах»
    assert "within_pm" not in yellow_band.reason
    within = gov.insider_net("ins1", -0.001, "2024-12-31", "doc#p4")
    assert within.reason == "within_pm_0.1pct"
    assert gov.insider_net("ins1", -0.006, "2024-12-31",
                           "doc#p4").color == "red"
    assert gov.insider_net("ins1", None, "2024-12-31",
                           "doc#p4").color == "gray"


# ── Индикатор 5: аудитор ───────────────────────────────────────────────
def test_indicator_5_auditor_all_four_colors():
    assert gov.auditor("ins1", 0, False, 6, "2024-12-31",
                       "doc#p5").color == "green"
    assert gov.auditor("ins1", 1, False, 8, "2024-12-31",
                       "doc#p5").color == "yellow"
    assert gov.auditor("ins1", 2, False, 9, "2024-12-31",
                       "doc#p5").color == "red"
    assert gov.auditor("ins1", 0, True, 6, "2024-12-31",
                       "doc#p5").color == "red"
    # окно раскрытия 3 года: «одна фирма 5 лет» не доказано — серый
    assert gov.auditor("ins1", 0, False, 3, "2024-12-31",
                       "doc#p5").color == "gray"
    assert gov.auditor("ins1", None, None, None, "2024-12-31",
                       "doc#p5").color == "gray"


# ── Светофор, а не балл ────────────────────────────────────────────────
def test_no_aggregate_score_anywhere():
    src = inspect.getsource(gov)
    for forbidden in ("score", "weight", "sum("):
        assert forbidden not in src, f"в модуле найдено {forbidden!r}"
    fields = {name for name in gov.Assessment.__dataclass_fields__}
    assert fields == {
        "instrument_id", "indicator", "color", "method_version",
        "as_of", "lineage_ref", "reason",
    }, "у оценки не должно быть полей агрегата"
    # пять индикаторов не сворачиваются в один цвет: нет «итоговой» функции
    public_calls = [n for n in dir(gov)
                    if not n.startswith("_") and callable(getattr(gov, n))]
    assert not any(("total" in n or "overall" in n) for n in public_calls)


def test_color_without_lineage_raises():
    with pytest.raises(ValueError, match="lineage"):
        gov.independent_directors("ins1", 0.6, "2024-12-31", "")
    with pytest.raises(ValueError, match="lineage"):
        gov.ceo_chair("ins1", True, False, "2024-12-31", "   ")
    with pytest.raises(ValueError, match="lineage"):
        gov.related_party("ins1", 0.01, True, "2024-12-31", None)
    with pytest.raises(ValueError, match="lineage"):
        gov.insider_net("ins1", 0.0, "2024-12-31", "")
    with pytest.raises(ValueError, match="lineage"):
        gov.auditor("ins1", 0, False, 6, "2024-12-31", "")
    # серый тоже несёт lineage: нет данных, но есть ссылка на раздел
    gray = gov.insider_net("ins1", None, "2024-12-31", "doc#section4")
    assert gray.lineage_ref == "doc#section4"


def test_migration_35_creates_table_and_repo_appends_history():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    try:
        apply_migrations(conn)
        assert _SCHEMA_VERSION == 35
        repos = RepoRegistry(conn, paths)
        repos.instrument.upsert_issuer(Issuer(
            "i1", "N", "US", None, None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            "ins1", "i1", None, "common", "active", None))

        first = gov.independent_directors("ins1", 0.6, "2023-12-31",
                                          "doc#p1")
        second = gov.independent_directors("ins1", 0.2, "2024-12-31",
                                           "doc#p9")
        repos.governance.record(first)
        repos.governance.record(second)

        rows = repos.governance.for_instrument("ins1")
        assert len(rows) == 2
        # история не переписывается: обе оценки на месте, latest — новая
        latest = repos.governance.latest("ins1", "independent_directors")
        assert latest["as_of"] == "2024-12-31"
        assert latest["color"] == "red"
        assert repos.governance.latest("ins1", "auditor") is None
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
