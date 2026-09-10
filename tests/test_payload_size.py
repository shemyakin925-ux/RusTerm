"""BACKLOG B25: размер записанного payload — страж-тест, а не строка
отчёта. Любой файл под tests/data/ (обрезанные payload провайдеров и
golden-файлы) обязан умещаться в 256 КБ: тест провалится на первом же
файле-переростке и назовет его.
"""
from __future__ import annotations

from pathlib import Path

MAX_PAYLOAD_BYTES = 256 * 1024
DATA_DIR = Path(__file__).resolve().parent / "data"


def test_no_recorded_payload_exceeds_256_kb():
    assert DATA_DIR.is_dir()
    offenders = [
        (p, p.stat().st_size)
        for p in sorted(DATA_DIR.rglob("*"))
        if p.is_file() and p.stat().st_size > MAX_PAYLOAD_BYTES
    ]
    assert not offenders, (
        "payload-переростки (лимит 256 КБ), обрезать:"
        + "; ".join(f"{p.name}={size}B" for p, size in offenders))
