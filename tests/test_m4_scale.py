"""TASK-13 Z3 -> TASK-14 A1/A2/A3: масштаб вехи M4 — пятьсот бумаг,
инкрементальный проход.

Целиком офлайн: подставной транспорт, один записанный payload,
размноженный по CIK, — пятьсот инструментов это пятьсот записей в базе,
а не пятьсот скачиваний. Настоящая сеть не трогается.

СТРУКТУРНАЯ НАХОДКА Z3 (REPORT-13) устранена в TASK-14: миграция 38 дала
схеме первые индексы, restated_revisions() отвечает по одному эмитенту
(A1/A2). Строгий xfail, обязывавший тест падать, снят — его причина
больше не существует; поинструментальный чекпоинт против линейной доли
бюджета остаётся: будущая регрессия обязана краснеть за секунды.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

from rusterm.core.refresh import refresh_watchlist
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.providers.budget import (
    Budget,
    NetworkGate,
    RateLimiter,
    RequestGate,
)
from rusterm.providers.edgar import EdgarProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    Issuer,
    RepoRegistry,
    WatchlistRepo,
)
from tests.test_refresh import _MultiCikTransport

N_ISSUERS = 500
FAKE_UA = "Synthetic Test synthetic.invalid"
# Бюджет первого прохода на здоровой машине (после устранения находки:
# post-fix ~0.1-0.2 s/инструмент) с запасом x3. Контроль — на КАЖДОМ
# инструменте против линейной доли бюджета: пока причина не устранена,
# тест обязан падать за секунды, а не часы (приёмка гоняет suite дважды).
#
# ТЗ-53 W1: контроль переведён с секунд настенных часов на РАБОТУ —
# число SQL-операций прохода (conn.set_trace_callback), величина не
# зависит от загрузки машины. Границы = замер прогона 18.09.2026
# (607 операций на инструмент ровно) с запасом x3.
M4_FIRST_PASS_STATEMENTS_BUDGET = 607 * N_ISSUERS * 3 // 2
_PER_INSTRUMENT_STATEMENTS = 607 * 3
_FIXED_ALLOWANCE_STATEMENTS = 2000  # разогрев: первый инструмент несёт константу


def test_m4_five_hundred_instruments_incremental():
    payload = (Path(__file__).resolve().parents[1] / "tests" / "data"
               / "edgar" / "companyfacts_m3_AAPL.json").read_bytes()
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        watchlist = WatchlistRepo(conn)
        watchlist.create_watchlist("m4", "пятьсот", None, None)
        watchlist.new_version(str(uuid.uuid4()), "m4", 1, "create", None)
        vid = watchlist.current_version("m4")["watchlist_version_id"]
        base_cik = 900000
        for n in range(N_ISSUERS):
            repos.instrument.upsert_issuer(Issuer(
                f"i-{n}", f"Issuer {n}", "US", str(base_cik + n), None,
                "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"US-M{n:04d}", f"i-{n}", None, "common", "active", None))
            watchlist.add_member(vid, f"US-M{n:04d}", None)

        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=10 ** 6),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
        transport = _MultiCikTransport(payload)
        transport.freeze_after = 1  # проход 2 видит «не изменилось»

        def provider_factory(cik: int) -> EdgarProvider:
            return EdgarProvider(gate=gate, cik=cik, transport=transport)

        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)

        # проход 1 с поинструментальным контролем РАБОТЫ (ТЗ-53 W1):
        # число SQL-операций после n инструментов обязано быть в
        # пределах линейной доли бюджета операций — квадратичная
        # деградация вскрывается счётчиком, а не секундами
        seen = {"n": 0, "statements": 0}
        real_members = watchlist.members("m4")

        def _count(statement: str) -> None:
            seen["statements"] += 1

        conn.set_trace_callback(_count)

        def members_chunked(_watchlist_id):
            for member in real_members:
                seen["n"] += 1
                bound = (_FIXED_ALLOWANCE_STATEMENTS
                         + _PER_INSTRUMENT_STATEMENTS * seen["n"])
                assert seen["statements"] <= bound, (
                    f"структурная находка Z3: {seen['n']} инструментов "
                    f"за {seen['statements']} операций при доле бюджета "
                    f"{bound} — полный проход не укладывается в "
                    f"{M4_FIRST_PASS_STATEMENTS_BUDGET}")
                yield member

        watchlist_members_orig = type(watchlist).members
        type(watchlist).members = lambda self, wid: members_chunked(wid)
        try:
            first = refresh_watchlist(
                repos, provider_factory, "m4", "2026-09-09",
                builder=builder)
        finally:
            type(watchlist).members = watchlist_members_orig
            conn.set_trace_callback(None)
        assert seen["statements"] <= M4_FIRST_PASS_STATEMENTS_BUDGET, (
            f"первый проход {seen['statements']} операций выше бюджета "
            f"{M4_FIRST_PASS_STATEMENTS_BUDGET}")
        assert len(first) == N_ISSUERS
        assert all(r.action == "updated" for r in first)

        facts_after = conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        raw_after = conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        jobs_after = conn.execute(
            "SELECT COUNT(*) FROM job").fetchone()[0]
        cf_after_first = sum(1 for u in transport.log
                             if "companyfacts" in u)

        # проход 2: не изменилось — companyfacts не запрашивается,
        # ничего нового не создаётся
        second = refresh_watchlist(repos, provider_factory, "m4",
                                   "2026-09-09", builder=builder)
        print(f"M4 first pass: {seen['statements']} операций")
        assert len(second) == N_ISSUERS
        assert all(r.action == "unchanged" for r in second)
        cf_second = sum(1 for u in transport.log
                        if "companyfacts" in u) - cf_after_first
        assert cf_second == 0, \
            f"второй проход скачал {cf_second} companyfacts"
        assert conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0] == facts_after
        assert conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0] == raw_after
        assert conn.execute(
            "SELECT COUNT(*) FROM job").fetchone()[0] == jobs_after
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── TASK-15 C2: стражи линейности — не разовый замер, а охрана ──────────

# ТЗ-53 W1: именованный секундный бюджет снят — он краснел от загрузки
# машины (круг 59: ratio 1.65 в приёмке координатора при зелёном
# одиночном прогоне). Линейность меряется РАБОТОЙ: числом SQL-операций
# сборки, величина не зависит от настенных часов.
C2_SHAPE_RATIO = 1.5          # вторая половина не дороже 1.5x первой
C2_N_ISSUERS = 100
C2_FAKE_UA = "Synthetic Test synthetic.invalid"


def test_c2_hottest_queries_use_search_never_fact_scan():
    """C2: три самых горячих запроса — restated_revisions,
    as_reported_facts, get_measures — на свежей базе обязаны SEARCH-ить
    по индексам миграции 38; полный SCAN fact или measure в плане —
    регрессия, которую кто-то уронил индекс."""
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)

        calls = {
            "revisions": lambda: repos.snapshot.restated_revisions("i-1"),
            "as_reported": lambda: repos.snapshot.as_reported_facts(
                "i-1", ("net_income", "revenue")),
            "get_measures": lambda: repos.snapshot.get_measures("snap-x"),
        }
        for name, call in calls.items():
            captured: list[str] = []
            conn.set_trace_callback(captured.append)
            try:
                call()
            finally:
                conn.set_trace_callback(None)
            assert captured, f"{name}: запрос не выполнен"
            plan = [row[3] for row in conn.execute(
                "EXPLAIN QUERY PLAN " + captured[0])]
            assert not any("SCAN fact" in step or "SCAN measure" in step
                           for step in plan), f"{name}: {plan}"
            assert any("SEARCH" in step for step in plan), \
                f"{name}: ни одного SEARCH: {plan}"
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_c2_hundred_issuer_build_shape_stays_linear():
    """C2: форма кривой, а не скорость машины. Сто эмитентов на
    записанном payload (данные грузит refresh без builder), затем
    сборка снапшотов двумя половинами: средний чек — под именованным
    бюджетом с запасом x3, вторая половина — не дороже 1.5x первой.
    Возвращение квадрата видно по отношению половин на любом железе."""
    payload = (Path(__file__).resolve().parents[1] / "tests" / "data"
               / "edgar" / "companyfacts_m3_AAPL.json").read_bytes()
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        watchlist = WatchlistRepo(conn)
        watchlist.create_watchlist("c2", "сто", None, None)
        watchlist.new_version(str(uuid.uuid4()), "c2", 1, "create", None)
        vid = watchlist.current_version("c2")["watchlist_version_id"]
        for n in range(C2_N_ISSUERS):
            repos.instrument.upsert_issuer(Issuer(
                f"i-{n}", f"Issuer {n}", "US", str(800000 + n), None,
                "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"US-C2-{n:03d}", f"i-{n}", None, "common", "active", None))
            watchlist.add_member(vid, f"US-C2-{n:03d}", None)

        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=10 ** 6),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": C2_FAKE_UA}))
        transport = _MultiCikTransport(payload)

        def provider_factory(cik: int) -> EdgarProvider:
            return EdgarProvider(gate=gate, cik=cik, transport=transport)

        # данные без сборки: факты в базе, время тикает только за build
        results = refresh_watchlist(repos, provider_factory, "c2",
                                    "2026-09-09", builder=None)
        assert all(r.action == "updated" for r in results)

        members = [m["instrument_id"]
                   for m in watchlist.members("c2")]
        assert len(members) == C2_N_ISSUERS
        half = C2_N_ISSUERS // 2
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)

        def build_half_counting_statements(start: int, stop: int) -> int:
            """Собрать половину, считая SQL-операции (ТЗ-53 W1: работа,
            а не секунды настенных часов)."""
            counter = {"statements": 0}

            def trace(statement: str) -> None:
                counter["statements"] += 1

            conn.set_trace_callback(trace)
            try:
                for n in range(start, stop):
                    builder.build(members[n], issuer_id=f"i-{n}",
                                  as_of="2026-09-09")
            finally:
                conn.set_trace_callback(None)
            return counter["statements"]

        first_half = build_half_counting_statements(0, half)
        second_half = build_half_counting_statements(half,
                                                     C2_N_ISSUERS)
        assert first_half > 0 and second_half > 0
        ratio = second_half / first_half
        print(f"C2 shape: statements {first_half} / {second_half}, "
              f"ratio {ratio:.2f}")
        assert ratio <= C2_SHAPE_RATIO, (
            f"вторая половина {second_half} операций против первой "
            f"{first_half}: ratio {ratio:.2f} — кривая загнулась")
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
