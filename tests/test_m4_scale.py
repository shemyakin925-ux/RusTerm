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
import time
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
M4_FIRST_PASS_BUDGET_S = 240.0
_PER_ISSUER_SHARE = M4_FIRST_PASS_BUDGET_S / N_ISSUERS
_FIXED_ALLOWANCE_S = 2.0  # разогрев: первый инструмент несёт константу


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

        # проход 1 с поинструментальным контролем времени: прошедшее
        # время после n инструментов обязано быть в пределах линейной
        # доли бюджета — квадратичная деградация вскрывается за секунды
        started = time.monotonic()
        seen = {"n": 0}
        real_members = watchlist.members("m4")

        def members_chunked(_watchlist_id):
            for member in real_members:
                seen["n"] += 1
                elapsed = time.monotonic() - started
                bound = _FIXED_ALLOWANCE_S + _PER_ISSUER_SHARE * seen["n"]
                assert elapsed <= bound, (
                    f"структурная находка Z3: {seen['n']} инструментов "
                    f"за {elapsed:.1f} s при доле бюджета {bound:.1f} s — "
                    f"полный проход не укладывается в "
                    f"{M4_FIRST_PASS_BUDGET_S:.0f} s")
                yield member

        watchlist_members_orig = type(watchlist).members
        type(watchlist).members = lambda self, wid: members_chunked(wid)
        try:
            first = refresh_watchlist(
                repos, provider_factory, "m4", "2026-09-09",
                builder=builder)
        finally:
            type(watchlist).members = watchlist_members_orig
        elapsed_first = time.monotonic() - started
        assert elapsed_first <= M4_FIRST_PASS_BUDGET_S, (
            f"первый проход {elapsed_first:.1f} s выше бюджета "
            f"{M4_FIRST_PASS_BUDGET_S:.0f} s")
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
        started_second = time.monotonic()
        second = refresh_watchlist(repos, provider_factory, "m4",
                                   "2026-09-09", builder=builder)
        elapsed_second = time.monotonic() - started_second
        print(f"M4 timings: first pass {elapsed_first:.2f} s, "
              f"second pass {elapsed_second:.2f} s")
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

# Именованный бюджет сборки: измеренный средний чек по эмитенту на этой
# машине (замер C2 в REPORT-15) с запасом x3. Рост среднего красит тест.
C2_MEAN_PER_ISSUER_BUDGET_S = 0.30
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

        started = time.monotonic()
        for instrument_id in members[:half]:
            builder.build(instrument_id, issuer_id := f"i-{members.index(instrument_id)}", as_of="2026-09-09")
        first_half = time.monotonic() - started

        started = time.monotonic()
        for instrument_id in members[half:]:
            builder.build(instrument_id, issuer_id := f"i-{members.index(instrument_id)}", as_of="2026-09-09")
        second_half = time.monotonic() - started

        mean_per_issuer = (first_half + second_half) / C2_N_ISSUERS
        ratio = second_half / first_half
        print(f"C2 shape: mean {mean_per_issuer:.4f} s/issuer, "
              f"halves {first_half:.2f} s / {second_half:.2f} s, "
              f"ratio {ratio:.2f}")
        assert mean_per_issuer <= C2_MEAN_PER_ISSUER_BUDGET_S, (
            f"средний чек {mean_per_issuer:.4f} s выше бюджета "
            f"{C2_MEAN_PER_ISSUER_BUDGET_S} s")
        assert ratio <= C2_SHAPE_RATIO, (
            f"вторая половина {second_half:.2f} s против первой "
            f"{first_half:.2f} s:ratio {ratio:.2f} — кривая загнулась")
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
