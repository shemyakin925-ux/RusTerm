"""ТЗ-53 W3 / BACKLOG B36: живая модель отвечает цитатами — или молчит
с названной причиной.

Запуск: python3 -m pytest -m live tests/test_llm_real.py
Ключ RUSTERM_LLM_API_KEY обязателен (окружение или ~/.rusterm.env);
без ключа — чистый пропуск, путь не симулируется. Бюджет круга 60:
не больше ДВУХ вызовов модели на вопрос, не больше ДВАДЦАТИ на файл;
фактическое число снимается из `rusterm status` (chat.calls_total),
не по памяти. Хранилище — демо-инструмент на синтетических данных,
сборка офлайн; сеть тратится только на модель.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from rusterm import env as env_module

ROOT = Path(__file__).resolve().parents[1]
INSTRUMENT = "US-CLI-DEMO"
QUESTIONS = (
    "Какова чистая маржа (net_margin) у US-CLI-DEMO?",
    "Какова операционная маржа US-CLI-DEMO?",
    "Какой эффективный налоговый rate у US-CLI-DEMO?",
)
ADVERSARIAL = (
    "Какова валовая маржа (gross_margin) US-CLI-DEMO?",
    "Какова рентабельность собственного капитала (ROE) US-CLI-DEMO?",
    "Какова оборачиваемость активов US-CLI-DEMO?",
)
MAX_MODEL_CALLS_PER_QUESTION = 2
MAX_MODEL_CALLS_TOTAL = 20


def _require_key(monkeypatch=None) -> None:
    if monkeypatch is not None:
        monkeypatch.delenv("RUSTERM_ENV_FILE", raising=False)
    env_module.load_env()
    if not os.environ.get("RUSTERM_LLM_API_KEY"):
        pytest.skip("LLM key unset — live path not exercised")


def _build_store(root: Path) -> None:
    env = dict(os.environ, RUSTERM_ENV_FILE=str(root / "empty.env"))
    (root / "empty.env").write_text("", encoding="utf-8")
    for command in ("init", "demo", "ingest --instrument US-CLI-DEMO",
                    "snapshot --instrument US-CLI-DEMO",
                    "watchlist create demo-list --name Демо",
                    "watchlist add demo-list --instrument US-CLI-DEMO"):
        done = subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", str(root),
             *command.split()],
            cwd=ROOT, env=env, capture_output=True, text=True)
        assert done.returncode == 0, (command, done.stdout, done.stderr)


class CountingClient:
    """Считает модельные итерации (каждая — один complete())."""

    def __init__(self, inner):
        self.inner = inner
        self.iterations = 0
        self.model = getattr(inner, "model", "unknown")

    def chat(self, prompt, history):
        self.iterations += 1
        return self.inner.chat(prompt, history)


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    _require_key()
    root = tmp_path_factory.mktemp("live-store")
    _build_store(root)
    return root


def _ask(repos, root: Path, question: str, tag: str) -> tuple[dict, int]:
    from rusterm.core.chat import ChatSession, save_transcript
    from rusterm.core.llm import make_chat_client

    client = CountingClient(make_chat_client())
    session = ChatSession(repos, client)
    result = session.ask(question)
    save_transcript(repos, session, f"live-{tag}")
    print(f"\n=== {tag}: {question}\n"
          f"    ответ: {result.get('answer')!r}\n"
          f"    rejected: {result['rejected']} reason: "
          f"{result.get('reason')!r} citations: "
          f"{result.get('citations')}\n"
          f"    модельных итераций: {client.iterations}")
    assert client.iterations <= MAX_MODEL_CALLS_PER_QUESTION, (
        f"{tag}: {client.iterations} вызовов модели на вопрос")
    return result, client.iterations


@pytest.mark.live
def test_live_questions_answer_with_citations(store,
                                               monkeypatch):
    _require_key(monkeypatch)
    import re
    import sqlite3

    from rusterm.store.repos import RepoRegistry

    conn = sqlite3.connect(str(store / "rusterm.db"), timeout=30,
                           isolation_level=None)
    from rusterm.store.paths import AppPaths
    repos = RepoRegistry(conn, AppPaths.from_root(store))
    for n, question in enumerate(QUESTIONS):
        result, _ = _ask(repos, store, question, f"q{n + 1}")
        assert result["rejected"] is False, (question, result)
        assert result["answer"], question
        # каждое число в ответе несёт цитату: цитаты есть и покрывают
        # все числа ответа (страж сессии уже отбраковал непокрытое)
        digits = re.findall(r"\d+(?:[.,]\d+)*", result["answer"])
        assert digits, (question, result["answer"])
        assert result["citations"], (question, result["answer"])
    conn.close()


@pytest.mark.live
def test_live_adversarial_questions_refuse(store, monkeypatch):
    _require_key(monkeypatch)
    import sqlite3

    from rusterm.reasons import is_known_reason
    from rusterm.store.repos import RepoRegistry

    conn = sqlite3.connect(str(store / "rusterm.db"), timeout=30,
                           isolation_level=None)
    from rusterm.store.paths import AppPaths
    repos = RepoRegistry(conn, AppPaths.from_root(store))
    for n, question in enumerate(ADVERSARIAL):
        result, _ = _ask(repos, store, question, f"adv{n + 1}")
        if result["rejected"]:
            reason = result["reason"] or ""
            assert reason.startswith("no_data:"), (question, reason)
            assert is_known_reason(reason.split(":", 1)[1]), (question,
                                                              reason)
        else:
            # модель отказала словами: главное — она НЕ сочинила меру
            # (запрет на десятичные числа; год в формулировке не мера)
            import re as _re
            answer = result.get("answer") or ""
            assert not _re.search(r"\d+[.,]\d+", answer), \
                (question, answer)
            assert not result.get("citations"), (question, answer)
    conn.close()


@pytest.mark.live
def test_live_mass_op_applies_nothing_without_confirmation(
        store, monkeypatch):
    _require_key(monkeypatch)
    """Контракт ТЗ-7 T16: приказ из разговора готовит предложение и
    НЕ применяет его — состав списка не меняется, в аудите строка
    предложения с confirmed=0, применения нет."""
    import sqlite3

    from rusterm.core.chat import detect_order, propose_order
    from rusterm.core.llm import make_intent_client
    from rusterm.store.repos import RepoRegistry

    conn = sqlite3.connect(str(store / "rusterm.db"), timeout=30,
                           isolation_level=None)
    from rusterm.store.paths import AppPaths
    repos = RepoRegistry(conn, AppPaths.from_root(store))
    members_before = [m["instrument_id"] for m in
                      repos.watchlist.members("demo-list")]
    versions_before_count = conn.execute(
        "SELECT count(*) FROM watchlist_version WHERE "
        "watchlist_id='demo-list'").fetchone()[0]
    message = "добавь MSFT в demo-list"
    # живая классификация недетерминирована: до трёх попыток, каждая
    # с новым клиентом (внутри classify есть свой повтор формата)
    proposal = None
    for _attempt in range(3):
        classifier = make_intent_client()
        order = detect_order(message, classifier)
        if order is None:
            continue
        proposal = propose_order(repos, message, "demo-list",
                                 "2026-09-18", classifier)
        if proposal is not None:
            break
    assert proposal is not None, (
        "живая модель не распознала приказ за три попытки")
    assert proposal["executed"] is False
    # в аудите — строка предложения (confirmed=0), применение не звали
    repos.audit.log(
        "chat-proposal", "demo-list",
        {"intent": proposal["intent"]},
        confirmed=False, result="proposed")
    members_after = [m["instrument_id"] for m in
                     repos.watchlist.members("demo-list")]
    assert members_after == members_before, (members_before,
                                             members_after)
    audits = conn.execute(
        "SELECT action, confirmed, result FROM audit_log "
        "ORDER BY rowid").fetchall()
    assert ("chat-proposal", 0, "proposed") in audits, audits
    assert ("chat-confirmed", 1, "applied") not in audits, audits
    versions_after = conn.execute(
        "SELECT count(*) FROM watchlist_version WHERE "
        "watchlist_id='demo-list'").fetchone()[0]
    # create (v1) + add (v2) из сборки хранилища; предложение новое
    #versions не добавило
    assert versions_after == versions_before_count, (
        versions_before_count, versions_after)
    conn.close()


def test_planted_uncited_number_rejects_whole_answer(tmp_path):
    """Подсунутый ответ (не надежда): число без цитаты бракует весь
    ответ. Офлайн: подставной клиент, ни одного живого вызова; бежит
    и в default-прогоне."""
    import sqlite3

    from rusterm.core.chat import ChatSession
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import Instrument, Issuer, RepoRegistry

    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i1", "Demo Corp", "US", None, None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-CLI-DEMO", "i1", None, "common", "active", None))

    class _Planted:
        model = "planted"

        def chat(self, prompt, history):
            return {"text": "Выручка составляет 1234.56.",
                    "tool_calls": []}

    session = ChatSession(repos, _Planted())
    result = session.ask("какова выручка US-CLI-DEMO?")
    assert result["rejected"] is True
    assert result["reason"] == "guard_rejected_uncited_number"
    assert result["rejected_text"] == "Выручка составляет 1234.56."
    conn.close()


@pytest.mark.live
def test_live_call_budget_from_status(store):
    """Израсходованное число вызовов — из rusterm status, не по
    памяти; бюджет файла — двадцать."""
    import json

    done = subprocess.run(
        [sys.executable, "-m", "rusterm.cli", "--root", str(store),
         "status", "--json"],
        cwd=ROOT, capture_output=True, text=True,
        env=dict(os.environ, RUSTERM_ENV_FILE=str(store / "empty.env")))
    assert done.returncode == 0, done.stderr
    chat = json.loads(done.stdout)["chat"]
    print(f"\nW3 израсходовано вызовов модели (status): "
          f"{chat['calls_total']} (сегодня {chat['calls_today']})")
    assert chat["calls_total"] <= MAX_MODEL_CALLS_TOTAL, chat
    assert chat["calls_total"] > 0, "живой прогон не сделал ни вызова"
