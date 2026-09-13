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


def test_client_repr_masks_the_key(tmp_path):
    """ТЗ-29 A4: ключ, подставленный в клиента (LLM и DART), не
    всплывает ни в repr(), ни в отформатированном сообщении ассерта
    (то, что pytest печатает при падении), ни в аудит-логе."""
    import os
    import sqlite3

    import rusterm.cli as cli
    from rusterm.providers.budget import HostLimit

    fake = "sk-or-v1-TESTONLY000000"
    tail = fake[4:]  # всё, кроме четырёхсимвольного префикса

    client = LlmApiClient(
        base_url="https://openrouter.ai/api/v1", model="free/model",
        api_key=fake,
        limit=HostLimit(host="openrouter.ai", per_second=1.0,
                        nightly_max=5000))
    dart = DartProvider(gate=RequestGate(), api_key=fake)
    for obj in (client, dart):
        shown = repr(obj)
        assert fake not in shown
        assert tail not in shown

    # отформатированное сообщение ассерта не несёт значения
    message = f"client state: {client!r} / {dart!r}"
    assert fake not in message and tail not in message

    # аудит-лог: ключ в окружении (модель не задана -> правило-клиент),
    # строка аудита не содержит ни значения, ни хвоста
    root = tmp_path / "app"
    injected = {"RUSTERM_LLM_API_KEY": fake,
                "RUSTERM_ENV_FILE": "/nonexistent/rusterm.env-for-tests",
                "RUSTERM_SEC_UA": "Synthetic Test a4.invalid"}
    saved = {n: os.environ.get(n) for n in injected}
    os.environ.update(injected)
    try:
        assert cli.main(["--root", str(root), "init"]) == 0
        assert cli.main(["--root", str(root), "watchlist", "create", "w1",
                         "--name", "n"]) == 0
        cli.main(["--root", str(root), "ops", "--watchlist", "w1",
                  "--request", "а как дела у рынка вообще?"])
        db = sqlite3.connect(str(root / "rusterm.db"))
        try:
            rows = db.execute(
                "SELECT action, target, payload, confirmed, result"
                " FROM audit_log").fetchall()
        finally:
            db.close()
        assert rows, "аудит-строка не появилась — проверка пуста"
        blob = json.dumps(rows, ensure_ascii=False, default=str)
        assert fake not in blob and tail not in blob
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
