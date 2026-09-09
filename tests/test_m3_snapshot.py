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

        # Пороги W4 по каждой мере (из 20), заданы координатором.
        # TASK-12 Y3, решение §0.2.2: operating_margin 14 и gross_margin
        # 7 — измеренная правда (JPM — банк, PFE/CVX/XOM не тегают
        # OperatingIncomeLoss стабильно; GrossProfit раскрывают 7 из 20),
        # пороги в проходном тесте — чтобы регрессия ловилась здесь.
        floors = {
            "net_margin": 20,
            "effective_tax": 15,
            "fcf": 12,
            "ebitda": 10,
            "interest_coverage": 8,
            "nopat": 12,
            "roe": 12,
            "asset_turnover": 12,
            "operating_margin": 14,
            "gross_margin": 7,
        }
        fixed_reasons = {
            "missing_data", "period_mismatch", "missing_prior_period",
            "concept_not_mapped", "denominator_zero",
            "negative_denominator",
        }
        table: dict[str, dict] = {}
        for snapshot in snapshots:
            for m in repos.snapshot.get_measures(snapshot["snapshot_id"]):
                if m[3] not in floors:
                    continue
                row = table.setdefault(m[3], {"values": 0, "reasons": {}})
                if m[4] is not None:
                    row["values"] += 1
                    assert m[6] and m[7], \
                        f"{snapshot['instrument_id']}/{m[3]}: значение без периода"
                else:
                    # X3: причина может продолжаться списком концептов —
                    # матч по первому токену, не по всей строке
                    assert m[10].split(":")[0] in fixed_reasons, \
                        f"{snapshot['instrument_id']}/{m[3]}: причина {m[10]!r}"
                    # TASK-14 A4: голый missing_data недопустим — пропуск
                    # называет отсутствующий вход
                    assert m[10] != "missing_data", \
                        f"{snapshot['instrument_id']}/{m[3]}: голая причина"
                    row["reasons"][m[10]] = row["reasons"].get(m[10], 0) + 1

        # TASK-14 A4: у V и UNH нет свежего тега total_equity — их roe
        # обязан называть отсутствующий знаменатель, а не голый пропуск
        for snapshot in snapshots:
            if snapshot["instrument_id"] not in ("in-V", "in-UNH"):
                continue
            for m in repos.snapshot.get_measures(snapshot["snapshot_id"]):
                if m[3] == "roe" and m[4] is None:
                    assert m[10] == "missing_data: total_equity", (
                        f"{snapshot['instrument_id']}/roe: {m[10]!r}")

        # таблица печатается до ассертов — она нужна отчёту в любом случае
        print("measure -> n/20 + reasons:")
        for measure, floor in floors.items():
            row = table.get(measure, {"values": 0, "reasons": {}})
            print(f"  {measure}: {row['values']}/20 "
                  f"(порог {floor}) причины: "
                  f"{row['reasons'] if row['reasons'] else '—'}")

        for measure, floor in floors.items():
            assert measure in table, f"меры {measure} нет в снапшотах"
            got = table[measure]["values"]
            assert got >= floor, (
                f"{measure}: {got}/20 ниже порога {floor}")

        # TASK-15 C1 (§0.1): строгий xfail W4 выведен из эксплуатации —
        # планки, которые может сдвинуть только третье лицо, заменены
        # точным составом пробелов. Замер M3-прогона 2026-09-09:
        # operating_margin пуст ровно у шести, все — без тега
        # OperatingIncomeLoss (JPM — банк; PFE/CVX/XOM не тегают;
        # BRKB/JNJ — та же история тегов); gross_margin со значением
        # ровно у семи. Новый эмитент, потерявший operating_income,
        # красит тест; эмитент, его ОБРЕТШИЙ, тоже — это и есть
        # сигнал для обзора, ради которого существовал xfail.
        om_null: dict[str, str] = {}
        gm_null: dict[str, str] = {}
        gm_values = 0
        for snapshot in snapshots:
            ticker = snapshot["instrument_id"].removeprefix("in-")
            for m in repos.snapshot.get_measures(snapshot["snapshot_id"]):
                if m[3] == "operating_margin" and m[4] is None:
                    om_null[ticker] = m[10]
                if m[3] == "gross_margin":
                    if m[4] is None:
                        gm_null[ticker] = m[10]
                    else:
                        gm_values += 1
        assert set(om_null) == {"BRKB", "CVX", "JNJ", "JPM", "PFE", "XOM"}, \
            f"состав пробела operating_margin уехал: {sorted(om_null)}"
        assert set(om_null.values()) == {"missing_data: operating_income"}
        assert gm_values == 7, f"gross_margin со значением: {gm_values}"
        assert len(gm_null) == 13
        assert set(gm_null.values()) == {"missing_data: gross_profit"}

        # W3: неотображённых фактов нет — тег Including… закрыт картой
        null_canonical = conn.execute(
            "SELECT COUNT(*) FROM fact WHERE canonical_concept IS NULL"
        ).fetchone()[0]
        assert null_canonical == 0, (
            f"{null_canonical} фактов без canonical_concept")
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
