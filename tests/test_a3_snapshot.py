"""ТЗ-90 A3: сборка снапшота не падает и не оставляет половину снапшота.

Три дефекта, каждый с проверкой:

1. `computed` в блоке отрасли перепривязывал словарь величин прохода 1
   к целому (числу отраслевых метрик): `own = computed.get(concept)`
   давал AttributeError, как только у инструмента есть сектор с метриками
   И переданы пиры, а покрытие `fundamentals` жило счётчиком отрасли.
2. `ps` делил капитализацию на нулевую годовую выручку (pre-revenue
   эмитент) — ZeroDivisionError вместо словарного `denominator_zero`;
   отрицательная выручка давала отрицательную величину вместо отказа.
3. Строка снапшота создавалась со статусом `ready` до сборки, а меры
   писались по одной транзакции: упавшая сборка оставляла готовый
   наполовину снапшот, и `latest_snapshot_id` его возвращал.
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)

AS_OF = "2024-12-31"
PEER_IDS = [f"US-P{i}" for i in range(6)]


def _env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths)


def _issuer(repos, iid: str, issuer: str) -> None:
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))


def _fact(conn, fact_id: str, issuer: str, concept: str, value) -> None:
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, ?, '2024-01-01', '2024-12-31', 'duration', ?,
           'USD', 'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (fact_id, issuer, concept, str(value), concept))


def _measure(repos, snap_id: str, measure_id: str, scope_ref: str,
             concept: str, value, fact_id: str) -> None:
    """Мера с lineage на факт — то, чем пользуется проход 2: валюты и
    периоды пира читаются по строкам measure."""
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id=measure_id, snapshot_id=snap_id,
             scope="issuer", scope_ref=scope_ref, concept=concept,
             value=str(value), unit="ratio", period_start="2024-01-01",
             period_end=AS_OF, formula_id=concept, method_version="v1",
             null_reason=None, peer_set_version=None),
        [{"fact_id": fact_id, "peer_measure_id": None, "role": "input"}])


def _six_peer_set(repos, conn, version_id: str = "psv1"):
    """Шесть эмитентов с revenue и net_income: net_margin считается
    первым проходом у любого из них, а в наборе пять свежих величин
    пиров — порог PERCENTILE_MIN_PEERS выполнен.

    Возвращает (peers, peer_measures, ids) в формате build():
    [(peer_id, measure_id, concept, value, fresh)].
    """
    peers = PeerSetRepo(conn)
    peers.create_peer_set("set", "industry", "single")
    peers.add_version(version_id, "set", 1, AS_OF, None, "manual",
                      "v1", True, None, None)
    measures: list[tuple] = []
    for i, iid in enumerate(PEER_IDS):
        issuer = f"i{i}"
        _issuer(repos, iid, issuer)
        repos.snapshot.create_snapshot(f"s-{iid}", iid, 1, AS_OF, None,
                                       "none", "ready")
        peers.add_member(version_id, iid, None)
        _fact(conn, f"f-{iid}-revenue", issuer, "revenue", 100 + 10 * i)
        _fact(conn, f"f-{iid}-net_income", issuer, "net_income", 20 + i)
        margin = round((20 + i) / (100 + 10 * i), 6)
        _measure(repos, f"s-{iid}", f"m-{iid}-nm", issuer, "net_margin",
                 margin, f"f-{iid}-net_income")
        measures.append((iid, f"m-{iid}-nm", "net_margin", margin, True))
    return peers, measures, PEER_IDS


def _metrics(*values):
    """Ответ отраслевого резолвера: ровно тот словарь, что читает блок
    отрасли (метрики с величиной или с причиной отказа)."""
    return {
        "sector": "tankers",
        "reason": None,
        "metrics": [
            {"concept": f"fleet_utilization_pct{i}",
             "value": v,
             "reason": None if v is not None else "no off_hire_days",
             "method_version": "maritime.v1"}
            for i, v in enumerate(values)],
        "unmapped": [],
    }


def _coverage(repos, iid: str) -> dict:
    return {b["block"]: (b["status"], b["reason"])
            for b in repos.coverage.for_instrument(iid)}


def _by_concept(repos, snap_id: str) -> dict:
    return {m[3]: (m[4], m[10])
            for m in repos.snapshot.get_measures(snap_id)}


def _statuses(conn, iid: str) -> list:
    """Статусы всех строк снапшота инструмента по возрастанию версии —
    прямое чтение, чтобы тест не зависел от того, что именно считает
    «последним» репозиторий."""
    return [r[0] for r in conn.execute(
        """SELECT status FROM snapshot WHERE instrument_id=?
           ORDER BY version""", (iid,)).fetchall()]


# ── 1. отрасль + пиры: сборка жива, покрытие прохода 1 не врёт ─────────

def test_industry_metrics_and_fresh_peers_build_together(tmp_path):
    """А3.1: на родителе — AttributeError на `computed.get(concept)`
    (целое вместо словаря). Здесь: сборка проходит, перцентиль по
    net_margin считается из собственной величины прохода 1."""
    conn, repos = _env(tmp_path)
    peers, peer_measures, ids = _six_peer_set(repos, conn)
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage,
                              industry=lambda iid, issuer: _metrics(87.0))
    result = builder.build(ids[0], "i0", AS_OF,
                           peer_set_version="psv1",
                           peer_measures=peer_measures,
                           peer_members_previous=[],
                           peer_members_current=ids)
    rows = _by_concept(repos, result.snapshot_id)
    percentiles = [m for m in repos.snapshot.get_measures(result.snapshot_id)
                   if m[3] == "percentile"]
    assert percentiles, "перцентиль должен построиться"
    assert all(m[4] is not None for m in percentiles), percentiles
    assert result.percentiles >= 1, result.percentiles
    # величина net_margin прохода 1 на месте — её не съел счётчик отрасли
    assert rows["net_margin"][0] is not None, rows["net_margin"]
    assert _coverage(repos, ids[0])["fundamentals"][0] == "ready"


def test_fundamentals_coverage_follows_pass1_not_the_industry_count(
        tmp_path):
    """А3.1: покрытие `fundamentals` — `ready` тогда и только тогда,
    когда у меры прохода 1 есть значение; счётчик отрасли на него не
    влияет ни в какую сторону."""
    conn, repos = _env(tmp_path)
    peers, _unused, _ids = _six_peer_set(repos, conn)
    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage,
                              industry=lambda iid, issuer: _metrics(
                                  87.0, 12.0, 3.0))

    # эмитент без фактов: отрасль посчитана, проходу 1 похвастаться нечем
    _issuer(repos, "US-BARE", "ibare")
    bare = builder.build("US-BARE", "ibare", AS_OF)
    rows = _by_concept(repos, bare.snapshot_id)
    assert all(v is None for v, _r in rows.values()), rows
    status, reason = _coverage(repos, "US-BARE")["fundamentals"]
    assert status == "missing", (status, reason)
    assert reason, (status, reason)

    # эмитент с фактами: все отраслевые метрики серые (счётчик 0),
    # а fundamentals по-прежнему ready
    _issuer(repos, "US-FACT", "ifact")
    _fact(conn, "f-ifact-revenue", "ifact", "revenue", 100.0)
    _fact(conn, "f-ifact-net_income", "ifact", "net_income", 20.0)
    grey = SnapshotBuilder(repos.snapshot, peers,
                           coverage_repo=repos.coverage,
                           industry=lambda iid, issuer: _metrics(None))
    built = grey.build("US-FACT", "ifact", AS_OF)
    assert _by_concept(repos, built.snapshot_id)["net_margin"][0] is not None
    status, reason = _coverage(repos, "US-FACT")["fundamentals"]
    assert status == "ready", (status, reason)


# ── 2. ps: нулевой и отрицательный знаменатель (словарь §1.4) ──────────

@pytest.mark.parametrize("revenue,expected", [
    (0.0, "denominator_zero"),
    (-50.0, "negative_denominator"),
])
def test_ps_names_the_denominator_refusal(tmp_path, revenue, expected):
    """А3.2: на родителе revenue=0 — ZeroDivisionError, revenue<0 —
    отрицательная величина вместо отказа по словарю §1.4."""
    conn, repos = _env(tmp_path)
    _issuer(repos, "US-V", "iv")
    repos.price.put_rows("US-V", "twelvedata",
                         [{"date": AS_OF, "close": 10.0,
                           "currency": "USD"}])
    _fact(conn, "f-iv-shares_outstanding", "iv", "shares_outstanding", 7.0)
    _fact(conn, "f-iv-revenue", "iv", "revenue", revenue)
    builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                              coverage_repo=repos.coverage,
                              price_repo=repos.price)
    result = builder.build("US-V", "iv", AS_OF)
    rows = _by_concept(repos, result.snapshot_id)
    value, reason = rows["ps"]
    assert value is None, rows["ps"]
    assert reason == expected, rows["ps"]


# ── 3. building -> ready, упавшая сборка не оставляет следа ────────────

def test_row_is_building_until_the_build_is_over(tmp_path):
    """А3.3: строка создаётся `building` и становится `ready` последней
    записью сборки. Статус подглядывается из середины сборки отраслевым
    резолвером — он вызван после прохода 1."""
    conn, repos = _env(tmp_path)
    peers, _unused, ids = _six_peer_set(repos, conn)
    seen: list = []

    def peek(iid, issuer):
        seen.append(_statuses(conn, iid))
        return _metrics(87.0)

    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage,
                              industry=peek)
    result = builder.build(ids[0], "i0", AS_OF)
    # версия 1 — предзаполненный ready-снапшот пиров, версия 2 — сборка
    assert seen == [["ready", "building"]], seen
    assert repos.snapshot.get_snapshot(result.snapshot_id)["status"] == \
        "ready"


def test_failed_build_leaves_no_half_snapshot(tmp_path):
    """А3.3: исключение в середине сборки ⇒ строк этого снапшота нет,
    предыдущий ready-снапшот цел, latest_snapshot_id не изменился,
    версия не сожжена."""
    conn, repos = _env(tmp_path)
    peers, _unused, _ids = _six_peer_set(repos, conn)
    _issuer(repos, "US-C", "ic")
    _fact(conn, "f-ic-revenue", "ic", "revenue", 100.0)
    _fact(conn, "f-ic-net_income", "ic", "net_income", 20.0)
    plain = SnapshotBuilder(repos.snapshot, peers,
                            coverage_repo=repos.coverage)
    first = plain.build("US-C", "ic", AS_OF)
    before = repos.snapshot.latest_snapshot_id("US-C")
    assert before == first.snapshot_id

    def boom(iid, issuer):
        raise RuntimeError("проверка: сборка падает в середине")

    failing = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage,
                              industry=boom)
    with pytest.raises(RuntimeError):
        failing.build("US-C", "ic", AS_OF)

    assert repos.snapshot.latest_snapshot_id("US-C") == before
    assert _statuses(conn, "US-C") == ["ready"], _statuses(conn, "US-C")
    assert conn.execute(
        """SELECT COUNT(*) FROM snapshot_block WHERE
           snapshot_id NOT IN (SELECT snapshot_id FROM snapshot)"""
    ).fetchone()[0] == 0, "осиротели блоки снапшота"
    assert conn.execute(
        """SELECT COUNT(*) FROM measure WHERE
           snapshot_id NOT IN (SELECT snapshot_id FROM snapshot)"""
    ).fetchone()[0] == 0, "осиротели меры"
    assert conn.execute(
        """SELECT COUNT(*) FROM measure_lineage WHERE measure_id
           NOT IN (SELECT measure_id FROM measure)"""
    ).fetchone()[0] == 0, "осиротела lineage"
    # версия не сожжена: следующая сборка — ровно вторая
    second = plain.build("US-C", "ic", AS_OF)
    assert second.version == 2, second.version
    assert repos.snapshot.get_snapshot(second.snapshot_id)["status"] == \
        "ready"


def test_previous_snapshot_skips_the_row_under_construction(tmp_path):
    """А3.3: diff строится против последней ГОТОВОЙ версии: пока идёт
    сборка версии 2, её собственной `building`-строки базой сравнения
    быть не должно."""
    conn, repos = _env(tmp_path)
    peers, _unused, _ids = _six_peer_set(repos, conn)
    _issuer(repos, "US-D", "id")
    _fact(conn, "f-id-revenue", "id", "revenue", 100.0)
    _fact(conn, "f-id-net_income", "id", "net_income", 20.0)
    plain = SnapshotBuilder(repos.snapshot, peers,
                            coverage_repo=repos.coverage)
    first = plain.build("US-D", "id", AS_OF)
    seen: list = []

    def peek(iid, issuer):
        seen.append(repos.snapshot.previous_snapshot(
            iid, before_version=repos.snapshot.max_version(iid)))
        return _metrics(87.0)

    builder = SnapshotBuilder(repos.snapshot, peers,
                              coverage_repo=repos.coverage,
                              industry=peek)
    second = builder.build("US-D", "id", AS_OF)
    assert seen == [first.snapshot_id], seen
    assert second.version == 2
    assert repos.snapshot.previous_snapshot("US-D") == first.snapshot_id
    assert repos.snapshot.latest_snapshot_id("US-D") == second.snapshot_id
