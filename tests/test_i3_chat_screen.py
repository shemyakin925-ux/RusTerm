"""ТЗ-42 I3/I4: экран разговора — чистые функции, никаких ANSI.

- chat_screen + render_chat собирают ходы, цитаты и строку
  стоимости из расшифровки (головной прогон, без терминала);
- в отрисовке нет управляющих последовательностей (B11);
- экран строит клиента только через дверь make_intent_client (I4).
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from rusterm.core.chat import ChatSession
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, PeerSetRepo,
                                 RepoRegistry)
from rusterm.tui import app  # noqa: F401 — I4 проверяет исходник экрана
from rusterm.tui.model import chat_screen, render_chat


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
    return conn, repos, paths


class Fake:
    model = "fake-model-1"

    def __init__(self, script):
        self.script = list(script)

    def chat(self, prompt, history):
        step = self.script.pop(0)
        return {"text": step.get("text"),
                "tool_calls": step.get("tool_calls") or []}


def test_chat_screen_and_render_headless(env):
    """I3: ходы, цитаты и стоимость собираются чистыми функциями;
    отказ помечен; в строках нет ANSI-управляющих последовательностей."""
    conn, repos, paths = env
    session = ChatSession(repos, Fake([
        {"tool_calls": [{"name": "get_peer_set",
                         "arguments": {"instrument_id": "US-T"}}]},
        {"text": "Набор: tankers, версия 1.", "tool_calls": []},
    ]))
    session.ask("в каком наборе US-T?")
    raw = json.dumps(session.transcript, default=str)
    session_dict = {"model": "fake-model-1", "calls": session.calls_made,
                    "turns": [{"role": e.role, "text": e.text,
                               "citations": e.citations,
                               "rejected": e.rejected,
                               "tool_calls": e.tool_calls}
                              for e in session.transcript]}
    screen = chat_screen(session_dict, session_dict["calls"])
    assert screen["model"] == "fake-model-1"
    assert screen["calls"] == 1
    lines = render_chat(screen)
    assert any("вы: " in line for line in lines)
    assert any("модель: Набор: tankers" in line for line in lines)
    assert any("цитата: 1" in line for line in lines), lines
    assert any("вызовов: 1" in line and "fake-model-1" in line
               for line in lines)
    for line in lines:
        assert "\x1b[" not in line, "ANSI в отрисовке (B11)"
    conn.close()


def test_rejected_turn_is_marked(env):
    """Отклонённый ход помечается [ОТКЛОНЕНО] — молчаливой выдачи нет."""
    conn, repos, paths = env
    session = ChatSession(repos, Fake([
        {"text": "net_margin равен 19.4 процента.", "tool_calls": []},
    ]))
    result = session.ask("каков net_margin?")
    assert result["rejected"] is True
    session_dict = {"model": "fake-model-1", "calls": 0,
                    "turns": [{"role": e.role, "text": e.text,
                               "citations": e.citations,
                               "rejected": e.rejected,
                               "tool_calls": e.tool_calls}
                              for e in session.transcript]}
    lines = render_chat(chat_screen(session_dict, 0))
    assert any("[ОТКЛОНЕНО]" in line for line in lines), lines
    conn.close()


def test_app_screen_constructs_client_through_the_door():
    """I4: экран не строит клиент сам — клиент приходит из
    make_intent_client; прямой конструкции RuleClient/LlmApiClient
    в app.py нет."""
    import inspect
    source = inspect.getsource(app)
    assert "make_intent_client" in source
    assert "LlmApiClient(" not in source
    assert "RuleClient(" not in source
