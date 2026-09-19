"""ТЗ-42 I2 (Q7): разговор знает, чего не знает.

Три случая — не тот эмитент, мера с причиной, устаревшая мера —
дают отказ с причиной из rusterm/reasons.py вместо ответа модели.
Модель подменяет ответ — чат обязан это перехватить.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from rusterm.core.chat import ChatSession
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Tanker Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-T", "i1", None, "common", "active", None))
    peers = PeerSetRepo(conn)
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("tv1", "tankers", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("tv1", "US-T", None)
    # снапшот, где net_margin серый с причиной из словаря
    repos.snapshot.create_snapshot("s1", "US-T", 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.insert_measure(
        "m-nm", "s1", "issuer", "i1", "net_margin", None, "ratio",
        "2024-01-01", "2024-12-31", "net_margin", "v1",
        "missing_data: net_income, revenue", None)
    return conn, repos, paths


class Fake:
    """Модель-выдумщик: всегда предлагает выдуманное число и вызывает
    указанные инструменты по сценарию."""

    model = "fake"

    def __init__(self, script):
        self.script = list(script)

    def chat(self, prompt, history):
        step = self.script.pop(0)
        if "tool_calls" in step:
            return {"text": None, "tool_calls": step["tool_calls"]}
        return {"text": step.get("text"), "tool_calls": []}


def _session(repos, script):
    return ChatSession(repos, Fake(script))


def _assert_refused(result, expected_reason: str, fabricated: str):
    """ТЗ-47 O1: отказ проверяется случай за случаем, отдельными
    assert-ами. Причина — из живого словаря rusterm/reasons.py, ответа
    нет, выдуманное число не просачивается ни в одно поле результата
    (включая rejected_text и расшифровку)."""
    assert result["rejected"] is True
    assert result["answer"] is None
    assert result["reason"] == f"no_data:{expected_reason}", result["reason"]
    token = result["reason"].split(":", 1)[1]
    assert is_known_reason(token), (
        f"причина {token!r} вне словаря rusterm/reasons.py")
    assert fabricated not in json.dumps(result, ensure_ascii=False), (
        f"выдуманное число {fabricated!r} просочилось в результат")


def test_no_such_issuer_refusal_names_reason(env):
    """Случай 1: инструмент отвечает not_found — выдуманный ответ
    модели заменяется отказом unknown_issuer."""
    conn, repos, paths = env
    session = _session(repos, [
        {"tool_calls": [{"name": "get_peer_set",
                         "arguments": {"instrument_id": "US-NOPE"}}]},
        {"text": "У эмитента US-NOPE net_margin равен 42.7 процента."},
    ])
    result = session.ask("каков net_margin у US-NOPE?")
    _assert_refused(result, "unknown_issuer", "42.7")
    conn.close()


def test_grey_measure_refusal_names_the_reason(env):
    """Случай 2: эмитент есть, мера серая с причиной missing_data:
    net_income, revenue — отказ называет эту причину, а не ответ
    модели."""
    conn, repos, paths = env
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        {"text": "net_margin Tanker Corp за 2024 год — 19.4 процента."},
    ])
    result = session.ask("каков net_margin у US-T за 2024?")
    _assert_refused(result, "missing_data", "19.4")
    conn.close()


def test_stale_measure_refusal_names_stale_reason(env):
    """Случай 3: мера устарела — в данных это продолжение причины
    missing_data: price_close_stale:<дата> (так пишет snapshot.py:806);
    отказ называет причину из словаря, число модели не проходит."""
    conn, repos, paths = env
    repos.snapshot.insert_measure(
        "m-stale", "s1", "instrument", "i1", "price_adj", None,
        "USD", "2025-01-01", "2025-01-05", "price_adj", "v1",
        "missing_data: price_close_stale:2025-01-05", None)
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        {"text": "Цена с поправкой — 12.5 доллара."},
    ])
    result = session.ask("какова цена US-T с поправкой?")
    _assert_refused(result, "missing_data", "12.5")
    conn.close()


def test_green_measure_still_answers(env):
    """ТЗ-47 O1, контроль: та же петля на ЗЕЛЁНОЙ мере отвечает, а не
    отказывает — отказ вызван причиной отсутствия данных, а не самим
    фактом вызова инструмента."""
    conn, repos, paths = env
    repos.snapshot.create_snapshot("s2", "US-T", 2, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.insert_measure(
        "m-green", "s2", "issuer", "i1", "net_margin", "0.194",
        "ratio", "2024-01-01", "2024-12-31", "net_margin", "v2",
        None, None)
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        # ответ называет ТОЛЬКО число из результата инструмента: год
        # периода инструмент не отдаёт, и страж чисел бракует ответ с
        # «за 2024» (см. Disputed в отчёте) — здесь проверяется ровно
        # сеть отказа, а не страж.
        {"text": "net_margin Tanker Corp — 0.194."},
    ])
    result = session.ask("каков net_margin у US-T за 2024?")
    assert result["rejected"] is False
    assert result["answer"] == "net_margin Tanker Corp — 0.194."
    assert result["citations"] == ["0.194"]
    conn.close()


# ── ТЗ-57 A1: порядок «страж → отказ с причиной данных» закреплён ──
# Хвост круга 60 (15c854f): серая мера в блоке не отменяет зелёный
# ответ, а отказ бракованного стражем ответа несёт ПРИЧИНУ ДАННЫХ.


def _mixed_block(repos):
    """Снапшот с зелёной И серой мерой в одном блоке — как в живом
    прогоне круга 60 (net_margin зелёный, блок серый целиком)."""
    repos.snapshot.create_snapshot("s-mix", "US-T", 3, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.insert_measure(
        "m-mix-nm", "s-mix", "issuer", "i1", "net_margin", "0.194",
        "ratio", "2024-01-01", "2024-12-31", "net_margin", "v3",
        None, None)
    repos.snapshot.insert_measure(
        "m-mix-roe", "s-mix", "issuer", "i1", "roe", None,
        "ratio", "2024-01-01", "2024-12-31", "roe", "v3",
        "missing_data: total_equity", None)


def test_green_answer_survives_gray_measure_in_block(env):
    """Случай (а): ответ прошёл страж, причина данных известна (в блоке
    есть серая мера) — ответ ВЫДАЁТСЯ, rejected ложь. Краснеет при
    откате 15c854f: там отказ no_data стрелял до стража."""
    conn, repos, paths = env
    _mixed_block(repos)
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        {"text": "net_margin Tanker Corp — 0.194."},
    ])
    result = session.ask("каков net_margin у US-T?")
    assert result["rejected"] is False, result
    assert result["answer"] == "net_margin Tanker Corp — 0.194."
    assert result["citations"] == ["0.194"]
    conn.close()


def test_guard_failure_with_known_reason_carries_data_reason(env):
    """Случай (б): ответ НЕ прошёл страж, причина данных известна —
    отказ несёт причину данных (no_data:<токен из словаря>), а не
    общее «число не процитировано»."""
    conn, repos, paths = env
    _mixed_block(repos)
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        {"text": "roe Tanker Corp — 42.7 процента."},
    ])
    result = session.ask("каков roe у US-T?")
    assert result["rejected"] is True
    assert result["answer"] is None
    assert result["reason"] == "no_data:missing_data", result["reason"]
    token = result["reason"].split(":", 1)[1]
    assert is_known_reason(token), token
    conn.close()


def test_guard_failure_without_data_reason_stays_generic(env):
    """Случай (в): страж не прошёл, причины данных нет (в блоке только
    зелёные меры) — отказ прежний, общий, на конкретный текст."""
    conn, repos, paths = env
    repos.snapshot.create_snapshot("s-green-only", "US-T", 4,
                                   "2024-12-31", None, "none", "ready")
    repos.snapshot.insert_measure(
        "m-go-nm", "s-green-only", "issuer", "i1", "net_margin",
        "0.194", "ratio", "2024-01-01", "2024-12-31", "net_margin",
        "v4", None, None)
    session = _session(repos, [
        {"tool_calls": [{"name": "get_snapshot_block",
                         "arguments": {"instrument_id": "US-T",
                                       "block": "fundamentals"}}]},
        {"text": "net_margin Tanker Corp — 42.7 процента."},
    ])
    result = session.ask("каков net_margin у US-T?")
    assert result["rejected"] is True
    assert result["answer"] is None
    assert result["reason"] == "guard_rejected_uncited_number", \
        result["reason"]
    conn.close()
