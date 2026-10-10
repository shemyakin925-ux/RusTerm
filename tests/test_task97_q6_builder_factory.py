"""ТЗ-97 Q6 (ТЗ-94 `E1`): одна фабрика построителя снапшота.

Буква `E1`: пять мест собирают `SnapshotBuilder` руками, и
census-сборка (`cli/__init__.py:1752`) из них самая бедная — без
репозитория цен, корпоративных действий, отрасли и governance. Значит
`rusterm census --instrument X --rebuild` записывает НОВУЮ последнюю
версию снапшота, у которой оценочные меры отказывают
`missing_data: price_close`, хотя цены в базе есть: диагностическая
команда портит данные пользователя, а потом докладывает об этом как о
переписи. Done when: `make_snapshot_builder(repos, as_of)` — единственный
конструктор вне тестов (страж грепает `SnapshotBuilder(`), и census
`--rebuild` на базе с ценой даёт значение `market_cap`.

Поправка `Q6` к букве `E2`: набор аналогов обязан доходить до второго
прохода во ВСЕХ вызовах (snapshot, refresh, verify, census, окно), а не
только там, где команда сама позвала `peer_inputs`. Зуб: e2e через
`refresh` даёт перцентили.

| где | было | стало |
|---|---|---|
| `rusterm/` | 5 ручных конструкторов, wiring расходится | 1 конструктор — фабрика |
| `census --rebuild` на базе с ценой | `market_cap: missing_data: price_close` | `market_cap` со значением |
| `refresh` с подтверждённым набором | перцентилей нет | перцентиль со значением |
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rusterm.cli import main as cli_main
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    PeerSetRepo,
    RepoRegistry,
    WatchlistRepo,
)

AS_OF = "2026-09-09"
FY = ("2025-01-01", "2025-12-31")
N_PEERS = 6                      # порог перцентиля: 5 аналогов плюс сама
PEER_VERSION = "psv-q6"


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return conn, RepoRegistry(conn, paths), str(paths.root)


def _paper(repos, iid="US-Q6", issuer="i6"):
    repos.instrument.upsert_issuer(Issuer(
        issuer, f"Corp {issuer}", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        iid, issuer, None, "common", "active", None))


def _flow(conn, issuer, concept, value, period=FY):
    start, end = period
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, currency, basis,
           origin, source_ref, locator, parser_version, status,
           ingested_at, canonical_concept, source_kind)
           VALUES (?, ?, 'us-gaap:' || ?, ?, ?, 'duration', ?, 'USD',
           'USD', 'as_reported', 'extracted', 's', '{}',
           'companyfacts.v1', 'ok', 0, ?, 'provider')""",
        (f"f-{issuer}-{concept}-{start}-{end}", issuer, concept, start, end,
         repr(value), concept))


def _priced_paper(conn, repos, iid="US-Q6", issuer="i6"):
    """Бумага, у которой есть всё для `market_cap`: цена и количество
    акций. Именно её census обязан перестать обнулять."""
    _paper(repos, iid, issuer)
    _flow(conn, issuer, "revenue", 1000.0)
    _flow(conn, issuer, "net_income", 100.0)
    _flow(conn, issuer, "shares_outstanding", 100.0)
    repos.price.put_rows(iid, "twelvedata",
                         [{"date": AS_OF, "close": 10.0, "currency": "USD"}])


def _measures(repos, iid):
    sid = repos.snapshot.latest_snapshot_id(iid)
    return {m[3]: m for m in repos.snapshot.get_measures(sid)}, sid


