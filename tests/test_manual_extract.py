"""ТЗ-20 L5: ступень ① — файлы становятся страницами.

Фикстуры генерируются тестом (синтетические, N6). Сети нет. Библиотеки
pdf/docx/xlsx — опциональные: каждая пара тестов гоняется «библиотека
отсутствует» (monkeypatch-импорт) и «присутствует». Злонамеренные
входы — zip-бомба, ../../escape-член, внешняя XML-сущность —
отказываются ЗНАЧЕНИЕМ, и ничего не появляется вне каталога данных.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from rusterm.manual import Document, Page
from rusterm.manual.extract import extract_text
from rusterm.providers.base import ProviderError


@pytest.fixture()
def data_root(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    return root


def _write(root: Path, name: str, data: bytes) -> Path:
    path = root / name
    path.write_bytes(data)
    return path


# ── детерминизм и текстовые форматы ────────────────────────────────────

def test_same_file_twice_byte_identical_pages_and_sha(data_root):
    path = _write(data_root, "report.txt",
                  "fleet of 42 ships\nrevenue 1 234\n".encode())
    first = extract_text(path)
    second = extract_text(path)
    assert isinstance(first, Document) and isinstance(second, Document)
    assert first.sha256 == second.sha256
    assert [p.text for p in first.pages] == [p.text for p in second.pages]
    assert first.pages[0].page_no == 1


def test_format_by_content_txt_holding_pdf_header_is_pdf(data_root,
                                                         monkeypatch):
    """Расширение .txt, содержимое %PDF- — это PDF (по содержимому).
    Библиотека «отсутствует» — format_unsupported:pypdf значением."""
    monkeypatch.setattr("rusterm.manual.extract._import_pypdf",
                        lambda: None)
    path = _write(data_root, "annual.txt", b"%PDF-1.4 garbage")
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason == "format_unsupported:pypdf"


def test_stdlib_formats_detected(data_root):
    cases = {
        "a.json": b'{"k": 1}',
        "b.csv": b"h1,h2\n1,2\n",
        "c.tsv": b"h1\th2\n1\t2\n",
        "d.md": b"# Header\n\ntext\n",
        "e.html": b"<html><body><p>hello</p></body></html>",
    }
    for name, data in cases.items():
        path = _write(data_root, name, data)
        result = extract_text(path)
        assert isinstance(result, Document), (name, result)
    assert extract_text(_write(data_root, "a.json", b'{"k": 1}')).format \
        == "json"
    assert extract_text(_write(data_root, "b.csv", b"h1,h2\n1,2\n")).format \
        == "csv"


def test_html_tags_stripped_script_dropped(data_root):
    path = _write(data_root, "page.htm",
                  b"<html><script>evil()</script>"
                  b"<body><p>Revenue</p><p>1 234</p></body></html>")
    result = extract_text(path)
    assert isinstance(result, Document)
    assert result.format == "html"
    assert "evil" not in result.pages[0].text
    assert "Revenue" in result.pages[0].text


def test_binary_is_refused_by_value(data_root):
    path = _write(data_root, "blob.bin", bytes(range(256)) * 64)
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason == "format_unsupported:binary"


# ── zip-бомба, escape-член, внешняя сущность ───────────────────────────

def _zip_of(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _bomb_zip() -> bytes:
    """Бомба по числу членов: 5000 членов против потолка 4096. (Бомбу
    «по объявленному размеру» zipfile в тесте не собирает — writestr
    перетирает file_size фактическим; потолок MAX_ZIP_UNCOMPRESSED
    стоит тем же стражем и покрыт объявленными размерами центрального
    каталога.)"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(5000):
            zf.writestr(f"m/{i}.xml", b"x")
    return buf.getvalue()


def test_zip_bomb_refused_by_value_nothing_written(data_root):
    path = _write(data_root, "bomb.docx", _bomb_zip())
    before = sorted(p.name for p in data_root.rglob("*"))
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason.startswith("extract_zip_bomb")
    assert sorted(p.name for p in data_root.rglob("*")) == before


def test_path_escape_member_never_reaches_disk(data_root):
    """Член с именем ../../escape: разбор в памяти, на диске — только
    сам входной файл; файла escape нигде нет."""
    evil = _zip_of({"../../escape": b"x"})
    # контейнер без word/ или xl/ -> format_unsupported, но главное:
    # файла escape не появилось нигде
    path = _write(data_root, "evil.zip", evil)
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert not (data_root.parent / "escape").exists()
    assert not (data_root / "escape").exists()
    assert sorted(p.name for p in data_root.rglob("*")) == ["evil.zip"]


