"""Отраслевые модули и их реестр (ТЗ-24 N2): сектор инструмента —
id его отраслевого peer set; модуль даёт метрики, method_version и
именованную серость. Второй сектор — mining (N11).
"""
from . import maritime_tanker  # noqa: F401
from . import mining  # noqa: F401

SECTOR_MODULES = {
    "tankers": maritime_tanker,
    "mining": mining,
}


def module_for_sector(sector: str | None):
    """Модуль сектора или None — сектор без модуля отвечает честной
    серостью, а не отсутствием блока."""
    if sector is None:
        return None
    return SECTOR_MODULES.get(sector)
