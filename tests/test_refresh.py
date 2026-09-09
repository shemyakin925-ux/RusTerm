"""TASK-13 Z2: инкрементальный проход — не изменилось, не скачивается.

Десять эмитентов на подставном транспорте (один записанный payload,
размноженный по CIK). Первый проход: по companyfacts на каждого.
Второй: только submissions — companyfacts не запрашивается вовсе,
факты и raw_object не растут. Настоящая сеть не трогается.
"""
from __future__ import annotations

import json
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

N_ISSUERS = 10
FAKE_UA = "Synthetic Test synthetic.invalid"


def _saved_payload() -> bytes:
    data = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"
    return (data / "companyfacts_m3_AAPL.json").read_bytes()


class _MultiCikTransport:
    """Один записанный payload, размноженный по CIK: каждый эмитент
    получает ответ со своим cik (уникальные байты, как у настоящего
    фида); считает запросы по виду URL. submissions отдаёт свежую дату
    подачи один раз (проход 1), после чего «замирает» — второй проход
    видит ту же дату."""

    def __init__(self, payload: bytes):
        self._base = json.loads(payload)
        self._per_cik: dict[int, bytes] = {}
        self.log: list[str] = []
        self.freeze_after = None      # запросов, после которого дата фиксирована
        self._frozen_date = None

    def __call__(self, url, headers):
        self.log.append(url)
        if "submissions" in url:
            date = f"2026-01-{self._next_day():02d}"
            if self.freeze_after is not None and len(self.log) > self.freeze_after:
                date = self._frozen_date
            else:
                self._frozen_date = date
            body = {"filings": {"recent": {
                "form": ["10-K"], "filingDate": [date],
                "reportDate": ["2025-12-31"]}}}
            return 200, json.dumps(body).encode(), {}
        cik = int(url.rsplit("CIK", 1)[1].split(".")[0])
        if cik not in self._per_cik:
            doc = dict(self._base)
            doc["cik"] = cik
            self._per_cik[cik] = json.dumps(doc).encode()
        return 200, self._per_cik[cik], {}

    def _next_day(self) -> int:
        return min(28, 10 + len(self.log))


def test_z2_second_pass_requests_submissions_only():
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)
        watchlist = WatchlistRepo(conn)
        watchlist.create_watchlist("wl1", "десять", None, None)
        watchlist.new_version(str(uuid.uuid4()), "wl1", 1, "create", None)

        payload = _saved_payload()
        base_cik = 900000
        for n in range(N_ISSUERS):
            issuer_id = f"i-{n:03d}"
            instrument_id = f"US-T{n:03d}"
            repos.instrument.upsert_issuer(Issuer(
                issuer_id, f"Issuer {n:03d} (recorded payload)", "US",
                str(base_cik + n), None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                instrument_id, issuer_id, None, "common", "active", None))
            watchlist.add_member(
                watchlist.current_version("wl1")["watchlist_version_id"],
                instrument_id, None)

        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=5000),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
        transport = _MultiCikTransport(payload)
        # заморозить дату подачи после первого submissions: второй
        # проход обязан увидеть «не изменилось»
        transport.freeze_after = 1

        def provider_factory(cik: int) -> EdgarProvider:
            return EdgarProvider(gate=gate, cik=cik, transport=transport)

        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)

        cf = lambda u: "companyfacts" in u
        sb = lambda u: "submissions" in u

        first = refresh_watchlist(repos, provider_factory, "wl1",
                                  "2026-09-09", builder=builder)
        assert len(first) == N_ISSUERS
        assert all(r.action == "updated" for r in first), \
            [(r.instrument_id, r.action, r.reason) for r in first]
        first_cf = sum(1 for u in transport.log if cf(u))
        assert first_cf == N_ISSUERS, (
            f"первый проход: {first_cf} companyfacts из {N_ISSUERS}")

        facts_after_first = conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        raw_after_first = conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        log_after_first = list(transport.log)

        second = refresh_watchlist(repos, provider_factory, "wl1",
                                   "2026-09-09", builder=builder)
        assert len(second) == N_ISSUERS
        assert all(r.action == "unchanged" for r in second), \
            [(r.instrument_id, r.action, r.reason) for r in second]

        second_cf = sum(1 for u in transport.log if cf(u)) - first_cf
        second_sb = sum(1 for u in transport.log if sb(u)) - \
            sum(1 for u in log_after_first if sb(u))
        assert second_cf == 0, \
            f"второй проход скачал {second_cf} companyfacts"
        assert second_sb == N_ISSUERS, \
            f"второй проход сделал {second_sb} запросов submissions"

        assert conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0] == facts_after_first
        assert conn.execute(
            "SELECT COUNT(*) FROM raw_object"
        ).fetchone()[0] == raw_after_first

        # skip виден: у каждой строки причина и дата последней отчётности
        for r in second:
            assert r.reason and r.last_filing_date, r
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
