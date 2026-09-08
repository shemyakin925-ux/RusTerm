"""doctor: самопроверка установки (И13, TASK-2).

Проверяет то, что не видно без базы: версию схемы, соответствие манифеста
и файлов в store, осиротевшие ссылки фактов на сырьё и мер без lineage.
SQL живёт здесь, в слое хранилища; CLI только показывает результат.
"""
from __future__ import annotations

from typing import Optional

from .db import _SCHEMA_VERSION
from .paths import AppPaths
from .raw_store import iter_manifest_entries, object_path


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

    return {
        "ok": not problems,
        "problems": problems,
        "schema_version": applied,
        "manifest_entries": manifest_entries,
        "env": env_info,
        "unmapped_concepts": {"count": unmapped_count,
                              "top": unmapped_top},
    }
