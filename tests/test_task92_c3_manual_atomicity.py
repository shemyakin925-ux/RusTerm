"""ТЗ-92 C3: ручной импорт переживает неудачный вызов модели.

`manual/pipeline.py` вставляет строку `document` (`:82`) ДО вызова модели
(`:99`) и кладёт байты в raw-хранилище (`:107`) ДО разбора ответа
(`:111`). Поэтому отказ модели (429, таймаут, битый JSON) оставляет
сироту: строка есть, записей нет, и повторный импорт того же файла
на всегда получает `replay` с нулём записей — файл больше нельзя
завести, не трогая базу руками. Второй симптом — doctor:
`rows_without_file` (строка без байтов) при 429 и
`imported_files_without_row` наоборот невозможны, но сама пара
«заголовок + байты» расходится.

Правило ТЗ: строка `document` и сырые байты появляются только когда
записи разобраны. Здесь: (1) 429 — ни строки, ни байтов; (2) повтор с
записанным 200 — записи сохранены и это НЕ replay; (3) битый ответ —
то же самое; (4) guard: повтор уже импортированного файла не трогает
модель (иначе переупорядочивание платит запросом за каждый replay); (5)
успешный импорт оставляет строку и байты вместе; (6) CLI на 429
называет настоящую причину, а не «ключ не задан».

Сети нет: клиент — подстава с записанным ответом.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from rusterm.manual.pipeline import import_document
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import ConfigError
from rusterm.store.repos import Instrument, InstrumentRepo, Issuer

FILE_TEXT = "the fleet comprised 42 ships at year end\nrevenue was 7 million\n"


def _rec(**over) -> dict:
    base = {"company": "Fleet Co", "category": "physical",
            "metric": "fleet_size", "value": "42", "unit": "ships",
            "period": "FY2025",
            "quote": "the fleet comprised 42 ships at year end",
            "page_no": 1}
    base.update(over)
    return base


ANSWER = json.dumps([
    _rec(),
    _rec(metric="crew", value="33", unit="people",
         quote="revenue was 7 million"),
])


class Client:
    """Подставной клиент ②: `answer` — чем отвечать (или объект-ошибка,
    как это делает LlmApiClient на 429/таймауте)."""

    model = "fake-model"

    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def complete(self, prompt: str):
        self.calls += 1
        return self.answer


HTTP_429 = ConfigError(reason="llm_http_429")


@pytest.fixture()
def app(tmp_path):
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir

    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = InstrumentRepo(conn)
    repos.upsert_issuer(Issuer("cik-0", "Fleet Co", "US", None, None,
                               "us-gaap", "USD"))
    repos.upsert_instrument(Instrument("US-FLT", "cik-0", None, "common",
                                       "active", None))
    doc = tmp_path / "annual.txt"
    doc.write_text(FILE_TEXT, encoding="utf-8")
    return conn, paths, doc


def _counts(conn) -> dict:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("document", "manual_extraction", "fact",
                      "raw_object")}


def _raw_on_disk(paths, sha: str) -> bool:
    """Есть ли байты документа в raw-хранилище (то, на что смотрит
    doctor-находка rows_without_file)."""
    from rusterm.store.doctor import _raw_file_exists
    return _raw_file_exists(paths.raw_store, sha)


def test_sha_of_the_file_is_the_document_sha(tmp_path):
    """Байты файла и заголовок сверяются по одному sha256: проверка
    «байты легли рядом со строкой» иначе висит в воздухе."""
    doc = tmp_path / "annual.txt"
    doc.write_text(FILE_TEXT, encoding="utf-8")
    from rusterm.manual.extract import extract_text
    extracted = extract_text(doc)
    assert extracted.sha256 == hashlib.sha256(
        doc.read_bytes()).hexdigest()


def test_429_leaves_no_document_row(app):
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0", Client(HTTP_429))
    assert isinstance(outcome, ConfigError), outcome
    assert outcome.reason == "llm_http_429"
    assert _counts(conn) == {"document": 0, "manual_extraction": 0,
                             "fact": 0, "raw_object": 0}, _counts(conn)


def test_429_leaves_no_bytes_either(app):
    """Строка без байтов — это doctor-находка `rows_without_file`; при
    старом порядке она появлялась на каждой отказной попытке."""
    conn, paths, doc = app
    import_document(conn, paths, doc, "cik-0", Client(HTTP_429))
    from rusterm.manual.extract import extract_text
    sha = extract_text(doc).sha256
    assert _raw_on_disk(paths, sha) is False


def test_unparsable_answer_leaves_nothing(app):
    """Второй симптом: битый JSON оставлял заголовок И байты, и повтор
    файла навсегда становился `replay` с нулём записей."""
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0",
                              Client("not json at all"))
    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == "parse_failed:not_json"
    assert _counts(conn)["document"] == 0
    first = import_document(conn, paths, doc, "cik-0", Client(ANSWER))
    assert first.replay is False, "сиротский заголовок съел повтор"
    assert first.records_total == 2 and first.facts_stored == 1


def test_timeout_exception_leaves_no_document_row(app):
    """Транспорт мог бросить (URLError и т.п.) — та же атомарность."""
    conn, paths, doc = app

    class Raises:
        model = "fake-model"
        calls = 0

        def complete(self, prompt):
            raise ConnectionError("reset by peer")

    outcome = import_document(conn, paths, doc, "cik-0", Raises())
    assert isinstance(outcome, ProviderError), outcome
    assert outcome.reason == "llm_failed:ConnectionError"
    assert _counts(conn)["document"] == 0


def test_retry_after_a_failure_stores_records(app):
    """Done-when ТЗ: первый вызов — 429 и ни одной строки, второй —
    записанный 200, записи сохранены и replay=False."""
    conn, paths, doc = app
    failed = import_document(conn, paths, doc, "cik-0", Client(HTTP_429))
    assert isinstance(failed, ConfigError)
    assert _counts(conn)["document"] == 0
    again = Client(ANSWER)
    outcome = import_document(conn, paths, doc, "cik-0", again)
    assert outcome.replay is False
    assert again.calls == 1
    assert outcome.records_total == 2
    assert outcome.records_verified == 1
    assert outcome.facts_stored == 1
    assert _counts(conn)["document"] == 1
    assert _counts(conn)["fact"] == 1


def test_successful_import_writes_row_and_bytes_together(app):
    """Пара «заголовок + байты» либо вместе, либо нет вовсе — иначе
    source_ref факта ссылается на несуществующие байты."""
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0", Client(ANSWER))
    assert _counts(conn)["document"] == 1
    assert _raw_on_disk(paths, outcome.document_sha) is True
    ref = conn.execute(
        "SELECT source_ref FROM fact WHERE source_kind='manual'").fetchone()[0]
    assert ref == outcome.document_sha


def test_replay_does_not_call_the_model(app):
    """Guard переупорядочивания: повтор уже импортированного файла
    обязан коротко замкнуть на проверке заголовка — иначе каждый replay
    стоит запроса к модели."""
    conn, paths, doc = app
    import_document(conn, paths, doc, "cik-0", Client(ANSWER))
    second = Client(HTTP_429)
    outcome = import_document(conn, paths, doc, "cik-0", second)
    assert outcome.replay is True
    assert second.calls == 0, "replay дошёл до модели"
    assert outcome.records_total == 2, outcome


def test_replay_counts_survive_the_reorder(app):
    """Счётчики повтора берутся из manual_extraction, а не из нулей:
    повтор не должен выглядеть как «в файле ничего нет»."""
    conn, paths, doc = app
    first = import_document(conn, paths, doc, "cik-0", Client(ANSWER))
    again = import_document(conn, paths, doc, "cik-0", Client(ANSWER))
    assert again.replay is True
    assert again.records_total == first.records_total == 2
    assert again.records_verified == 1
    assert again.records_unverified == 1


def test_cli_names_the_real_reason_for_a_429(app, monkeypatch, capsys):
    """cmd_import печатал «ключ RUSTERM_LLM_API_KEY не задан» для
    ЛЮБОГО ConfigError — на 429 это ложь про причину (и про то, что
     помогает пользователю)."""
    import rusterm.cli as cli

    conn, paths, doc = app
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test c3.invalid")
    monkeypatch.setenv("RUSTERM_LLM_API_KEY", "sk-recorded-not-used")
    monkeypatch.setattr("rusterm.providers.llm_api.LlmApiClient.from_env",
                        classmethod(lambda cls, gate, environ=None:
                                    Client(HTTP_429)))
    code = cli.main(["--root", str(paths.root), "import", str(doc),
                     "--issuer", "FLT", "--market", "US"])
    assert code == 1
    err = capsys.readouterr().err
    assert "llm_http_429" in err, err
    assert "RUSTERM_LLM_API_KEY не задан" not in err, err
    assert _counts(conn)["document"] == 0


def test_the_old_order_is_named_by_a_doctor_finding(tmp_path):
    """Сирота, который оставлял прежний порядок, — находка doctor:
    строка `document` без байтов в raw-хранилище."""
    from rusterm.store.db import apply_migrations
    from rusterm.store.doctor import doctor_report
    from rusterm.store.paths import AppPaths, ensure_app_dir

    root = tmp_path / "app2"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    sha = hashlib.sha256(b"orphan header").hexdigest()
    conn.execute(
        """INSERT INTO document(sha256, filename, format, page_count,
           issuer_id, imported_at, bytes) VALUES (?, 'a.txt', 'text',
           1, NULL, 1.0, 5)""", (sha,))
    report = doctor_report(paths, conn)
    assert report["documents"]["rows_without_file"] == 1, report["documents"]
    conn.close()
