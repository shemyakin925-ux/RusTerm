"""TASK-C7: разговор внутри окна — история переживанием перезапуска,
счётчики из того же места, что rusterm status, гвард цитат на
записанном ответе.

Слой данных без Qt: расшифровки — та же таблица, что у CLI; счётчики —
calls_totals, то же место, что rusterm status. Гвард проверяется на
записанном ответе (заготовленный клиент, ни одного вызова модели).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3  # noqa: E402

import pytest  # noqa: E402

from rusterm.desktop import data as desktop_data  # noqa: E402
from rusterm.store.db import apply_migrations  # noqa: E402
from rusterm.store.paths import AppPaths, ensure_app_dir  # noqa: E402
from rusterm.store.repos import (  # noqa: E402
    Instrument, Issuer, Listing, RepoRegistry)


@pytest.fixture()
def env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-CNQ", "Canadian Natural", "CA", "101", None,
        "ifrs-full", "CAD"))
    repos.instrument.upsert_instrument(Instrument(
        "CA-CNQ", "i-CNQ", None, "common", "active", None))
    repos.instrument.upsert_listing(Listing(
        "l-CA-CNQ", "CA-CNQ", "NASDAQ", "USD", 1, None, None))
    repos.instrument.add_ticker_history(
        "l-CA-CNQ", "CNQ", "2000-01-01", None, None, None)
    yield repos, conn, paths
    conn.close()


SESSIONS = (("s-aaa", "fake-model", 3,
             [("user", "почему roe пустой?", []),
              ("assistant", "roe нет: не подан total_equity", [])]),
            ("s-bbb", "fake-model", 1,
             [("user", "что по net_margin?", []),
              ("assistant", "net_margin 0.2043 [10-K 2025, стр. 64]",
               ["[10-K 2025, стр. 64]"])]))


@pytest.fixture()
def with_transcripts(env):
    repos, conn, paths = env
    import time
    for sid, model, calls, _turns in SESSIONS:
        repos.chat_transcript.create_session(sid, model, None,
                                             time.time(), calls)
        for index, (role, text, citations) in enumerate(_turns):
            repos.chat_transcript.add_turn(
                sid, index, role, text, citations, [], False)
    yield repos, conn, paths
    conn.close()


import json  # noqa: E402


# ── C7.1: история разговоров ─────────────────────────────────────────────

def test_sessions_listed_fresh_first_and_openable(with_transcripts):
    repos, _conn, _paths = with_transcripts
    sessions = desktop_data.chat_sessions(repos)
    assert [s["session_id"] for s in sessions] == ["s-bbb", "s-aaa"]
    lines = desktop_data.chat_transcript_lines(repos, "s-aaa")
    assert any("вы: почему roe пустой?" in line for line in lines)
    assert any("модель: roe нет" in line for line in lines)
    assert desktop_data.chat_transcript_lines(repos, "s-nope") == \
        ["разговора s-nope нет"]


def test_sessions_survive_window_restart(with_transcripts, monkeypatch,
                                         tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QComboBox
    from rusterm.desktop import window as desktop_window

    QApplication.instance() or QApplication([])
    repos, _conn, paths = with_transcripts
    monkeypatch.setenv("RUSTERM_LLM_API_KEY", "sk-fake-key-abc123")

    window = desktop_window._build_window(repos, paths, "wl-1")
    combo = window.findChild(QComboBox, "chat_sessions_box")
    assert combo.count() == 3  # заголовок + два разговора
    combo.setCurrentIndex(2)  # s-aaa — свежайший
    answer = window.findChild(QLabel := __import__(
        "PySide6.QtWidgets", fromlist=["QLabel"]).QLabel,
        "answer_label")
    assert "почему roe пустой?" in answer.text()
    window.close()

    # перезапуск окна: разговоры на месте, ключ в тексте не светится
    window2 = desktop_window._build_window(repos, paths, "wl-1")
    combo2 = window2.findChild(QComboBox, "chat_sessions_box")
    assert combo2.count() == 3
    texts = " ".join(label.text() for label in
                     window2.findChildren(__import__(
                         "PySide6.QtWidgets",
                         fromlist=["QLabel"]).QLabel))
    assert "sk-fake-key-abc123" not in texts
    window2.close()


# ── C7.2: счётчики на виду ───────────────────────────────────────────────

def test_usage_line_from_calls_totals(with_transcripts):
    repos, _conn, _paths = with_transcripts
    line = desktop_data.llm_usage_line(repos)
    assert "вызовы: 4 (сегодня" in line
    assert "fake-model: 4" in line
    totals = repos.chat_transcript.calls_totals()
    assert str(totals["calls_total"]) in line
    assert "sk-" not in line


# ── C7.3: гвард цитат в окне ─────────────────────────────────────────────

class RecordedClient:
    """Записанные ответы; каждый вызов chat() — одна итерация."""

    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, prompt, transcript):
        return {"text": self.replies.pop(0)}


def test_uncited_number_shown_as_refusal_not_answer(env,
                                                    monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit)
    from rusterm.desktop import window as desktop_window

    QApplication.instance() or QApplication([])
    repos, _conn, paths = env
    import rusterm.core.llm as llm_module
    client = RecordedClient(["выручка 12345, всё хорошо"])
    client.model = "fake-model"
    monkeypatch.setattr(llm_module, "make_chat_client",
                        lambda: client)
    window = desktop_window._build_window(repos, paths, None)
    question = window.findChild(QLineEdit, "question_line")
    answer = window.findChild(QLabel, "answer_label")
    question.setText("как выручка?")
    question.returnPressed.emit()
    text = answer.text()
    assert text.startswith("отказ:")
    assert "guard_rejected_uncited_number" in text
    assert "12345" not in text, "бракованный ответ не показывается"
    window.close()
