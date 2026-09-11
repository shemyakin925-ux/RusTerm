"""Ступень ① ручного импорта: файл -> страницы текста (ADR-0011,
ТЗ-20 L5). Реализует контракт TASK-19 F8, интерфейс не меняет.

Формат — по СОДЕРЖИМОМУ файла, не по расширению: %PDF- — pdf,
PK\x03\x04 — контейнер zip (docx: word/document.xml, xlsx:
xl/workbook.xml), иначе текст. Стандартная библиотека: txt, md, csv,
tsv, json, htm, html; библиотечные: pdf (pypdf), docx (python-docx),
xlsx (openpyxl). Библиотеки опциональны: нет пакета —
format_unsupported ЗНАЧЕНИЕМ с именем пакета, не исключение.

Ненадёжный ввод, границы (каждая — значение, не исключение):
- MAX_INPUT_BYTES 256 МБ на файл, MAX_PAGE_CHARS 2 МБ на страницу;
- zip: MAX_ZIP_MEMBERS 4096 членов, MAX_ZIP_UNCOMPRESSED 512 МБ
  суммарно по объявленным размерам — zip-бомба отказывается ДО
  распаковки (объявленные размеры читаются из центрального каталога);
- члены архива НИКОГДА не пишутся на диск по пути из архива — разбор
  в памяти;
- XML: defusedxml, если он есть, иначе xml.etree с отключёнными
  внешними сущностями и запретом DTD (этот выбор фиксируется здесь);
  документ с внешней сущностью — отказ extract_xml_refused;
- DEADLINE_SECONDS 60 на документ: злонамеренно тяжёлый файл —
  extract_timeout, ночь не зависает.
- OCR в проекте нет: pdf без текстового слоя — no_text_layer.

PDF-текст извлекается в layout-режиме pypdf (строки таблицы читаются
поперёк, а не вниз по колонкам) — главный урок прототипа rusconv.
Повторный вызов на том же файле даёт байт-в-байт те же страницы и тот
же sha256 (детерминизм).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree  # noqa: S405 - см. докстринг: DTD/внешние сущности запрещены ниже

from ..providers.base import ProviderError
from . import Document, Page

MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_PAGE_CHARS = 2 * 1024 * 1024
MAX_ZIP_MEMBERS = 4096
MAX_ZIP_UNCOMPRESSED = 512 * 1024 * 1024
DEADLINE_SECONDS = 60.0

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"

try:  # XML-парсер: defusedxml, если есть; иначе stdlib (см. докстринг)
    import defusedxml.ElementTree as _SafeET  # type: ignore

    _XML_PARSER_NAME = "defusedxml"
except ImportError:  # pragma: no cover - defusedxml в этом окружении есть
    _SafeET = ElementTree
    _XML_PARSER_NAME = "xml.etree (DTD и внешние сущности отключены)"


def extract_text(path) -> Document | ProviderError:
    """① контракт (ADR-0011): файл -> Document со страницами."""
    p = Path(path)
    deadline = time.monotonic() + DEADLINE_SECONDS
    try:
        raw = p.read_bytes()
    except OSError as e:
        return ProviderError(reason=f"extract_unreadable:{e.strerror}")
    if len(raw) > MAX_INPUT_BYTES:
        return ProviderError(
            reason=f"extract_too_large:{len(raw)}>{MAX_INPUT_BYTES}")
    sha = hashlib.sha256(raw).hexdigest()

    if raw.startswith(_PDF_MAGIC):
        return _extract_pdf(raw, sha, p.name, deadline)
    if raw.startswith(_ZIP_MAGIC):
        return _extract_zip_container(raw, sha, p.name, deadline)
    return _extract_textish(raw, sha, p.name)


# ── контейнер zip: docx / xlsx / отказ ─────────────────────────────────

def _zip_guard(zf: zipfile.ZipFile) -> ProviderError | None:
    """Потолки по ОБЪЯВЛЕННЫМ размерам из центрального каталога:
    zip-бомба распознаётся до всякой распаковки."""
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_MEMBERS:
        return ProviderError(
            reason=f"extract_zip_bomb:members>{MAX_ZIP_MEMBERS}")
    total = sum(i.file_size for i in infos)
    if total > MAX_ZIP_UNCOMPRESSED:
        return ProviderError(
            reason=f"extract_zip_bomb:uncompressed>{MAX_ZIP_UNCOMPRESSED}")
    return None


def _extract_zip_container(raw: bytes, sha: str, name: str,
                           deadline: float) -> Document | ProviderError:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return ProviderError(reason="format_unsupported:zip_corrupt")
    guard = _zip_guard(zf)
    if guard is not None:
        return guard
    names = set(zf.namelist())
    if "word/document.xml" in names:
        return _extract_docx(raw, sha, name, deadline)
    if "xl/workbook.xml" in names:
        return _extract_xlsx(raw, sha, name, deadline)
    return ProviderError(reason="format_unsupported:unknown_zip_container")


def _parse_xml(data: bytes):
    """defusedxml есть — он; stdlib-фолбэк сам не тянет внешние
    сущности (ParseException на неопределённой сущности — отказ)."""
    return _SafeET.fromstring(data)


def _extract_docx(raw: bytes, sha: str, name: str,
                  deadline: float) -> Document | ProviderError:
    """python-docx, если он есть; иначе format_unsupported:python-docx.
    Разбор — в памяти: контейнер целиком в BytesIO, никакие пути из
    архива на диск не попадают."""
    if _import_docx() is None:
        return ProviderError(reason="format_unsupported:python-docx")
    try:
        import docx  # noqa: PLC0415

        document = docx.Document(io.BytesIO(raw))
    except Exception as e:  # битый/злонамеренный пакет — значение
        return ProviderError(reason=f"extract_docx_refused:{type(e).__name__}")
    lines: list[str] = []
    for paragraph in document.paragraphs:
        if time.monotonic() > deadline:
            return ProviderError(reason="extract_timeout")
        lines.append(paragraph.text)
    for table in document.tables:
        for row in table.rows:
            lines.append("\t".join(cell.text for cell in row.cells))
    text = "\n".join(line for line in lines if line.strip())
    if not text.strip():
        return ProviderError(reason="no_text_layer")
    return Document(sha256=sha, filename=name, format="docx",
                    pages=(Page(page_no=1, text=text),),
                    byte_len=0)


def _extract_xlsx(raw: bytes, sha: str, name: str,
                  deadline: float) -> Document | ProviderError:
    if _import_openpyxl() is None:
        return ProviderError(reason="format_unsupported:openpyxl")
    try:
        import openpyxl  # noqa: PLC0415

        book = openpyxl.load_workbook(
            io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as e:
        return ProviderError(reason=f"extract_xlsx_refused:{type(e).__name__}")
    sheet = book.worksheets[0]
    lines: list[str] = []
    for row in sheet.iter_rows(values_only=True):
        if time.monotonic() > deadline:
            return ProviderError(reason="extract_timeout")
        if row and any(cell is not None for cell in row):
            lines.append("\t".join("" if c is None else str(c)
                                   for c in row))
        if len(lines) > 500_000:
            return ProviderError(reason="extract_too_many_rows")
    text = "\n".join(lines)
    if not text.strip():
        return ProviderError(reason="no_text_layer")
    return Document(sha256=sha, filename=name, format="xlsx",
                    pages=(Page(page_no=1, text=text),),
                    byte_len=0)


def _import_docx():
    try:
        import docx  # noqa: F401,PLC0415

        return docx
    except ImportError:
        return None


def _import_openpyxl():
    try:
        import openpyxl  # noqa: F401,PLC0415

        return openpyxl
    except ImportError:
        return None


def _import_pypdf():
    try:
        import pypdf  # noqa: F401,PLC0415

        return pypdf
    except ImportError:
        return None


# ── pdf: layout-режим, строки поперёк ──────────────────────────────────

def _extract_pdf(raw: bytes, sha: str, name: str,
                 deadline: float) -> Document | ProviderError:
    pypdf = _import_pypdf()
    if pypdf is None:
        return ProviderError(reason="format_unsupported:pypdf")
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw))
    except Exception as e:
        return ProviderError(reason=f"format_unsupported:pdf_parse_{type(e).__name__}")
    pages: list[Page] = []
    for no, page in enumerate(reader.pages, start=1):
        if time.monotonic() > deadline:
            return ProviderError(reason="extract_timeout")
        try:
            text = page.extract_text(extraction_mode="layout")
        except TypeError:  # старый pypdf без layout-режима
            text = page.extract_text()
        except Exception:
            # страница, на которой парсер споткнулся (пустая, битый
            # шрифт), даёт пустой текст; если НЕ ПУСТОЙ ни одной
            # страницы не вышло — отказ ниже, no_text_layer
            text = ""
        text = _clip(text)
        pages.append(Page(page_no=no, text=text))
    if not pages or all(not p.text.strip() for p in pages):
        return ProviderError(reason="no_text_layer")
    return Document(sha256=sha, filename=name, format="pdf",
                    pages=tuple(pages), byte_len=0)


def _clip(text: str) -> str:
    if len(text) > MAX_PAGE_CHARS:
        return text[:MAX_PAGE_CHARS]
    return text


# ── текстовые форматы ──────────────────────────────────────────────────

def _extract_textish(raw: bytes, sha: str,
                     name: str) -> Document | ProviderError:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except (UnicodeDecodeError, ValueError):
            return ProviderError(reason="format_unsupported:binary")
    if "\x00" in text[:8192]:
        return ProviderError(reason="format_unsupported:binary")
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            json.loads(text)
            return _one_page(sha, name, "json", text)
        except ValueError:
            pass
    low = stripped[:4096].lower()
    if "<html" in low or "<!doctype html" in low or "<body" in low:
        return _one_page(sha, name, "html", _html_to_text(text))
    lines_ = text.splitlines()
    first = lines_[0] if lines_ else ""
    if "\t" in first:
        return _one_page(sha, name, "tsv", text)
    if "," in first:
        try:
            next(csv.reader(io.StringIO(text)))
            return _one_page(sha, name, "csv", text)
        except csv.Error:
            pass
    suffix = Path(name).suffix.lower().lstrip(".")
    kind = suffix if suffix in ("md", "csv", "tsv", "json") else "txt"
    return _one_page(sha, name, kind, text)


def _html_to_text(html: str) -> str:
    """Детерминированное снятие тегов стандартным парсером; скрипты и
    стили выбрасываются."""
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.chunks: list[str] = []
            self._skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self._skip += 1
            if tag in ("p", "br", "tr", "div", "li", "h1", "h2", "h3"):
                self.chunks.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self._skip:
                self._skip -= 1

        def handle_data(self, data):
            if not self._skip:
                self.chunks.append(data)

    parser = _Stripper()
    parser.feed(html)
    text = "".join(parser.chunks)
    return "\n".join(line.strip() for line in text.splitlines()
                     if line.strip())


def _one_page(sha: str, name: str, kind: str,
              text: str) -> Document | ProviderError:
    text = _clip(text)
    if not text.strip():
        return ProviderError(reason="no_text_layer")
    return Document(sha256=sha, filename=name, format=kind,
                    pages=(Page(page_no=1, text=text),), byte_len=0)


__all__ = ["extract_text", "MAX_INPUT_BYTES", "DEADLINE_SECONDS"]
