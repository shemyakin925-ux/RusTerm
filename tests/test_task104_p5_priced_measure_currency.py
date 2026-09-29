"""ТЗ-104 P5: у меры с ценой валюта берётся из строки меры.

Буква пункта (agent/TASK-104.md, P5): «for estimate (priced) measures the
currency is `measure.unit`; a currency-less share-count fact does not count
as `""`». Это развёрнутое решение координатора: пункт 13 раздела «Спорное»
отчёта TASK-103 (agent/REPORT-103.md) — пустота несущественного входа
убивала сравнение, в котором участвовало одно число и одна валюта.

Почему это дыра, а не мелочь: `market_cap_total` = цена × число акций. Цена
— не факт, её валюта живёт в `unit` строки меры (ТЗ-23 K4/K6). Число акций —
факт без валюты (unit `shares`), и `currencies_for_measure` (ТЗ-22 J1.0)
клало в множество валют пустоту его `currency`. Стоп-кран ТЗ-21 H3 читает
«записанная валюта + пустота» как смешение и отказывает:
`currency_mismatch: USD, (blank)`. На копии базы пользователя так отказывали
все пять наборов — и строку заранее вычеркнули из отраслевой таблицы
(rusterm/tui/model.py:35-40: «`market_cap_total` проверена и отброшена»).

| где | было | стало |
|---|---|---|
| `currencies_for_measure` | любой факт без `currency` → `""` в множестве | факт, у которого валюты не бывает по единице (`shares`, `pure`, `USD/shares`), в множество не входит; денежный факт, потерявший `currency` (unit — три буквы), по-прежнему даёт `""`: J1.0 цел |
| мера с ценой | `{USD, ""}` → `currency_mismatch: USD, (blank)` | `{USD}` → агрегат с квартилями и `currency == "USD"` |
| отраслевая таблица | `market_cap_total` вычеркнута | стоит в `_SECTOR_MEASURES` |
| две разные валюты среди участников СО ЗНАЧЕНИЕМ | `currency_mismatch: GBP, USD` | то же: стоп-кран не тронут |

Проверки офлайном, настоящий `build_sector_aggregates`; девять участников —
ровно `AGGREGATE_MIN_PEERS + 1`, чтобы «считается» не было случайностью
границы.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.industry.aggregate import build_sector_aggregates
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument, Issuer, PeerSetRepo, RepoRegistry)

AS_OF = "2026-06-30"
BASE = "2025-12-31"
CONCEPT = "market_cap_total"


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    peers = PeerSetRepo(conn)
    peers.create_peer_set("ps", "industry", "mixed")
    peers.add_version("psv", "ps", 1, "2025-01-01", None, "manual",
                      "v1", True, None, None)
    return conn, repos, peers


def _fact(conn, fact_id, issuer, concept, unit, currency, value="1000"):
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, ?, '2025-01-01', ?, 'duration', ?, ?, ?,
           'as_reported', 'extracted', 's', '{}', 'synthetic.v1', 'ok',
           0, ?, 'provider')""",
        (fact_id, issuer, concept, BASE, value, unit, currency, concept))


def _capital_member(repos, conn, peers, iid, currency, value,
                    share_unit="shares"):
    """Участник набора с капитализацией: строка меры в валюте `currency`
    (цена — не факт, валюта живёт в unit меры, ТЗ-23 K4/K6) и lineage на
    факт числа акций. У последнего валюты нет по природе единицы:
    `shares`, `currency IS NULL` — ровно как после разбора companyfacts."""
    issuer = f"i-{iid}"
    peers.add_member("psv", iid, None)
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {iid}", "US", None, None, "us_gaap", currency))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, BASE, None,
                                   "none", "ready")
    repos.snapshot.add_block(f"s-{iid}", "fundamentals", "ready", None)
    _fact(conn, f"f-{iid}", issuer, "shares_outstanding", share_unit, None,
          value="500")
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id=f"m-{iid}", snapshot_id=f"s-{iid}",
             scope="issuer", scope_ref=issuer, concept=CONCEPT,
             value=repr(value) if value is not None else None,
             unit=currency if value is not None else "",
             period_start="2025-01-01", period_end=BASE,
             formula_id=CONCEPT, method_version="v1",
             null_reason=None if value is not None
             else "missing_data: price_close",
             peer_set_version=None),
        [{"fact_id": f"f-{iid}", "peer_measure_id": None,
          "role": "input"}])
    return f"m-{iid}"


def _aggregate(repos, count=9):
    built = build_sector_aggregates(repos, "ps", AS_OF, (CONCEPT,))
    assert built["outcome"] == "resolved"
    assert len(built["members"]) == count
    return built["aggregates"][0]


# ── множество валют меры ─────────────────────────────────────────────────

