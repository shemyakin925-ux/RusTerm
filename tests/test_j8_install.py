"""ТЗ-22 J8: rusterm — команда, а не модуль.

Консольный вход [project.scripts] разрешается в вызываемое; extra
[documents] объявлен; отсутствие библиотеки формата даёт
format_unsupported ЗНАЧЕНИЕМ (ADR-0011 ①), а не исключение.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from rusterm.providers.base import ProviderError

ROOT = Path(__file__).resolve().parents[1]


def test_console_script_entry_point_resolves_to_callable():
    from importlib.metadata import entry_points
    eps = [e for e in entry_points(group="console_scripts")
           if e.name == "rusterm"]
    if eps:
        obj = eps[0].load()
    else:
        # пакет не установлен в это окружение: pyproject всё равно
        # обязан указывать на вызываемое
        data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        spec = data["project"]["scripts"]["rusterm"]
        module, _, attr = spec.partition(":")
        obj = getattr(importlib.import_module(module), attr)
    assert callable(obj)


def test_documents_extra_is_declared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    extra = data["project"]["optional-dependencies"]["documents"]
    assert any("pypdf" in d for d in extra)
    assert any("python-docx" in d for d in extra)
    assert any("openpyxl" in d for d in extra)


def test_absent_pdf_library_yields_format_unsupported_value(
        tmp_path, monkeypatch):
    """Без pypdf — format_unsupported:pypdf значением (не исключение)."""
    # та же дверь, что у pipeline ручного импорта: rusterm.manual.extract
    from rusterm.manual.extract import extract_text
    monkeypatch.setitem(sys.modules, "pypdf", None)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 minimal body")
    outcome = extract_text(pdf)
    assert isinstance(outcome, ProviderError)
    assert outcome.reason == "format_unsupported:pypdf"


def test_absent_docx_library_yields_format_unsupported_value(
        tmp_path, monkeypatch):
    """Без python-docx — format_unsupported:python-docx значением."""
    from rusterm.manual.extract import extract_text
    monkeypatch.setitem(sys.modules, "docx", None)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
    docx = tmp_path / "doc.docx"
    docx.write_bytes(buf.getvalue())
    outcome = extract_text(docx)
    assert isinstance(outcome, ProviderError)
    assert outcome.reason == "format_unsupported:python-docx"
