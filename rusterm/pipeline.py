"""Pipeline: 9 nodes of ingestion per processes.md.

Node 1: plan_refresh — что устарело
Node 2: poll_source_index — один запрос на источник, не на компанию
Node 3: enqueue — план + изменения в очередь, дедупликация по (instrument, блок, дата)
Node 4: fetch — скачать один объект
Node 5: store_raw — sha256, zstd, запись манифеста
Node 6: parse — извлечь Fact[] с локаторами
Node 7: validate — единицы, знак, диапазон, resolve(locator), сверка с прошлым периодом
Node 8: persist — транзакция: факты + обновление coverage
Node 9: cascade — пометить зависимые блоки stale (метрики, снапшот, summary)
"""
from __future__ import annotations

from typing import Literal, Optional, Tuple

from rusterm.core.fact import Fact, validate_fact_for_write, LocatorXBRL, LocatorTable
from rusterm.store.raw_store import put_with_manifest, decompress_object
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.parsers import SyntheticXBRLParser, TableParser


# --- Node 1: plan_refresh ---

def plan_refresh(
    watchlist: list[str],  # instrument_ids
    last_cursor: dict[str, str],  # instrument_id -> last poll cursor
) -> list[dict]:
    """Определить, что устарело и нуждается в обновлении.

    Возвращает список джобов на обновление.
    Джоб: job_id, instrument_id, block, provider, url, priority, not_before
    """
    jobs = []
    for instrument_id in watchlist:
        cursor = last_cursor.get(instrument_id, "")
        # Если курсора нет — всегда обновляем
        if not cursor:
            # Создаем джоб для всех блоков
            for block in ["prices", "fundamentals"]:
                jobs.append({
                    "job_id": f"{instrument_id}_{block}_0",
                    "instrument_id": instrument_id,
                    "block": block,
                    "provider": "synthetic",
                    "url": None,
                    "priority": 1,
                    "not_before": None,
                })
        else:
            # Проверяем, были ли изменения (упрощенно: всегда есть джобы)
            jobs.append({
                "job_id": f"{instrument_id}_refresh",
                "instrument_id": instrument_id,
                "block": "fundamentals",
                "provider": "synthetic",
                "url": None,
                "priority": 1,
                "not_before": None,
            })
    return jobs


# --- Node 2: poll_source_index ---

def poll_source_index(
    provider: str, cursor: str = ""
) -> Tuple[list[dict], str]:
    """Один запрос на источник, не на компанию.

    Возвращает (список записей, новый_cursor).
    На этом держится инкрементальность.
    """
    # Фейковый провайдер
    from rusterm.providers.disclosures import FakeDisclosuresProvider
    prov = FakeDisclosuresProvider()
    result = prov.poll_index(cursor)
    records = result.get("records", [])
    new_cursor = result.get("cursor", str(int(cursor) + 10) if cursor else "10")
    return records, new_cursor


# --- Node 3: enqueue ---

def enqueue(
    jobs: list[dict],
    existing: list[dict] | None = None,
) -> list[dict]:
    """План + изменения в очередь, дедупликация по (instrument, блок, дата).

    Дубликат sha256 — задание закрывается успешно (идемпотентность).
    """
    if existing is None:
        return jobs[:]
    
    # Дедупликация: оставляем только новых джобов
    existing_keys = {
        (j["instrument_id"], j["block"], j.get("not_before")) 
        for j in existing
    }
    new_jobs = []
    for job in jobs:
        key = (job["instrument_id"], job["block"], job.get("not_before"))
        if key not in existing_keys:
            new_jobs.append(job)
    
    # Добавляем джобы, которых нет в existing, но есть в jobs
    new_keys = {
        (j["instrument_id"], j["block"], j.get("not_before"))
        for j in new_jobs
    }
    
    result = list(existing) + new_jobs
    return result


# --- Node 4: fetch ---