def test_a_share_count_fact_claims_no_currency(env):
    """Ядро пункта: факт числа акций — не сторона валютного спора.
    Множество валют меры с ценой = {USD}, пустоты в нём нет."""
    conn, repos, peers = env
    mid = _capital_member(repos, conn, peers, "US-A", "USD", 1e9)

    assert repos.snapshot.currencies_for_measure(mid) == {"USD"}


def test_a_money_fact_that_lost_its_currency_still_claims_a_blank(env):
    """ТЗ-22 J1.0 не сломан: ДЕНЕЖНЫЙ вход (unit — три буквы, валюта) с
    потерянной `currency` остаётся пустой стороной. P5 убирает из спора
    только то, у чего валюты не бывает по единице."""
    conn, repos, peers = env
    issuer = "i-US-B"
    repos.instrument.upsert_issuer(Issuer(
        issuer, "Corp B", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-B", issuer, None, "common", "active", None))
    repos.snapshot.create_snapshot("s-US-B", "US-B", 1, BASE, None,
                                   "none", "ready")
    _fact(conn, "f-legacy", issuer, "revenue", "USD", None)
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-legacy", snapshot_id="s-US-B", scope="issuer",
             scope_ref=issuer, concept="revenue", value="1000",
             unit="USD", period_start="2025-01-01", period_end=BASE,
             formula_id="revenue", method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": "f-legacy", "peer_measure_id": None,
          "role": "input"}])

    assert repos.snapshot.currencies_for_measure("m-legacy") == {"", "USD"}


def test_a_non_currency_unit_on_the_measure_claims_nothing(env):
    """Обратная сторона той же двери: мера в `shares` (unit не валюта) с
    акциями без валюты ничего не заявляет — пустое множество, а не {""}."""
    conn, repos, peers = env
    mid = _capital_member(repos, conn, peers, "US-C", "USD", 1e9,
                          share_unit="pure")
    repos.conn.execute("UPDATE measure SET unit='shares' WHERE measure_id=?",
                        (mid,))

    assert repos.snapshot.currencies_for_measure(mid) == set()


# ── агрегат ──────────────────────────────────────────────────────────────

def test_the_capital_measure_is_in_the_industry_table():
    """Зуб структуры (Done-when «in the industry table»): капитализация
    обязана быть среди мер, для которых экран «Отрасль» просит агрегат.
    Её вычеркнули именно из-за этого отказа — зуб краснеет, если её
    уберут, не починив источник валюты."""
    from rusterm.tui.model import _SECTOR_MEASURES

    assert CONCEPT in _SECTOR_MEASURES, _SECTOR_MEASURES


def test_nine_usd_capitals_make_an_aggregate(env):
    """Done-when P5: девять долларовых капитализаций — агрегат считается и
    заявляет USD. До правки строка отказывала `currency_mismatch: USD,
    (blank)`: к записи каждой меры приложена акция без валюты."""
    conn, repos, peers = env
    for i in range(9):
        _capital_member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                        "USD", 1e9 + i * 1e8)

    agg = _aggregate(repos)

    assert agg.null_reason is None, agg.null_reason
    assert agg.n == 9
    assert agg.currency == "USD"
    # квартили inclusive-метода по 1,0…1,8 млрд — порядковые 3, 5, 7
    assert (float(agg.p25), float(agg.median), float(agg.p75)) == (
        1_200_000_000.0, 1_400_000_000.0, 1_600_000_000.0), agg


def test_a_second_currency_among_capitals_still_refuses(env):
    """Стоп-кран на месте: восемь USD и один GBP — отказ со списком двух
    валют. Пункт убирает из спора пустоту, а не чужую валюту."""
    conn, repos, peers = env
    for i in range(8):
        _capital_member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                        "USD", 1e9 + i * 1e8)
    _capital_member(repos, conn, peers, "GB-X", "GBP", 2e9)

    agg = _aggregate(repos)

    assert agg.null_reason == "currency_mismatch: GBP, USD", agg.null_reason
    assert (agg.p25, agg.median, agg.p75) == (None, None, None)


def test_refused_capitals_do_not_start_a_currency_argument(env):
    """ТЗ-103 N2 переживает правку: отказы (unit пустой, значения нет) не
    вносят ни валют, ни спора — причина называется по числу участников."""
    conn, repos, peers = env
    for i in range(4):
        _capital_member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                        "USD", 1e9 + i * 1e8)
    for i in range(5):
        _capital_member(repos, conn, peers, f"US-{chr(ord('E') + i)}",
                        "USD", None)

    agg = _aggregate(repos)

    # n на отказе всегда нуль (ТЗ-17 E1): кто дошёл и у кого есть число —
    # в members_seen/with_value (ТЗ-102 M4)
    assert (agg.n, agg.members_seen, agg.with_value) == (0, 9, 4), agg
    assert agg.null_reason == "peer_set_too_small", agg.null_reason
    assert "currency_mismatch" not in (agg.null_reason or "")
    assert agg.currency == "USD", agg.currency
