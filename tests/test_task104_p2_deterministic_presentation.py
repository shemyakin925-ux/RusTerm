"""ТЗ-104 P2: период, поданный в двух валютах, имеет одну presentation.

AMX подаёт один и тот же 2024 год дважды — в MXN (выручка
869 220 584 000, прибыль 22 902 025 000) и в USD (42 886 000 000 и
1 362 000 000). `_issuer_inputs` строит `common` как **множество** троек
`(unit, start, end)` и выбирает `max(..., key=(end, start))`: ключ не
смотрит на `unit`, тройки равны, и `max` отдаёт ту, которую множество
отдало первым. Порядок обхода множества зависит от seed хеширования
процесса — один и тот же код, та же база и та же дата дают два разных
числа (Disputed 5/23):

| PYTHONHASHSEED | net_margin | валюта подачи |
|---|---|---|
| 0 | `0.026347771119971546` | MXN |
| 1 | `0.031758615865317356` | USD |

Стало: среди троек свежайшего периода берётся **доминирующая валюта
подачи эмитента** — unit с наибольшим числом денежных фактов; при
равенстве наименьшая по алфавиту, и она же, если доминирующей среди
поданных нет. Тем же правилом на сборе и пересборе обновляется
`issuer.reporting_currency` (KSPI на копии: `USD` → `KZT`, Disputed 23).

Денежным считается факт с unit из трёх заглавных букв — то же правило,
что у `core.fact.currency_of_unit` (`^[A-Z]{3}$`): `shares`, `pure`,
`USD/shares` голоса не имеют. По колонке `currency` не считаем: у
строк, разобранных до J1.0, он пуст, а подавались они в той же
валюте. Базис не фильтруется: повтор периода сравнительной колонкой —
тоже подача в своей валюте, а починка basis валюту не меняет, и
доминирующая валюта не обязана подпрыгивать от пересборки.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path

import pytest

from rusterm.core.reparse import rebuild_companyfacts
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 dominant_filing_currency,
                                 persist_ingestion_results)

REPO = Path(__file__).resolve().parents[1]
VZ = REPO / "tests" / "data" / "edgar" / "companyfacts_vz_shares.json"
CIK_URL = ("https://data.sec.gov/api/xbrl/companyfacts/"
           "CIK0000732712.json")
AS_OF = date.today().isoformat()
FRESH_SHARES = date.fromordinal(date.today().toordinal() - 90).isoformat()
FY = ("2024-01-01", "2024-12-31")
# квартальная подача позже годового: окно выручки уходит в запасной
# годовой базис, у прибыли окно остаётся ttm — общий вход меры запрещён,
# и выборки однопериодной ветки (тот самый `common`) достигает мера
QUARTER = "2025-03-31"
QUARTER_START = "2025-01-02"
MXN_MARGIN = 22_902_025_000 / 869_220_584_000
USD_MARGIN = 1_362_000_000 / 42_886_000_000

# Дочерний процесс: собрать снапшот этой же базы и напечатать значение
# меры — seed хеширования задаётся извне, как в repro из Disputed 5.
_CHILD = """
import sqlite3, sys
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry

db, root, instrument, issuer, as_of, concept = sys.argv[1:7]
conn = sqlite3.connect(db, timeout=30, isolation_level=None)
apply_migrations(conn)
repos = RepoRegistry(conn, AppPaths.from_root(root))
SnapshotBuilder(repos.snapshot, repos.peer_set,
                coverage_repo=repos.coverage,
                price_repo=repos.price).build(instrument, issuer, as_of)
rows = {m[3]: m for m in repos.snapshot.get_measures(
    repos.snapshot.latest_snapshot_id(instrument))}
