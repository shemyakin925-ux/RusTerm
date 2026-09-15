"""ТЗ-36 H1-H4: расшифровка — данные.

- разговор переживает процесс: сохранённая сессия читается с теми же
  ходами и цитатами (H2), в строке сессии — модель и вызовы;
- rusterm export --chat выдаёт расшифровку; grep по фейковому ключу —
  ноль попаданий (H4);
- повторная верификация: цитата, которой больше нет в свежих данных,
  сообщается как не резолвящаяся (Q8);
- status --json несёт вызовы сегодня/всего по моделям, и итог равен
  сумме строк расшифровок (H3).
"""
from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from rusterm.core.chat import ChatSession, reverify_transcript, \
    save_transcript
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)


class FakeClient:
    model = "fake-model-1"

    def __init__(self, script):
        self.script = list(script)

    def chat(self, prompt, history):
        return self.script.pop(0)


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
    repos.snapshot.create_snapshot("s1", "US-T", 1, "2024-12-31",
                                   None, "none", "ready")
    return conn, repos, paths, tmp_path


def _session(repos, script):
    return ChatSession(repos, FakeClient(script))


def test_conversation_survives_the_process(env):
    """H2: разговор сохранён, закрыт, открыт заново (новый репозиторий
    над тем же файлом базы) — те же ходы, те же цитаты; в строке
    сессии модель и вызовы."""
    conn, repos, paths, tmp_path = env
    session = _session(repos, [
        {"text": "", "tool_calls": [
            {"name": "get_peer_set",
             "arguments": {"instrument_id": "US-T"}}]},
        {"text": "Набор: tankers, версия 1.", "tool_calls": []},
    ])
    result = session.ask("в каком наборе US-T?")
    assert result["rejected"] is False
    sid = save_transcript(repos, session, "chat-test-1",
                          instrument_id="US-T")
    assert sid == "chat-test-1"
    conn.close()

    # «новый процесс»: свежее соединение к той же базе
    conn2 = sqlite3.connect(str(paths.db_path), timeout=30,
                            isolation_level=None)
    repos2 = RepoRegistry(conn2, paths)
    transcript = repos2.chat_transcript.get("chat-test-1")
    assert transcript["model"] == "fake-model-1"
    assert transcript["calls"] == session.calls_made
    roles = [t["role"] for t in transcript["turns"]]
    assert roles == ["user", "tool", "assistant"]
    assistant = transcript["turns"][-1]
    assert assistant["text"] == "Набор: tankers, версия 1."
    assert result["citations"] and assistant["citations"] == \
        result["citations"]
    conn2.close()


def test_citation_invalidated_by_newer_data_is_reported(env):
    """Q8: цитата 1 резолвится, пока снапшот старый; после новой
    версии снапшота с другим числом повторная верификация называет
    цитату не резолвящейся, а не подменяет число."""
    conn, repos, paths, tmp_path = env
    repos.snapshot.insert_measure(
        "m-nm", "s1", "issuer", "i1", "net_margin", "0.12", "ratio",
        "2024-01-01", "2024-12-31", "net_margin", "v1", None, None)
    session = _session(repos, [
        {"text": "", "tool_calls": [
            {"name": "get_snapshot_block",
             "arguments": {"instrument_id": "US-T",
                           "block": "fundamentals"}}]},
        {"text": "net_margin равен 0.12.", "tool_calls": []},
    ])
    session.ask("каков net_margin?")
    save_transcript(repos, session, "chat-test-2")
    fresh = reverify_transcript(repos, "chat-test-2")
    assert fresh["verified"] is True

    # данные ушли вперёд: новая версия снапшота с другим числом
    repos.snapshot.create_snapshot("s2", "US-T", 2, "2026-06-30",
                                   None, "none", "ready")
    repos.snapshot.insert_measure(
        "m-nm-v2", "s2", "issuer", "i1", "net_margin", "0.34", "ratio",
        "2026-01-01", "2026-06-30", "net_margin", "v1", None, None)
    stale = reverify_transcript(repos, "chat-test-2")
    assert stale["verified"] is False
    assert stale["stale_citations"] == {2: ["0.12"]}, stale
    conn.close()


def test_export_chat_writes_transcript_json(env, capsys, tmp_path):
    """H2/H4: rusterm export --chat выдаёт расшифровку; фейковый ключ
    из окружения в ней не встречается ни разу."""
    conn, repos, paths, tmp_path = env
    session = _session(repos, [
        {"text": "Ответ без чисел.", "tool_calls": []},
    ])
    session.ask("вопрос")
    save_transcript(repos, session, "chat-exp-1")
    conn.close()

    import subprocess
    import sys
    import os
    env_vars = {**os.environ, "RUSTERM_LLM_API_KEY": "FAKE-KEY-abc123"}
    out = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root",
         str(paths.root), "export", "--chat", "chat-exp-1"],
        capture_output=True, text=True, env=env_vars)
    assert out.returncode == 0, out.stderr
    assert "FAKE-KEY-abc123" not in out.stdout
    assert out.stdout.count("FAKE-KEY") == 0
    doc = json.loads(out.stdout)
    assert doc["session_id"] == "chat-exp-1"
    assert doc["turns"][0]["role"] == "user"


def test_status_chat_counters_equal_transcript_rows(env):
    """H3: итоги status равны сумме вызовов строк расшифровок; ключи
    закреплены расширением B16, не ослаблением."""
    conn, repos, paths, tmp_path = env
    repos.chat_transcript.create_session("s-a", "glm-5.3-flash", None,
                                         100.0, 5)
    repos.chat_transcript.create_session("s-b", "other-model", None,
                                         200.0, 3)
    from rusterm.cli import main
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert main(["--root", str(paths.root), "status", "--json"]) == 0
    payload = json.loads(buf.getvalue())
    assert set(payload["chat"]) == {"calls_total", "calls_today",
                                    "per_model"}
    rows_sum = conn.execute(
        "SELECT SUM(calls) FROM chat_transcript").fetchone()[0]
    assert payload["chat"]["calls_total"] == rows_sum
    assert payload["chat"]["per_model"] == {"glm-5.3-flash": 5,
                                            "other-model": 3}
    conn.close()


def test_migration_45_idempotent_and_transcript_tables(env):
    """H1: миграция 45 применяется повторно без дублей; таблицы
    расшифровок на месте."""
    conn, repos, paths, tmp_path = env
    repos.chat_transcript.create_session("s-x", "m", None, 1.0, 2)
    repos.chat_transcript.add_turn("s-x", 0, "user", "вопрос", [], [],
                                   False)
    from rusterm.store.db import apply_migrations
    apply_migrations(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM chat_turn").fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM chat_transcript").fetchone()[0] == 1
    conn.close()
