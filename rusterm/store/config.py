"""Загрузка config.toml.

Формат минимальный, парсится стандартной библиотекой (tomllib с 3.11).
Секреты (ключ LLM) сюда не пишутся никогда — ADR-0003.
"""
from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    raw_retention: str = "facts_only"  # full | facts_only
    provider_rate_limit: dict[str, float] = field(default_factory=dict)
    log_level: str = "INFO"
    providers_enabled: list[str] = field(default_factory=list)


_DEFAULTS = Config()


def load_config(path: os.PathLike | str | None) -> Config:
    """Грузит config.toml. Отсутствие или повреждение — defaults, не падать.

    Если файл повреждён так, что tomllib бросает — мы обязаны сказать
    пользователю, но не уронить `init`. Поэтому логируем и возвращаем
    defaults, помечая источник.
    """
    if path is None:
        return _DEFAULTS
    p = Path(path)
    if not p.exists():
        return _DEFAULTS
    try:
        with p.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        print(
            f"[rusterm] config.toml не разобран, используются defaults: {exc}",
            file=sys.stderr,
        )
        return _DEFAULTS
    except OSError as exc:
        print(
            f"[rusterm] config.toml не прочитан, используются defaults: {exc}",
            file=sys.stderr,
        )
        return _DEFAULTS
    return Config(
        raw_retention=str(data.get("raw_retention", _DEFAULTS.raw_retention)),
        provider_rate_limit=dict(data.get("provider_rate_limit", {})),
        log_level=str(data.get("log_level", _DEFAULTS.log_level)),
        providers_enabled=list(data.get("providers_enabled", [])),
    )


def write_default_config(path: os.PathLike | str) -> None:
    """Записывает разумный default config.toml, если файла нет.

    Не перезаписывает существующий. Никаких ключей и паролей.
    """
    p = Path(path)
    if p.exists():
        return
    p.write_text(
        'raw_retention = "facts_only"\n'
        'providers_enabled = []\n'
        'log_level = "INFO"\n'
        "[provider_rate_limit]\n",
        encoding="utf-8",
    )
