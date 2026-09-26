"""Повторный разбор уже скачанных companyfacts: починка basis.

Зачем (находка координатора 24.09.2026). Регрессия ТЗ-78 Y2: с тех пор
как CompanyFactsParser разбирает раздел ``dei``, дата обложки сдвигала
«конец периода подачи», и каждый финансовый факт подачи записывался
``restated``. Снапшот берёт только ``as_reported`` — у половины реальных
американских эмитентов считались 4 меры из 28 и меньше.

Починка разборщика не лечит уже сохранённое: сбор пропускает ответ,
который уже лежит в хранилище (дедупликация по sha256). Этот модуль
заново разбирает сохранённые сырые ответы нынешним разборщиком и
исправляет у фактов ТОЛЬКО basis. Значения, периоды, происхождение и
вытеснение не трогаются; сеть не нужна.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RebasisResult:
    objects: int = 0
    facts_checked: int = 0
    changed: int = 0
    to_as_reported: int = 0
    to_restated: int = 0
    unmatched: int = 0          # разобран, но среди сохранённых не найден
    unreadable: list = field(default_factory=list)


def rebasis_companyfacts(repos) -> RebasisResult:
    """Пройти все сохранённые companyfacts и выровнять basis фактов с
    нынешним CompanyFactsParser. Идемпотентно: второй прогон ничего не
    меняет."""
    from rusterm.parsers import CompanyFactsParser

    result = RebasisResult()
    parser = CompanyFactsParser()
    for sha in repos.fact.companyfacts_sources():
        try:
            raw = repos.raw.get(sha)
        except (OSError, ValueError) as exc:
            result.unreadable.append(f"{sha[:12]}: {type(exc).__name__}")
            continue
        parsed = parser.parse(raw, {"source_ref": sha})
        stored = repos.fact.basis_by_pointer(sha)
        changes = []
        for fact in parsed.facts:
            pointer = fact.get("locator", {}).get("json_pointer")
            result.facts_checked += 1
            if pointer not in stored:
                result.unmatched += 1
                continue
            fact_id, basis = stored[pointer]
            if basis != fact["basis"]:
                changes.append((fact_id, fact["basis"]))
                if fact["basis"] == "as_reported":
                    result.to_as_reported += 1
                else:
                    result.to_restated += 1
        result.changed += repos.fact.update_basis(changes)
        result.objects += 1
    return result
