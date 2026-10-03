"""ТЗ-92 C0: исправленный факт не доходит до формулы.

`rusterm verify` вставляет верный факт и помечает старый `superseded_by`
(`core/verification.py:69`), но ни один читатель таблицы `fact` эту колонку
не фильтрует (перепись 21 места под `rusterm/store/` — в отчёте). Значит
отвергнутое значение продолжает попадать в меры: `latest_annual_fact`
сортирует по `period_end DESC` без разрыва равенства, и на связанном
периоде строка с меньшим rowid — то есть старый факт — приходит первой.

Зубы берут читательницы, которые кормят меры: знаменатель `pe`/`ps`,
TTM-окно по потокам, сток-концепты пересчёта (ТЗ-102 M3) и валюта подачи
(ТЗ-104 P2). Снапшот-зуб «`pe` считает 200» живёт отдельным файлом, ему
нужен фабричный сборщик.

Фильтр стоит в SQL, поэтому план обязан остаться покрывающим: индекс
ревизий пересоздан с `superseded_by` (миграция 47), и шестой зуб это
проверяет.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pytest

from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.db import apply_migrations
from rusterm.store.repos import Issuer, Instrument, RepoRegistry

NET_INCOME = "net_income"


@pytest.fixture
def env():
    """Живая БД и один сырой объект: `fact.source_ref` — FK на raw_object."""
    tmpdir = tempfile.mkdtemp()
    conn = sqlite3.connect(os.path.join(tmpdir, "test.db"), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    reg = RepoRegistry(conn, paths)
    reg.instrument.upsert_issuer(
        Issuer("issuer-1", "Test", "US", None, None, "us_gaap", "USD"))
    reg.instrument.upsert_instrument(
        Instrument("inst-1", "issuer-1", None, "common", "active", None))
    raw = reg.raw.put(b"c0 xbrl payload", provider="sec_edgar",
                      block="fundamentals")
    try:
        yield conn, reg, raw.sha256
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def put(reg, source_ref, fact_id, value, *, canonical=NET_INCOME, unit="USD",
        currency="USD", basis="as_reported", period_type="duration",
        start="2023-01-01", end="2023-12-31"):
    """Годовой факт 2023: 365 дней — коридор 350..380 из ТЗ-91 B4."""
    reg.fact.insert_fact(
        fact_id=fact_id, issuer_id="issuer-1", listing_id=None,
        concept=canonical, period_start=start, period_end=end,
        period_type=period_type, value=value, unit=unit, currency=currency,
        basis=basis, origin="extracted", source_ref=source_ref,
        locator={"kind": "xbrl", "doc_sha256": source_ref, "fact_id": fact_id},
        parser_version="test", status="ok",
        canonical_concept=canonical, concept_map_version="us-gaap.v4")


def correct(reg, source_ref, old_id, new_id, new_value):
    """Как `store_ground_truth`: новый факт поверх, старый под `superseded_by`."""
    put(reg, source_ref, new_id, new_value)
    reg.fact.mark_superseded(old_id, new_id)


def test_latest_annual_fact_skips_superseded(env):
    """Знаменатель `pe`/`ps`: после правки 100 → 200 живой — 200.
    Читательница отдаёт число (`float`), не строку."""
    conn, reg, src = env
    put(reg, src, "fact-old", "100")
    correct(reg, src, "fact-old", "fact-new", "200")
    row = reg.snapshot.latest_annual_fact("issuer-1", NET_INCOME)
    assert row is not None
    assert float(row[0]) == 200.0, f"вернулся отвергнутый факт: {row[0]}"


def test_as_reported_facts_skips_superseded(env):
    """Отбор входов сборки: отвергнутая строка не выходит из SQL вовсе."""
    conn, reg, src = env
    put(reg, src, "fact-old", "100")
    correct(reg, src, "fact-old", "fact-new", "200")
    rows = reg.snapshot.as_reported_facts("issuer-1", (NET_INCOME,))
    assert [r["value"] for r in rows] == ["200"], [
        (r["fact_id"], r["value"]) for r in rows]


def test_duration_facts_skips_superseded(env):
    """TTM-окно по потокам: в окне только живые строки."""
    conn, reg, src = env
    put(reg, src, "fact-old", "100")
    correct(reg, src, "fact-old", "fact-new", "200")
    rows = reg.snapshot.duration_facts("issuer-1", NET_INCOME)
    assert [r["value"] for r in rows] == ["200"], [
        (r["fact_id"], r["value"]) for r in rows]


def test_restated_stock_facts_skips_superseded(env):
    """Стоки пересчёта (ТЗ-102 M3): правка сток-факта не оставляет старья.
    Мгновенный период — `period_start` равен `period_end`, колонка NOT NULL."""
    conn, reg, src = env
    put(reg, src, "fact-old", "700", canonical="cash", basis="restated",
        period_type="instant", start="2023-12-31", end="2023-12-31")
    put(reg, src, "fact-new", "800", canonical="cash", basis="restated",
        period_type="instant", start="2023-12-31", end="2023-12-31")
    reg.fact.mark_superseded("fact-old", "fact-new")
    rows = reg.snapshot.restated_stock_facts("issuer-1", ("cash",))
    assert [r["value"] for r in rows] == ["800"], [
        (r["fact_id"], r["value"]) for r in rows]


def test_dominant_filing_currency_skips_superseded(env):
    """Валюта подачи (ТЗ-104 P2) не голосует отвергнутыми строками: две
    снятые с учёта EUR-записи не перевешивают живую USD."""
    conn, reg, src = env
    put(reg, src, "eur-1", "10", canonical="revenue", unit="EUR",
        currency="EUR")
    put(reg, src, "eur-2", "11", canonical="cogs", unit="EUR", currency="EUR")
    put(reg, src, "usd-1", "12", canonical="gross_profit", unit="USD",
        currency="USD")
    reg.fact.mark_superseded("eur-1", "usd-1")
    reg.fact.mark_superseded("eur-2", "usd-1")
    got = reg.snapshot.dominant_filing_currency("issuer-1")
    assert got == "USD", f"доминирующей осталась валюта двух отвергнутых строк: {got}"


def test_revisions_index_covers_superseded(env):
    """Фильтр `superseded_by IS NULL` обязан оставаться покрывающим:
    миграция 47 пересоздаёт индекс ревизий с пятым, хвостовым столбцом.
    Без него план сходит с покрывающего индекса на поиск сходом в таблицу
    — краснеет страж миграции 38, а здесь закреплено имя столбца в самом
    индексе."""
    conn, reg, src = env
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index'"
        " AND name='idx_fact_issuer_concept_period_basis'").fetchone()[0]
    assert "superseded_by" in ddl, ddl
