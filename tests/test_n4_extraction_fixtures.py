"""ТЗ-24 N4: аудит извлечения физических метрик на синтетических
таблицах нарастающей пакостности.

Фикстуры — синтетика (ни одна строка не принадлежит реальной
компании). Сам аудит (запуски модели, verified-but-wrong) требует
RUSTERM_LLM_API_KEY; без ключа тесты доказывают только стадию ①
(извлечение страниц) и честно пропускают модельную половину (N7-стиль,
N2 сетевых правил). Прогон с ключом: RUSTERM_N4_WITH_MODEL=1.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from rusterm.manual.extract import extract_text

TABLES = Path(__file__).resolve().parent / "data" / "n4_fleet_tables"
NAMES = sorted(p.name for p in TABLES.glob("*.html"))

EXPECTED = {
    "table1_clean_two_column.html": 1,
    "table2_ten_column_fleet_by_class.html": 1,
    "table3_with_total_row.html": 1,
    "table4_footnote_in_number.html": 1,
}


def test_four_fixtures_exist_and_cover_the_ladder():
    assert NAMES == sorted(EXPECTED)
    for name in NAMES:
        text = (TABLES / name).read_text(encoding="utf-8")
        assert "<table>" in text
        assert "Total" in text or "footnote" in name.lower() \
            or "Off-hire" in text


def test_stage1_extraction_reaches_every_table():
    """① работает офлайн: каждая таблица становится страницей
    документа; маркер сноски доезжает в текст как есть."""
    for name in NAMES:
        outcome = extract_text(TABLES / name)
        assert not isinstance(outcome, Exception), (name, outcome)
        assert outcome.pages, name
        joined = "\n".join(p.text for p in outcome.pages)
        assert "Vessel class" in joined or "Off-hire" in joined
    # сноска внутри числа не выброшена извлечением
    foot = extract_text(TABLES / "table4_footnote_in_number.html")
    joined = "\n".join(p.text for p in foot.pages)
    assert "210(3)" in joined


@pytest.mark.skipif(os.environ.get("RUSTERM_LLM_API_KEY") is None,
                    reason="RUSTERM_LLM_API_KEY unset (N2 сетевых "
                           "правил): модельная половина N4 не гоняется")
def test_n4_model_audit_table():
    """Аудит на модели: для каждой таблицы — records / verified /
    verified-but-wrong. Запускается ТОЛЬКО с ключом; результат идёт в
    REPORT-24.md без подгонки промпта."""
    from rusterm.providers.budget import RequestGate
    from rusterm.providers.llm_api import LlmApiClient
    from rusterm.manual.pipeline import import_document
    import tempfile

    client = LlmApiClient.from_env(gate=RequestGate())
    assert not isinstance(client, Exception)
    summary = {}
    for name in NAMES:
        with tempfile.TemporaryDirectory() as tmp:
            conn = None  # import_document пишет в БД; для аудита
            # достаточно исхода ②-③ по одной таблице
            outcome = import_document(
                _memory_conn(), TABLES / name, "physical", "i-audit",
                client)
        summary[name] = outcome
    for name, outcome in summary.items():
        print(name, outcome)
    raise AssertionError("раскомментируйте учёт после прогона с ключом")


def _memory_conn():
    import sqlite3
    from rusterm.store.db import apply_migrations
    conn = sqlite3.connect(":memory:", isolation_level=None)
    apply_migrations(conn)
    return conn