def _peer_set(repos, ids):
    peers = PeerSetRepo(repos.conn)
    peers.create_peer_set("ps-q6", "industry", "single")
    peers.add_version(PEER_VERSION, "ps-q6", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    for iid in ids:
        peers.add_member(PEER_VERSION, iid, None)
    return peers


def _six_papers(repos, conn):
    """Шесть бумаг с выручкой и прибылью — минимум для перцентиля."""
    ids = [f"US-Q6{i}" for i in range(N_PEERS)]
    for n, iid in enumerate(ids):
        _paper(repos, iid, f"i6-{n}")
        _flow(conn, f"i6-{n}", "revenue", float(1000 + 100 * n))
        _flow(conn, f"i6-{n}", "net_income", float(100 + n))
    _peer_set(repos, ids)
    return ids


def _percentile_values(repos, ids):
    """{instrument_id: число valued-перцентилей в последнем снапшоте}."""
    out = {}
    for iid in ids:
        rows, _ = _measures(repos, iid)
        out[iid] = sum(1 for m in rows.values()
                       if m[3] == "percentile" and m[4] is not None)
    return out


# ── E1: цена доживает до census ──────────────────────────────────────

def test_census_rebuild_does_not_erase_the_price(env):
    """Диагностика не имеет права писать снапшот беднее обычной сборки."""
    conn, repos, root = env
    _priced_paper(conn, repos)
    assert cli_main(["--root", root, "snapshot", "--instrument", "US-Q6",
                     "--as-of", AS_OF]) == 0
    before, _ = _measures(repos, "US-Q6")
    assert before["market_cap"][4] is not None, before["market_cap"]

    assert cli_main(["--root", root, "census", "--instrument", "US-Q6",
                     "--rebuild", "--as-of", AS_OF]) == 0
    after, sid = _measures(repos, "US-Q6")
    assert after["market_cap"][4] is not None, (
        f"census --rebuild записал {sid} без цены: {after['market_cap'][10]}")


def test_census_rebuild_writes_the_same_snapshot_as_snapshot(env):
    """Тот же wiring — те же строки: ни одной меры не стало меньше и ни
    одна причина не съехала."""
    conn, repos, root = env
    _priced_paper(conn, repos)
    assert cli_main(["--root", root, "snapshot", "--instrument", "US-Q6",
                     "--as-of", AS_OF]) == 0
    before, _ = _measures(repos, "US-Q6")
    assert cli_main(["--root", root, "census", "--instrument", "US-Q6",
                     "--rebuild", "--as-of", AS_OF]) == 0
    after, _ = _measures(repos, "US-Q6")
    assert {k: (v[4], v[10]) for k, v in after.items()} == \
           {k: (v[4], v[10]) for k, v in before.items()}


# ── E1: единственный конструктор вне тестов ──────────────────────────

def _construction_sites():
    """Каждый `SnapshotBuilder(` в рабочем коде — с именем функции, в
    которой он лежит."""
    root = Path(__file__).resolve().parents[1] / "rusterm"
    sites = []
    for path in sorted(root.rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        enclosing = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def "):
                enclosing = stripped.split("(")[0][4:].strip()
            if "SnapshotBuilder(" in line and not stripped.startswith(
                    "class "):
                sites.append(f"{path.relative_to(root.parent)}"
                             f"::{enclosing}")
    return sites


def test_the_factory_is_the_only_production_constructor():
    """Ни одного ручного `SnapshotBuilder(` вне фабрики: страж из `E1`
    («Done when: guard test greps SnapshotBuilder(»). Пять call-сайтов
    были породой, а не случайностью одного места."""
    assert _construction_sites() == [
        "rusterm/core/snapshot.py::make_snapshot_builder"]


def test_every_command_goes_through_the_factory(env):
    """Фабрику вызывают, а не только написали: четыре пути CLI и окно."""
    root = Path(__file__).resolve().parents[1] / "rusterm"
    cli = (root / "cli" / "__init__.py").read_text(encoding="utf-8")
    # refresh, snapshot, verify, census — по вызову на команду
    assert cli.count("make_snapshot_builder(repos") >= 4, cli.count(
        "make_snapshot_builder(repos")
    actions = (root / "desktop" / "actions.py").read_text(encoding="utf-8")
    assert "make_snapshot_builder(" in actions


# ── Q6: peer_inputs во всех вызовах ──────────────────────────────────

def test_the_factory_resolves_the_peer_set_itself(env):
    """build() без явных peer-аргументов обязан получить второй проход:
    рабочий вызов не обязан помнить про `peer_inputs`."""
    from rusterm.core.snapshot import make_snapshot_builder
    conn, repos, _ = env
    ids = _six_papers(repos, conn)
    builder = make_snapshot_builder(repos, AS_OF)
    for n, iid in enumerate(ids):         # первый проход для всех
        builder.build(iid, f"i6-{n}", AS_OF)
    counts = _percentile_values(repos, ids)
    assert max(counts.values()) >= 1, counts
    sid = repos.snapshot.latest_snapshot_id(ids[-1])
    version = repos.conn.execute(
        "SELECT peer_set_version FROM snapshot WHERE snapshot_id=?",
        (sid,)).fetchone()[0]
    assert version == PEER_VERSION, version


def test_refresh_pass_through_the_factory_yields_percentiles(env):
    """Зуб Q6: e2e через `refresh`, а не через `rusterm snapshot`.

    Проход идёт на настоящем разборе записанного payload (AAPL,
    tests/data/edgar) с подставным транспортом: сети нет, шесть
    эмитентов получают по одному companyfacts.
    """
    from tests.test_refresh import (FAKE_UA, _MultiCikTransport,
                                    _saved_payload)
    from rusterm.core.refresh import refresh_watchlist
    from rusterm.core.snapshot import make_snapshot_builder
    from rusterm.providers.budget import (Budget, NetworkGate, RateLimiter,
                                          RequestGate)
    from rusterm.providers.edgar import EdgarProvider

    conn, repos, _ = env
    watchlist = WatchlistRepo(conn)
    watchlist.create_watchlist("wl-q6", "шесть", None, None)
    watchlist.new_version("wlv-q6", "wl-q6", 1, "create", None)
    ids = []
    for n in range(N_PEERS):
        iid, issuer, cik = f"US-R{n:03d}", f"i-r{n:03d}", 900000 + n
        repos.instrument.upsert_issuer(Issuer(
            issuer, f"Issuer {n:03d} (recorded payload)", "US", str(cik),
            None, "us_gaap", "USD"))
        repos.instrument.upsert_instrument(Instrument(
            iid, issuer, None, "common", "active", None))
        watchlist.add_member("wlv-q6", iid, None)
        ids.append(iid)
    _peer_set(repos, ids)

    transport = _MultiCikTransport(_saved_payload())
    gate = RequestGate(budget=Budget(max_requests=5000),
                       limiter=RateLimiter(per_second=5000),
                       gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))

    def provider_factory(cik: int):
        return EdgarProvider(gate=gate, cik=cik, transport=transport)

    results = refresh_watchlist(repos, provider_factory, "wl-q6", AS_OF,
                                builder=make_snapshot_builder(repos, AS_OF))
    assert all(r.action != "error" for r in results), \
        [(r.instrument_id, r.reason) for r in results]
    counts = _percentile_values(repos, ids)
    assert max(counts.values()) >= 1, (
        f"проход refresh не дал ни одного перцентиля со значением: {counts}")