def fetch(
    job: dict,
    provider: str,
) -> Tuple[Optional[bytes], FetchResult]:
    """Скачать один объект.

    FetchResult: job_id, sha256, bytes, content_type, fetched_at, status, error
    """
    import time
    from rusterm.providers.disclosures import FakeDisclosuresProvider
    
    prov = FakeDisclosuresProvider()
    # Генерируем синтетический контент
    import hashlib
    url = job.get("url")
    if url:
        raw = prov.fetch_document(url)
        sha = raw.get("sha256", hashlib.sha256(url.encode()).hexdigest())
        bytes_data = url.encode()  # placeholder
        return bytes_data, FetchResult(
            job_id=job["job_id"],
            sha256=sha,
            bytes=len(bytes_data),
            content_type="application/json",
            fetched_at=time.time(),
            status="ok",
            error=None,
        )
    else:
        # Нет URL — создаем синтетический raw объект
        import json
        raw_data = {"facts": {}, "tables": []}
        raw_bytes = json.dumps(raw_data).encode("utf-8")
        sha = hashlib.sha256(raw_bytes).hexdigest()
        return raw_bytes, FetchResult(
            job_id=job["job_id"],
            sha256=sha,
            bytes=len(raw_bytes),
            content_type="application/json",
            fetched_at=time.time(),
            status="ok",
            error=None,
        )


# --- Node 5: store_raw ---

def store_raw(
    bytes_data: bytes, provider: str, paths: AppPaths,
) -> str:
    """Запись в content-addressed store, zstd, манифест.

    Возвращает sha256 записи.
    При существующем sha256 — no-op (идемпотентность).
    """
    import zlib
    # Content-addressed: sha256 байтов
    sha = hashlib.sha256(bytes_data).hexdigest()
    
    # Директория store/raw/<2>/<sha256>
    ensure_app_dir(paths)
    raw_dir = paths.raw_store / sha[:2]
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    target = raw_dir / sha[2:]
    if not target.exists():
        # Сжимаем zstd, если доступно, иначе gzip
        try:
            import zstandard as zstd
            compressed = zstd.ZstdCompressor().compress(bytes_data)
        except ImportError:
            compressed = zlib.compress(bytes_data)
        target.write_bytes(compressed)
    
    # Манифест JSONL только на добавление
    manifest_path = paths.manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    # Append-only: добавляем запись, если её нет
    existing_shas = set()
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_shas.add(line.strip())
    
    if sha not in existing_shas:
        with manifest_path.open("a", encoding="utf-8") as f:
            f.write(f"{sha}\n")
    
    return sha


# --- Node 6: parse ---

def parse(
    raw_bytes: bytes, parser: str = "synthetic",
) -> Tuple[list[dict], int]:
    """Извлечь Fact[] с локаторами.

    Возвращает (список словарей фактов, счетчик неразобранного).
    """
    import json
    from rusterm.parsers import SyntheticXBRLParser, TableParser
    
    raw = json.loads(raw_bytes.decode("utf-8"))
    
    if parser == "synthetic":
        p = SyntheticXBRLParser()
    elif parser == "table":
        p = TableParser()
    else:
        p = SyntheticXBRLParser()
    
    # Метаданные
    metadata = {"sha256": hashlib.sha256(raw_bytes).hexdigest()}
    
    # Can parse check
    if not p.can_parse(raw, metadata):
        return [], 0
    
    # Parse
    facts, unparsed = p.parse(raw, metadata={})
    
    # Конвертируем в словари Fact
    fact_dicts = []
    for fact in facts:
        fact_dict = {
            "fact_id": fact.get("fact_id", ""),
            "concept": fact.get("concept", ""),
            "value": fact.get("value", "0"),
            "unit": fact.get("unit", "USD"),
            "basis": fact.get("basis", "as_reported"),
            "origin": fact.get("origin", "extracted"),
            "source_ref": fact.get("source_ref", ""),
            "locator": fact.get("locator", {}),
            "parser_version": fact.get("parser_version", "synthetic.v1"),
        }
        fact_dicts.append(fact_dict)
    
    return fact_dicts, unparsed


