"""ТЗ-42 I1 (Q3): вопрос и приказ различаются.

- приказ «добавь MSFT в список» из чата превращается в ПРЕДЛОЖЕНИЕ
  ops и не пишет ничего (hash базы не меняется);
- применение предложения идёт через подтверждённый путь ops.apply
  и попадает в журнал аудита;
- вопрос никогда не становится предложением.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from rusterm.core.chat import detect_order, propose_order
from rusterm.core.intent import RuleClient, classify
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry, WatchlistRepo)


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
    repos.instrument.upsert_issuer(Issuer(
        "i2", "Microsoft Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-MSFT", "i2", None, "common", "active", None))
    repos.instrument.upsert_listing(
        __import__("rusterm.store.repos", fromlist=["Listing"]).Listing(
            "l-US-MSFT", "US-MSFT", "US", "USD", 1, None, None))
    repos.instrument.add_ticker_history("l-US-MSFT", "MSFT",
                                        "2020-01-01", None, None, None)
    peers = PeerSetRepo(conn)
    peers.create_peer_set("tankers", "industry", "tankers")
    peers.add_version("tv1", "tankers", 1, "2024-01-01", None,
                      "manual", "v1", True, None, None)
    peers.add_member("tv1", "US-T", None)
    repos.watchlist.create_watchlist("w1", "Наблюдение", None, None)
    # применение через ops требует существующей версии списка
    repos.watchlist.new_version("wv1", "w1", 1, "create", None)
    return conn, repos, paths


def _db_hash(paths) -> str:
    conn = sqlite3.connect(str(paths.db_path))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    data = open(str(paths.db_path), "rb").read()
    conn.close()
    import hashlib
    return hashlib.sha256(data).hexdigest()


def test_order_is_detected_not_a_question():
    assert detect_order("добавь MSFT в список наблюдения",
                        classifier=RuleClient()) is not None
    # вопрос — не приказ
    assert detect_order("в каком наборе состоит US-T?",
                        classifier=RuleClient()) is None


def test_propose_writes_nothing_until_confirmed(env):
    """Приказ -> предложение ops; hash базы не меняется; применение —
    через ops.apply (подтверждённый путь) и попадает в аудит."""
    conn, repos, paths = env
    before = _db_hash(paths)
    proposal = propose_order(repos, "добавь MSFT в список",
                             "w1", "2026-09-16",
                             classifier=RuleClient())
    after = _db_hash(paths)
    assert before == after, "предложение не имеет права писать"
    assert proposal["executed"] is False
    assert proposal["intent"] == "add_instruments"
    assert proposal["addable"], proposal
    assert "предложение" in proposal["summary"]

    # предложение попадает в аудит ДО применения: confirmed=0
    file_error = repos.audit.log(
        "chat-proposal", "w1",
        {"intent": proposal["intent"], "addable": len(proposal["addable"])},
        confirmed=False, result="proposed")
    assert file_error is None, file_error

    # применение — подтверждённый путь ops.apply
    from rusterm.core.ops import apply
    result = apply(repos.watchlist, "w1", proposal["addable"],
                   action="chat-confirmed")
    assert result["applied"] is True, result
    applied = _db_hash(paths)
    assert applied != before

    # подтверждённое применение пишет строку аудита (§3.5)
    file_error = repos.audit.log(
        "chat-confirmed", "w1",
        {"intent": proposal["intent"], "addable": len(proposal["addable"])},
        confirmed=True, result="applied")
    assert file_error is None, file_error
    # ТЗ-46 N3: журнал аудита РАЗЛИЧАЕТ предложение и применение —
    # обе строки на месте, порядок предложение -> применение
    audits = conn.execute(
        "SELECT action, confirmed, result FROM audit_log "
        "ORDER BY rowid").fetchall()
    assert ("chat-proposal", 0, "proposed") in audits, audits
    assert ("chat-confirmed", 1, "applied") in audits, audits
    assert audits[-1] == ("chat-confirmed", 1, "applied"), audits
    conn.close()


def test_proposal_to_audit_marks_unconfirmed(env):
    """Само предложение (до подтверждения) тоже оставляет строку
    аудита с confirmed=0 — различимую с применённой."""
    conn, repos, paths = env
    proposal = propose_order(repos, "добавь MSFT в список",
                             "w1", "2026-09-16",
                             classifier=RuleClient())
    repos.audit.log("chat-proposal", "w1",
                    {"intent": proposal["intent"],
                     "addable": len(proposal["addable"])},
                    confirmed=False, result="proposed")
    rows = conn.execute(
        "SELECT action, confirmed FROM audit_log ORDER BY rowid").fetchall()
    assert rows[-1] == ("chat-proposal", 0)
    conn.close()


def test_question_never_proposes(env):
    """Вопрос (сравни/расскажи) детектором приказов не ловится."""
    conn, repos, paths = env
    assert propose_order(repos, "сравни US-T с peer set",
                         "w1", "2026-09-16",
                         classifier=RuleClient()) is None
    assert propose_order(repos, "в каком наборе состоит US-T?",
                         "w1", "2026-09-16",
                         classifier=RuleClient()) is None
    conn.close()
