"""ТЗ-97 Q12 (вердикт 6, вариант 1): `rusterm reparse` пересобирает
ФАКТЫ из сырья, а не только чинит `basis`.

Замер на копии базы пользователя (REPORT-97, Run 11; сам каталог — только
на чтение): из 44 сохранённых companyfacts у семи нет ни одной строки
`dei:*`, и у шести из семи раздел dei в самом сыре лежит (у TECK в payload
только `ifrs-full` — его reparse не чинит). Сырой ответ лежит в raw-store,
а сбор пропускает ответ, который уже скачан (дедупликация по sha256), —
поэтому после починки разборщика (ТЗ-78 Y2) эти строки не появились ничем.
Итог в цифрах отказами: 54 меры `missing_data: shares_outstanding`
(`rusterm/core/snapshot.py:1015,1034`) во всех версиях снапшотов, 8 из них
в свежем снапшоте каждой из четырёх бумаг — по две меры, `market_cap` и
`market_cap_total`.

Прежний `reparse` этого не лечит по двум причинам: он правит у сохранённых
фактов ТОЛЬКО basis (а здесь нужны новые строки) и обходит только те
объекты, из которых хоть один факт уже разобран (`companyfacts_sources`
фильтрует по EXISTS), — то есть объект без единого факта не мог быть
разобран никогда. Вердикт требует: пересобирать факты нынешним
разборщиком, 0 запросов, те же двери записи, что у `ingest`
(`apply_concept_map` + `persist_ingestion_results`), повтор идемпотентен.

Здесь закреплено поведение на фикстуре; чисел копии базы пользователя (44
объекта, +414 фактов, отказы 8 → 2 в свежих снапшотах) и мутаций M1-M7 —
REPORT-97, Runs 9 и 11.

Что закреплено здесь:
- сырьё с dei, база без dei-фактов — после reparse строки появились,
  канон `shares_outstanding`, версия карты `dei.v1`;
- отказ меры до reparse и её значение после — через настоящую сборку
  снапшота, а не через подсчёт строк;
- ни один уже сохранённый факт не задублирован и не тронут;
- объект, из которого не разобрано ни одного факта, тоже разбирается (в
  базе пользователя таких сейчас нет — граница закреплена здесь, а не в
  замере);
- сеть не трогается, счётчик запросов не двигается;
- объект без владельца и объект без указателей в локаторах не
  вставляется молча — они посчитаны и названы;
- прежняя починка basis живёт в том же прогоне.

Офлайн: настоящий разборщик, настоящие двери записи, фикстура — реальный
VZ payload (TASK-76 W5). Каталог — `tmp_path`, сеть не трогается
(P7, страж `test_no_shared_tmp`).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.core.reparse import rebuild_companyfacts
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 persist_ingestion_results)

REPO = Path(__file__).resolve().parents[1]
VZ = REPO / "tests" / "data" / "edgar" / "companyfacts_vz_shares.json"

DEI_TAG = "dei:EntityCommonStockSharesOutstanding"
CIK_URL = ("https://data.sec.gov/api/xbrl/companyfacts/"
           "CIK0000732712.json")
AS_OF = "2026-02-20"
PRICE_DATE = "2026-02-18"
CLOSE = 40.0
# свежайшее значение обложки VZ из фикстуры (тот же замер, что в
# tests/test_w5_verizon_shares.py)
DEI_LATEST = "4217684168"
VALUE, REASON = 4, 10       # колонки get_measures: value, null_reason


def _catalog(root: Path) -> tuple:
    """Открытый каталог в tmp_path: та же схема, что у пользователя."""
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-VZ", "VERIZON COMMUNICATIONS", "US", "0000732712", None,
        "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-VZ", "i-VZ", None, "common", "active", None))
    return repos, conn


def _base(root: Path, stored: str = "pre-fix") -> tuple:
    """Бумага VZ с её настоящим companyfacts в raw-store.

    `stored` — какие факты из этого сырья попали в таблицу:
    "pre-fix" (таксономия без dei — состояние базы до ТЗ-78 Y2),
    "none" (сырьё скачано, фактов нет), "all" (разобрано всё).
    """
    repos, conn = _catalog(root)
    raw = VZ.read_bytes()
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        instrument_id="US-VZ", url=CIK_URL)
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": "i-VZ", "source_ref": obj.sha256})
    facts = parsed.facts
    if stored == "pre-fix":
        facts = [f for f in facts if not f["concept"].startswith("dei:")]
    elif stored == "none":
        facts = []
    dicts = []
    for fact in facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        dicts.append(fact)
    persist_ingestion_results(conn, dicts, [])
    return repos, conn, obj.sha256


def _concepts(conn) -> set[str]:
    return {r["concept"] for r in conn.execute("SELECT concept FROM fact")}


def _rows(conn, concept: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM fact WHERE concept = ? ORDER BY period_end",
        (concept,)).fetchall()


def _count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM fact").fetchone()[0]


def _market_cap(repos) -> tuple:
    """Строка меры market_cap из настоящего снапшота — та же дверь,
    которая считает отказы у пользователя."""
    repos.price.put_rows("US-VZ", "twelvedata",
                         [{"date": PRICE_DATE, "close": CLOSE,
                           "currency": "USD"}])
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price,
                              corp_action_repo=repos.corp_action)
    builder.build("US-VZ", "i-VZ", AS_OF)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id("US-VZ"))
    return next(m for m in rows if m[3] == "market_cap")


def test_the_stored_payload_carries_dei_and_the_base_does_not(tmp_path):
    """Посылка задачи, а не выдуманный случай: сырьё с dei лежит,
    фактов dei в таблице нет — и прежний обход такому объекту не рад."""
    repos, conn, sha = _base(tmp_path / "app")
    try:
        doc = json.loads(repos.raw.get(sha))
        assert DEI_TAG.split(":")[1] in doc["facts"]["dei"]
        assert not any(c.startswith("dei:") for c in _concepts(conn)), \
            sorted(_concepts(conn))
        res = rebuild_companyfacts(repos)
        assert res.added > 0, f"reparse не добавил ни одного факта: {res}"
    finally:
        conn.close()


def test_the_added_rows_are_mapped_like_ingest_does(tmp_path):
    """Та же дверь нормализации: канон `shares_outstanding`, версия
    карты `dei.v1`, происхождение — extracted, и связка ровно с тем
    сырьём, из которого он разобран."""
    repos, conn, sha = _base(tmp_path / "app")
    try:
        rebuild_companyfacts(repos)
        rows = _rows(conn, DEI_TAG)
        assert rows, "строк dei нет"
        latest = max(rows, key=lambda r: r["period_end"])
        assert (latest["canonical_concept"],
                latest["concept_map_version"], latest["origin"],
                latest["value"], latest["source_ref"]) == (
            "shares_outstanding", "dei.v1", "extracted", DEI_LATEST, sha), \
            dict(latest)
    finally:
        conn.close()


def test_no_stored_fact_is_touched_or_duplicated(tmp_path):
    """Пересборка добавляет недостающее и не трогает сохранённое: тот
    же набор fact_id с теми же значениями, дублей нет."""
    repos, conn, _sha = _base(tmp_path / "app")
    try:
        before = {r["fact_id"]: (r["concept"], r["period_end"], r["value"],
                                 r["basis"])
                  for r in conn.execute("SELECT * FROM fact")}
        res = rebuild_companyfacts(repos)
        after = {r["fact_id"]: (r["concept"], r["period_end"], r["value"],
                                r["basis"])
                 for r in conn.execute("SELECT * FROM fact")}
        assert set(before) <= set(after), "сохранённые факты исчезли"
        assert {k: after[k] for k in before} == before, \
            "сохранённые факты изменены"
        assert _count(conn) == len(before) + res.added
    finally:
        conn.close()


def test_the_measure_refuses_before_reparse_and_computes_after(tmp_path):
    """Сам вердикт: до reparse `market_cap` — отказ
    `missing_data: shares_outstanding`, после — значение. Мера
    считается настоящим сборщиком снапшотов."""
    repos, conn, _sha = _base(tmp_path / "app")
    try:
        refused = _market_cap(repos)
        assert refused[VALUE] is None, refused
        assert refused[REASON] == "missing_data: shares_outstanding", \
            refused
        rebuild_companyfacts(repos)
        built = _market_cap(repos)
        assert built[VALUE] is not None, built
        assert float(built[VALUE]) == pytest.approx(CLOSE * int(DEI_LATEST),
                                                   rel=1e-9), built
    finally:
        conn.close()


def test_a_second_reparse_adds_nothing(tmp_path):
    """Идемпотентность из вердикта: повтор — 0 новых строк и 0
    изменений basis."""
    repos, conn, _sha = _base(tmp_path / "app")
    try:
        first = rebuild_companyfacts(repos)
        assert first.added > 0
        total = _count(conn)
        second = rebuild_companyfacts(repos)
        assert (second.added, second.changed) == (0, 0), second
        assert _count(conn) == total
    finally:
        conn.close()


def test_an_object_that_contributed_no_facts_is_reparsed_too(tmp_path):
    """Сырьё скачано, фактов нет вовсе — прежний фильтр по EXISTS
    оставлял такой объект навсегда без покрытия."""
    repos, conn, _sha = _base(tmp_path / "app", stored="none")
    try:
        assert _count(conn) == 0
        res = rebuild_companyfacts(repos)
        assert res.added > 0, "объект без фактов снова пропущен"
        assert _rows(conn, DEI_TAG), "после пересборки фактов нет"
    finally:
        conn.close()


def test_reparse_never_asks_the_network(tmp_path, monkeypatch):
    """0 запросов из вердикта: ни один провайдер не создаётся, счётчик
    израсходованного не двигается."""
    root = tmp_path / "app"
    repos, conn, _sha = _base(root)
    try:
        def boom(*args, **kwargs):
            raise AssertionError("reparse полез в сеть")

        monkeypatch.setattr("rusterm.providers.get_provider", boom)
        monkeypatch.setattr(cli, "get_provider", boom)
        before = cli._requests_used(str(root))
        res = rebuild_companyfacts(repos)
        assert res.objects > 0
        assert cli._requests_used(str(root)) == before
    finally:
        conn.close()


def test_an_object_without_an_owner_is_counted_not_inserted(tmp_path):
    """Вставлять нечем: у объекта нет инструмента — факту некому
    принадлежать. Молча не проходит: посчитано и названо."""
    repos, conn = _catalog(tmp_path / "orphan")
    try:
        repos.raw.put(VZ.read_bytes(), provider="edgar",
                      block="fundamentals", url=CIK_URL)
        res = rebuild_companyfacts(repos)
        assert res.ownerless == 1, res
        assert res.added == 0
        assert _count(conn) == 0
    finally:
        conn.close()


def test_facts_without_pointers_are_not_re_inserted(tmp_path):
    """Граница дедупликации: указатель в локаторе — единственное, чем
    сверяется «что уже разобрано». Если у сохранённых строк его нет,
    вставка удвоила бы каждую — объект считается и пропускается."""
    repos, conn, sha = _base(tmp_path / "pointless", stored="none")
    try:
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
               period_end, period_type, value, unit, currency, basis,
               origin, source_ref, locator, parser_version, status,
               ingested_at, canonical_concept, source_kind)
               VALUES (?, 'i-VZ', 'us-gaap:Assets', '2025-12-31',
               '2025-12-31', 'instant', '1', 'USD', 'USD', 'as_reported',
               'manual', ?, '{}', 'companyfacts.v1', 'ok', 0, NULL,
               'provider')""", (str(uuid.uuid4()), sha))
        res = rebuild_companyfacts(repos)
        assert res.unlocatable == 1, res
        assert res.added == 0
        assert _count(conn) == 1
    finally:
        conn.close()


def test_the_basis_fix_still_happens_in_the_same_pass(tmp_path):
    """Прежняя цель прогона не вытеснена новой: регрессия ТЗ-78 Y2
    (всё restated) лечится тем же вызовом, что дописывает факты."""
    repos, conn, _sha = _base(tmp_path / "app", stored="all")
    try:
        conn.execute("UPDATE fact SET basis = 'restated'")
        res = rebuild_companyfacts(repos)
        assert res.to_as_reported > 0, res
        assert res.added == 0, res
        assert conn.execute(
            "SELECT COUNT(*) FROM fact WHERE basis = 'restated'"
        ).fetchone()[0] == 0
    finally:
        conn.close()
