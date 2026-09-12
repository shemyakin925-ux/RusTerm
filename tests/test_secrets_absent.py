"""ТЗ-21 H8: секреты доказанно отсутствуют, а не «предположительно».

1. Ни один файл из git ls-files не совпадает с формами ключа
   OpenRouter (sk-or-…), bearer-токена или строки RUSTERM_*_KEY= со
   значением.
2. ConfigError за отсутствующий ключ содержит только ИМЯ переменной —
   никогда её значение (проверяется на подставном значении-ловушке).
3. doctor показывает ключи именами и только фактом set/unset — без
   префиксов, суффиксов и длин.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from rusterm.providers.budget import ConfigError, NetworkGate, RequestGate
from rusterm.providers.dart import DartProvider
from rusterm.providers.llm_api import LlmApiClient

ROOT = Path(__file__).resolve().parents[1]

# Формы НАСТОЯЩИХ секретов: документационные примеры вида
# RUSTERM_LLM_API_KEY=... / <key> / «Имя Фамилия email» секретами не
# являются (значение-плейсхолдер короткое, с пробелами или угловыми
# скобками); настоящий токен — длинная бессмысленная строка.
_KEY_SHAPES = (
    re.compile(r"sk-or-[A-Za-z0-9]{16,}"),               # OpenRouter
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),        # bearer-токен
    re.compile(r"RUSTERM_[A-Z_]*KEY\s*=\s*[A-Za-z0-9._\-]{16,}"),
)

_SENTINEL = "SENTINEL-VALUE-H7-0123456789"


def _tracked_files() -> list[Path]:
    listed = subprocess.run(["git", "ls-files"], cwd=ROOT,
                            capture_output=True, text=True)
    return [ROOT / line for line in listed.stdout.splitlines()
            if line.strip()]


def test_no_tracked_file_matches_key_shapes():
    files = _tracked_files()
    assert len(files) > 100  # скан покрыл репозиторий, а не пустоту
    offenders: list[str] = []
    for path in files:
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for shape in _KEY_SHAPES:
            if shape.search(text):
                offenders.append(f"{path.name}:{shape.pattern}")
    assert not offenders, ("формы ключей в git: " + "; ".join(offenders))


def test_config_error_never_carries_the_value():
    """Ловушка: значение подставлено в ДРУГУЮ переменную и в соседнюю —
    ни одна ошибка-значение не содержит его; имя переменной содержит."""
    provider = DartProvider.from_env(
        RequestGate(gate=NetworkGate(environ={
            "RUSTERM_DART_KEY": "",
            "RUSTERM_SEC_UA": _SENTINEL})),
        environ={"RUSTERM_DART_KEY": ""})
    assert isinstance(provider, ConfigError)
    assert provider.reason == "dart_key_unset"
    assert _SENTINEL not in provider.reason
    assert _SENTINEL not in repr(provider)

    client = LlmApiClient.from_env(
        environ={"RUSTERM_LLM_API_KEY": "", "RUSTERM_SEC_UA": _SENTINEL})
    assert isinstance(client, ConfigError)
    assert client.reason == "llm_key_unset"
    assert _SENTINEL not in client.reason


def test_doctor_reports_keys_by_name_and_set_unset_only(capsys, tmp_path):
    import rusterm.cli as cli

    monkey_env = {
        "RUSTERM_SEC_UA": _SENTINEL,
        "RUSTERM_ENV_FILE": str(tmp_path / "absent.env"),
    }
    import os
    for name, value in monkey_env.items():
        os.environ[name] = value
    try:
        root = tmp_path / "app"
        assert cli.main(["--root", str(root), "init"]) == 0
        capsys.readouterr()
        assert cli.main(["--root", str(root), "doctor"]) == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        report = json.dumps(payload, ensure_ascii=False)
        assert _SENTINEL not in report
        env_vars = payload["env"]["vars"]
        assert env_vars["RUSTERM_SEC_UA"] == "окружение"
        assert _SENTINEL not in env_vars["RUSTERM_SEC_UA"]
        # никакое значение в отчёте doctor не длиннее статуса
        for name, state in env_vars.items():
            assert state in ("окружение", "—") or state.endswith(
                ".env") or state.startswith("/"), (name, state)
    finally:
        for name in monkey_env:
            os.environ.pop(name, None)
