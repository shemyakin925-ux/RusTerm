"""ТЗ-90 A2: `rusterm chat` работает у пользователя с ключом.

Разбираемая часть болезни — не модель, а CLI: `cmd_chat` читал
`args.max_calls`, у sub-парсера `chat` не было ни одного аргумента, и
сессия кончалась AttributeError ещё до первого вопроса; второй NameError
(`time.time()` при модульном `import time as _time`) дожидался пользователя
в конце каждой сессии. ТЗ-26 коммит `4fd5e9e` нёс оба с рождения, а
приёмка их не видела: единственный тест чата (`test_free_only.py`) водил
путь БЕЗ ключа и умирал раньше — тот же урок ТЗ-46 N2, что дверь надо
водить, а не функцию около неё.

Страж нуля сети — autouse-фикстура conftest (urlopen падает), поэтому
«ноль сети» здесь доказана самим прогоном, а не обещанием.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

import rusterm.cli as cli
from rusterm.core.chat import MAX_TOOL_CALLS_PER_SESSION
from rusterm.providers import budget as budget_module

FAKE_UA = "Synthetic Test t.invalid"


class _StubGate:
    """Гейт-заглушка на нижнем сиде, какое остаётся честным: дверь
    `make_chat_client` вызывается настоящая, клиент строится настоящий,
    подменён только `request` — network-дверь. Прецедент — _StubGate в
    tests/test_chat_door.py."""

    def __init__(self, content: str):
        self._reply = (200, json.dumps(
            {"choices": [{"message": {"content": content}}]}).encode(), {})
        self.calls = 0

    def request(self, send, limit=None):
        self.calls += 1
        return self._reply


def _chat_env(tmp_path, monkeypatch, content="ответ без чисел"):
    monkeypatch.setenv("RUSTERM_LLM_API_KEY", "TESTONLY-key")
    monkeypatch.setenv("RUSTERM_LLM_MODEL", "fake-model")
    monkeypatch.setenv("RUSTERM_SEC_UA", FAKE_UA)
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env-t90")
    gates = []

    def fake_gate(*args, **kwargs):
        gate = _StubGate(content)
        gates.append(gate)
        return gate

    monkeypatch.setattr(budget_module, "RequestGate", fake_gate)
    answers = iter(["вопрос", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    return tmp_path / "app", gates


def test_chat_parser_declares_its_arguments():
    """`args.max_calls` обязан существовать: дефолт — словарь
    MAX_TOOL_CALLS_PER_SESSION, `--instrument` опционален."""
    parser = cli._build_parser()
    args = parser.parse_args(["chat"])
    assert args.max_calls == MAX_TOOL_CALLS_PER_SESSION
    assert args.instrument is None
    args = parser.parse_args(["chat", "--max-calls", "5",
                              "--instrument", "US-AAPL"])
    assert args.max_calls == 5 and args.instrument == "US-AAPL"


def test_chat_with_a_key_exits_zero_and_leaves_one_transcript(tmp_path,
                                                              monkeypatch,
                                                              capsys):
    """Полный путь дверью: ключ есть, вопрос задан, пустая строка —
    выход. Выход 0, одна строка chat_transcript, вызов модели был,
    сети не было (страж conftest)."""
    root, gates = _chat_env(tmp_path, monkeypatch)
    code = cli.main(["--root", str(root), "chat"])
    out = capsys.readouterr().out
    assert code == 0, "чат с ключом не доехал до конца сессии"
    assert any(g.calls for g in gates), "ни одного вызова модели — тест пустой"
    assert "расшифровка сохранена" in out, out

    rows = sqlite3.connect(str(root / "rusterm.db")).execute(
        "SELECT session_id, model, calls FROM chat_transcript").fetchall()
    assert len(rows) == 1, rows
    session_id, model, calls = rows[0]
    assert session_id.startswith("chat-") and model == "fake-model"
    # колонка calls — счётчик вызовов ИНСТРУМЕНТОВ (core/chat.py:83), а
    # не модели; на прямом ответе без инструмента он честный ноль.
    # Сам вызов модели доказан выше счётчиком гейта.
    assert calls == 0, calls


def test_chat_max_calls_reaches_the_session(tmp_path, monkeypatch, capsys):
    """`--max-calls 0` — сессия не имеет права ни на один вызов: ответ
    приходит отказом с именованной причиной, а расшифровка всё равно
    сохраняется (чат никогда не пишет данные, только свой след)."""
    root, gates = _chat_env(tmp_path, monkeypatch)
    code = cli.main(["--root", str(root), "chat", "--max-calls", "0"])
    out = capsys.readouterr().out
    assert code == 0
    assert "[отказ:" in out, out
    assert not any(g.calls for g in gates), \
        "бюджет сессии не удержал вызовы модели"
    n = sqlite3.connect(str(root / "rusterm.db")).execute(
        "SELECT COUNT(*) FROM chat_transcript").fetchone()[0]
    assert n == 1


def test_chat_without_a_key_still_refuses_by_name(tmp_path, monkeypatch,
                                                  capsys):
    """Прежний пин свободности не сломан: без ключа — причина и код 1."""
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env-t90")
    code = cli.main(["--root", str(tmp_path / "app"), "chat"])
    err = capsys.readouterr().err
    assert code == 1 and "бесплатн" in err, err
    assert "Traceback" not in err and "AttributeError" not in err
