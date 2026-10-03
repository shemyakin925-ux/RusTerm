"""ТЗ-92 C1: дедупликация EDGAR сохраняет as_reported оригинал.

Правило (ТЗ-92 C1): ключ дедупликации — `(concept, unit, start, end,
basis)`. as_reported — запись той подачи, чей СОБСТВЕННЫЙ период
кончается на конце факта, ранней по `filed`; restated — запись новейшей
поздней подачи. Оба basis живые. Остальные проигравшие того же basis
сохраняются со ссылкой на победителя — ничего не выбрасывается.

Почему прежнее правило ломало расчёты: в настоящем companyfacts одно
число повторяется сравнительным в каждой поздней подаче. Новейшая копия
помечена `restated` (свой период подачи кончается позже), а
as_reported-оригинал уходил в `result.superseded`, который ни один
вызывающий не писал (`cli`-ingest, `core/refresh.py:59`, `pipeline.py`
передают только `parsed.facts`). Замер на живом ответе AAPL: из 25 135
записей живыми оставались 12 452, 12 683 исчезали из базы совсем
(`superseded_by` — 0 строк).

Фикстура `companyfacts_c1_AAPL.json` — настоящий ответ SEC, обрезанный
ПО ПОДАЧАМ, а не по периодам: 9 accession (четыре годовые подачи с
их revision-парой и три свежих 10-Q), 17 тегов из `base_concepts`, 407
записей, все повторы внутри периода сохранены. Обрезка по периодам
убивала признак basis: без записей собственного периода подачи
`latest_end_by_accn` терял её год, и сравнительное число становилось
as_reported (замер: периодов с обоими basis и РАЗНЫМ значением — 0).

Что закреплено здесь:
- правило на синтетике: оригинал и поздний рестейт одного числа живые
  оба;
- направление победителя: as_reported — ранняя `filed`, restated —
  поздняя; проигравший помечен локатором и basis победителя;
- фикстура: 407 записей = 357 живых + 50 проигравших, 139 as_reported
  вместо 83;
- у двух периодов FY2017 оба basis и значения различаются по делу
  (D&A: 8 200 000 000 → 10 157 000 000);
- дверь записи доводит проигравших до базы с `superseded_by` на строку
  победителя;
- `roe` считает, а diff называет периоды реальной ревизии;
- `reparse` дописывает недостающие оригиналы в базу, собранную прежним
  правилом, помечает вытесненными уже сохранённые дубли, повтор
  идемпотентен.

Офлайн: сеть 0, каталог в `tmp_path` (страж `test_no_shared_tmp`).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from pathlib import Path

from rusterm.core.refresh import _persist_companyfacts
from rusterm.core.reparse import rebuild_companyfacts
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 link_superseded, persist_ingestion_results)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "data" / "edgar" / "companyfacts_c1_AAPL.json"
FIXTURE_SHA256 = ("a5e37e43b1133e46e5c52fbe170db14d672ba262"
                  "ebe6d85f5810bad3621795c0")
CIK_URL = ("https://data.sec.gov/api/xbrl/companyfacts/"
           "CIK0000320193.json")
AS_OF = "2026-09-12"
# Единственные два период, где поздняя подача приносит ДРУГОЕ число,
# а не копию (замер фикстуры).
REVISED = [
    ("us-gaap:DepreciationDepletionAndAmortization",
     "2017-09-30", "8200000000", "10157000000"),
    ("us-gaap:NetCashProvidedByUsedInOperatingActivities",
     "2017-09-30", "63598000000", "64225000000"),
]


def _doc(filings: list[tuple[str, str, list[tuple]]]) -> bytes:
    """Синтетический payload формы companyfacts.

    filings — [(accn, filed, [(tag, start, end, val), ...])]: каждая
    подача несёт собственный период и сравнительные, как настоящий API.
    """
    concepts: dict = defaultdict(lambda: defaultdict(list))
    for accn, filed, entries in filings:
        for tag, start, end, val in entries:
            concepts[tag]["USD"].append(
                {"val": val, "accn": accn, "form": "10-K", "filed": filed,
                 "fy": int(end[:4]), "fp": "FY", "start": start, "end": end})
    return json.dumps({
        "cik": 1, "entityName": "Synthetic",
        "facts": {"us-gaap": {
            tag: {"units": dict(units)} for tag, units in concepts.items()}},
    }, sort_keys=True).encode()


def _parse(raw: bytes):
    return CompanyFactsParser().parse(
        raw, {"issuer_id": "i-AAPL", "source_ref": "sha"})


def _key(fact: dict) -> tuple:
    return (fact["concept"], fact["unit"], fact["period_start"],
            fact["period_end"], fact["basis"])


def _catalog(root: Path) -> tuple:
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    # FK включается в `open_connection` — здесь тот же режим, чтобы
    # порядок вставки проигравших после победителей был проверен, а не
    # обещан (TASK-92 C1).
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-AAPL", "Apple Inc.", "US", "0000320193", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "in-AAPL", "i-AAPL", None, "common", "active", None))
    return repos, conn


def _measures(repos, conn) -> dict:
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage)
    built = builder.build("in-AAPL", "i-AAPL", AS_OF)
    rows = {m[3]: m for m in repos.snapshot.get_measures(built.snapshot_id)}
    return rows, built


def test_as_reported_original_survives_the_later_comparative():
    """Оригинал подачи своего периода и поздний рестайт того же числа
    живые ОБА: прежде новейший filed вытеснял оригинал совсем."""
    raw = _doc([
        ("0001-22", "2023-02-01", [("Revenues", "2022-01-01", "2022-12-31",
                                    90)]),
        ("0001-23", "2024-02-01", [("Revenues", "2023-01-01", "2023-12-31",
                                    100),
                                   ("Revenues", "2022-01-01", "2022-12-31",
                                    91)]),
        ("0001-24", "2025-02-01", [("Revenues", "2024-01-01", "2024-12-31",
                                    110),
                                   ("Revenues", "2023-01-01", "2023-12-31",
                                    101)]),
    ])
    result = _parse(raw)
    by = {(f["concept"], f["period_end"], f["basis"]): f["value"]
          for f in result.facts}
    assert by[("us-gaap:Revenues", "2022-12-31", "as_reported")] == "90"
    assert by[("us-gaap:Revenues", "2022-12-31", "restated")] == "91"
    assert by[("us-gaap:Revenues", "2023-12-31", "as_reported")] == "100"
    assert by[("us-gaap:Revenues", "2023-12-31", "restated")] == "101"
    assert by[("us-gaap:Revenues", "2024-12-31", "as_reported")] == "110"
    # каждая запись жива: повтор того же периода поздней подачей — это
    # ДРУГОЙ basis, а не дубликат
    assert result.superseded == []
    assert len(result.facts) == 5


def test_as_reported_winner_is_the_earliest_filing_of_its_own_period():
    """Две подачи одного собственного периода (10-K и его версия с
    пересмотром): as_reported — РАННЯЯ filed, поздняя уходит проигравшей."""
    raw = _doc([
        ("0001-24", "2025-02-01", [("Revenues", "2024-01-01", "2024-12-31",
                                    110)]),
        ("0002-24", "2025-06-01", [("Revenues", "2024-01-01", "2024-12-31",
                                    115)]),
    ])
    result = _parse(raw)
    live = [f for f in result.facts
            if (f["concept"], f["period_end"], f["basis"])
            == ("us-gaap:Revenues", "2024-12-31", "as_reported")]
    assert len(live) == 1
    assert live[0]["value"] == "110", "ранняя filed — оригинал подачи"
    assert live[0]["filed"] == "2025-02-01"
    losers = [f for f in result.superseded if f["value"] == "115"]
    assert len(losers) == 1
    assert losers[0]["superseded_by_locator"]["json_pointer"] == \
        live[0]["locator"]["json_pointer"]
    assert losers[0]["superseded_by_basis"] == "as_reported"


def test_restated_winner_is_the_newest_revision():
    """Среди restated-копий одного периода побеждает НОВЕЙШАЯ подача —
    прежнее направление здесь остаётся. У каждой поздней подачи есть свой
    период, иначе её сравнительное число разбор и не сочёл бы restated."""
    raw = _doc([
        ("0001-23", "2024-02-01", [("Revenues", "2023-01-01", "2023-12-31",
                                    100)]),
        ("0001-24", "2025-02-01", [("Revenues", "2024-01-01", "2024-12-31",
                                    110),
                                   ("Revenues", "2023-01-01", "2023-12-31",
                                    101)]),
        ("0001-25", "2026-02-01", [("Revenues", "2025-01-01", "2025-12-31",
                                    120),
                                   ("Revenues", "2023-01-01", "2023-12-31",
                                    103)]),
    ])
    result = _parse(raw)
    live = [f for f in result.facts
            if (f["concept"], f["period_end"], f["basis"])
            == ("us-gaap:Revenues", "2023-12-31", "restated")]
    assert len(live) == 1
    assert live[0]["value"] == "103"
    original = [f for f in result.facts
                if (f["concept"], f["period_end"], f["basis"])
                == ("us-gaap:Revenues", "2023-12-31", "as_reported")]
    assert [f["value"] for f in original] == ["100"]
    losers = sorted(result.superseded, key=lambda f: f["value"])
    assert [f["value"] for f in losers] == ["101"]
    for loser in losers:
        assert loser["superseded_by_locator"]["json_pointer"] == \
            live[0]["locator"]["json_pointer"]
        assert loser["superseded_by_basis"] == "restated"


def test_every_entry_of_the_fixture_is_accounted_for():
    """Ни одна запись фикстуры не теряется: 407 = 357 живых + 50
    проигравших; у каждого проигравшего победитель — живая строка того
    же 5-ключа."""
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    doc = json.loads(raw)
    total = sum(len(entries)
                for section in doc["facts"].values()
                for node in section.values()
                for entries in node["units"].values())
    assert total == 407

    result = _parse(raw)
    assert len(result.facts) == 357
    assert len(result.superseded) == 50
    assert len(result.facts) + len(result.superseded) == total
    assert result.unparsed == 0
    counts = {b: sum(1 for f in result.facts if f["basis"] == b)
              for b in ("as_reported", "restated")}
    assert counts == {"as_reported": 139, "restated": 218}

    live_keys = {_key(f) for f in result.facts}
    assert len(live_keys) == len(result.facts), "на 5-ключ — одна живая"
    pointers = {f["locator"]["json_pointer"] for f in result.facts}
    for loser in result.superseded:
        assert _key(loser) in live_keys
        assert loser["superseded_by_locator"]["json_pointer"] in pointers


def test_the_fixture_carries_a_real_revision_in_both_bases():
    """Фикстура отвечает на «if the payload has one»: у двух периодов
    FY2017 живые оба basis, и значения различаются по делу."""
    result = _parse(FIXTURE.read_bytes())
    by = {(f["concept"], f["period_end"], f["basis"]): f["value"]
          for f in result.facts}
    for concept, end, as_rep, restated in REVISED:
        assert by[(concept, end, "as_reported")] == as_rep
        assert by[(concept, end, "restated")] == restated


def test_losers_reach_the_database_linked_to_the_winner(tmp_path):
    """Настоящая дверь записи пишет и проигравших: `superseded_by` —
    fact_id живой строки того же 5-ключа и того же basis (колонка есть,
    ТЗ-92 C0 её читает)."""
    repos, conn = _catalog(tmp_path)
    try:
        doc = json.loads(FIXTURE.read_bytes())
        kept = _persist_companyfacts(repos, doc, "i-AAPL", 320193)
        assert kept == 357, "дверь считает ЖИВЫЕ факты"
        assert conn.execute(
            "SELECT count(*) FROM fact").fetchone()[0] == 407
        rows = conn.execute(
            """SELECT f.fact_id AS loser, f.basis AS loser_basis,
                      w.fact_id AS winner_id, w.basis AS winner_basis,
                      w.superseded_by AS winner_winner
               FROM fact f LEFT JOIN fact w ON w.fact_id = f.superseded_by
               WHERE f.superseded_by IS NOT NULL""").fetchall()
        assert len(rows) == 50
        for r in rows:
            assert r["winner_id"] is not None, "победитель обязан в базе"
            assert r["winner_basis"] == r["loser_basis"]
            assert r["winner_winner"] is None, "победитель сам жив"
        assert conn.execute(
            """SELECT count(*) FROM fact
               WHERE superseded_by IS NULL""").fetchone()[0] == 357
    finally:
        conn.close()


def test_roe_has_a_value_and_the_revision_is_visible(tmp_path):
    """Done-when C1 на фикстуре: `roe` считает, а diff называет периоды,
    где поздняя подача принесла другое число."""
    repos, conn = _catalog(tmp_path)
    try:
        doc = json.loads(FIXTURE.read_bytes())
        _persist_companyfacts(repos, doc, "i-AAPL", 320193)
        rows, built = _measures(repos, conn)
        roe = rows.get("roe")
        assert roe is not None
        assert roe[4] is not None, f"roe отказался: {roe[10]!r}"
        revisions = set(built.diff.revisions)
        for concept, end, _a, _r in REVISED:
            assert (concept, end) in revisions
        for concept, end, as_rep, restated in REVISED:
            live = {r["basis"]: r["value"] for r in conn.execute(
                """SELECT basis, value FROM fact WHERE concept=?
                   AND period_end=? AND superseded_by IS NULL""",
                (concept, end))}
            assert live == {"as_reported": as_rep, "restated": restated}
    finally:
        conn.close()


def test_reparse_backfills_originals_into_an_old_base(tmp_path):
    """База, собранная прежним правилом (одна живая строка на 4-ключ,
    проигравшие не записаны), после `reparse` добирает as_reported-
    оригиналы; сохранённые дубли помечены вытесненными; повтор
    идемпотентен."""
    repos, conn = _catalog(tmp_path)
    try:
        raw = FIXTURE.read_bytes()
        obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                            url=CIK_URL, instrument_id="in-AAPL")
        parsed = CompanyFactsParser().parse(
            raw, {"issuer_id": "i-AAPL", "source_ref": obj.sha256})
        best: dict[tuple, dict] = {}
        for fact in list(parsed.facts) + list(parsed.superseded):
            k4 = (fact["concept"], fact["unit"], fact["period_start"],
                  fact["period_end"])
            prev = best.get(k4)
            if prev is None or fact["filed"] > prev["filed"]:
                best[k4] = fact
        old = list(best.values())
        dicts = []
        for fact in old:
            fact = dict(fact)
            fact["fact_id"] = str(uuid.uuid4())
            apply_concept_map(fact)
            dicts.append(fact)
        persist_ingestion_results(conn, dicts, [])
        assert conn.execute(
            "SELECT count(*) FROM fact").fetchone()[0] == len(old)
        before = conn.execute(
            """SELECT count(*) FROM fact WHERE basis='as_reported'
               AND superseded_by IS NULL""").fetchone()[0]

        old_pointers = {d["locator"]["json_pointer"] for d in dicts}
        loser_pointers = {l["locator"]["json_pointer"]
                          for l in parsed.superseded}
        expected_marked = len(old_pointers & loser_pointers)

        result = rebuild_companyfacts(repos)
        assert result.added == 407 - len(old)
        assert result.superseded_marked == expected_marked
        live_after = conn.execute(
            """SELECT count(*) FROM fact WHERE basis='as_reported'
               AND superseded_by IS NULL""").fetchone()[0]
        assert live_after == 139
        assert live_after > before
        assert conn.execute(
            """SELECT count(*) FROM fact f
               WHERE f.superseded_by IS NOT NULL
                 AND NOT EXISTS (SELECT 1 FROM fact w
                                 WHERE w.fact_id = f.superseded_by)"""
        ).fetchone()[0] == 0
        assert conn.execute(
            """SELECT count(*) FROM fact l JOIN fact w
               ON w.fact_id = l.superseded_by
               WHERE l.basis <> w.basis OR w.superseded_by IS NOT NULL"""
        ).fetchone()[0] == 0

        again = rebuild_companyfacts(repos)
        assert (again.added, again.changed, again.superseded_marked) == (0, 0, 0)
        assert conn.execute(
            "SELECT count(*) FROM fact").fetchone()[0] == 407
    finally:
        conn.close()


def test_loser_linking_ignores_facts_without_a_json_pointer():
    """Локаторы `xbrl` и `table` не несут json_pointer — дверь не вправе
    требовать его у них: `pipeline`, `cli` и `refresh` подают на вход все
    факты объекта, а не только companyfacts. Регрессия из полного прогона
    (`KeyError: 'json_pointer'` на 9 тестах pipeline и следом cli/desktop).
    """
    xbrl = {"fact_id": "f-xbrl",
            "locator": {"kind": "xbrl", "doc_sha256": "s",
                        "fact_id": "f-xbrl", "concept": "revenue"},
            "superseded_by": None}
    table = {"fact_id": "f-table",
             "locator": {"kind": "table", "doc_sha256": "s",
                         "table_index": 0, "row": 1, "col": 2},
             "superseded_by": None}
    loser = {"fact_id": "f-lose",
             "locator": {"kind": "companyfacts",
                         "json_pointer": "/facts/us-gaap/C/units/USD/1"},
             "superseded_by_locator": {
                 "kind": "companyfacts",
                 "json_pointer": "/facts/us-gaap/C/units/USD/0"},
             "superseded_by": None}

    assert link_superseded([xbrl, table, loser]) == 0
    assert xbrl["superseded_by"] is None
    assert table["superseded_by"] is None
    assert loser["superseded_by"] is None

    # победитель — строка, сохранённая раньше: известность по указателю
    assert link_superseded(
        [xbrl, table, loser],
        {"/facts/us-gaap/C/units/USD/0": "f-earlier"}) == 1
    assert loser["superseded_by"] == "f-earlier"
    assert xbrl["superseded_by"] is None
