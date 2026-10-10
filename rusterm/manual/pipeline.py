"""Конвейер ручного импорта (ADR-0011, ТЗ-20 L6): ① extract ->
② records -> ③ verify -> хранение. SQL здесь не пишется — только
репозитории store (проверка 7); сеть не трогается — клиент приходит
снаружи (llm_api).

Правила хранения:
- документ идемпотентен по sha256: повторный импорт того же файла не
  плодит строк (проверка заголовка до вызова модели -> исход replay,
  счётчики берутся из counts());
- ключа модели нет -> ConfigError после ① (ступень ② не выполняется,
  ничего не пишется);
- неудача ступени ② (429, таймаут, битый ответ) не оставляет ничего:
  строка `document` и байты в raw-хранилище появляются только после
  успешного разбора записей (ТЗ-92 C3) — иначе повтор файла навечно
  получает replay с нулём записей, а doctor считает строки без файла;
- verified=yes -> факт: source_kind='manual', origin='manual',
  locator sha256:<hash>#page=<N>, source_ref = сам документ в
  raw-хранилище (FK fact.source_ref честно указывает на байты);
- verified=yes к тому же получает форму (ТЗ-92 C4, manual/shape.py):
  канонический концепт из карты денег словаря, значение-число с
  масштабом единицы, валюту и фискальный год эмитента. Без этого шага
  ручной факт не доходил ни до одной меры: `as_reported_facts`
  фильтрует по `canonical_concept IN (...)`, а он был NULL у всех.
  Ничего не переопределяется и не удаляется: не отображённая строка
  остаётся ровно такой, какой лежала (NULL + значение дословно);
- verified=no -> запись сохраняется и помечается (manual_extraction,
  verified=0), а факта не получает: в меры снапшота она попасть не
  может по построению, видна в карточке источника (counts) и в
  выгрузке полосы L9; причина покрытия — manual_unverified;
- ручной факт никогда не перезаписывает машинный: разные source_kind,
  запись только добавлением.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from ..providers.base import ProviderError
from ..providers.budget import BudgetExceeded, ConfigError
from ..providers.llm_api import LlmApiClient
from ..store.repos import (DocumentRepo, FactRepo, InstrumentRepo,
                           ManualExtractionRepo, RawRepo)
from . import NEAR_MISS, VERIFIED, verify_status
from .extract import extract_text
from .records import (PROMPT_VERSION, build_prompt, is_year_like,
                      parse_records, period_bounds)
from .shape import shape_record


@dataclass(frozen=True)
class ImportOutcome:
    document_sha: str
    filename: str
    replay: bool
    records_total: int
    dropped_no_quote: int
    dropped_bad_category: int
    dropped_bad_shape: int
    records_verified: int
    records_unverified: int
    facts_stored: int
    model: str
    prompt_version: str
    records_near_miss: int = 0
    # ТЗ-92 C4: сколько проверенных записей получило канонический
    # концепт. Replay и dry-run дают 0 — формы они не касаются (счётчики
    # повтора берутся из manual_extraction, где canonical не хранится).
    records_mapped: int = 0


def import_document(conn, paths, file_path, issuer_id: str,
                    client,
                    dry_run: bool = False):
    """Провести файл через ①-②-③ и сохранить исход.

    client — готовый LlmApiClient ИЛИ ConfigError('llm_key_unset'):
    без ключа конвейер останавливается после ①, ничего не пишя.
    dry_run — только ①: исход извлечения печатается, ничего не пишется
    (BACKLOG B21). Возвращает ImportOutcome или ошибку значением.
    """
    extracted = extract_text(file_path)
    if isinstance(extracted, ProviderError):
        return extracted
    if dry_run:
        return ImportOutcome(
            document_sha=extracted.sha256, filename=extracted.filename,
            replay=False, records_total=0, dropped_no_quote=0,
            dropped_bad_category=0, dropped_bad_shape=0,
            records_verified=0, records_unverified=0,
            records_near_miss=0, facts_stored=0,
            model="dry-run", prompt_version="dry-run")
    if isinstance(client, ProviderError) or isinstance(client, ConfigError):
        # ① выполнено; ② без ключа не выполняется, ничего не пишем
        return client

    def _replay():
        counts = ManualExtractionRepo(conn).counts(extracted.sha256)
        return ImportOutcome(
            document_sha=extracted.sha256, filename=extracted.filename,
            replay=True,
            records_total=counts["total"],
            dropped_no_quote=0, dropped_bad_category=0,
            dropped_bad_shape=0,
            records_verified=counts["verified"],
            records_unverified=counts["unverified"],
            records_near_miss=0,
            facts_stored=0, model=client.model,
            prompt_version=PROMPT_VERSION)

    documents = DocumentRepo(conn)
    # ТЗ-92 C3: повтор замыкается на ЧТЕНИИ заголовка, а не на попытке
    # вставить — иначе проверка «уже импортировано» неотделима от записи.
    if documents.get(extracted.sha256) is not None:
        return _replay()

    try:
        raw_answer = client.complete(build_prompt(extracted.pages))
    except Exception as e:  # транспорт мог бросить (URLError и т.п.)
        return ProviderError(reason=f"llm_failed:{type(e).__name__}")
    if isinstance(raw_answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
        return raw_answer
    parsed = parse_records(raw_answer)
    if isinstance(parsed, ProviderError):
        return parsed

    # ТЗ-92 C3: заголовок и байты — только когда ② разобрано. Байты
    # первыми: падение посередине оставляет raw без строки, и повтор это
    # чинит (insert документа + ON CONFLICT DO NOTHING), тогда как строка
    # без байтов блокировала бы повтор навсегда — это и есть баг C3.
    RawRepo(paths, conn).put(Path(file_path).read_bytes(),
                             provider="manual-import", block="manual",
                             url=extracted.filename, instrument_id=None)
    if documents.put(extracted.sha256, extracted.filename,
                     extracted.format, len(extracted.pages),
                     extracted.byte_len, issuer_id=issuer_id) is False:
        return _replay()

    extractions = ManualExtractionRepo(conn)
    facts = FactRepo(conn)
    # ТЗ-92 C4: календарь и валюта эмитента нужны ДО разбора записей —
    # «FY2025» без fye эмитента был бы январём–декабрём, а «$m» без
    # валюты реестра не имел бы ни валюты, ни её кода в unit.
    issuer = InstrumentRepo(conn).get_issuer(issuer_id)
    fye = issuer.fiscal_year_end if issuer is not None else None
    issuer_currency = (issuer.reporting_currency
                       if issuer is not None else None)
    verified_count = unverified_count = facts_stored = 0
    mapped_count = 0
    near_miss_count = 0
    for record in parsed.records:
        status = verify_status(record, extracted)
        ok = status == VERIFIED
        if status == NEAR_MISS:
            near_miss_count += 1
        extractions.add(
            document_sha256=extracted.sha256, page_no=record.page_no,
            category=record.category, metric=record.metric,
            value=record.value, unit=record.unit, period=record.period,
            quote=record.quote, verified=ok, model=client.model,
            prompt_version=PROMPT_VERSION)
        if ok:
            verified_count += 1
            shape = shape_record(record, issuer_currency)
            period_start, period_end, period_type = \
                period_bounds(record.period, fye)
            locator = f"sha256:{extracted.sha256}#page={record.page_no}"
            if is_year_like(record.period):
                # какой календарь дал границы — часть факта, а не догадка
                locator += f"#fy={fye or 'calendar'}"
            facts.insert_fact(
                fact_id=str(uuid.uuid4()), issuer_id=issuer_id,
                listing_id=None, concept=record.metric,
                period_start=period_start, period_end=period_end,
                period_type=period_type, value=shape.value,
                unit=shape.unit, currency=shape.currency,
                basis="as_reported",
                origin="manual", source_ref=extracted.sha256,
                locator={"locator": locator},
                parser_version=f"manual:{client.model}:"
                               f"{PROMPT_VERSION}",
                status="ok", source_kind="manual",
                canonical_concept=shape.canonical,
                concept_map_version=shape.map_version)
            facts_stored += 1
            if shape.canonical:
                mapped_count += 1
        else:
            unverified_count += 1
    return ImportOutcome(
        document_sha=extracted.sha256, filename=extracted.filename,
        replay=False,
        records_total=len(parsed.records),
        dropped_no_quote=parsed.dropped_no_quote,
        dropped_bad_category=parsed.dropped_bad_category,
        dropped_bad_shape=parsed.dropped_bad_shape,
        records_verified=verified_count,
        records_unverified=unverified_count,
        records_near_miss=near_miss_count,
        facts_stored=facts_stored, model=client.model,
        prompt_version=PROMPT_VERSION,
        records_mapped=mapped_count)


__all__ = ["import_document", "ImportOutcome"]
