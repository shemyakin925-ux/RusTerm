"""doctor: самопроверка установки (И13, TASK-2).

Проверяет то, что не видно без базы: версию схемы, соответствие манифеста
и файлов в store, осиротевшие ссылки фактов на сырьё и мер без lineage.
SQL живёт здесь, в слое хранилища; CLI только показывает результат.
"""
from __future__ import annotations

from typing import Optional

from .db import _SCHEMA_INDEXES, _SCHEMA_VERSION
from .paths import AppPaths
from .raw_store import iter_manifest_entries, object_path


def _raw_file_exists(raw_store, sha: str) -> bool:
    """Файл объекта лежит в raw-хранилище (любая форма сжатия)."""
    import os as _os
    return any(_os.path.exists(_os.path.join(str(raw_store), sha[:2],
                                             sha + ext))
               for ext in ("", ".gz", ".zst"))


def doctor_report(paths: AppPaths, conn) -> dict:
    """Вернуть отчёт doctor: список проблем и счётчики проверенного."""
    problems: list[str] = []

    # окружение: имена и происхождение, никогда значения (TASK-8 U4)
    from .. import env as env_module
    env_info = env_module.report()
    if env_info["world_readable"]:
        problems.append(
            f"env-файл читается группой/остальными: {env_info['file']}")

    # схема: версия применённая и ожидаемая
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version").fetchone()
        applied = row[0] if row else None
    except Exception:
        applied = None
    if applied != _SCHEMA_VERSION:
        problems.append(f"schema_version={applied}, ожидается {_SCHEMA_VERSION}")

    # без таблиц версии схемы остальные проверки БД бессмысленны
    db_ready = applied == _SCHEMA_VERSION

    # манифест против файлов: запись манифеста обязана иметь файл
    manifest_entries = 0
    missing_files = 0
    try:
        for entry in iter_manifest_entries(paths.raw_manifests):
            manifest_entries += 1
            plain = object_path(paths.raw_store, entry.sha256)
            candidates = [plain,
                          plain.with_suffix(plain.suffix + ".gz"),
                          plain.with_suffix(plain.suffix + ".zst")]
            if not any(p.exists() for p in candidates):
                missing_files += 1
    except FileNotFoundError:
        problems.append("каталог манифестов не существует")
    if missing_files:
        problems.append(f"объектов в манифесте без файла: {missing_files}")

    orphans = 0
    bad_measures = 0
    if db_ready:
        # осиротевшие ссылки: факт на несуществующее сырьё
        orphans = conn.execute(
            """SELECT COUNT(*) FROM fact f
               LEFT JOIN raw_object ro ON ro.sha256 = f.source_ref
               WHERE ro.sha256 IS NULL""").fetchone()[0]
        if orphans:
            problems.append(f"фактов со ссылкой на отсутствующее сырьё: {orphans}")

        # меры без lineage при непустом значении (I4)
        bad_measures = conn.execute(
            """SELECT COUNT(*) FROM measure m
               WHERE m.value IS NOT NULL AND NOT EXISTS (
                     SELECT 1 FROM measure_lineage l
                     WHERE l.measure_id = m.measure_id)""").fetchone()[0]
        if bad_measures:
            problems.append(f"мер с значением, но без lineage: {bad_measures}")

        # осиротевшее состояние сбора: строка без эмитента (TASK-15 C4)
        state_orphans = conn.execute(
            """SELECT COUNT(*) FROM issuer_ingest_state s
               LEFT JOIN issuer i ON i.issuer_id = s.issuer_id
               WHERE i.issuer_id IS NULL""").fetchone()[0]
        if state_orphans:
            problems.append(
                f"строк issuer_ingest_state без эмитента: {state_orphans}")

        # объявленные схемой индексы на месте (TASK-15 C4)
        placeholders = ",".join("?" * len(_SCHEMA_INDEXES))
        present = {r[0] for r in conn.execute(
            f"SELECT name FROM sqlite_master WHERE type='index'"
            f" AND name IN ({placeholders})", _SCHEMA_INDEXES)}
        missing_indexes = sorted(set(_SCHEMA_INDEXES) - present)
        if missing_indexes:
            problems.append("индексов схемы нет в базе: "
                            + ", ".join(missing_indexes))

    # сырьё против базы: дрейф в обе стороны (BACKLOG B9)
    if db_ready:
        # строка raw_object без файла на диске
        import os as _os
        rows = conn.execute("SELECT sha256 FROM raw_object").fetchall()
        no_file = [r[0] for r in rows
                   if not any((_os.path.exists(_os.path.join(
                       str(paths.raw_store), r[0][:2], r[0] + ext)))
                       for ext in ("", ".gz", ".zst"))]
        if no_file:
            problems.append(
                f"строк raw_object без файла: {len(no_file)}")

        # файлы под raw/store без строки в базе
        orphans = []
        for dirpath, _dirs, files in _os.walk(str(paths.raw_store)):
            for fname in files:
                if len(fname) < 64:
                    continue
                sha = fname[:64]
                if not conn.execute(
                        "SELECT 1 FROM raw_object WHERE sha256=?",
                        (sha,)).fetchone():
                    orphans.append(fname)
        if orphans:
            problems.append(
                f"файлов в raw/store без строки в базе: {len(orphans)}")

    # факты без канонического концепта: как следующая дыра в карте
    # находится без чтения кода (TASK-9 V6). Имена тегов и счётчики —
    # никаких значений.
    unmapped_count = 0
    unmapped_top: list = []
    if db_ready:
        unmapped_count = conn.execute(
            "SELECT COUNT(*) FROM fact WHERE canonical_concept IS NULL"
        ).fetchone()[0]
        unmapped_top = [
            {"tag": tag, "count": n} for tag, n in conn.execute(
                """SELECT concept, COUNT(*) AS n FROM fact
                   WHERE canonical_concept IS NULL
                   GROUP BY concept ORDER BY n DESC LIMIT 5""")

        ]

    # счётчики запросов по хостам (BACKLOG B24): последние пробы
    # provider_used_<хост>; потолки добавляет CLI из реестра провайдеров
    request_budget: dict = {}
    documents: dict = {"rows": 0, "rows_without_file": 0,
                       "imported_files_without_row": 0}
    manual_facts_missing_document = 0
    registry: list = []
    market_coverage: dict = {}
    if db_ready:
        rows = conn.execute(
            """SELECT name, provider, value FROM metric_sample
               WHERE name LIKE 'provider_used_%'
               ORDER BY ts""").fetchall()
        for name, provider, value in rows:
            host = name[len("provider_used_"):]
            request_budget[host] = int(value)

        # ── ТЗ-21 H6: документы в обе стороны ──
        # строка document без файла на диске
        for (sha,) in conn.execute("SELECT sha256 FROM document"):
            documents["rows"] += 1
            if not _raw_file_exists(paths.raw_store, sha):
                documents["rows_without_file"] += 1
        if documents["rows_without_file"]:
            problems.append(
                "документов в базе без файла в raw-хранилище: "
                f"{documents['rows_without_file']}")
        # импортированный файл (raw provider='manual-import') без
        # строки document
        documents["imported_files_without_row"] = conn.execute(
            """SELECT COUNT(*) FROM raw_object ro
               WHERE ro.provider = 'manual-import' AND NOT EXISTS (
                     SELECT 1 FROM document d
                     WHERE d.sha256 = ro.sha256)""").fetchone()[0]
        if documents["imported_files_without_row"]:
            problems.append(
                "импортированных файлов без строки document: "
                f"{documents['imported_files_without_row']}")

        # ── ТЗ-21 H6: ручной факт без документа-источника ──
        manual_facts_missing_document = conn.execute(
            """SELECT COUNT(*) FROM fact f
               WHERE f.source_kind = 'manual' AND NOT EXISTS (
                     SELECT 1 FROM document d
                     WHERE d.sha256 = f.source_ref)""").fetchone()[0]
        if manual_facts_missing_document:
            problems.append(
                "ручных фактов без документа-источника: "
                f"{manual_facts_missing_document}")

        # ── ТЗ-21 H6: строки реестра с отсутствующим модулем ──
        import importlib
        from ..markets import MARKETS
        for m in MARKETS:
            try:
                importlib.import_module(
                    f"rusterm.providers.{m.provider}")
                status = "implemented"
            except ModuleNotFoundError as e:
                if e.name in (m.provider,
                              f"rusterm.providers.{m.provider}"):
                    status = "provider_not_implemented"
                    registry.append({"code": m.code,
                                     "provider": m.provider,
                                     "status": status})
                else:
                    raise
        if registry:
            problems.append(
                "рынков с нереализованным провайдером: "
                + ", ".join(f"{r['code']}:{r['provider']}"
                            for r in registry))

        # ── ТЗ-21 H6: покрытие по рынкам ──
        # рынок определяется префиксом instrument_id "<код>-<тикер>"
        # (cmd_add); переопределённый --instrument_id попадает в «—».
        for m in MARKETS:
            prefix = f"{m.code}-%"
            issuers = conn.execute(
                """SELECT COUNT(DISTINCT i.issuer_id) FROM issuer i
                   JOIN instrument ins ON ins.issuer_id = i.issuer_id
                   WHERE ins.instrument_id LIKE ?""",
                (prefix,)).fetchone()[0]
            facts = conn.execute(
                """SELECT COUNT(*) FROM fact f
                   JOIN instrument ins ON ins.issuer_id = f.issuer_id
                   WHERE ins.instrument_id LIKE ?""",
                (prefix,)).fetchone()[0]
            last = conn.execute(
                """SELECT MAX(s.updated_at) FROM issuer_ingest_state s
                   JOIN instrument ins ON ins.issuer_id = s.issuer_id
                   WHERE ins.instrument_id LIKE ?""",
                (prefix,)).fetchone()[0]
            market_coverage[m.code] = {
                "issuers": issuers, "facts": facts,
                "last_collection": last}

    return {
        "ok": not problems,
        "problems": problems,
        "request_budget": request_budget,
        "schema_version": applied,
        "manifest_entries": manifest_entries,
        "env": env_info,
        "unmapped_concepts": {"count": unmapped_count,
                              "top": unmapped_top},
        "documents": documents,
        "manual_facts_missing_document": manual_facts_missing_document,
        "registry_gaps": registry,
        "market_coverage": market_coverage,
    }