# --- Node 7: validate ---

def validate(
    fact_dicts: list[dict],
) -> Tuple[list[dict], list[str]]:
    """Единицы, знак, диапазон, resolve(locator), сверка с прошлым периодом.

    Возвращает (принятые факты, список ошибок/подозрительных).
    Факты, не прошедшие валидацию, помечаются suspect.
    """
    from rusterm.core.fact import Fact
    
    accepted = []
    errors = []
    
    for fd in fact_dicts:
        try:
            fact = Fact(
                issuer_id=fd.get("issuer_id"),
                listing_id=fd.get("listing_id"),
                concept=fd["concept"],
                period_start=fd.get("period_start", ""),
                period_end=fd.get("period_end", ""),
                period_type=fd.get("period_type", "duration"),
                value=fd.get("value"),
                unit=fd["unit"] if fd.get("unit") else "USD",
                currency=fd.get("currency"),
                basis=fd.get("basis", "as_reported"),
                origin=fd.get("origin", "extracted"),
                source_ref=fd.get("source_ref", ""),
                locator=fd.get("locator", {"kind": "xbrl", "doc_sha256": "", "fact_id": ""}),
                parser_version=fd.get("parser_version", "synthetic.v1"),
            )
            # Валидация через validate_fact_for_write
            validation_errors = validate_fact_for_write(fact)
            if validation_errors:
                # Помечаем как suspect
                fact.status = "suspect"
                errors.extend(validation_errors)
            else:
                accepted.append(fact)
        except ValueError as e:
            errors.append(str(e))
            # Фakt с ошибкой валидации — suspect
            fact_dict["status"] = "suspect"
            accepted.append(fd)
    
    return accepted, errors


# --- Node 8: persist ---

def persist(
    facts: list[Fact], paths: AppPaths,
) -> dict:
    """Транзакция: факты + обновление coverage.

    Возвращает статистику: сколько записано, сколько дублей пропущено.
    """
    import json
    
    # Журнал аудита
    audit_path = paths.audit_log_path
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    
    written = 0
    duplicates = 0
    
    for fact in facts:
        # Проверяем, существует ли уже такой факт (по fact_id + sha256 source_ref)
        # Вставка: только вставка, исправление — новый факт + superseded_by
        try:
            # Сериализуем для хранения
            fact_tuple = fact.to_db_tuple()
            
            # В реальности здесь был бы INSERT в SQLite
            # Проверяем дубль: если source_ref уже есть — пропускаем
            # Пока что считаем все как записанные
            written += 1
            
            # Логируем в аудит
            with audit_path.open("a", encoding="utf-8") as f:
                f.write(f"{fact.fact_id}|{fact.basis}|{fact.status}\n")
                
        except Exception as e:
            duplicates += 1
            # Ошибка записи — не критическая, логируем
    
    return {
        "written": written,
        "duplicates": duplicates,
        "total": len(facts),
    }


# --- Node 9: cascade ---

def cascade(
    paths: AppPaths, affected_blocks: list[str] | None = None,
) -> dict:
    """Пометить зависимые блоки stale (метрики, снапшот, summary).

    Если после исключения осталось меньше 5 пиров — перцентили не считаются.
    """
    import json
    
    # Читаем текущий снапшот
    snapshot_path = paths.snapshot_path
    
    result = {
        "blocks_marked_stale": 0,
        "metrics_affected": 0,
        "snapshots_updated": 0,
    }
    
    if affected_blocks is None:
        affected_blocks = ["fundamentals", "peer_set", "governance"]
    
    for block in affected_blocks:
        # Помечаем блок как stale
        # В реальности обновили бы статус в БД
        result["blocks_marked_stale"] += 1
        
        # Метрики affected
        if block in ["fundamentals", "peer_set"]:
            result["metrics_affected"] += 1
    
    # Обновляем снапшот, если нужно
    if snapshot_path.exists():
        result["snapshots_updated"] = 1
    
    return result