print(rows[concept][4])
"""


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths), paths


def _issuer(repos, iid="US-AMX", issuer="i1", currency="USD"):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "MX", None, None, "ifrs", currency))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))


def _fact(conn, concept, value, start, end, currency, issuer="i1",
          period_type="duration"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'as_reported', 'extracted',
           's', '{}', 'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer}-{currency}-{concept}-{end}", issuer, concept, start,
         end, period_type, str(value), currency, currency, concept))


def _twice_filed_year(conn, issuer="i1"):
    """Тот год, что подан дважды: MXN (3 денежных факта) и USD (2)."""
    for currency, (rev, ni) in (("MXN", (869_220_584_000, 22_902_025_000)),
                                ("USD", (42_886_000_000, 1_362_000_000))):
        _fact(conn, "revenue", rev, FY[0], FY[1], currency, issuer)
        _fact(conn, "net_income", ni, FY[0], FY[1], currency, issuer)
    _fact(conn, "revenue", 220_000_000_000, QUARTER_START, QUARTER, "MXN",
          issuer)


def _build(repos, iid="US-AMX", issuer="i1"):
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    builder.build(iid, issuer, AS_OF)
    return {m[3]: m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(iid))}


def _seed_value(tmp_path, paths, seed, concept="net_margin",
                iid="US-AMX", issuer="i1"):
    script = tmp_path / "child.py"
    script.write_text(_CHILD, encoding="utf-8")
    child_env = dict(os.environ)
    child_env["PYTHONHASHSEED"] = str(seed)
    child_env["PYTHONPATH"] = str(REPO)
    child_env["RUSTERM_ENV_FILE"] = "/nonexistent/rusterm.env"
    child_env.pop("RUSTERM_DATA", None)
    out = subprocess.run(
        [sys.executable, str(script), str(paths.db_path), str(paths.root),
         iid, issuer, AS_OF, concept],
        capture_output=True, text=True, check=True, cwd=str(REPO),
        env=child_env)
    return out.stdout.strip()


# ── один период — одна подача ─────────────────────────────────────────

def test_a_period_filed_twice_presents_in_the_dominant_currency(env):
    """MXN — 3 денежных факта против 2 у USD: число одно и то же, что
    прежде выдавал seed 0, а не то, что отдаст первое попавшееся
    множество."""
    conn, repos, _ = env
    _issuer(repos)
    _twice_filed_year(conn)
    rows = _build(repos)
    assert float(rows["net_margin"][4]) == pytest.approx(MXN_MARGIN), \
        rows["net_margin"]
    assert float(rows["net_margin"][4]) != pytest.approx(USD_MARGIN)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_same_shape_gives_the_same_number_under_every_hash_seed(
        tmp_path, env, seed):
    """Зуб из Done-when: три процесса с разными seed печатают одно
    число. До починки seed 1 печатал 0.031758615865317356."""
    conn, repos, paths = env
    _issuer(repos)
    _twice_filed_year(conn)
    assert _seed_value(tmp_path, paths, seed) == repr(MXN_MARGIN)


def test_the_two_period_path_presents_the_same_way(env):
    """Двухпериодная ветка (`roe`: поток + сток на границах) выбирает
    подачу тем же движком: у потока нет ни окна, ни годового — только
    квартал 2024, поданный в MXN и USD, сток подан одной MXN.
    Доминирующая валюта i2 — MXN (3 денежных факта против 1)."""
    conn, repos, _ = env
    _issuer(repos, iid="US-I2", issuer="i2")
    _fact(conn, "net_income", 22_902_025, "2024-10-01", "2024-12-31", "MXN",
          issuer="i2")
    _fact(conn, "net_income", 1_362_000, "2024-10-01", "2024-12-31", "USD",
          issuer="i2")
    _fact(conn, "total_equity", 300_000_000_000, "2023-12-31", "2023-12-31",
          "MXN", issuer="i2", period_type="instant")
    _fact(conn, "total_equity", 330_000_000_000, FY[1], FY[1], "MXN",
          issuer="i2", period_type="instant")
    rows = _build(repos, iid="US-I2", issuer="i2")
    assert rows["roe"][4] is not None, rows["roe"]
    assert float(rows["roe"][4]) == pytest.approx(
        22_902_025 / ((300_000_000_000 + 330_000_000_000) / 2)), rows["roe"]


# ── разрезание равенства ──────────────────────────────────────────────

def test_a_tie_in_fact_counts_goes_to_the_smallest_unit(env):
    """Ровно по три денежных факта на валюту: доминирующей нет, и
    берётся наименьшая unit по алфавиту (TJS), а не та, что выше в
    таблице."""
    conn, repos, _ = env
    _issuer(repos)
    for currency, (rev, ni) in (("USD", (42_886_000_000, 1_362_000_000)),
                                ("TJS", (80_000_000_000, 4_000_000_000))):
        _fact(conn, "revenue", rev, FY[0], FY[1], currency)
        _fact(conn, "net_income", ni, FY[0], FY[1], currency)
        # квартальная подача выручки есть у обеих валют: она и разводит
        # базисы окон (мера уходит в запасной годовой путь), и оставляет
        # голосование равным — 3 против 3
        _fact(conn, "revenue", 220_000_000_000,
              QUARTER_START, QUARTER, currency)
    rows = _build(repos)
    assert float(rows["net_margin"][4]) == pytest.approx(
        4_000_000_000 / 80_000_000_000), rows["net_margin"]


def test_a_dominant_currency_without_this_period_invents_nothing(env):
    """Доминирующая валюта (EUR) этот период не подавалась: мера не
    ищет EUR-строку и не отказывает — выбор остаётся детерминированным
    среди поданных (MXN против USD — наименьшая по алфавиту MXN)."""
    conn, repos, _ = env
    _issuer(repos)
    _twice_filed_year(conn)
    for i in range(4):                      # EUR перевешивает MXN в голосе
        _fact(conn, f"noise_{i}", 1.0, FY[0], FY[1], "EUR")
    assert dominant_filing_currency(conn, "i1") == "EUR"
    rows = _build(repos)
    assert float(rows["net_margin"][4]) == pytest.approx(MXN_MARGIN), \
        rows["net_margin"]


def test_share_and_per_share_units_do_not_vote(env):
    """Голосуют только денежные unit: `shares` и `USD/shares` валюты не
    имеют (`core.fact.currency_of_unit`), и восемь их строк не перевешивают
    три MXN-факта."""
    conn, repos, _ = env
    _issuer(repos)
    _twice_filed_year(conn)
    for unit in ("USD/shares", "shares"):
        for i in range(4):
            conn.execute(
                """INSERT INTO fact(fact_id, issuer_id, concept,
                   period_start, period_end, period_type, value, unit,
                   currency, basis, origin, source_ref, locator,
                   parser_version, status, ingested_at, canonical_concept,
                   source_kind)
                   VALUES (?, 'i1', ?, ?, ?, 'instant', '1', ?, NULL,
                   'as_reported', 'extracted', 's', '{}',
                   'companyfacts.v1', 'ok', 0, ?, 'provider')""",
                (f"f-noise-{unit}-{i}", f"noise_{unit}_{i}", FRESH_SHARES,
                 FRESH_SHARES, unit, f"noise_{unit}_{i}"))
    assert dominant_filing_currency(conn, "i1") == "MXN"


# ── issuer.reporting_currency обновляется тем же правилом ─────────────

def _fact_dict(concept, currency, end=FY[1], issuer="i1"):
    return {"fact_id": f"f-{issuer}-{currency}-{concept}-{end}",
            "issuer_id": issuer, "listing_id": None, "concept": concept,
            "period_start": FY[0], "period_end": end,
            "period_type": "duration", "value": "1.0", "unit": currency,
            "currency": currency, "basis": "as_reported",
            "origin": "extracted", "source_ref": "s", "locator": {},
            "parser_version": "companyfacts.v1",
            "canonical_concept": concept, "concept_map_version": "v1"}


def test_ingest_refreshes_the_reporting_currency(env):
    """Реестр сказал USD, подачи — KZT (форма KSPI на копии): сбор
    правит колонку тем же правилом, которым выбирается presentation."""
    conn, repos, _ = env
    _issuer(repos, currency="USD")
    persist_ingestion_results(conn, [
        _fact_dict("revenue", "KZT"), _fact_dict("net_income", "KZT"),
        _fact_dict("total_assets", "KZT"), _fact_dict("revenue", "USD")],
        [])
    row = conn.execute("SELECT reporting_currency FROM issuer "
                       "WHERE issuer_id='i1'").fetchone()
    assert row[0] == "KZT", row


def test_a_later_ingest_in_the_other_direction_moves_it_back(env):
    """Колонка не памятник: перевес другой валюты на следующем сборе
    перекрашивает её обратно — правило применяется каждый раз, а не
    один раз при заведении эмитента."""
    conn, repos, _ = env
    _issuer(repos, currency="USD")
    persist_ingestion_results(conn, [
        _fact_dict("revenue", "KZT"), _fact_dict("net_income", "KZT"),
        _fact_dict("total_assets", "KZT"), _fact_dict("revenue", "USD")],
        [])
    end = "2025-12-31"
    persist_ingestion_results(conn, [
        _fact_dict("revenue", "USD", end=end),
        _fact_dict("net_income", "USD", end=end),
        _fact_dict("total_assets", "USD", end=end),
        _fact_dict("total_equity", "USD", end=end)], [])
    row = conn.execute("SELECT reporting_currency FROM issuer "
                       "WHERE issuer_id='i1'").fetchone()
    assert row[0] == "USD", row


def test_an_issuer_without_monetary_facts_keeps_the_registry_value(env):
    """Денег в базе нет — голосовать не по чему: колонку не обнуляем и
    валюту из `shares`-строки не выдумываем."""
    conn, repos, _ = env
    _issuer(repos, currency="USD")
    row = {"fact_id": "f-shares", "issuer_id": "i1", "listing_id": None,
           "concept": "shares_outstanding", "period_start": FRESH_SHARES,
           "period_end": FRESH_SHARES, "period_type": "instant",
           "value": "7.0", "unit": "shares", "currency": None,
           "basis": "as_reported", "origin": "extracted",
           "source_ref": "s", "locator": {},
           "parser_version": "companyfacts.v1",
           "canonical_concept": "shares_outstanding",
           "concept_map_version": "v1"}
    persist_ingestion_results(conn, [row], [])
    assert dominant_filing_currency(conn, "i1") is None
    got = conn.execute("SELECT reporting_currency FROM issuer "
                       "WHERE issuer_id='i1'").fetchone()
    assert got[0] == "USD", got


# ── пересборка правит колонку, даже когда дописывать нечего ───────────

def _column(conn, issuer="i-VZ"):
    return conn.execute("SELECT reporting_currency FROM issuer "
                        "WHERE issuer_id=?", (issuer,)).fetchone()[0]


def _fully_parsed_object(repos, conn, iid="US-VZ", issuer="i-VZ"):
    """Сырьё скачано и разобрано нынешним разборщиком целиком — то, что
    делает `ingest` для нового ответа. Фактов этого объекта в базе ровно
    столько, сколько отдаёт разбор, и дописывать пересборке нечего."""
    raw = VZ.read_bytes()
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        instrument_id=iid, url=CIK_URL)
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": issuer, "source_ref": obj.sha256})
    dicts = []
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        dicts.append(fact)
    persist_ingestion_results(conn, dicts, [])
    return len(dicts)


def test_reparse_refreshes_the_currency_when_it_adds_nothing(env):
    """Массовое состояние базы пользователя: ответ лежит в хранилище и
    разобран нынешним разборщиком целиком — дописывать нечего, и
    `persist_ingestion_results`, который правит колонку на сборе, не
    вызывается. Валюту подачи всё равно пересобирают по тому же правилу:
    3 MXN-факта против 2 USD, реестровый USD уходит в MXN. На копии это
    KSPI — 568 KZT-фактов и колонка USD (Disputed 23, Done-when ТЗ-104 P2).

    Unit строк самого сырья — `shares`, денежного голоса они не имеют:
    после записи объекта колонка ещё реестровая, и двигает её именно
    прогон пересборки, а не сбор."""
    conn, repos, _ = env
    _issuer(repos, iid="US-VZ", issuer="i-VZ", currency="USD")
    stored = _fully_parsed_object(repos, conn)
    for currency, n in (("MXN", 3), ("USD", 2)):
        for i in range(n):
            _fact(conn, f"noise_{i}", 1.0, FY[0], FY[1], currency,
                  issuer="i-VZ")
    assert stored and _column(conn) == "USD"
    res = rebuild_companyfacts(repos)
    assert (res.added, res.objects) == (0, 1), res
    assert _column(conn) == "MXN", _column(conn)


def test_a_second_reparse_leaves_the_column_alone(env):
    """Идемпотентность из вердикта Q12 распространяется и на новую
    запись: правило отдаёт то же число, и второй прогон не двигает ни
    строки фактов, ни колонку."""
    conn, repos, _ = env
    _issuer(repos, iid="US-VZ", issuer="i-VZ", currency="USD")
    _fully_parsed_object(repos, conn)
    for i in range(3):
        _fact(conn, f"noise_{i}", 1.0, FY[0], FY[1], "MXN", issuer="i-VZ")
    rebuild_companyfacts(repos)
    assert _column(conn) == "MXN"
    second = rebuild_companyfacts(repos)
    assert (second.added, second.changed) == (0, 0), second
    assert _column(conn) == "MXN"
