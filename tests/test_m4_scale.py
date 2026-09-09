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
