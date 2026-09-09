"""TASK-13 Z3: масштаб вехи M4 — пятьсот бумаг, инкрементальный проход.

Целиком офлайн: подставной транспорт, один записанный payload,
размноженный по CIK, — пятьсот инструментов это пятьсот записей в базе,
а не пятьсот скачиваний. Настоящая сеть не трогается.

СТРУКТУРНАЯ НАХОДКА (подробно в ## Disputed agent/REPORT-13.md):
SnapshotBuilder.build() на каждой сборке зовёт restated_revisions() —
коррелированный EXISTS с полным SCAN fact; индексов в схеме нет, поэтому
полный проход деградирует квадратично: замер 416.6 s на 100 эмитентах,
экстраполяция на 500 — порядка 2.9 часов. До починки тест обязан падать
(xfail(strict=True)) и делает это БЫСТРО: чекпоинт после первых 20
инструментов против линейной доли бюджета. Когда причина уйдёт (индекс
или отложенный diff), тест пройдёт и strict-xfail покраснеет — это
задуманный исход, встанет на координацию.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path

import pytest

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


@pytest.mark.xfail(
    strict=True,
    reason="Z3: полный проход деградирует квадратично — build() зовёт "
           "restated_revisions() (SCAN fact, без индексов) на каждую "
           "сборку; 416.6 s на 100 эмитентах, на 500 — порядка 2.9 ч. "
           "Замер и разбор в ## Disputed agent/REPORT-13.md")
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
        second = refresh_watchlist(repos, provider_factory, "m4",
                                   "2026-09-09", builder=builder)
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
