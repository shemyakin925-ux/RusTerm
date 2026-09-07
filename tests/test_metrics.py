"""Тесты системных метрик (TASK-7 T12).

Для каждой из девяти: вычисленное значение на засеянных данных и
«не записано» на пустых — отсутствие пробы и нуль суть разные факты.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time

import pytest

from rusterm.core.metrics import METRIC_NAMES, SystemMetrics
from rusterm.providers.budget import (
    Budget,
    NetworkGate,
    RateLimiter,
    RequestGate,
)
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    MetricsRepo,
    PeerSetRepo,
    RepoRegistry,
    SnapshotRepo,
)


def _registry():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "N", "US", None, None, "us_gaap", "USD"))
    return tmpdir, conn, repos


def _seed(repos):
    """Факты (один suspect), сырьё, peer set в двух версиях, job'ы."""
    obj = repos.raw.put(b'{"synthetic": "x"}', provider="synthetic",
                        block="fundamentals")
    for i, status in enumerate(("ok", "suspect")):
        repos.fact.insert_fact(
            fact_id=f"f{i}", issuer_id="i1", listing_id=None,
            concept="revenue", period_start="2024-01-01",
            period_end="2024-12-31", period_type="duration",
            value="100", unit="USD", currency=None,
            basis="as_reported", origin="extracted",
            source_ref=obj.sha256,
            locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                     "fact_id": f"f{i}", "concept": "revenue"},
            parser_version="synthetic.v1", status=status)
    peers = PeerSetRepo(repos.conn)
    peers.create_peer_set("ps1", "industry", "tankers")
    peers.add_version("psv1", "ps1", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_version("psv2", "ps1", 2, "2024-06-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("psv1", "ins1", None)
    peers.add_member("psv1", "ins2", None)
    peers.add_member("psv2", "ins1", None)
    peers.add_member("psv2", "ins3", None)
    repos.instrument.upsert_instrument(Instrument(
        "ins1", "i1", None, "common", "active", None))
    repos.instrument.upsert_instrument(Instrument(
        "ins2", "i1", None, "common", "active", None))
    repos.instrument.upsert_instrument(Instrument(
        "ins3", "i1", None, "common", "active", None))
    repos.job.enqueue("j1", "ins1", "fundamentals", "synthetic",
                      None, None, 1, "k1")
    repos.job.finish("j1")
    repos.job.enqueue("j2", "ins1", "prices", "synthetic",
                      None, None, 1, "k2")
    repos.job.fail("j2", "boom", retry=False)
    repos.verification.capture("f0", "f1", "note")


def test_all_nine_names_present():
    assert len(METRIC_NAMES) == 9
    assert "provider_success_rate" in METRIC_NAMES
    assert "locator_resolve_failures" in METRIC_NAMES


def test_each_metric_computed_on_seeded_data():
    tmpdir, conn, repos = _registry()
    try:
        _seed(repos)

        class FakeClock:
            def __init__(self):
                self.now = 0.0

            def __call__(self):
                return self.now

            def sleep(self, s):
                self.now += s

        fc = FakeClock()
        gate = RequestGate(
            budget=Budget(max_requests=4),  # 5-й charge — отказ бюджета
            limiter=RateLimiter(per_second=5, clock=fc, sleeper=fc.sleep),
            gate=NetworkGate(
                environ={"RUSTERM_SEC_UA": "Synthetic Test x.invalid"}))
        # реальные счётчики: 4 прошло, 1 отказано бюджетом
        seen = []
        for i in range(4):
            gate.request(lambda headers, i=i: seen.append(i))
        gate.budget.charge()  # отказ бюджета -> refused

        metrics = SystemMetrics(repos.metrics, request_gate=gate)
        values = metrics.compute(now=1_000_000.0)

        assert values["provider_success_rate"] == pytest.approx(4 / 5)
        # 4 запроса через лимитер 5/с: вызовы 2-4 задержаны — реальный
        # счётчик гейта, не заглушка
        assert values["provider_rate_limited"] == 3.0
        assert values["data_lag"] == pytest.approx(
            1_000_000.0 - repos.metrics.last_fetch_ts())
        assert values["suspect_share"] == pytest.approx(1 / 2)
        assert values["unparsed_share"] == pytest.approx(0.0)
        assert values["verification_queue"] == 1.0
        assert values["peer_set_coverage"] == pytest.approx(2 / 3)
        # v1 {ins1,ins2} -> v2 {ins1,ins3}: симразность 2, знаменатель 2
        assert values["peer_set_churn"] == pytest.approx(1.0)
        assert values["locator_resolve_failures"] == pytest.approx(0.0)
        assert all(v is not None for v in values.values())
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_empty_data_records_nothing():
    tmpdir, conn, repos = _registry()
    try:
        metrics = SystemMetrics(repos.metrics, request_gate=None)
        values = metrics.compute()
        # на пустой базе нет данных ни для одной метрики
        assert all(v is None for v in values.values())
        written = metrics.record(values)
        assert written == 0
        assert repos.metrics.samples() == []
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_record_writes_only_values_with_data():
    tmpdir, conn, repos = _registry()
    try:
        _seed(repos)
        metrics = SystemMetrics(repos.metrics, request_gate=None)
        values = metrics.compute(now=1_000_000.0)
        assert values["provider_success_rate"] is None  # гейта нет — не врём
        written = metrics.record(values, provider="synthetic", ts=42.0)
        samples = repos.metrics.samples()
        assert written == len(samples) > 0
        by_name = {s[1]: s[3] for s in samples}
        assert "provider_success_rate" not in by_name
        assert by_name["suspect_share"] == pytest.approx(0.5)
        assert all(s[0] == 42.0 for s in samples)
    finally:
        conn.close()
        shutil.rmtree(tmpdir)
