"""Тесты загрузки окружения из ~/.rusterm.env (TASK-8 U4).

Программа не зависит от способа запуска шелла. Значения никогда не
попадают в вывод doctor — только имена переменных и их происхождение.
"""
from __future__ import annotations

import json
import os
import stat

import pytest

from rusterm import env as env_module
from rusterm.cli import main


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Временный env-файл + RUSTERM_ENV_FILE на него; наши имена
    вычищаются из окружения, чтобы файл был единственным источником."""
    path = tmp_path / "rusterm.env"
    path.write_text(
        "# комментарий\n"
        "export RUSTERM_SEC_UA=\"Synthetic Test synthetic.invalid\"\n"
        "RUSTERM_LLM_PROVIDER='fake'\n"
        "UNRELATED_NAME=ignored\n"
        "\n",
        encoding="utf-8")
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(path))
    return path


def test_values_picked_up_from_env_file(env_file, monkeypatch):
    origins = env_module.load_env()
    assert os.environ["RUSTERM_SEC_UA"] == \
        "Synthetic Test synthetic.invalid"
    assert os.environ["RUSTERM_LLM_PROVIDER"] == "fake"
    assert "RUSTERM_LLM_API_KEY" not in os.environ
    assert origins["RUSTERM_SEC_UA"] == str(env_file)
    assert origins["RUSTERM_LLM_API_KEY"] == "—"


def test_existing_environment_wins_over_file(env_file, monkeypatch):
    monkeypatch.setenv("RUSTERM_SEC_UA", "From Shell synthetic.invalid")
    env_module.load_env()
    assert os.environ["RUSTERM_SEC_UA"] == "From Shell synthetic.invalid"
    origins = env_module.report()["vars"]
    assert origins["RUSTERM_SEC_UA"] == "окружение"


def test_missing_env_file_is_not_an_error(tmp_path, monkeypatch, capsys):
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(tmp_path / "does_not_exist.env"))
    origins = env_module.load_env()
    assert set(origins) == set(env_module.ENV_NAMES)
    assert all(v == "—" for v in origins.values())


def test_doctor_reports_names_and_origins_never_values(env_file,
                                                       capsys, monkeypatch):
    root = os.path.join(str(env_file.parent), "data")
    env_file.chmod(0o600)  # мирочитаемость проверяется отдельным тестом
    assert main(["--root", root, "init"]) == 0
    capsys.readouterr()
    monkeypatch.delenv("RUSTERM_SEC_UA", raising=False)
    assert main(["--root", root, "doctor"]) == 0
    payload = capsys.readouterr().out
    assert "RUSTERM_SEC_UA" in payload
    assert str(env_file) in payload          # происхождение видно
    assert "Synthetic Test" not in payload   # значение — никогда
    assert "synthetic.invalid" not in payload
    parsed = json.loads(payload)
    assert parsed["env"]["vars"]["RUSTERM_LLM_PROVIDER"] == str(env_file)
    assert parsed["env"]["vars"]["RUSTERM_LLM_API_KEY"] == "—"


def test_world_readable_env_file_is_reported(env_file, monkeypatch,
                                              capsys):
    env_file.chmod(env_file.stat().st_mode | stat.S_IRGRP | stat.S_IROTH)
    assert env_module.file_world_readable(env_file) is True
    root = os.path.join(str(env_file.parent), "data2")
    assert main(["--root", root, "doctor"]) == 1  # проблема = не ok
    payload = capsys.readouterr().out
    assert "читается группой/остальными" in payload
    # значение по-прежнему не утекает
    assert "Synthetic Test" not in payload
