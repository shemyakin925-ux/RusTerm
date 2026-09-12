"""ТЗ-21 H3: валютный стоп-кран — числа шести стран не смешиваются
молча. Абсолютные меры в наборе с разными валютами получают
currency_mismatch с перечнем валют; ratio считаются; существующий
одновалютный набор не меняется; агрегат сектора несёт свою валюту.

Пороги программы честны и здесь: перцентиль считается от пяти пиров
(peers.PERCENTILE_MIN_PEERS), агрегат — от восьми, а собственная
величина для перцентиля берётся только из мер первого прохода, поэтому
ratio-концепт в тестах — net_margin (входы revenue + net_income),
а абсолютный — as-reported revenue.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.industry.aggregate import build_sector_aggregates
from rusterm.core.peers import currency_bound, currency_guard
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument, Issuer, PeerSetRepo, RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    return conn, repos


def _add_issuer(repos, conn, instrument_id: str, issuer_id: str,
                currency: str, facts: list[tuple[str, str]]) -> None:
    """Эмитент с инструментом, снапшотом и фактами в заданной валюте.

    facts — [(concept, value)]; каждый факт получает currency, пустая
    валюта в тестах не встречается: легаси-случай покрыт тем, что
    страж пустую валюту не считает стороной смешения.
    """
    repos.instrument.upsert_issuer(Issuer(
        issuer_id, f"Corp {issuer_id}", "US", None, None, "us_gaap",
        currency))
    repos.instrument.upsert_instrument(Instrument(
        instrument_id, issuer_id, None, "common", "active", None))
    obj = repos.raw.put(f'{{"{issuer_id}": 1}}'.encode(),
                        provider="synthetic", block="fundamentals")
    repos.snapshot.create_snapshot(f"s-{issuer_id}", instrument_id, 1,
                                   "2024-12-31", None, "none", "ready")
    repos.snapshot.add_block(f"s-{issuer_id}", "fundamentals", "ready",
                             None)
    for concept, value in facts:
        conn.execute(
            """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
               period_end, period_type, value, unit, currency, basis,
               origin, source_ref, locator, parser_version, status,
               ingested_at, canonical_concept, source_kind)
               VALUES (?, ?, ?, '2024-01-01', '2024-12-31',
               'duration', ?, 'USD', ?, 'as_reported', 'extracted', ?,
               '{}', 'synthetic.v1', 'ok', 0, ?, 'provider')""",
            (f"f-{issuer_id}-{concept}", issuer_id, concept, value,
             currency, obj.sha256, concept))


def _measure_row(repos, conn, issuer_id: str, measure_id: str,
                 concept: str, value: str, fact_concept: str) -> None:
    """Строка меры с lineage на факт — то, через что страж видит
    валюту входов (repos.currencies_for_measure идёт по lineage)."""
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id=measure_id, snapshot_id=f"s-{issuer_id}",
             scope="issuer", scope_ref=issuer_id, concept=concept,
             value=value, unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id=concept, method_version="v1", null_reason=None,
             peer_set_version=None),
        [{"fact_id": f"f-{issuer_id}-{fact_concept}",
          "peer_measure_id": None, "role": "input"}])


def _six_issuer_set(repos, conn, second_currency: str | None,
                    set_id: str = "ps", version_id: str = "psv1",
                    tag: str = ""):
    """Шесть эмитентов: три US и три (second_currency или US).

    facts у всех: revenue + net_income, чтобы net_margin считался
    первым проходом у любого из них. Возвращает (peers, peer_measures):
    на каждого участника по две строки меры — revenue (absolute) и
    net_margin (ratio) с lineage на свои факты.
    """
    currencies = ["USD", "USD", "USD"]
    currencies += ([second_currency] * 3 if second_currency
                   else ["USD"] * 3)
    ids = [f"{tag}{cur[:2].upper()}-{chr(ord('A') + i)}"
           for i, cur in enumerate(currencies)]
    peer_measures: list[tuple] = []
    for i, (iid, cur) in enumerate(zip(ids, currencies)):
        issuer = f"{tag}i{i}"
        _add_issuer(repos, conn, iid, issuer, cur,
                    [("revenue", str(100 + 10 * i)),
                     ("net_income", str(20 + i))])
        _measure_row(repos, conn, issuer, f"{tag}m{i}-rev", "revenue",
                     str(100 + 10 * i), "revenue")
        _measure_row(repos, conn, issuer, f"{tag}m{i}-nm", "net_margin",
                     f"0.{2 + i}", "net_income")
        peer_measures.append((iid, f"{tag}m{i}-rev", "revenue",
                              str(100 + 10 * i), True))
        peer_measures.append((iid, f"{tag}m{i}-nm", "net_margin",
                              f"0.{2 + i}", True))
    peers = PeerSetRepo(conn)
    peers.create_peer_set(set_id, "industry",
                          "mixed" if second_currency else "single")
    peers.add_version(version_id, set_id, 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for iid in ids:
        peers.add_member(version_id, iid, None)
    return peers, peer_measures, ids


def lineage_concepts(conn, measure_id: str) -> set[str]:
    rows = conn.execute(
        """SELECT m.concept FROM measure_lineage l
           JOIN measure m ON m.measure_id = l.peer_measure_id
           WHERE l.measure_id = ? AND l.role = 'peer'""",
        (measure_id,)).fetchall()
    return {r[0] for r in rows}


def test_currency_guard_semantics():
    # абсолютные меры: смешение -> перечисление валют; одна — пусто
    assert currency_guard("ebitda", {"USD", "KRW"}) == \
        "currency_mismatch: KRW, USD"
    assert currency_guard("nopat", {"usd"}) is None
    assert currency_guard("fcf", set()) is None
    # as-reported концепты вне карты единиц — денежные входы, тоже связаны
    assert currency_guard("revenue", {"USD", "KRW"}) == \
        "currency_mismatch: KRW, USD"
    assert currency_guard("total_equity", {"usd", "brl"}) == \
        "currency_mismatch: BRL, USD"
    assert currency_guard("revenue", {"USD"}) is None
    # ratio и count нейтральны
    assert currency_guard("net_margin", {"USD", "KRW"}) is None
    assert currency_guard("shares_diluted", {"USD", "KRW"}) is None
    assert not currency_bound("net_margin")
    assert currency_bound("revenue")
    assert currency_bound("fcf")


def test_peer_set_two_currencies_mismatch_ratios_compute(env):
    conn, repos = env
    peers, peer_measures, ids = _six_issuer_set(repos, conn, "KRW")
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    builder.build(ids[0], "i0", "2024-12-31",
                  peer_set_version="psv1",
                  peer_measures=peer_measures,
                  peer_members_previous=[],
                  peer_members_current=ids)
    rows = repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(ids[0]))
    percentile_rows = [m for m in rows if m[3] == "percentile"]
    assert percentile_rows, "перцентильные меры должны существовать"
    mismatched = [m for m in percentile_rows
                  if m[10] and m[10].startswith("currency_mismatch")]
    computed = [m for m in percentile_rows
                if m[10] is None and m[4] is not None]
    # ratio считается: одна строка со значением, lineage — net_margin
    assert len(computed) == 1, [(m[4], m[10]) for m in percentile_rows]
    assert lineage_concepts(conn, computed[0][0]) == {"net_margin"}
    # absolute отказывает: currency_mismatch называет обе валюты
    assert mismatched, [m[10] for m in percentile_rows]
    for m in mismatched:
        assert "KRW" in m[10] and "USD" in m[10]
        assert m[4] is None  # значения нет — честный отказ
        assert lineage_concepts(conn, m[0]) == {"revenue"}


def test_single_currency_set_unchanged(env):
    conn, repos = env
    peers, peer_measures, ids = _six_issuer_set(repos, conn, None)
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage)
    result = builder.build(ids[0], "i0", "2024-12-31",
                           peer_set_version="psv1",
                           peer_measures=peer_measures,
                           peer_members_previous=[],
                           peer_members_current=ids)
    percentile_rows = [m for m in repos.snapshot.get_measures(
        repos.snapshot.latest_snapshot_id(ids[0]))
        if m[3] == "percentile"]
    # перцентиль одна: net_margin (own есть только у мер первого
    # прохода); revenue и до ТЗ-21 перцентильной строки не давал —
    # поведение одновалютного набора не изменилось
    assert result.percentiles == 1
    assert len(percentile_rows) == 1
    # ни одна валюта не мешала — причин нет, значение на месте
    assert all(m[10] is None for m in percentile_rows)
    assert all(m[4] is not None for m in percentile_rows)
    assert lineage_concepts(conn, percentile_rows[0][0]) == \
        {"net_margin"}


def test_sector_aggregate_carries_currency_or_refuses_mixture(env):
    conn, repos = env
    # смешанный набор: отказ называет обе валюты, даже когда мал
    peers, peer_measures, ids = _six_issuer_set(repos, conn, "KRW")
    built = build_sector_aggregates(repos, "ps", "2024-12-31",
                                    ("revenue",))
    assert built["outcome"] == "resolved"
    agg = built["aggregates"][0]
    assert agg.null_reason and agg.null_reason.startswith(
        "currency_mismatch")
    assert "KRW" in agg.null_reason and "USD" in agg.null_reason

    # одновалютный набор от восьми: квартили есть и валюта заявлена
    peers2, _, ids2 = _six_issuer_set(repos, conn, None,
                                      set_id="ps-us",
                                      version_id="psv-us", tag="b")
    for j in range(2):  # 6 + 2 = AGGREGATE_MIN_PEERS
        iid = f"US-{chr(ord('H') + j)}"
        peers2.add_member("psv-us", iid, None)
        _add_issuer(repos, conn, iid, f"b{iid}", "USD",
                    [("revenue", str(200 + j))])
        _measure_row(repos, conn, f"b{iid}", f"bx{j}-rev", "revenue",
                     str(200 + j), "revenue")
    built2 = build_sector_aggregates(repos, "ps-us", "2024-12-31",
                                     ("revenue",))
    assert built2["outcome"] == "resolved"
    agg2 = built2["aggregates"][0]
    assert agg2.null_reason is None
    assert agg2.p25 is not None and agg2.median is not None \
        and agg2.p75 is not None
    assert agg2.n == 8
    assert agg2.currency == "USD"
