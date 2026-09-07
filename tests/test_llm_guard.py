"""Тесты LLM-предохранителя (TASK-7 T15, watchlist-and-llm.md §2.6).

Фальшивый клиент живёт здесь (контракт); ответ с выдуманным числом
бракуется целиком — в llm_summary не попадает ничего, блок coverage
остаётся missing с причиной. Полностью цитируемый ответ хранится.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid

from rusterm.core.llm import LlmSummarizer
from rusterm.store.db import apply_migrations, open_connection
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
)


class FakeObedientClient:
    """Использует только плейсхолдеры — числа даёт подстановка."""

    def summarize(self, prompt):
        return {
            "summary": "Компания: выручка {{revenue}}, "
                       "период {{revenue}} закончился 2024-12-31.",
            "highlights": ["маржа {{net_margin}}"],
            "risks": [],
            "confidence": 0.9,  # логируется, в решениях не участвует
        }


class FakeInventingClient:
    """Пишет число, которого нет в снапшоте."""

    def summarize(self, prompt):
        return {
            "summary": "Выручка 999999 условных единиц, "
                       "маржа {{net_margin}}.",
            "highlights": [],
            "risks": ["долг 42 миллиарда"],
        }


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(os.path.join(tmpdir, "app"))
    ensure_app_dir(paths)
    conn = open_connection(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "N", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "ins1", "i1", None, "common", "active", None))

    # сырьё + факты, чтобы lineage мер вёл на настоящие fact_id (FK)
    obj = repos.raw.put(b'{"synthetic": "x"}', provider="synthetic",
                        block="fundamentals")
    fact_ids = {}
    for concept, value in (("revenue", "1000"), ("net_income", "100")):
        fact_id = str(uuid.uuid4())
        fact_ids[concept] = fact_id
        repos.fact.insert_fact(
            fact_id=fact_id, issuer_id="i1", listing_id=None,
            concept=concept, period_start="2024-01-01",
            period_end="2024-12-31", period_type="duration",
            value=value, unit="USD", currency=None,
            basis="as_reported", origin="extracted",
            source_ref=obj.sha256,
            locator={"kind": "xbrl", "doc_sha256": obj.sha256,
                     "fact_id": fact_id, "concept": concept},
            parser_version="synthetic.v1")

    repos.snapshot.create_snapshot("s1", "ins1", 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.add_block("s1", "fundamentals", "ready", None)
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-rev", snapshot_id="s1", scope="issuer",
             scope_ref="i1", concept="revenue", value="1000", unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="revenue", method_version="v1",
             null_reason=None, peer_set_version=None),
        [{"fact_id": fact_ids["revenue"], "peer_measure_id": None,
          "role": "input"}])
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-ni", snapshot_id="s1", scope="issuer",
             scope_ref="i1", concept="net_income", value="100", unit="USD",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="net_income", method_version="v1",
             null_reason=None, peer_set_version=None),
        [{"fact_id": fact_ids["net_income"], "peer_measure_id": None,
          "role": "input"}])
    repos.snapshot.insert_measure_with_lineage(
        dict(measure_id="m-margin", snapshot_id="s1", scope="issuer",
             scope_ref="i1", concept="net_margin", value="0.1", unit="ratio",
             period_start="2024-01-01", period_end="2024-12-31",
             formula_id="net_margin", method_version="v1",
             null_reason=None, peer_set_version=None),
        [{"fact_id": fact_ids["revenue"], "peer_measure_id": None,
          "role": "input"},
         {"fact_id": fact_ids["net_income"], "peer_measure_id": None,
          "role": "input"}])
    return tmpdir, conn, repos


def test_invented_number_rejects_whole_text():
    tmpdir, conn, repos = _setup()
    try:
        summarizer = LlmSummarizer(FakeInventingClient(), repos.snapshot,
                                   repos.llm_summary, repos.coverage)
        outcome = summarizer.run("ins1", "s1", model="fake")
        assert outcome["stored"] is False
        assert "не смогла удержаться" in outcome["reason"]
        # в llm_summary не попало ничего
        assert repos.llm_summary.for_instrument("ins1") == []
        # блок coverage missing с причиной
        cov = {r["block"]: r for r in repos.coverage.for_instrument("ins1")}
        assert cov["llm_summary"]["status"] == "missing"
        assert cov["llm_summary"]["reason"] == \
            LlmSummarizer.GUARD_REASON
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_unknown_placeholder_and_missing_number_reject_too():
    tmpdir, conn, repos = _setup()

    class UnknownPlaceholder:
        def summarize(self, prompt):
            return {"summary": "Мультипликатор {{pe_ratio}} растёт.",
                    "highlights": [], "risks": []}

    try:
        summarizer = LlmSummarizer(UnknownPlaceholder(), repos.snapshot,
                                   repos.llm_summary, repos.coverage)
        assert summarizer.run("ins1", "s1")["stored"] is False
        assert repos.llm_summary.for_instrument("ins1") == []
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_fully_cited_response_is_stored():
    tmpdir, conn, repos = _setup()
    try:
        summarizer = LlmSummarizer(FakeObedientClient(), repos.snapshot,
                                   repos.llm_summary, repos.coverage)
        outcome = summarizer.run("ins1", "s1", model="fake")
        assert outcome["stored"] is True
        rows = repos.llm_summary.for_instrument("ins1")
        assert len(rows) == 1
        row = rows[0]
        assert row["model"] == "fake"
        assert row["snapshot_version"] == 1
        assert len(row["prompt_hash"]) == 64  # sha256 промпта, без ключей
        stored = row
        citations = [c["concept"] for c in json.loads(row["citations"])]
        # числа текста обязаны цитироваться
        assert "revenue" in citations
        assert "net_margin" in citations
        cov = {r["block"]: r for r in repos.coverage.for_instrument("ins1")}
        assert cov["llm_summary"]["status"] == "ready"
    finally:
        conn.close()
        shutil.rmtree(tmpdir)


def test_no_http_libraries_in_core_or_normalize():
    result = subprocess.run(
        ["grep", "-rnE", "httpx|requests", "rusterm/core/",
         "rusterm/normalize/"],
        capture_output=True, text=True)
    assert result.returncode == 1, result.stdout  # 1 = совпадений нет