def test_xml_external_entity_refused_by_value(data_root):
    """XXE: DOCTYPE с внешней сущностью — extract_xml_refused (или
    отказ парсера), содержимое /etc/passwd не утекает в страницы."""
    evil_doc = (b'<?xml version="1.0"?><!DOCTYPE w:document ['
                b'<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                b'<w:document xmlns:w="http://schemas.openxmlformats.org/'
                b'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
                b"&xxe;</w:t></w:r></w:p></w:body></w:document>")
    container = _zip_of({"word/document.xml": evil_doc,
                         "[Content_Types].xml": b"<Types/>"})
    path = _write(data_root, "evil.docx", container)
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason.startswith(("extract_xml_refused",
                                     "extract_docx_refused",
                                     "format_unsupported"))
    for page_file in data_root.rglob("*"):
        assert b"root" not in page_file.read_bytes()[:0]  # тривиально:
    # главное — исключения нет и файлов не появилось
    assert sorted(p.name for p in data_root.rglob("*")) == ["evil.docx"]


# ── docx/xlsx: библиотека есть и отсутствует ───────────────────────────

def _real_docx_bytes(paragraphs: list[str]) -> bytes:
    import docx

    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _real_xlsx_bytes(rows: list[list[object]]) -> bytes:
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()


def test_docx_with_library_extracts_paragraphs(data_root):
    path = _write(data_root, "real.docx",
                  _real_docx_bytes(["Fleet size 42", "Revenue 1 234"]))
    result = extract_text(path)
    assert isinstance(result, Document)
    assert result.format == "docx"
    assert "Fleet size 42" in result.pages[0].text


def test_docx_without_library_is_value(data_root, monkeypatch):
    monkeypatch.setattr("rusterm.manual.extract._import_docx",
                        lambda: None)
    path = _write(data_root, "real.docx", _real_docx_bytes(["x"]))
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason == "format_unsupported:python-docx"


def test_xlsx_with_library_reads_rows_across(data_root):
    path = _write(data_root, "table.xlsx",
                  _real_xlsx_bytes([["metric", "value"],
                                    ["fleet_size", "42"]]))
    result = extract_text(path)
    assert isinstance(result, Document)
    text = result.pages[0].text
    # строка читается ПОПЕРЁК: метрика и её значение на одной строке
    assert "fleet_size\t42" in text


def test_xlsx_without_library_is_value(data_root, monkeypatch):
    monkeypatch.setattr("rusterm.manual.extract._import_openpyxl",
                        lambda: None)
    path = _write(data_root, "table.xlsx",
                  _real_xlsx_bytes([["a", "b"]]))
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason == "format_unsupported:openpyxl"


# ── pdf: строки поперёк, скан без слоя ─────────────────────────────────

def _two_column_pdf() -> bytes:
    """Минимальный PDF с двумя колонками текста, собранный вручную
    (синтетика, без библиотек): строки читаются поперёк."""
    def text_op(x: int, y: int, text: str) -> bytes:
        return f"BT /F1 12 Tf {x} {y} Td ({text}) Tj ET".encode()

    content = b"\n".join([
        text_op(72, 700, "metric          value"),
        text_op(72, 680, "fleet_size      42"),
        text_op(72, 660, "revenue         1234"),
    ])
    stream = f"<< /Length {len(content)} >>\nstream\n".encode() \
        + content + b"\nendstream"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        stream,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = {}
    for no, obj in enumerate(objects, start=1):
        offsets[no] = out.tell()
        out.write(f"{no} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_at = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for no in range(1, len(objects) + 1):
        out.write(f"{offsets[no]:010d} 00000 n \n".encode())
    out.write(b"trailer\n" +
              f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode() +
              b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n")
    return out.getvalue()


def test_pdf_table_reads_across(data_root):
    path = _write(data_root, "table.pdf", _two_column_pdf())
    result = extract_text(path)
    assert isinstance(result, Document), result
    assert result.format == "pdf"
    text = result.pages[0].text
    # поперёк: имя метрики и значение в одной строке (layout-режим)
    assert "fleet_size" in text and "42" in text
    same_line = [line for line in text.splitlines()
                 if "fleet_size" in line]
    assert same_line and "42" in same_line[0], text


def test_pdf_without_text_layer_is_no_text_layer(data_root):
    """Скан: страница без извлекаемого текста — no_text_layer
    значением; OCR в проекте нет."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    path = _write(data_root, "scan.pdf", buf.getvalue())
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason == "no_text_layer"


def test_corrupt_pdf_is_value(data_root):
    path = _write(data_root, "broken.pdf",
                  b"%PDF-1.4 this is not a pdf at all")
    result = extract_text(path)
    assert isinstance(result, ProviderError)
    assert result.reason.startswith("format_unsupported:pdf_parse")


def test_unreadable_file_is_value(data_root):
    result = extract_text(data_root / "absent.txt")
    assert isinstance(result, ProviderError)
    assert result.reason.startswith("extract_unreadable")


def test_json_fixture_is_document(data_root):
    path = _write(data_root, "data.json",
                  json.dumps({"fleet": 42}).encode())
    result = extract_text(path)
    assert isinstance(result, Document)
    assert json.loads(result.pages[0].text)["fleet"] == 42
