"""ТЗ-103 N2: валюта агрегата — только от тех, кто принёс значение.

Зачем (решение координатора по пункту 2 из REPORT-102 «Спорное»):
стоп-кран ТЗ-21 H3 смотрел валюты всех строк меры, включая отказные
(`value IS NULL` с lineage на факты). Мера, у которой не доехало ни
одного значения, получала `currency_mismatch: KRW, USD` — отказ,
который называет валюты участников, не внесших в сравнение ни одного
числа, и прячет настоящую причину (значений нет вообще). Порог
`AGGREGATE_MIN_PEERS` и сам стоп-кран не двигаются: смешение валют
среди участников СО ЗНАЧЕНИЕМ отказывается как раньше.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.industry.aggregate import (build_sector_aggregates,
                                             shortfall_note)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument, Issuer, PeerSetRepo, RepoRegistry)

AS_OF = "2026-06-30"
BASE = "2025-12-31"
CONCEPT = "revenue"


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


def _member(repos, conn, peers, iid: str, currency: str,
            value: float | None) -> None:
    """Участник набора: снапшот на дату, факт выручки в своей валюте и
    строка меры `revenue` с lineage на этот факт.

    `value=None` — отказная строка (`missing_data`): валюта входа в
    базе известна, числа в сравнении нет. Именно такие строки раньше
    подставляли свою валюту в валютный стоп-кран. Unit и факта, и меры —
    'pure' (не ISO, `currency_of_unit` его валютой не считает): смешение
    в тесте создаётся только записанной валютой входа."""
    issuer = f"i-{iid}"
    peers.add_member("psv", iid, None)
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {iid}", "US", None, None, "us_gaap", currency))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))
    obj = repos.raw.put(f'{{"{issuer}": 1}}'.encode(),
                        provider="synthetic", block="fundamentals")
    repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, BASE, None,
                                   "none", "ready")
    repos.snapshot.add_block(f"s-{iid}", "fundamentals", "ready", None)
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, ?, '2025-01-01', ?, 'duration', ?, 'pure', ?,
           'as_reported', 'extracted', ?, '{}', 'synthetic.v1', 'ok',
           0, ?, 'provider')""",
        (f"f-{iid}", issuer, CONCEPT, BASE, repr(value or 100.0),
         currency, obj.sha256, CONCEPT))
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id=f"m-{iid}", snapshot_id=f"s-{iid}",
             scope="issuer", scope_ref=issuer, concept=CONCEPT,
             value=repr(value) if value is not None else None,
             unit='pure', period_start="2025-01-01", period_end=BASE,
             formula_id=CONCEPT, method_version="v1",
             null_reason=None if value is not None else "missing_data",
             peer_set_version=None),
        [{"fact_id": f"f-{iid}", "peer_measure_id": None,
          "role": "input"}])


def _aggregate(repos, peers):
    built = build_sector_aggregates(repos, "ps", AS_OF, (CONCEPT,))
    assert built["outcome"] == "resolved"
    assert len(built["members"]) == 9
    return built["aggregates"][0]


def test_no_values_never_claim_a_currency_conflict(env):
    """Зуб 1 (Done when): девять участников, ноль значений, валюты
    входов смешаны — отказ называется по причине, а не по валютам,
    которых в сравнении не было ни одного."""
    conn, repos, peers = env
    for i in range(4):
        _member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                "USD", None)
    for i in range(5):
        _member(repos, conn, peers, f"KR-{chr(ord('A') + i)}",
                "KRW", None)
    agg = _aggregate(repos, peers)
    assert agg.null_reason == "peer_set_too_small", agg.null_reason
    assert "currency_mismatch" not in (agg.null_reason or "")
    assert (agg.members_seen, agg.with_value) == (9, 0)
    assert shortfall_note(agg) == "участников 9, значение меры есть у 0"
    assert agg.currency is None
    assert agg.reason_counts.get("no_value") == 9


def test_valueless_member_does_not_poison_a_valued_set(env):
    """Зуб 2: восемь значений в USD и один отказ в KRW — агрегат
    считается и заявляет USD: участник без числа не участвует ни в
    квартилях, ни в валютном споре."""
    conn, repos, peers = env
    for i in range(8):
        _member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                "USD", 100.0 + i)
    _member(repos, conn, peers, "KR-X", "KRW", None)
    agg = _aggregate(repos, peers)
    assert agg.null_reason is None, agg.null_reason
    assert agg.n == 8 and agg.currency == "USD"
    assert agg.reason_counts.get("no_value") == 1


def test_mismatch_among_valued_members_still_refuses(env):
    """Зуб 3 (стоп-кран на месте): смешение валют среди участников СО
    ЗНАЧЕНИЕМ отказывается как раньше — список валют честен и не
    включает валюту отказного участника (BRL значения не даёт)."""
    conn, repos, peers = env
    for i in range(4):
        _member(repos, conn, peers, f"US-{chr(ord('A') + i)}",
                "USD", 100.0 + i)
    for i in range(4):
        _member(repos, conn, peers, f"KR-{chr(ord('A') + i)}",
                "KRW", 9000.0 + i)
    _member(repos, conn, peers, "BR-X", "BRL", None)
    agg = _aggregate(repos, peers)
    assert agg.null_reason == "currency_mismatch: KRW, USD", \
        agg.null_reason
    assert "BRL" not in agg.null_reason
    assert agg.p25 is None and agg.median is None and agg.p75 is None
