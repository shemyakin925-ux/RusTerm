"""ТЗ-90 A4: имена, которые программа читает, приезжают из env-файла.

`GUIDE.md` §0 велит положить `RUSTERM_DART_KEY=...` в `~/.rusterm.env`,
но `load_env` пропускает всё, чего нет в `ENV_NAMES`, — строка
должна была до `providers/dart.py` никогда не доезжать (а `.app` из
Finder окружения не имеет вовсе). Проверки:

1. ключ из файла доезжает до провайдера, который его ждёт;
2. `rusterm status` и панель ключей окна называют имя и происхождение
   (значение — никогда);
3. страж: любое `RUSTERM_*`-имя, читаемое из окружения под `rusterm/`,
   должно быть в `ENV_NAMES` — иначе список и код расходятся молча.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from rusterm import env as env_module
from rusterm.cli import main
from rusterm.desktop import data as desktop_data
from rusterm.providers.budget import ConfigError, RequestGate
from rusterm.providers.dart import DartProvider
from rusterm.providers.llm_api import LlmApiClient

ROOT = Path(__file__).resolve().parents[1]

# синтетические значения: проверяем, что они НЕ утекают в вывод
DART_VALUE = "test-dart-value-0123456789"
BASE_URL = "https://llm.example.invalid/v1"

# Имена, которые читаются из окружения, но не обязаны приезжать из
# env-файла: первый ищет сам файл, второй — служебный флаг дыма окна.
NOT_LOADABLE = {
    "RUSTERM_ENV_FILE": "ищет сам env-файл: load_env обязан читать его "
                        "до ENV_NAMES, иначе файл негде взять",
    "RUSTERM_APP_SMOKE": "флаг самодиагностики окна (desktop/window.py), "
                         "конфигурацией пользователя не является",
}


@pytest.fixture(autouse=True)
def _restore_environ():
    saved = {n: os.environ.get(n) for n in env_module.ENV_NAMES}
    saved["RUSTERM_ENV_FILE"] = os.environ.get("RUSTERM_ENV_FILE")
    env_module._LAST_ORIGINS = None
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture
def guide_env_file(tmp_path, monkeypatch):
    """Файл в форме, которую обещает GUIDE §0, + путь к нему."""
    path = tmp_path / "rusterm.env"
    path.write_text(
        f"RUSTERM_DART_KEY={DART_VALUE}\n"
        f"RUSTERM_LLM_BASE_URL={BASE_URL}\n"
        "RUSTERM_LLM_MODEL=fake-model\n"
        "RUSTERM_LLM_API_KEY=sk-fake-value\n",
        encoding="utf-8")
    path.chmod(0o600)
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(path))
    return path


# ── 1. имя доезжает до того, кто его ждёт ───────────────────────────────

def test_the_dart_line_from_the_guide_reaches_the_provider(
        guide_env_file):
    origins = env_module.load_env()
    assert origins["RUSTERM_DART_KEY"] == str(guide_env_file)
    assert os.environ["RUSTERM_DART_KEY"] == DART_VALUE
    # дальше — настоящий путь провайдера: ключ из окружения, а не
    # ConfigError «ключа нет»
    provider = DartProvider.from_env(RequestGate())
    assert not isinstance(provider, ConfigError), provider.reason
    assert provider.api_key == DART_VALUE


def test_the_llm_base_url_is_loadable_too(guide_env_file):
    env_module.load_env()
    client = LlmApiClient.from_env(gate=RequestGate())
    assert not isinstance(client, ConfigError), client.reason
    assert client.base_url == BASE_URL.rstrip("/")


# ── 2. name + origin в status и в панели окна, значения нет ─────────────

def test_status_names_the_key_and_where_it_came_from(guide_env_file,
                                                     tmp_path,
                                                     monkeypatch,
                                                     capsys):
    root = str(tmp_path / "data")
    assert main(["--root", root, "init"]) == 0
    capsys.readouterr()
    # init уже применил файл к окружению — чистим имена, чтобы status
    # показал происхождение из файла, а не «окружение»: это и есть
    # запуск двойным щелчком, где шелла нет вовсе (тот же приём, что в
    # test_env.py::test_doctor_reports_names_and_origins_never_values)
    for name in env_module.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_module._LAST_ORIGINS = None
    assert main(["--root", root, "status"]) == 0
    out = capsys.readouterr().out
    assert "RUSTERM_DART_KEY: задана" in out
    assert str(guide_env_file) in out          # происхождение видно
    assert DART_VALUE not in out               # значение — никогда
    assert BASE_URL not in out
    assert "RUSTERM_LLM_BASE_URL: задана" in out


def test_desktop_key_view_lists_both_names_with_a_purpose(
        guide_env_file):
    env_module.load_env()
    view = desktop_data.keys_view()
    rows = {r["name"]: r for r in view["rows"]}
    for name in ("RUSTERM_DART_KEY", "RUSTERM_LLM_BASE_URL"):
        assert name in rows, sorted(rows)
        assert rows[name]["found"] is True
        assert rows[name]["origin"] == str(guide_env_file)
        assert rows[name]["purpose"], name     # пустое назначение —
        #                      молчаливая строка панели (C9.1)
    assert DART_VALUE not in str(view)
    assert BASE_URL not in str(view)
    assert all(r["purpose"] for r in view["rows"]), \
        [r["name"] for r in view["rows"] if not r["purpose"]]


# ── 3. страж: список ENV_NAMES и то, что код правда читает ──────────────

def _env_names_read_in_the_package() -> dict:
    """{имя: файл:строка} — каждое точное `RUSTERM_*`-имя, лежащее в
    пакете строковой константой (так его читают из окружения или
    показывают в таблице назначений). Имена из AST, а не из текста
    файла: комментарии и проза длинных строк («нет RUSTERM_SEC_UA —
    сети нет») в константы не собираются."""
    found: dict[str, str] = {}
    for path in sorted((ROOT / "rusterm").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(
                    node.value, str):
                continue
            if not _looks_like_env_name(node.value):
                continue
            found.setdefault(node.value, f"{path.relative_to(ROOT)}:"
                                        f"{node.lineno}")
    return found


def _looks_like_env_name(value: str) -> bool:
    if not value.startswith("RUSTERM_") or not value:
        return False
    rest = value[len("RUSTERM_"):]
    return bool(rest) and all(c.isupper() or c.isdigit() or c == "_"
                              for c in rest)


def test_guard_every_env_name_read_by_the_package_is_loadable():
    """ТЗ-90 A4: имя, которое код читает из окружения, обязано быть в
    `ENV_NAMES` — иначе GUIDE обещает строку в `~/.rusterm.env`, а
    `load_env` её молча выбрасывает. Направление одно: сам список тоже
    лежит в пакете константами, так что «имя в списке, но никем не
    читается» этот страж не видит."""
    # «Done when» ТЗ-90 A4 называет три имени списком: RUSTERM_DATA
    # приехал раньше (ТЗ-81 B3), и явный пин не даёт ему молча выпасть
    # из ENV_NAMES, когда страж ниже видит только читаемый код.
    for name in ("RUSTERM_DART_KEY", "RUSTERM_LLM_BASE_URL",
                 "RUSTERM_DATA"):
        assert name in env_module.ENV_NAMES, name
    names = _env_names_read_in_the_package()
    assert names, "страж ничего не нашёл — он сломан, а не зелёный"
    loadable = set(env_module.ENV_NAMES)
    unannounced = {n: where for n, where in sorted(names.items())
                   if n not in loadable and n not in NOT_LOADABLE}
    assert not unannounced, (
        "читается из окружения, но не в ENV_NAMES и не в списке "
        f"исключений: {unannounced}")
    # обратная сторона: исключение, которое больше нигде не читается, —
    # мёртвая строчка, оправдывающая имя вне списка
    dead = {n for n in NOT_LOADABLE if n not in names}
    assert not dead, f"NOT_LOADABLE содержит нечитаемые имена: {dead}"
