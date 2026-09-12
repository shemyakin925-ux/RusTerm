"""Конвейер ручного импорта (ADR-0011, ТЗ-20 L6): ① extract ->
② records -> ③ verify -> хранение. SQL здесь не пишется — только
репозитории store (проверка 7); сеть не трогается — клиент приходит
снаружи (llm_api).

Правила хранения:
- документ идемпотентен по sha256: повторный импорт того же файла не
  плодит строк (DocumentRepo.put -> False -> исход replay, счётчики
  берутся из counts());
- ключа модели нет -> ConfigError после ① (ступень ② не выполняется,
  ничего не пишется);
- verified=yes -> факт: source_kind='manual', origin='manual',
  locator sha256:<hash>#page=<N>, source_ref = сам документ в
  raw-хранилище (FK fact.source_ref честно указывает на байты);
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
from ..store.repos import (DocumentRepo, FactRepo, ManualExtractionRepo,
                           RawRepo)
from . import NEAR_MISS, VERIFIED, verify_status
from .extract import extract_text
from .records import PROMPT_VERSION, build_prompt, parse_records, \
    period_bounds


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

    documents = DocumentRepo(conn)
    if documents.put(extracted.sha256, extracted.filename,
                     extracted.format, len(extracted.pages),
                     extracted.byte_len, issuer_id=issuer_id) is False:
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

    try:
        raw_answer = client.complete(build_prompt(extracted.pages))
    except Exception as e:  # транспорт мог бросить (URLError и т.п.)
        return ProviderError(reason=f"llm_failed:{type(e).__name__}")
    if isinstance(raw_answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
        return raw_answer
    # тело документа попадает в raw-хранилище: FK fact.source_ref
    # честно указывает на байты; sha256 документа == sha256 объекта
    raw_repo = RawRepo(paths, conn)
    raw_repo.put(Path(file_path).read_bytes(), provider="manual-import",
                 block="manual", url=extracted.filename,
                 instrument_id=None)
    parsed = parse_records(raw_answer)
    if isinstance(parsed, ProviderError):
        return parsed

    extractions = ManualExtractionRepo(conn)
    facts = FactRepo(conn)
    verified_count = unverified_count = facts_stored = 0
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
            period_start, period_end, period_type = \
                period_bounds(record.period)
            facts.insert_fact(
                fact_id=str(uuid.uuid4()), issuer_id=issuer_id,
                listing_id=None, concept=record.metric,
                period_start=period_start, period_end=period_end,
                period_type=period_type, value=record.value,
                unit=record.unit, currency=None, basis="as_reported",
                origin="manual", source_ref=extracted.sha256,
                locator={"locator":
                         f"sha256:{extracted.sha256}"
                         f"#page={record.page_no}"},
                parser_version=f"manual:{client.model}:"
                               f"{PROMPT_VERSION}",
                status="ok", source_kind="manual")
            facts_stored += 1
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
        facts_stored=facts_stored, model=client.model,
        prompt_version=PROMPT_VERSION)


__all__ = ["import_document", "ImportOutcome"]
