"""Загрузка переменных окружения приложения (TASK-8 U4).

Программа не зависит от того, как запустили её шелл: если
RUSTERM_SEC_UA / RUSTERM_LLM_PROVIDER / RUSTERM_LLM_API_KEY не заданы
в окружении, они читаются из $RUSTERM_ENV_FILE или ~/.rusterm.env.

Правила: уже заданная в окружении переменная выигрывает; понимаются
строки `export NAME=value` и `NAME=value`, кавычки снимаются, пустые
строки и комментарии пропускаются, имена вне трёх наших игнорируются.
Значения никогда не печатаются, не логируются и не пишутся в аудит —
наружу идут только имена и происхождение.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

ENV_NAMES = ("RUSTERM_SEC_UA", "RUSTERM_LLM_PROVIDER", "RUSTERM_LLM_API_KEY")


def env_file_path(environ=None) -> Path:
    env = os.environ if environ is None else environ
    custom = env.get("RUSTERM_ENV_FILE")
    if custom:
        return Path(custom)
    return Path.home() / ".rusterm.env"


def parse_env_file(text: str) -> dict:
    """Разобрать текст файла: {name: value} только для ENV_NAMES."""
    values: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if name in ENV_NAMES and value:
            values[name] = value
    return values


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def file_world_readable(path) -> bool:
    """True, если файл читается группой или остальными: там контакт,
    может быть ключ; doctor обязан это показать."""
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return False
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH))


def load_env(environ=None) -> dict:
    """Применить env-файл к окружению (уже заданное не трогается).

    Возвращает {name: origin} для doctor: «окружение» / путь файла / «—».
    """
    env = os.environ if environ is None else environ
    path = env_file_path(env)
    file_values = parse_env_file(_read(path)) if path.is_file() else {}
    origins: dict = {}
    for name in ENV_NAMES:
        if env.get(name):
            origins[name] = "окружение"
        elif name in file_values:
            env[name] = file_values[name]
            origins[name] = str(path)
        else:
            origins[name] = "—"
    return origins


def report(environ=None) -> dict:
    """Сводка для doctor: имена, происхождение, состояние файла.
    Никаких значений."""
    env = os.environ if environ is None else environ
    path = env_file_path(env)
    exists = path.is_file()
    file_values = parse_env_file(_read(path)) if exists else {}
    origins: dict = {}
    for name in ENV_NAMES:
        if env.get(name):
            origins[name] = "окружение"
        elif name in file_values:
            origins[name] = str(path)
        else:
            origins[name] = "—"
    return {
        "file": str(path),
        "exists": exists,
        "world_readable": exists and file_world_readable(path),
        "vars": origins,
    }
