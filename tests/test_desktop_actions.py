"""TASK-C2: действия из окна — сбор и бюджет без Qt и без сети.

Сбор зовёт те же двери ядра, что CLI (IngestionPipeline,
SnapshotBuilder), логика не дублируется; отмена кооперативная и не
оставляет половины снапшота; отказ провайдера виден причиной словами,
не трассировкой; бюджет читается из того же источника, что
`rusterm budget`, и меняется после сбора.
"""
from __future__ import annotations

import sqlite3
import time as _time

import pytest

from rusterm.desktop import actions
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import ConfigError
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, Listing, RepoRegistry)
from rusterm.pipeline import IngestionPipeline


def _connect(paths):
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _make_demo(repos):
    """Демо-эмитент и инструмент теми же дверями, что rusterm demo —
    идентификаторы импортируются, не копируются."""
    from rusterm.cli import DEMO_INSTRUMENT, DEMO_ISSUER
    repos.instrument.upsert_issuer(Issuer(
        DEMO_ISSUER, "CLI Demo Corp (synthetic)", "US", None, None,
        "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        DEMO_INSTRUMENT, DEMO_ISSUER, None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        f"{DEMO_INSTRUMENT}-listing", DEMO_INSTRUMENT, "XNAS", "USD",
        1, None, None))
    repos.instrument.add_ticker_history(
        f"{DEMO_INSTRUMENT}-listing", "DEMO", "2020-01-01", None,
        None, None)
    return DEMO_INSTRUMENT


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    demo_id = _make_demo(repos)
    # посторонний инструмент: окно обязано отказаться собирать его
    # синтетикой и назвать команду CLI
    repos.instrument.upsert_issuer(Issuer(
        "i-AAA", "Alpha Alpha", "US", None, None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-AAA", "i-AAA", None, "common", "active", None))
    yield repos, paths, demo_id
    conn.close()


def test_collect_happy_path_builds_snapshot(env):
    repos, paths, demo_id = env
    stages = []
    outcome = actions.collect_synthetic(paths.root, demo_id,
                                        on_stage=stages.append)
    assert outcome.ok, f"{outcome.reason}: {outcome.detail}"
    assert outcome.snapshot_id is not None
    assert repos.snapshot.latest_snapshot_id(demo_id) == \
        outcome.snapshot_id
    assert "конвейер" in " ".join(stages)
    assert "снапшот" in " ".join(stages)
    # карточка после сбора показывает меры — окно не считает само
    from rusterm.desktop import data
    table = data.measure_table_rows(repos, demo_id)
    assert table["measures"]


def test_collect_refuses_non_demo_and_names_cli(env):
    repos, paths, _demo = env
    outcome = actions.collect_synthetic(paths.root, "US-AAA")
    assert outcome.ok is False
    assert outcome.reason == "synthetic_demo_only"
    assert "rusterm ingest --source edgar" in outcome.detail


def test_collect_unknown_instrument_names_demo_command(tmp_path):
    paths = AppPaths.from_root(tmp_path / "empty")
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    from rusterm.cli import DEMO_INSTRUMENT
    repos = RepoRegistry(conn, paths)
    outcome = actions.collect_synthetic(paths.root, DEMO_INSTRUMENT)
    assert outcome.ok is False
    assert outcome.reason == "unknown_issuer"
    assert "rusterm demo" in outcome.detail
    conn.close()


def test_provider_refusal_is_words_not_traceback(env):
    repos, paths, demo_id = env
    outcome = actions.collect_synthetic(
        paths.root, demo_id,
        providers={"synthetic": ConfigError(reason="edgar_key_unset")})
    assert outcome.ok is False
    assert outcome.reason == "edgar_key_unset"
    assert "недоступен" in outcome.detail


def test_index_unavailable_is_named_words(env):
    """E1: источник раскрытий не отвечает — причина словами, покрытие
    помечено конвейером; окно не молчит и не падает."""
    repos, paths, demo_id = env
    silent = lambda _s: None  # noqa: E731 — паузы повторов не ждём

    class DeadProvider:
        reason = None

        def poll_index(self, cursor):
            return ProviderError(reason="host_unreachable")

    outcome = actions.collect_synthetic(
        paths.root, demo_id, providers={"synthetic": DeadProvider()},
        sleep=silent)
    assert outcome.ok is False
    assert outcome.reason == "index_unavailable"
    cov = {r["block"]: r for r in repos.coverage.for_instrument(demo_id)}
    assert cov["fundamentals"]["status"] == "error"


def test_fetch_failure_is_named_words(env):
    """E3: индекс отвечает, документы не забираются — причина словами."""
    repos, paths, demo_id = env
    silent = lambda _s: None  # noqa: E731
    inner = actions._synthetic_providers()["synthetic"]

    class HalfDeadProvider:
        reason = None

        def poll_index(self, cursor):
            return inner.poll_index(cursor)

        def fetch_document(self, url):
            return ProviderError(reason="source_unreachable")

    outcome = actions.collect_synthetic(
        paths.root, demo_id,
        providers={"synthetic": HalfDeadProvider()}, sleep=silent)
    assert outcome.ok is False
    assert outcome.reason == "fetch_failed"


def test_cancel_before_start_creates_nothing(env):
    repos, paths, demo_id = env
    flag = actions.CancelFlag()
    flag.cancel()
    outcome = actions.collect_synthetic(paths.root, demo_id, cancel=flag)
    assert outcome.cancelled
    assert repos.snapshot.latest_snapshot_id(demo_id) is None


def test_cancel_mid_flight_leaves_no_half_snapshot(env):
    """Отмена на лету: снапшот не строится вовсе — половины не бывает
    (конвейер идемпотентен, снапшот атомарен)."""
    repos, paths, demo_id = env
    flag = actions.CancelFlag()
    inner = actions._synthetic_providers()["synthetic"]

    class CancelDuringPipeline:
        reason = None

        def poll_index(self, cursor):
            flag.cancel()
            return inner.poll_index(cursor)

        def fetch_document(self, url):
            return inner.fetch_document(url)

    outcome = actions.collect_synthetic(
        paths.root, demo_id, cancel=flag,
        providers={"synthetic": CancelDuringPipeline()})
    assert outcome.cancelled
    assert outcome.snapshot_id is None
    assert repos.snapshot.latest_snapshot_id(demo_id) is None


def test_budget_view_same_source_as_cli_and_updates(env):
    repos, paths, demo_id = env
    repos.metrics.record_sample(_time.time(), "provider_requests_used",
                                "edgar", 3.0)
    before = actions.budget_view(repos)
    assert before["ceiling_per_night"] == 5000
    assert before["used_today"] == 3

    # сбор с провайдером, который тратит запросы: сэмпл пишет сам
    # провайдер — тем же вызовом, каким его пишут функции CLI
    inner = actions._synthetic_providers()["synthetic"]

    class CountingProvider:
        reason = None
        calls = 0

        def poll_index(self, cursor):
            return inner.poll_index(cursor)

        def fetch_document(self, url):
            self.calls += 1
            repos.metrics.record_sample(
                _time.time(), "provider_requests_used", "synthetic", 2.0)
            return inner.fetch_document(url)

    provider = CountingProvider()
    outcome = actions.collect_synthetic(
        paths.root, demo_id, providers={"synthetic": provider})
    assert outcome.ok
    after = actions.budget_view(repos)
    # каждый запрос провайдера — +2 в сумме сэмплов; число изменилось
    assert after["used_today"] == before["used_today"] + 2 * provider.calls


def test_pipeline_door_is_the_core_one_not_a_copy():
    """Логика не продублирована: сбор идёт через IngestionPipeline и
    строитель снапшотов ядра; тела CLI не копируются в десктоп."""
    import inspect
    src = inspect.getsource(actions)
    assert "IngestionPipeline(" in src
    assert "SnapshotBuilder(" in src
    for locked in actions.CLI_LOCKED_FUNCTIONS:
        assert f"def {locked}" not in src, locked
