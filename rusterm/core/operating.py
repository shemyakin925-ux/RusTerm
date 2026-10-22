"""Операционная прибыль без своей строки (ТЗ-143 F1, REPORT-141).

PFE и XOM не подают OperatingIncomeLoss вовсе — вся цепочка (ebitda,
маржа, roic, nopat, ev_ebitda, net_debt_ebitda, interest_coverage)
честно отказывает. Правило ОДНОЙ функции для всех лиц (снапшот и
карточка): строка «прибыль до налогов» + процентные расходы −
процентные доходы; доходы не поданы — ноль. Знак вычитания доходов
содержится в тексте роли родословной — дерево называет вывод.
Вызывающий решает, на каком периоде правило применять: снапшот
сопоставляет (unit, start, end) строк, карточка — год; свой тег
операционной прибыли на период всегда сильнее вывода.
"""
from __future__ import annotations

from typing import Optional

# роль входа в родословной, когда операционная прибыль выведена
DERIVED_ROLE = ("выведено: pretax_income + interest_expense "
                "− interest_income")


def derive_operating_income(pretax: Optional[float],
                            interest_expense: Optional[float],
                            interest_income: Optional[float] = None
                            ) -> Optional[float]:
    """operating_income = pretax + interest_expense − interest_income.

    Экономика: прибыль до налогов отличается от операционной на
    процентные платежи/поступления и разовые статьи; для PFE и XOM
    разовые статьи в этих годах не искажают сравнение (сверка с Yahoo —
    REPORT-143). Доходы или расходы не поданы — вывода нет (None);
    доходы поданы — вычитаются, не поданы — ноль."""
    if pretax is None or interest_expense is None:
        return None
    return pretax + interest_expense - (interest_income or 0.0)
