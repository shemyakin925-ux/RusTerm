"""ТЗ-20 L6: записи ②, контроль ③, конвейер ручного импорта и команда
`rusterm import`. Всё офлайн: модель — подставной клиент с
записанными ответами, сети нет. Ключа модели нет ни в одном тесте.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from rusterm.manual.pipeline import import_document
from rusterm.manual.records import (
    ParsedRecords, build_prompt, parse_records, period_bounds)
from rusterm.providers.base import ProviderError
from rusterm.providers.budget import (
    ConfigError, HostLimit, NetworkGate, RequestGate)


# ── ② разбор ответа модели ─────────────────────────────────────────────

def _rec(**over) -> dict:
    base = {"company": "Fleet Co", "category": "physical",
            "metric": "fleet_size", "value": "42", "unit": "ships",
            "period": "FY2025", "quote": "the fleet comprised 42 ships",
            "page_no": 1}
    base.update(over)
    return base


def test_parse_records_good_array():
    parsed = parse_records(json.dumps([_rec(), _rec(metric="dwt",
                                                    value="1000")]))
    assert isinstance(parsed, ParsedRecords)
    assert len(parsed.records) == 2
    assert parsed.dropped_no_quote == 0


def test_parse_records_drops_no_quote_with_count():
    """Пустая цитата = иной ключ → счётчик «ломаной формы»; пробельная
    цитата = «без цитаты». Оба счётчика честные, ничего не молчит."""
    parsed = parse_records(json.dumps([
        _rec(),
        _rec(metric="bad", quote=""),
        _rec(metric="worse", quote="  "),
    ]))
    assert len(parsed.records) == 1
    assert parsed.dropped_no_quote == 1
    assert parsed.dropped_bad_shape == 1


def test_parse_records_drops_bad_category_with_count():
    parsed = parse_records(json.dumps([
        _rec(),
        _rec(metric="bad", category="esoteric"),
    ]))
    assert len(parsed.records) == 1
    assert parsed.dropped_bad_category == 1


def test_parse_records_malformed_is_value():
    assert parse_records("not json").reason == "parse_failed:not_json"
    assert parse_records('{"a": 1}').reason == "parse_failed:not_a_list"
    assert isinstance(parse_records("not json"), ProviderError)


def test_parse_records_strips_code_fence():
    raw = "```json\n" + json.dumps([_rec()]) + "\n```"
    parsed = parse_records(raw)
    assert len(parsed.records) == 1


def test_build_prompt_carries_pages_and_verbatim_rule():
    from rusterm.manual import Page
    prompt = build_prompt([Page(1, "alpha"), Page(2, "beta")])
    assert "[page 1]" in prompt and "[page 2]" in prompt
    assert "VERBATIM" in prompt


def test_period_bounds_mapping():
    assert period_bounds("FY2025") == ("2025-01-01", "2025-12-31",
                                       "duration")
    assert period_bounds("2025-06-30") == ("2025-06-30", "2025-06-30",
                                           "instant")
    assert period_bounds("something else") == ("something else",
                                               "something else", "instant")


# ── конвейер: хранение, верификация, идемпотентность ───────────────────

FILE_TEXT = "the fleet comprised 42 ships at year end\nrevenue was 7 million\n"


class FakeClient:
    """Подставной клиент ②: возвращает записанный ответ."""

    model = "fake-model"
    answer = json.dumps([
        _rec(quote="the fleet comprised 42 ships at year end"),
        # непроверяемая: числа из значения в цитате нет
        _rec(metric="crew", value="33", unit="people",
             quote="revenue was 7 million"),
    ])

    def complete(self, prompt: str):
        return self.answer


class _Paths:
    """Минимальная подстава путей: RawRepo нужен только paths.raw_store
    и paths.raw_manifests."""

    def __init__(self, root):
        from rusterm.store.paths import AppPaths
        real = AppPaths.from_root(root)
        self.raw_store = real.raw_store
        self.raw_manifests = real.raw_manifests
        self.root = real.root
        self.db_path = real.db_path
        self.app_log_path = real.app_log_path
        self.audit_log_path = real.audit_log_path


@pytest.fixture()
def app(tmp_path):
    from rusterm.store.db import apply_migrations
    from rusterm.store.paths import AppPaths, ensure_app_dir
    from rusterm.store.repos import (
        Instrument, InstrumentRepo, Issuer)

    root = tmp_path / "app"
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos_i = InstrumentRepo(conn)
    repos_i.upsert_issuer(Issuer("cik-0", "Fleet Co", "US", None, None,
                                 "us_gaap", "USD"))
    repos_i.upsert_instrument(Instrument("US-FLT", "cik-0", None,
                                         "common", "active", None))
    doc = tmp_path / "annual.txt"
    doc.write_text(FILE_TEXT, encoding="utf-8")
    return conn, paths, doc


def test_pipeline_stores_verified_fact_manual_kind(app):
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0", FakeClient())
    assert outcome.records_total == 2
    assert outcome.records_verified == 1
    assert outcome.records_unverified == 1
    assert outcome.facts_stored == 1
    row = conn.execute(
        """SELECT concept, source_kind, origin, status, locator, value
           FROM fact WHERE source_kind='manual'""").fetchone()
    assert row[0] == "fleet_size"
    assert row[1] == "manual" and row[2] == "manual" and row[3] == "ok"
    assert f"sha256:{outcome.document_sha}#page=1" in row[4]
    assert row[5] == "42"


def test_unverified_record_stored_marked_and_never_a_fact(app):
    """ADR-0011 ③ в зоне L6: запись с verified=no сохраняется и видна
    (manual_extraction, verified=0), а факта у неё нет — в measures
    она попасть не может по построению. Презентация в экспорте —
    полоса L9 (см. Disputed отчёта)."""
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0", FakeClient())
    assert outcome.records_unverified == 1
    marked = conn.execute(
        """SELECT metric, verified FROM manual_extraction
           WHERE verified=0""").fetchone()
    assert marked[0] == "crew" and marked[1] == 0
    facts = conn.execute(
        """SELECT COUNT(*) FROM fact f WHERE concept='crew'""").fetchone()[0]
    assert facts == 0


def test_no_key_stops_after_first_stage_writing_nothing(app):
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0",
                              ConfigError(reason="llm_key_unset"))
    assert isinstance(outcome, ConfigError)
    for table in ("document", "manual_extraction", "fact"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n == 0, table


def test_same_file_twice_is_idempotent_by_counts(app):
    conn, paths, doc = app
    first = import_document(conn, paths, doc, "cik-0", FakeClient())
    assert not first.replay
    counts_before = [
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("document", "manual_extraction", "fact")]
    second = import_document(conn, paths, doc, "cik-0", FakeClient())
    assert second.replay is True
    assert second.records_verified == 1
    counts_after = [
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("document", "manual_extraction", "fact")]
    assert counts_before == counts_after


def test_manual_fact_never_overwrites_provider_fact(app):
    """Машинский факт на месте: ручная запись его не трогает — у
    фактов разные source_kind, запись только добавлением."""
    conn, paths, doc = app
    conn.execute(
        """INSERT INTO fact(fact_id, issuer_id, concept, period_start,
           period_end, period_type, value, unit, basis, origin,
           source_ref, locator, parser_version, status, ingested_at,
           source_kind)
           VALUES ('prov-1','cik-0','fleet_size','2025-01-01',
           '2025-12-31','duration','99','ships','as_reported',
           'extracted','seed','l','p','ok',0,'provider')""")
    import_document(conn, paths, doc, "cik-0", FakeClient())
    prov = conn.execute(
        "SELECT value FROM fact WHERE fact_id='prov-1'").fetchone()
    assert prov[0] == "99"
    kinds = conn.execute(
        """SELECT source_kind, COUNT(*) FROM fact
           WHERE concept='fleet_size' GROUP BY source_kind""").fetchall()
    assert dict(kinds) == {"provider": 1, "manual": 1}


def test_dry_run_writes_nothing(app):
    conn, paths, doc = app
    outcome = import_document(conn, paths, doc, "cik-0", FakeClient(),
                              dry_run=True)
    assert outcome.model == "dry-run"
    for table in ("document", "manual_extraction", "fact"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n == 0, table


# ── CLI: настоящая команда import ──────────────────────────────────────

def test_cli_import_happy_path_offline(app, monkeypatch, capsys):
    import rusterm.cli as cli

    conn, paths, doc = app
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test l6.invalid")
    monkeypatch.setattr("rusterm.providers.llm_api.LlmApiClient.from_env",
                        classmethod(
                            lambda cls, gate, environ=None: FakeClient()))
    code = cli.main(["--root", str(paths.root), "import", str(doc),
                     "--issuer", "FLT", "--market", "US"])
    assert code == 0
    out = capsys.readouterr().out
    assert "подтверждено контролем: 1" in out
    assert "manual_unverified" in out


def test_cli_import_without_key_stops_after_first_stage(
        app, monkeypatch, capsys):
    import rusterm.cli as cli

    conn, paths, doc = app
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test l6.invalid")
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       str(paths.root / "no-such.env"))
    code = cli.main(["--root", str(paths.root), "import", str(doc),
                     "--issuer", "FLT", "--market", "US"])
    assert code == 1
    err = capsys.readouterr().err
    assert "RUSTERM_LLM_API_KEY" in err and "ТЗ-20" in err
    for table in ("document", "manual_extraction", "fact"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n == 0, table


def test_cli_import_unknown_issuer_refused(app, capsys):
    import rusterm.cli as cli

    conn, paths, doc = app
    code = cli.main(["--root", str(paths.root), "import", str(doc),
                     "--issuer", "GHOST", "--market", "US"])
    assert code == 1
    assert "не найден" in capsys.readouterr().err
