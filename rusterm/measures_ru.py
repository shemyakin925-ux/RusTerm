"""Имена мер и разделы таблицы (ТЗ-111 U2): концепт → «Валовая маржа»,
концепт → раздел. Разделы таблицы — те шесть, что названы в задании;
формулы для подсказок берутся из docs/data-dictionary.md (§3, документ
заморожен — разбор стабильный), единица — из словаря формул.

Каждый концепт из MEASURE_UNIT_KINDS обязан иметь имя и раздел — страж
в tests/test_task111_measures_ru.py сверяет множества.
"""
from __future__ import annotations

from pathlib import Path

import rusterm.formulas as _formulas

# концепт → имя в таблице окна (колонка 0 — без подчёркиваний)
MEASURE_RU: dict[str, str] = {
    "market_cap": "Капитализация",
    "market_cap_total": "Капитализация (всех классов)",
    "ev": "Стоимость компании (EV)",
    "pe": "P/E",
    "pb": "P/B",
    "ps": "P/S",
    "ev_ebitda": "EV/EBITDA",
    "price_adj": "Цена (скорректированная)",
    "ebitda": "EBITDA",
    "gross_profit": "Валовая прибыль",
    "gross_margin": "Валовая маржа",
    "operating_margin": "Операционная маржа",
    "net_margin": "Чистая маржа",
    "effective_tax": "Эффективная налоговая ставка",
    "nopat": "NOPAT",
    "roic": "ROIC",
    "roe": "ROE",
    "roe_incl_nci": "ROE с учётом доли меньшинств",
    "asset_turnover": "Оборачиваемость активов",
    "net_debt": "Чистый долг",
    "net_debt_ebitda": "Чистый долг / EBITDA",
    "invested_capital": "Инвестированный капитал",
    "interest_coverage": "Покрытие процентов",
    "fcf": "Свободный денежный поток",
    "div_yield": "Дивидендная доходность",
    "fcf_yield": "Доходность FCF",
    "total_return": "Полная доходность",
    "drawdown": "Просадка",
    "cagr": "CAGR",
    "eps_diluted": "Прибыль на акцию (разводнённая)",
    "dps": "Дивиденд на акцию",
    "shares_diluted": "Акции (разводнённые)",
    "hhi": "Концентрация отрасли (HHI)",
}

# порядок разделов в таблице
SECTION_ORDER: tuple[str, ...] = ("Оценка", "Рентабельность",
                                  "Эффективность", "Долг",
                                  "Денежный поток", "Доходность")

# концепт → раздел
MEASURE_SECTIONS: dict[str, str] = {}
for _concept in ("market_cap", "market_cap_total", "ev", "pe", "pb",
                 "ps", "ev_ebitda", "price_adj"):
    MEASURE_SECTIONS[_concept] = "Оценка"
for _concept in ("ebitda", "gross_profit", "gross_margin",
                 "operating_margin", "net_margin", "effective_tax",
                 "nopat"):
    MEASURE_SECTIONS[_concept] = "Рентабельность"
for _concept in ("roic", "roe", "roe_incl_nci", "asset_turnover",
                 "hhi"):
    MEASURE_SECTIONS[_concept] = "Эффективность"
for _concept in ("net_debt", "net_debt_ebitda", "invested_capital",
                 "interest_coverage"):
    MEASURE_SECTIONS[_concept] = "Долг"
MEASURE_SECTIONS["fcf"] = "Денежный поток"
for _concept in ("div_yield", "fcf_yield", "total_return", "drawdown",
                 "cagr", "eps_diluted", "dps", "shares_diluted"):
    MEASURE_SECTIONS[_concept] = "Доходность"

_FORMULA_CACHE: dict[str, str] | None = None


def measure_name(concept: str) -> str:
    """Имя в колонке 0; неизвестный концепт — как есть (честность)."""
    return MEASURE_RU.get(concept, concept)


def measure_section(concept: str) -> str:
    """Раздел меры; неизвестный — «Прочее» в конце таблицы."""
    return MEASURE_SECTIONS.get(concept, "Прочее")


def _dictionary_root() -> Path:
    return Path(__file__).resolve().parents[1] / "docs" / \
        "data-dictionary.md"


def measure_formula(concept: str, doc: str | None = None) -> str:
    """Формула концепта из §3 docs/data-dictionary.md: строка
    «concept = …» и её продолжения (отступ) до следующего концепта.
    Нет записи — пустая строка (подсказка тогда из одной единицы)."""
    global _FORMULA_CACHE
    if _FORMULA_CACHE is None:
        _FORMULA_CACHE = {}
        text = doc if doc is not None else _dictionary_root().read_text(
            encoding="utf-8")
        block_start = text.find("## 3. Формулы")
        block = text[block_start:] if block_start != -1 else text
        current: str | None = None
        buffer: list[str] = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("###"):
                continue
            head = stripped.split("=", 1)
            if len(head) == 2 and head[0].split() \
                    and head[0].split()[0].islower():
                if current is not None:
                    _FORMULA_CACHE[current] = " ".join(buffer)
                current = head[0].split()[0].strip()
                buffer = [stripped]
                continue
            if current is not None and stripped:
                buffer.append(stripped)
        if current is not None:
            _FORMULA_CACHE[current] = " ".join(buffer)
    return _FORMULA_CACHE.get(concept, "")


def measure_tooltip(concept: str, unit: str | None = None) -> str:
    """Подсказка колонки 0: формула из словаря + единица измерения."""
    parts = []
    formula = measure_formula(concept)
    if formula:
        parts.append(formula)
    unit_text = _formulas.measure_unit(concept, unit or "")
    if unit_text:
        parts.append(f"единица: {unit_text}")
    return "; ".join(parts)


# ТЗ-111 U2: показатели governance словами (вкладка «Качество»,
# колонка «показатель»); список индикаторов — закрытый в core/governance
GOVERNANCE_RU: dict[str, str] = {
    "independent_directors": "Независимые директора",
    "ceo_chair": "Председатель и CEO в одном лице",
    "related_party": "Сделки со связанными сторонами",
    "insider_net": "Чистые операции инсайдеров",
    "auditor": "Аудитор",
}
