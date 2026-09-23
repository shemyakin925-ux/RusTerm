"""Пути и структура каталога данных по ADR-0003.

Единственный источник правды о том, где лежит что. Все остальные модули
берут пути отсюда, а не собирают сами — иначе перенос каталога превратится
в охоту.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Все абсолютные пути приложения, выведенные из корня."""

    root: Path
    db_path: Path
    raw_store: Path
    raw_manifests: Path
    raw_index_by2: Path  # raw/store/<2>/<sha256>
    exports: Path
    logs: Path
    config_path: Path

    @classmethod
    def from_root(cls, root: os.PathLike | str) -> "AppPaths":
        r = Path(root).resolve()
        return cls(
            root=r,
            db_path=r / "rusterm.db",
            raw_store=r / "raw" / "store",
            raw_manifests=r / "raw" / "manifests",
            raw_index_by2=r / "raw" / "store",  # фактически тот же каталог
            exports=r / "exports",
            logs=r / "logs",
            config_path=r / "config.toml",
        )

    @property
    def app_log_path(self) -> Path:
        """logs/app.log — приложение, ротация 5 × 1 МБ (TASK-7 T13)."""
        return self.logs / "app.log"

    @property
    def audit_log_path(self) -> Path:
        """logs/audit.jsonl — операции пользователя, только добавление,
        переживает потерю базы; ротация как у app.log (B24)."""
        return self.logs / "audit.jsonl"


def ensure_app_dir(paths: AppPaths) -> AppPaths:
    """Идемпотентно создаёт структуру каталога. Возвращает те же paths.

    Существующие файлы не трогает. Права не меняет. Никаких секретов
    не пишет.
    """
    for p in (
        paths.root,
        paths.raw_store,
        paths.raw_manifests,
        paths.exports,
        paths.logs,
    ):
        p.mkdir(parents=True, exist_ok=True)
    return paths


def resolve_root(explicit=None) -> tuple[Path, int]:
    """Каталог данных: один порядок для всех дверей (ТЗ-90 A5).

    | правило | откуда |
    |---|---|
    | 1 | явно заданный `--root` (или корень, который выбрало окно) |
    | 2 | `RUSTERM_DATA` — окружение или `~/.rusterm.env` (пишет load_env) |
    | 3 | `./rusterm.db` есть — текущий каталог |
    | 4 | `~/.rusterm` |

    Возвращает `(путь, номер правила)`: номер нужен наружу — `status` и
    шапка окна печатают, каким правилом получили каталог, иначе
    «открылось не то» невозможно отличить от «там нет данных». Прежний
    порядок расходился: CLI по умолчанию молчал про `.` (правило 3), а
    окно и `.app` из Finder смотрели только 2 и 4 — `rusterm add` в
    каталоге проекта и `rusterm desktop` из него же открывали две разные
    базы.

    Правила 2 и 4 не зависят от рабочего каталога; правило 3 зависит —
    это и есть смысл «база лежит рядом с проектом».
    """
    if explicit:
        return Path(explicit), 1
    env = os.environ.get("RUSTERM_DATA")
    if env:
        return Path(env), 2
    if Path("rusterm.db").exists():
        return Path("."), 3
    return Path.home() / ".rusterm", 4
