"""M3 (TASK-8 U8): двадцать эмитентов, один проход сбора, снапшот на
каждого, пропуски с причинами. Повтор прохода не создаёт ни нового
сырья, ни фактов, ни заданий (M1 на настоящих данных).

Сборка офлайн: транспорт подставной, ответы — настоящие обрезанные
companyfacts (tests/data/edgar/companyfacts_m3_*.json и m2-пятёрка).
Каждый эмитент — один запрос (companyfacts целиком), что в шесть раз
меньше оценки docs/processes.md для disclosures-пути; расхождение —
в Disputed отчёта.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path

import pytest

from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.providers.budget import (
    Budget,
    ConfigError,
    NetworkGate,
    RateLimiter,
    RequestGate,
)
from rusterm.providers.edgar import EdgarProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RawRepo,
    RepoRegistry,
    persist_ingestion_results,
)

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"
M3_ISSUERS = ["NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRKB", "V", "JPM",
              "WMT", "PG", "UNH", "HD", "DIS", "PFE", "CVX"]
M2_ISSUERS = ["AAPL", "MSFT", "JNJ", "KO", "XOM"]
ALL = M3_ISSUERS + M2_ISSUERS

FAKE_UA = "Synthetic Test synthetic.invalid"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now += s


def _payload_path(ticker: str) -> Path:
    m2 = DATA / f"companyfacts_m2_{ticker}.json"
    if m2.exists():
        return m2
    return DATA / f"companyfacts_m3_{ticker}.json"


def _provider_for(ticker: str, gate: RequestGate) -> EdgarProvider:
    payload = _payload_path(ticker).read_bytes()
    cik = json.loads(payload)["cik"]

    def transport(url, headers):
        assert headers.get("User-Agent") == FAKE_UA
        return 200, payload, {}

    return EdgarProvider(gate=gate, cik=int(cik), transport=transport)


def _ingest_companyfacts(repos, ticker: str, gate: RequestGate,
                         stored_urls: dict) -> dict:
    """Узлы 4-8 процесса 1 для companyfacts. Узел 3 (дедупликация по
    url) обязателен: url уже собран — запрос не делается вовсе."""
    provider = _provider_for(ticker, gate)
    url = (f"https://data.sec.gov/api/xbrl/companyfacts/"
           f"CIK{provider.cik:010d}.json")
    if url in stored_urls:
        return {"fetched": False, "facts": 0}
    outcome = provider.fetch_companyfacts()
    assert not isinstance(outcome, ConfigError), outcome
    raw = json.dumps(outcome, ensure_ascii=False).encode()
    sha = hashlib.sha256(raw).hexdigest()
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        url=url)
    stored_urls[url] = sha
    result = CompanyFactsParser().parse(
        raw, {"issuer_id": f"i-{ticker}", "source_ref": obj.sha256})
    fact_dicts = []
    for fact in result.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        apply_concept_map(fact)
        fact_dicts.append(fact)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    return {"fetched": True, "facts": len(fact_dicts)}


def test_m3_twenty_issuers_one_pass_gaps_with_reasons_and_idempotent():
    tmpdir = tempfile.mkdtemp()
    try:
        paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
        ensure_app_dir(paths)
        conn = sqlite3.connect(str(paths.db_path), timeout=30,
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, paths)

        gate = RequestGate(
            budget=Budget(max_requests=5000),
            limiter=RateLimiter(per_second=5),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA}))
        stored_urls: dict = {}

        # один проход сбора: 20 эмитентов, по одному companyfacts на каждого
        for ticker in ALL:
            repos.instrument.upsert_issuer(Issuer(
                f"i-{ticker}", f"{ticker} Corp (recorded payload)", "US",
                None, None, "us_gaap", "USD"))
            repos.instrument.upsert_instrument(Instrument(
                f"in-{ticker}", f"i-{ticker}", None, "common", "active",
                None))
            _ingest_companyfacts(repos, ticker, gate, stored_urls)
        assert gate.calls_made == 20, "по запросу на эмитента"
        assert len(stored_urls) == 20

        # снапшот на каждого
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        for ticker in ALL:
            builder.build(f"in-{ticker}", f"i-{ticker}", "2026-09-08")

        snapshots = repos.snapshot.latest_per_instrument()
        assert len(snapshots) == 20

        # Усиление V5: у большинства эмитентов net_margin имеет значение
        # с настоящим периодом; каждый null — с причиной из набора
        fixed_reasons = {
            "missing_data", "period_mismatch", "missing_prior_period",
            "concept_not_mapped", "denominator_zero",
            "negative_denominator",
        }
        non_null_net_margin = 0
        for snapshot in snapshots:
            measures = repos.snapshot.get_measures(
                snapshot["snapshot_id"])
            net_margin = next(m for m in measures
                              if m[3] == "net_margin")
            if net_margin[4] is not None:
                non_null_net_margin += 1
                assert net_margin[6] and net_margin[7], \
                    "значение без периода"
            else:
                assert net_margin[10] in fixed_reasons, \
                    f"{snapshot['instrument_id']}: {net_margin[10]!r}"
        assert non_null_net_margin >= 15, (
            f"non-null net_margin: {non_null_net_margin}/20")
        coverage_rows = conn.execute(
            "SELECT instrument_id, COUNT(*) FROM coverage"
            " GROUP BY instrument_id").fetchall()
        assert len(coverage_rows) == 20
        assert all(n == 8 for _, n in coverage_rows)

        # пропуски показаны с непустой причиной, не спрятаны
        missing = conn.execute(
            "SELECT reason FROM coverage WHERE status='missing'").fetchall()
        assert all(r[0] and r[0].strip() for r in missing)
        blocks_missing = len(missing)

        # повтор прохода: 0 запросов, 0 новых объектов/фактов/заданий
        objects_before = conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        facts_before = conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        jobs_before = conn.execute("SELECT COUNT(*) FROM job").fetchone()[0]
        for ticker in ALL:
            outcome = _ingest_companyfacts(repos, ticker, gate, stored_urls)
            assert outcome["fetched"] is False
        assert gate.calls_made == 20
        assert conn.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0] \
            == objects_before
        assert conn.execute("SELECT COUNT(*) FROM fact").fetchone()[0] \
            == facts_before
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] \
            == jobs_before
        conn.close()
        print(f"M3: 20 issuers, one pass, {gate.calls_made} requests, "
              f"{blocks_missing} blocks missing with reasons, repeat pass "
              "created 0 new objects/facts/jobs")
    finally:
        shutil.rmtree(tmpdir)
