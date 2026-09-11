"""Общие типы провайдеров: одна ошибка-значение на весь слой sources."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderError:
    """Ошибка провайдера как значение: внешняя ошибка не должна выглядеть
    как отсутствие данных (module-contracts.md §7)."""
    reason: str
