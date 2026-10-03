"""Общая дверца к записанным ответам EDGAR (ТЗ-97 Q2).

Стадия `ingest --source ownership` тянет тела Forms 3/4/5 с Archives по
каноническому URL. Офлайн-тесты, которые проводят обычный путь
(`rusterm follow`), обязаны отвечать на них с диска: один транспорт на
каждый модуль означал бы, что четвёртый тест путь не проходит, а третий
отстаёт от первого молча.

Нет записи — None, то есть честный 404: заглушку вместо тела здесь
писать нельзя, иначе разбор проверялся бы на выдуманном XML.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "tests" / "data" / "edgar"


def ownership_body(url: str) -> bytes | None:
    """Тело формы владения по URL Archives.

    Имя файла в записи = accession без дефисов + имя первичного
    документа (`000114036126035362_form4.xml`), как его получает
    `EdgarProvider.raw_document_url` из ленты.
    """
    parts = url.split("/")
    if len(parts) < 2:
        return None
    name = (f"{parts[-2].replace('-', '')}_"
            f"{parts[-1].removesuffix('.xml')}.xml")
    path = DATA / "ownership" / name
    return path.read_bytes() if path.exists() else None
