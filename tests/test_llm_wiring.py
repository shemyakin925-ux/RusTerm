"""ТЗ-27 N1: cmd_ops получает клиента модели только через дверь
make_intent_client; без ключа — RuleClient (поведение прежнее),
с ключом — API-клиент; ключ нигде не печатается.
"""
from __future__ import annotations

import json
import os

import pytest

import rusterm.cli as cli
from rusterm.core.llm import make_intent_client


def test_make_intent_client_without_key_is_rule_client(monkeypatch):
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    from rusterm.core.intent import RuleClient
    assert isinstance(make_intent_client({}), RuleClient)


def test_make_intent_client_with_key_and_contact_is_api_client():
    from rusterm.providers.llm_api import LlmApiClient
    env = {"RUSTERM_LLM_API_KEY": "sk-or-TEST1234567890",
           "RUSTERM_SEC_UA": "Synthetic Test n1.invalid",
           "RUSTERM_LLM_MODEL": "glm-5.3-flash"}
    assert isinstance(make_intent_client(env), LlmApiClient)


def test_key_without_model_env_falls_back_to_rule_client():
    """Ключ есть, модель/контакт не настроены: дверь падает на
    правило — команда работает, сеть не трогается (§0.2.2)."""
    from rusterm.core.intent import RuleClient
    env = {"RUSTERM_LLM_API_KEY": "sk-or-TEST1234567890"}
    assert isinstance(make_intent_client(env), RuleClient)


def test_cmd_ops_uses_the_door(monkeypatch, tmp_path, capsys):
    """Подмена двери ловит вызов: cmd_ops не строит клиента сам."""
    calls = []
    from rusterm.core.intent import RuleClient

    class Spy(RuleClient):
        def __init__(self):
            super().__init__()
            calls.append("door")

    monkeypatch.setattr(cli, "make_intent_client",
                        lambda env=None: Spy())
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test n1.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "absent.env"))
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    capsys.readouterr()
    wl = cli.main(["--root", str(root), "watchlist", "create", "w",
                   "--name", "n"])
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ops", "--watchlist", "w",
                     "--request", "добавь MSFT"]) == 0
    capsys.readouterr()
    assert calls, "клиент получен не через дверь"


def test_key_never_printed_by_ops(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test n1.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(tmp_path / "absent.env"))
    monkeypatch.setenv("RUSTERM_LLM_API_KEY", "sk-or-SENTINEL-KEY-9")
    # правило вместо живого API: проверяется утечка ЗНАЧЕНИЯ, не путь
    from rusterm.core.intent import RuleClient
    monkeypatch.setattr(cli, "make_intent_client",
                        lambda env=None: RuleClient())
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "watchlist", "create", "w",
                     "--name", "n"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ops", "--watchlist", "w",
                     "--request", "добавь MSFT"]) == 0
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "sk-or-SENTINEL-KEY-9" not in out
