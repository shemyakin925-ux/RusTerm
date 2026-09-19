"""ТЗ-53 W3 / B36: текстовый протокол инструментов живой модели.

_ChatAdapter учит живую модель пользоваться read-only набором без
нативного function-calling: системная инструкция описывает набор и
форму запроса (ровно одна JSON-строка {"tool", "arguments"}); запрос
известного инструмента возвращается как tool_calls — вызывает
ChatSession (реестр, страж чисел, отказ значением). Здесь —
офлайн-проверки протокола на подставном complete(); живой прогон —
tests/test_llm_real.py (маркер live).
"""
from __future__ import annotations

import sqlite3

import pytest

from rusterm.core.chat import ChatSession
from rusterm.core.llm import _ChatAdapter
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry


class ScriptedModel:
    """complete() -> заготовленные ответы, каждый вызов = одна
    модельная итерация."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return self.replies.pop(0)


TOOL_REQUEST = ('{"tool": "get_snapshot_block", "arguments": '
                '{"instrument_id": "US-T", "block": "fundamentals"}}')


@pytest.fixture()
def demo_env(tmp_path):
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
    repos.snapshot.create_snapshot("s1", "US-T", 1, "2024-12-31",
                                   None, "none", "ready")
    repos.snapshot.insert_measure(
        "m1", "s1", "issuer", "i1", "net_margin", "0.1", "ratio",
        "2023-01-01", "2023-12-31", "net_margin", "v1", None, None)
    yield repos, conn
    conn.close()


def test_model_tool_request_becomes_tool_call():
    adapter = _ChatAdapter(ScriptedModel([TOOL_REQUEST]))
    reply = adapter.chat("каков net_margin у US-T?", [])
    assert reply["text"] is None
    assert reply["tool_calls"] == [{
        "name": "get_snapshot_block",
        "arguments": {"instrument_id": "US-T",
                      "block": "fundamentals"}}]


def test_instructions_name_tools_and_the_law(tmp_path):
    model = ScriptedModel(["любой ответ"])
    _ChatAdapter(model).chat("вопрос", [])
    prompt = model.prompts[0]
    for name in ("get_snapshot_block", "get_peer_set",
                 "resolve_ticker", "get_industry_metrics"):
        assert name in prompt, name
    assert "НИКОГДА" in prompt  # запрет выдуманных чисел — в промпте


def test_full_loop_model_requests_data_then_answers_with_citation(
        demo_env):
    repos, conn = demo_env
    model = ScriptedModel([
        TOOL_REQUEST,
        "net_margin Tanker Corp — 0.1",
    ])
    session = ChatSession(repos, _ChatAdapter(model))
    result = session.ask("каков net_margin у US-T?")
    assert result["rejected"] is False
    assert result["answer"] == "net_margin Tanker Corp — 0.1"
    assert result["citations"] == ["0.1"]
    assert result["tool_calls"] == ["get_snapshot_block"]
    # бюджет: одна модельная итерация на запрос данных, одна на ответ
    assert len(model.prompts) == 2
    # результат инструмента попадает в историю следующей итерации
    assert any("результат инструмента get_snapshot_block" in p
               for p in model.prompts[1:])
    conn.close()


def test_unknown_tool_name_is_not_a_tool_call(demo_env):
    repos, conn = demo_env
    model = ScriptedModel([
        '{"tool": "delete_everything", "arguments": {}}',
    ])
    session = ChatSession(repos, _ChatAdapter(model))
    result = session.ask("сотри всё")
    # не признанный инструмент — это текст модели, вызова не было;
    # чисел в тексте нет, поэтому страж чисел молчит
    assert result["rejected"] is False
    assert result["tool_calls"] == []
    assert result["answer"] == ('{"tool": "delete_everything", '
                                '"arguments": {}}')
    conn.close()
