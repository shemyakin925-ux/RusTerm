"""Тесты И8: конвейер сбора — девять узлов, ветки E1-E5, идемпотентность.

Все данные синтетические: фикстуры fixtures/ и встроенные в тест
синтетические документы (помечены словом synthetic).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass

import pytest

from rusterm.pipeline import IngestionPipeline, PruneResult
from rusterm.providers.base import ProviderError
from rusterm.providers.disclosures import (
    DocumentList,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)
import hashlib

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (
    Instrument,
    InstrumentRepo,
    Issuer,
    RepoRegistry,
    persist_ingestion_results,
)

FIXTURES = __import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ── Синтетические документы для веток E4/E5 ─────────────────────────────

BAD_KIND_DOC = json.dumps({
    "source": "synthetic",
    "note": "Документ неизвестного типа — ни один парсер не берёт.",
    "payload": "mystery",
}).encode()

NO_UNIT_DOC = json.dumps({
    "source": "synthetic",
    "note": "Таблица без единиц — факт не пройдёт валидацию (E5).",
    "doc_kind": "table",
    "period_end": "2024-05-21",
    "tables": [{"table_name": "prices", "rows": [
        {"cells": [{"concept": "price_close", "value": "10.0"}]}]}],
}).encode()

EMPTY_PARSE_DOC = json.dumps({
    "source": "synthetic",
    "note": "Таблица из неразобранных ячеек — ноль фактов.",
    "doc_kind": "table",
    "period_end": "2024-05-21",
    "tables": [{"table_name": "prices", "rows": [
        {"cells": [{"concept": "", "value": "x"}]}]}],
}).encode()


class StubProvider:
    """Синтетический провайдер раскрытий с заданным сценарием отказов."""

    source_name = "synthetic"

    def __init__(self, docs: dict[str, bytes], urls: list[tuple[str, str]],
                 fail_poll_times: int = 0, fail_fetch_urls: set[str] = frozenset()):
        self._docs = dict(docs)
        self._urls = list(urls)  # [(url, doc_type)]
        self._fail_poll_times = fail_poll_times
        self._fail_fetch_urls = set(fail_fetch_urls)

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError:
        if self._fail_poll_times > 0:
            self._fail_poll_times -= 1
            return ProviderError("index_unavailable")
        records = []
        for i, (url, doc_type) in enumerate(self._urls, start=1):
            records.append(IndexRecord(
                cursor=f"{i:04d}", issuer_id="issuer-demo",
                doc_type=doc_type, period="2024", url=url,
                published_at="2024-01-01"))
        fresh = tuple(r for r in records if r.cursor > cursor)
        return IndexPoll(records=fresh,
                         cursor=fresh[-1].cursor if fresh else cursor)

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError:
        if url in self._fail_fetch_urls:
            return ProviderError("network_down")
        content = self._docs[url]
        return FetchedDocument(url=url, content=content,
                               sha256=hashlib.sha256(content).hexdigest(),
                               content_type="application/json")

    def list_documents(self, issuer_id, doc_type=None, period=None):
        return DocumentList(())


class NoSleep:
    """Паузы повторов в тестах не ждут реального времени."""

    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def _setup():
    tmpdir = tempfile.mkdtemp()
    paths = AppPaths.from_root(tmpdir)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    instruments = InstrumentRepo(conn)
    instruments.upsert_issuer(Issuer(
        issuer_id="issuer-demo", name="Demo Corp (synthetic)",
        jurisdiction="US", registry_id=None, fiscal_year_end=None,
        reporting_standard="us_gaap", reporting_currency="USD"))
    instruments.upsert_instrument(Instrument(
        instrument_id="US-DEMO-A", issuer_id="issuer-demo",
        isin=None, class_="common", status="active", superseded_by=None))
    return tmpdir, conn, paths, repos


def _provider_from_fixtures() -> StubProvider:
    return StubProvider(
        docs={
            "synthetic://report-10k": _fixture_bytes("synthetic_report_10k.json"),
            "synthetic://insider-form4": _fixture_bytes("synthetic_insider_form4.json"),
        },
        urls=[("synthetic://report-10k", "10-K"),
              ("synthetic://insider-form4", "INSIDER")],
    )


def test_pipeline_happy_path():
    tmpdir, conn, paths, repos = _setup()
    try:
        pipe = IngestionPipeline(repos, {"synthetic": _provider_from_fixtures()},
                                 sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")

        # 10-K -> 3 факта fundamentals; insider -> 1 факт ownership
        assert result.jobs_done == 2
        assert result.facts_stored == 4
        assert result.suspects == 0
        fundamentals = repos.fact.get_facts(issuer_id="issuer-demo",
                                            concept="revenue")
        assert len(fundamentals) == 2  # текущая + сравнительная (restated)
        assert fundamentals[0]["status"] == "ok"

        # курсор продвинулся: повторный poll не вернёт старое
        assert repos.job.get_cursor("synthetic", "disclosures") == "0002"

        # coverage по обоим блокам готов
        assert repos.job.get_coverage("US-DEMO-A", "fundamentals")["status"] == "ready"
        assert repos.job.get_coverage("US-DEMO-A", "ownership")["status"] == "ready"
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_i7_double_run_creates_nothing_new():
    """I7: двойной прогон не создаёт ни нового объекта, ни фактов."""
    tmpdir, conn, paths, repos = _setup()
    try:
        pipe = IngestionPipeline(repos, {"synthetic": _provider_from_fixtures()},
                                 sleep=NoSleep())
        first = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        objects_after_first = conn.execute(
            "SELECT COUNT(*) FROM raw_object").fetchone()[0]
        facts_after_first = conn.execute(
            "SELECT COUNT(*) FROM fact").fetchone()[0]
        assert facts_after_first == first.facts_stored

        second = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        # курсор сдвинулся — новых заданий нет вообще
        assert second.facts_stored == 0
        assert second.jobs_done == 0
        assert conn.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0] \
            == objects_after_first
        assert conn.execute("SELECT COUNT(*) FROM fact").fetchone()[0] \
            == facts_after_first

        # потеря курсора не ломает идемпотентность: те же url не ставят
        # новых заданий (узел 3 отсекает их по ключу)
        repos.job.set_cursor("synthetic", "disclosures", "")
        third = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert third.deduped_jobs == 2
        assert third.facts_stored == 0
        assert conn.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0] \
            == objects_after_first
        assert conn.execute("SELECT COUNT(*) FROM fact").fetchone()[0] \
            == facts_after_first
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_double_run_creates_no_new_job_rows():
    """BACKLOG B3: идемпотентность очереди заданий. Второй прогон —
    и даже третий с потерянным курсором — не добавляет строк в job."""
    tmpdir, conn, paths, repos = _setup()
    try:
        pipe = IngestionPipeline(repos, {"synthetic": _provider_from_fixtures()},
                                 sleep=NoSleep())
        pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        jobs_after_first = conn.execute(
            "SELECT COUNT(*) FROM job").fetchone()[0]
        assert jobs_after_first == 2

        pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] \
            == jobs_after_first, "повтор добавил задания в очередь"

        repos.job.set_cursor("synthetic", "disclosures", "")
        pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] \
            == jobs_after_first, "poll с нулевым курсором дублирует задания"
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_duplicate_sha256_closes_job_without_parsing():
    """Один документ под двумя url: второй закрывается по дублю sha256,
    факты не дублируются — узел 5, processes.md §119."""
    tmpdir, conn, paths, repos = _setup()
    try:
        doc_bytes = _fixture_bytes("synthetic_report_10k.json")
        provider = StubProvider(
            docs={"synthetic://report-10k": doc_bytes,
                  "synthetic://report-10k-mirror": doc_bytes},
            urls=[("synthetic://report-10k", "10-K"),
                  ("synthetic://report-10k-mirror", "10-K")])
        pipe = IngestionPipeline(repos, {"synthetic": provider}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.duplicates == 1
        assert result.facts_stored == 3  # только с первого url
        assert conn.execute("SELECT COUNT(*) FROM raw_object").fetchone()[0] == 1
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_e1_index_unavailable_marks_coverage_error():
    tmpdir, conn, paths, repos = _setup()
    try:
        flaky = StubProvider(docs={}, urls=[], fail_poll_times=99)
        sleeper = NoSleep()
        pipe = IngestionPipeline(repos, {"synthetic": flaky}, sleep=sleeper)
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.coverage_errors == 1
        cov = repos.job.get_coverage("US-DEMO-A", "fundamentals")
        assert cov["status"] == "error"
        assert "E1" in cov["reason"]
        # три попытки с экспоненциальной паузой
        assert len(sleeper.calls) == 3
        assert sleeper.calls == [2.0, 4.0, 8.0]
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_e1_recovers_after_transient_failure():
    tmpdir, conn, paths, repos = _setup()
    try:
        # индекс недоступен один раз, со второй попытки отвечает
        flaky = _provider_from_fixtures()
        flaky._fail_poll_times = 1
        pipe = IngestionPipeline(repos, {"synthetic": flaky}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.facts_stored == 4
        assert result.coverage_errors == 0
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_e3_fetch_failure_dead_letters_job():
    tmpdir, conn, paths, repos = _setup()
    try:
        provider = _provider_from_fixtures()
        provider._fail_fetch_urls = {"synthetic://report-10k"}
        pipe = IngestionPipeline(repos, {"synthetic": provider}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.fetch_failures == 1
        cov = repos.job.get_coverage("US-DEMO-A", "fundamentals")
        assert cov["status"] == "error"
        assert "E3" in cov["reason"]
        # задание в dead-letter с сохранением причины
        row = conn.execute(
            "SELECT status, last_error FROM job WHERE last_error LIKE 'E3%'"
        ).fetchone()
        assert row is not None and row[0] == "dead"
        # второй блок (ownership) не задет
        assert repos.job.get_coverage("US-DEMO-A", "ownership")["status"] == "ready"
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_e4_unparsed_document_is_kept_and_marked():
    tmpdir, conn, paths, repos = _setup()
    try:
        provider = StubProvider(
            docs={"synthetic://mystery": BAD_KIND_DOC},
            urls=[("synthetic://mystery", "MYSTERY-TYPE")])
        pipe = IngestionPipeline(repos, {"synthetic": provider}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.needs_verification == 1
        cov = repos.job.get_coverage("US-DEMO-A", "fundamentals")
        assert cov["status"] == "missing"
        assert "needs_verification" in cov["reason"]
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_e5_invalid_fact_persisted_as_suspect():
    tmpdir, conn, paths, repos = _setup()
    try:
        provider = StubProvider(
            docs={"synthetic://bad-unit": NO_UNIT_DOC},
            urls=[("synthetic://bad-unit", "PRICES")])
        pipe = IngestionPipeline(repos, {"synthetic": provider}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.suspects == 1
        assert result.facts_stored == 1
        cov = repos.job.get_coverage("US-DEMO-A", "prices")
        # у coverage нет статуса «частично»: проблема живёт в reason
        assert cov["status"] == "ready"
        assert "suspect" in cov["reason"]
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_cascade_marks_dependents_stale():
    tmpdir, conn, paths, repos = _setup()
    try:
        pipe = IngestionPipeline(repos, {"synthetic": _provider_from_fixtures()},
                                 sleep=NoSleep())
        pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        for dep in ("industry_metrics", "llm_summary"):
            cov = repos.job.get_coverage("US-DEMO-A", dep)
            assert cov is not None and cov["status"] == "stale", dep
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_persist_is_atomic_no_half_state():
    """Сбой узла 8 откатывает факты и coverage целиком."""
    tmpdir, conn, paths, repos = _setup()
    try:
        raw_repo = repos.raw
        obj = raw_repo.put(b"synthetic test bytes", provider="synthetic",
                           block="fundamentals")
        good = {
            "fact_id": "f-ok", "issuer_id": "issuer-demo",
            "listing_id": None, "concept": "revenue",
            "period_start": "2024-01-01", "period_end": "2024-12-31",
            "period_type": "duration", "value": "1", "unit": "USD",
            "currency": None, "basis": "as_reported", "origin": "extracted",
            "source_ref": obj.sha256, "locator": {"kind": "xbrl"},
            "parser_version": "synthetic.v1", "status": "ok",
        }
        broken = dict(good, fact_id="f-bad", issuer_id=None,
                      listing_id=None)  # нарушает CHECK: ровно одна сущность
        with pytest.raises(sqlite3.IntegrityError):
            persist_ingestion_results(
                conn, [good, broken],
                [("US-DEMO-A", "fundamentals", "ready", None)])
        # полусостояния нет: ни фактов, ни coverage
        assert conn.execute("SELECT COUNT(*) FROM fact").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM coverage").fetchone()[0] == 0
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_i13_facts_only_keeps_needs_verification():
    """I13: facts_only не удаляет неразобранное. Документ с пометкой
    needs_verification остаётся, пустой разбор убирается из индекса."""
    tmpdir, conn, paths, repos = _setup()
    try:
        provider = StubProvider(
            docs={
                "synthetic://mystery": BAD_KIND_DOC,
                "synthetic://empty": EMPTY_PARSE_DOC,
            },
            urls=[("synthetic://mystery", "MYSTERY-TYPE"),
                  ("synthetic://empty", "PRICES")])
        pipe = IngestionPipeline(repos, {"synthetic": provider}, sleep=NoSleep())
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.needs_verification == 1

        mystery_sha = hashlib.sha256(BAD_KIND_DOC).hexdigest()
        empty_sha = hashlib.sha256(EMPTY_PARSE_DOC).hexdigest()
        assert repos.raw.has(mystery_sha)
        assert repos.raw.has(empty_sha)

        prune = pipe.prune_unparsed("facts_only")
        assert isinstance(prune, PruneResult)
        assert prune.kept_needs_verification == 1
        assert prune.deleted_without_facts == 1
        # неразобранное на месте, пустой разбор убран
        assert repos.raw.has(mystery_sha)
        assert not repos.raw.has(empty_sha)
        conn.close()
    finally:
        shutil.rmtree(tmpdir)


def test_run_twice_with_fresh_state_is_deduped():
    """Постановка идемпотентна по ключу: те же url не ставят вторых заданий."""
    tmpdir, conn, paths, repos = _setup()
    try:
        pipe = IngestionPipeline(repos, {"synthetic": _provider_from_fixtures()},
                                 sleep=NoSleep())
        pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        repos.job.set_cursor("synthetic", "disclosures", "")
        result = pipe.run("US-DEMO-A", "issuer-demo", "synthetic")
        assert result.deduped_jobs == 2
        assert conn.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 2
        conn.close()
    finally:
        shutil.rmtree(tmpdir)
