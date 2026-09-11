"""Назначение №1 из трёх (TASK-7 T13): logs/app.log.

Ротация по размеру 5 × 1 МБ. Аудит пользователя сюда не пишется —
он в logs/audit.jsonl и дублируется только туда и в базу; манифесты
сырья живут в raw/manifests и этим модулем не трогаются.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_LOG_MAX_BYTES = 1_000_000
APP_LOG_BACKUP_COUNT = 5


def setup_app_logging(app_log_path, max_bytes: int = APP_LOG_MAX_BYTES,
                      backup_count: int = APP_LOG_BACKUP_COUNT,
                      level: int = logging.INFO) -> logging.Logger:
    """Идемпотентно настроить журнал приложения «rusterm»."""
    logger = logging.getLogger("rusterm")
    logger.setLevel(level)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    path = Path(app_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=max_bytes,
                                  backupCount=backup_count,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger
