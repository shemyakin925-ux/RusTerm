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
выравнивается basis. Значения, периоды и происхождение сохранённых строк
не трогаются; сеть не нужна — 0 запросов.

ТЗ-92 C1 добавил к прогону третье: разбор теперь отдаёт и проигравших
дедупликации (``ParseResult.all_facts``), поэтому прогон дописывает их
тоже и помечает вытесненными (``superseded_by``) те сохранённые строки,
которыми новое правило их считает. Без этого база, собранная прежним
ключом без basis, осталась бы с одним числом на период навсегда: сбор
пропускает уже скачанный ответ, и оригинал подачи не появился бы ничем.
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
    # ТЗ-92 C1: сколько сохранённых строк прогон помечает вытесненными
    # (новое правило дедупликации считает их проигравшими).
    superseded_marked: int = 0
    # ТЗ-141 D1: локаторов выровнено (дата подачи дописана парсером)
    locators_updated: int = 0
    # ТЗ-108 W4: эмитентов, чьё состояние сбора восстановлено из
    # сохранённого companyfacts (refresh больше не видит «первый сбор»)
    states_restored: int = 0
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
    from rusterm.store.repos import (link_superseded,
                                     persist_ingestion_results,
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
        from rusterm.core.refresh import remember_ingest
        if remember_ingest(repos, issuer_id, raw):
            result.states_restored += 1
        parsed = parser.parse(raw, {"issuer_id": issuer_id,
                                    "source_ref": sha})
        stored = repos.fact.basis_by_pointer(sha)
        stored_locators = repos.fact.locators_by_pointer(sha)
        if not stored and repos.fact.count_for_source(sha):
            # Строки этого объекта есть, но ни в одной нет json_pointer:
            # сверить «что уже разобрано» нечем, и прогон удвоил бы каждую
            # из них. Это не повод молчать — считается.
            result.unlocatable += 1
            continue
        # ТЗ-92 C1: пропущенные строки добираются все, что отдаёт разбор,
        # — и живые факты, и проигравших дедупликации. Прежний прогон
        # смотрел только parsed.facts и потому никогда не лечил базу,
        # собранную правилом без basis.
        live = {f.get("locator", {}).get("json_pointer")
                for f in parsed.facts}
        changes = []
        fresh = []
        fresh_ids: dict = {}
        for fact in parsed.all_facts:
            pointer = fact.get("locator", {}).get("json_pointer")
            if pointer in live:
                result.facts_checked += 1
            if pointer not in stored:
                row = dict(fact)
                row["fact_id"] = str(_uuid.uuid4())
                result.unmapped += apply_concept_map(row)
                fresh_ids[pointer] = row["fact_id"]
                fresh.append(row)
                continue
            fact_id, basis = stored[pointer]
            if pointer in live and basis != fact["basis"]:
                changes.append((fact_id, fact["basis"]))
                if fact["basis"] == "as_reported":
                    result.to_as_reported += 1
                else:
                    result.to_restated += 1
        # ТЗ-141 D1: локатор сохранённой строки выравнивается по
        # нынешнему разбору — парсер дописывает в locator дату подачи
        # (`filed`), база счётчика акций иначе никогда её не увидит.
        # Значение, период, basis и происхождение не трогаются;
        # идемпотентно: второй прогон сравнивает равные.
        locator_changes = []
        for fact in parsed.all_facts:
            pointer = fact.get("locator", {}).get("json_pointer")
            known = stored_locators.get(pointer)
            if not known:
                continue
            fact_id, locator_text = known
            try:
                import json as _json
                stored_locator = _json.loads(locator_text)
            except ValueError:
                continue
            if stored_locator != fact.get("locator"):
                import json as _json
                locator_changes.append((_json.dumps(
                    fact["locator"], ensure_ascii=False,
                    sort_keys=True), fact_id))
        result.locators_updated += repos.fact.update_locators(
            locator_changes)
        # Указатели сохранённых строк — тоже кандидаты в победители:
        # проигравший мог приехать сейчас, а его победитель лежит в базе
        # с прошлого прогона, и наоборот.
        known = {p: fid for p, (fid, _basis) in stored.items()}
        known.update(fresh_ids)
        link_superseded(fresh, known)
        # Из прежнего разбора победитель мог быть записан живым, а новым
        # правилом он проигравший — его помечаем здесь, в базе.
        marks = []
        for loser in parsed.superseded:
            pointer = loser.get("locator", {}).get("json_pointer")
            if pointer in stored:
                winner = known.get(
                    (loser.get("superseded_by_locator") or {})
                    .get("json_pointer"))
                if winner:
                    marks.append((stored[pointer][0], winner))
        if fresh:
            # Одна транзакция на объект (те же двери, что у сбора):
            # сбой на середине не оставляет половину фактов.
            persist_ingestion_results(repos.conn, fresh, [])
            result.added += len(fresh)
        result.changed += repos.fact.update_basis(changes)
        result.superseded_marked += repos.fact.mark_superseded_rows(marks)
        result.objects += 1
        if issuer_id not in walked:
            walked.append(issuer_id)
    # Валюта подачи пересчитывается для каждого пройденного эмитента, а
    # не только там, где дописали факты: на базе, разобранной прежним
    # разборщиком, fresh пуст и persist бы не вызвался.
    for issuer_id in walked:
        refresh_reporting_currency(repos.conn, issuer_id)
    return result
