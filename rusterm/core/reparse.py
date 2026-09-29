"""Повторный разбор уже скачанных companyfacts: пересобрать факты и
выровнять basis.

Зачем (координатор, 24.09.2026; вердикт ТЗ-97 Q12 (6)). Регрессия ТЗ-78
Y2: с тех пор как CompanyFactsParser разбирает раздел ``dei``, дата
обложки сдвигала «конец периода подачи», и каждый финансовый факт подачи
записывался ``restated``. Снапшот берёт только ``as_reported`` — у
половины реальных американских эмитентов считались 4 меры из 28 и меньше.

Починка разборщика не лечит уже сохранённое: сбор пропускает ответ,
который лежит в хранилище (дедупликация по sha256). Первый вариант этого
модуля правил у сохранённых фактов ТОЛЬКО basis — то есть недостающие
строки не дописывал нигде, — и обходил объекты, из которых не разобрано
ни одного факта. Состояние «сырьё скачано до починки, новых фактов в базе
нет» оставалось навсегда: в копии базы пользователя (замер 26.09) у семи
сохранённых companyfacts из 44 не было ни одной dei-строки, и у шести из
них раздел dei в самом сыре есть (у TECK payload его не содержит); 54 меры
отказывали ``missing_data: shares_outstanding`` у четырёх бумаг (KSPI,
TECK, VALE, VZ — по две на бумагу в каждой версии снапшота).

Теперь прогон делает обе вещи одним движением: недостающие факты
довставляются нынешним разборщиком через те же двери, что и сбор
(``apply_concept_map`` + ``persist_ingestion_results``), а у имеющихся
выравнивается basis. Значения, периоды, происхождение и вытеснение
сохранённых строк не трогаются; сеть не нужна — 0 запросов.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReparseResult:
    objects: int = 0          # объектов пересобрано
    facts_checked: int = 0
    changed: int = 0          # basis выровнен
    to_as_reported: int = 0
    to_restated: int = 0
    added: int = 0            # фактов, которых в базе не было
    unmapped: int = 0         # из них — вне карты концептов
    ownerless: int = 0        # объектов без инструмента-владельца
    unlocatable: int = 0      # объектов, чьи строки не несут указателей
    unreadable: list = field(default_factory=list)


def rebuild_companyfacts(repos) -> ReparseResult:
    """Пройти все сохранённые companyfacts нынешним CompanyFactsParser:
    чего в базе нет — дописать, что есть — выровнять по basis, у каждого
    пройденного эмитента перевыбрать `reporting_currency` (ТЗ-104 P2).
    Идемпотентно: второй прогон не добавляет ни строки и ничего не
    меняет — в том числе и валюту подачи, потому что она то же число."""
    import uuid as _uuid

    from rusterm.parsers import CompanyFactsParser
    from rusterm.pipeline import apply_concept_map
    from rusterm.store.repos import (persist_ingestion_results,
                                     refresh_reporting_currency)

    result = ReparseResult()
    parser = CompanyFactsParser()
    walked = []
    for row in repos.fact.companyfacts_objects():
        sha, instrument_id = row[0], row[1]
        instrument = (repos.instrument.get_instrument(instrument_id)
                      if instrument_id else None)
        issuer_id = instrument.issuer_id if instrument else None
        if not issuer_id:
            # Факту некому принадлежать: вставка без эмитента создала бы
            # строку, которую ни один снапшот не прочитает. Молча не
            # проходит — считается и называется в выводе.
            result.ownerless += 1
            continue
        try:
            raw = repos.raw.get(sha)
        except (OSError, ValueError) as exc:
            result.unreadable.append(f"{sha[:12]}: {type(exc).__name__}")
            continue
        parsed = parser.parse(raw, {"issuer_id": issuer_id,
                                    "source_ref": sha})
        stored = repos.fact.basis_by_pointer(sha)
        if not stored and repos.fact.count_for_source(sha):
            # Строки этого объекта есть, но ни в одной нет json_pointer:
            # сверить «что уже разобрано» нечем, и прогон удвоил бы каждую
            # из них. Это не повод молчать — считается.
            result.unlocatable += 1
            continue
        changes = []
        fresh = []
        for fact in parsed.facts:
            pointer = fact.get("locator", {}).get("json_pointer")
            result.facts_checked += 1
            if pointer not in stored:
                fresh.append(dict(fact))
                continue
            fact_id, basis = stored[pointer]
            if basis != fact["basis"]:
                changes.append((fact_id, fact["basis"]))
                if fact["basis"] == "as_reported":
                    result.to_as_reported += 1
                else:
                    result.to_restated += 1
        if fresh:
            for fact in fresh:
                fact["fact_id"] = str(_uuid.uuid4())
                result.unmapped += apply_concept_map(fact)
            # Одна транзакция на объект (те же двери, что у сбора):
            # сбой на середине не оставляет половину фактов.
            persist_ingestion_results(repos.conn, fresh, [])
            result.added += len(fresh)
        result.changed += repos.fact.update_basis(changes)
        result.objects += 1
        if issuer_id not in walked:
            walked.append(issuer_id)
    # Валюта подачи пересчитывается для каждого пройденного эмитента, а
    # не только там, где дописали факты: на базе, разобранной прежним
    # разборщиком, fresh пуст и persist бы не вызвался.
    for issuer_id in walked:
        refresh_reporting_currency(repos.conn, issuer_id)
    return result
