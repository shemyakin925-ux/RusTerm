"""ТЗ-57 A4: канал ingest Австралии — форма ТЗ-56 Z2 на записанных
телах ASX (живая выкачка 11.09: tests/data/asx/header_CBA.json,
announcements_CBA.json). add — через НАСТОЯЩИЙ AsxProvider (resolve +
can_auto_ingest по записанным байтам, без адаптера), ingest --source
asx кладёт список анонсов в raw store с провенансом; тела документов
бесплатным каналом недостижимы — каждая подача называется
manual_import_required:asxdoc:<ключ>, фактов ноль, ни одной меры из
воздуха. Счёт запросов ведёт настоящий гейт, то же число печатает
rusterm budget.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.providers.asx import AsxProvider
from rusterm.providers.budget import RequestGate
from rusterm.reasons import is_known_reason
from rusterm.store.paths import AppPaths

DATA = Path(__file__).resolve().parent / "data"
HEADER = (DATA / "asx" / "header_CBA.json").read_bytes()
ANNOUNCE = (DATA / "asx" / "announcements_CBA.json").read_bytes()

_BASE = "https://asx.api.markitdigital.com/asx-research/1.0/companies"

# десять мер переписи ТЗ-49 + roe_incl_nci (ТЗ-56 Z1)
MEASURES = ("asset_turnover", "ebitda", "effective_tax", "fcf",
            "gross_margin", "interest_coverage", "net_margin", "nopat",
            "operating_margin", "roe", "roe_incl_nci")


@pytest.fixture()
def au_app(monkeypatch, tmp_path):
    """Записанный транспорт ASX + настоящий AsxProvider в двери CLI."""
    monkeypatch.setenv("RUSTERM_SEC_UA", "Synthetic Test au57.invalid")
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")
    monkeypatch.delenv("RUSTERM_DART_KEY", raising=False)
    monkeypatch.delenv("RUSTERM_LLM_API_KEY", raising=False)
    calls: list[tuple[str, str]] = []

    def transport(url, headers):
        calls.append(("GET", url))
        if url == f"{_BASE}/CBA/header":
            return 200, HEADER, {}
        if url == f"{_BASE}/CBA/announcements":
            return 200, ANNOUNCE, {}
        return 404, b"", {}

    monkeypatch.setattr(
        cli, "get_provider",
        lambda name, gate=None: AsxProvider(gate=gate or RequestGate(),
                                            transport=transport))
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    monkeypatch.setattr(cli, "args_as_of_default",
                        lambda: "2025-06-30")
    return root, calls


def test_add_ingest_snapshot_full_path_offline(au_app, capsys):
    """add -> ingest --source asx -> snapshot: эмитент создан настоящим
    провайдером, сырьё в raw store, фактов ноль — честно."""
    root, calls = au_app
    assert cli.main(["--root", str(root), "add", "--ticker", "CBA",
                     "--market", "AU"]) == 0
    added = capsys.readouterr().out
    assert "COMMONWEALTH BANK" in added, added
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    ingested = capsys.readouterr().out
    assert "анонсов: " in ingested, ingested
    assert "фактов: 0" in ingested, ingested
    assert "manual_import_required" in ingested, ingested
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "AU-CBA"]) == 0
    capsys.readouterr()
    # путь провайдер -> сырой объект сработал: как минимум 3 запроса
    # add (header + header + announcements) и 1 ingest
    assert len(calls) >= 4, calls


def test_ingest_raw_object_provenance_and_cache(au_app, capsys):
    """Список анонсов — raw_object провайдера asx с каноническим URL;
    второй прогон инкрементален: тело берётся из кеша, ноль запросов."""
    root, calls = au_app
    assert cli.main(["--root", str(root), "add", "--ticker", "CBA",
                     "--market", "AU"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    capsys.readouterr()
    before = len(calls)
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    out = capsys.readouterr().out
    assert "запросов: 0" in out, out
    assert len(calls) == before, calls

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT provider, url, block FROM raw_object
               WHERE provider='asx'""").fetchone()
        assert row is not None, "анонсы не в raw store"
        assert row["url"] == f"{_BASE}/CBA/announcements", row
        assert row["block"] == "disclosures", row
    finally:
        conn.close()


def test_no_measure_appears_from_thin_air(au_app, capsys):
    """Канал не приносит фактов — ни одна мера не возникает из воздуха:
    значение у ЛЮБОЙ меры снапшота отсутствует, причины — из словаря."""
    root, _ = au_app
    assert cli.main(["--root", str(root), "add", "--ticker", "CBA",
                     "--market", "AU"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "snapshot", "--instrument",
                     "AU-CBA"]) == 0
    capsys.readouterr()

    paths = AppPaths.from_root(root)
    conn = sqlite3.connect(str(paths.db_path))
    try:
        rows = conn.execute(
            """SELECT m.concept, m.value, m.null_reason
               FROM measure m
               JOIN snapshot s ON m.snapshot_id = s.snapshot_id
               WHERE s.instrument_id='AU-CBA'""").fetchall()
        assert rows, "меры не построены"
        for concept, value, reason in rows:
            assert value is None, (concept, value)
            token = (reason or "").split(":", 1)[0]
            assert is_known_reason(token), (concept, reason)
        fundamental = {c for c, _v, _r in rows if c in MEASURES}
        assert fundamental == set(MEASURES), sorted(fundamental ^
                                                    set(MEASURES))
    finally:
        conn.close()


def test_markets_names_au_channel_honestly(au_app, capsys):
    """rusterm markets: у AU канал назван (он теперь есть); KR остаётся
    честным отсутствием."""
    root, _ = au_app
    assert cli.main(["--root", str(root), "markets", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_code = {row["code"]: row for row in payload["markets"]}
    assert by_code["AU"]["channel"] == "asx", by_code["AU"]
    assert by_code["KR"]["channel"] is None
    assert by_code["US"]["channel"] == "edgar"


def test_budget_names_requests_by_number(au_app, capsys):
    """Бюджет назван числом из rusterm budget: свежий прогон ingest —
    один запрос, кеш-прогон — ноль (последняя проба гейта)."""
    root, _ = au_app
    assert cli.main(["--root", str(root), "add", "--ticker", "CBA",
                     "--market", "AU"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "budget"]) == 0
    out = capsys.readouterr().out
    assert "provider_requests_used" in out, out
    named = float(out.split("provider_requests_used =")[1].split()[0])
    assert named == 1.0, out
    assert cli.main(["--root", str(root), "ingest", "--instrument",
                     "AU-CBA", "--source", "asx"]) == 0
    capsys.readouterr()
    assert cli.main(["--root", str(root), "budget"]) == 0
    out = capsys.readouterr().out
    named = float(out.split("provider_requests_used =")[1].split()[0])
    assert named == 0.0, out
