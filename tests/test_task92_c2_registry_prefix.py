"""ТЗ-92 C2: идентификатор эмитента принадлежит своему рынку.

Префикс строки `issuer_id` — часть схемы, а не украшение: до C2 `cmd_add`
писал `cik-` каждому рынку (CD_CVM Бразилии и корейский corp_code — тоже
цифры), поэтому `refresh` по списку с бразильским эмитентом уходил в SEC
за CIK = <код CVM> и записывал чужие факты под этим id. Правила ТЗ:
префикс из `Market.identifier`, `reporting_standard` из
`Market.default_taxonomy`, валюта из новой таблицы `markets.py`
(угадывать запрещено — CA и OTC лежат под `XXX`), `--cik` — строка со
схемой проверки, а каждая дверь сбора сверяет префикс своего провайдера
и отказывает без запроса.

Сети ни один тест не трогает: `add` идёт офлайн (оба флага заданы,
контакт SEC снят monkeypatch-ем), `refresh` считает транспорт.
"""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import uuid

from rusterm.cli import main
from rusterm.core.refresh import refresh_watchlist
from rusterm.providers.budget import (Budget, NetworkGate, RateLimiter,
                                      RequestGate)
from rusterm.providers.edgar import EdgarProvider
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.doctor import doctor_report
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RepoRegistry,
                                 WatchlistRepo)

FAKE_UA = "Synthetic Test synthetic.invalid"


def _no_contact(monkeypatch):
    """Офлайн-режим `add`: ни контакта SEC, ни env-файла — при заданных
    `--cik`/`--name` провайдер не строится вовсе."""
    monkeypatch.delenv("RUSTERM_SEC_UA", raising=False)
    monkeypatch.setenv("RUSTERM_ENV_FILE",
                       "/nonexistent/rusterm.env-for-tests")


def _issuer_row(root: str, issuer_id: str):
    conn = sqlite3.connect(f"{root}/rusterm.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM issuer WHERE issuer_id=?",
            (issuer_id,)).fetchone()
    finally:
        conn.close()


def _issuer_ids(root: str) -> list[str]:
    conn = sqlite3.connect(f"{root}/rusterm.db")
    try:
        return [r[0] for r in
                conn.execute("SELECT issuer_id FROM issuer").fetchall()]
    finally:
        conn.close()


# ── реестр: префиксы и валюты ──────────────────────────────────────────
def test_every_market_names_its_own_identifier_prefix():
    """Префиксы ровно те, что названы в ТЗ: cik-/cvm-/dart-/asx-; у
    провайдера EDGAR он `cik-`, потому что identifier его рынков — CIK."""
    from rusterm.markets import (MARKETS, provider_prefix,
                                 registry_prefix, registry_prefix_owner)

    expected = {"US": "cik-", "CA": "cik-", "OTC": "cik-",
                "BR": "cvm-", "KR": "dart-", "AU": "asx-"}
    assert {m.code: registry_prefix(m) for m in MARKETS} == expected
    assert provider_prefix("edgar") == "cik-"
    assert provider_prefix("cvm") == "cvm-"
    assert provider_prefix("dart") == "dart-"
    assert provider_prefix("asx") == "asx-"
    # у провайдера без схемы идентификатора префикса нет — дверь не
    # должна сравнивать строку с пустым префиксом
    assert provider_prefix("twelvedata") is None
    # чей префикс — то и решает отказ
    assert registry_prefix_owner("cik-320193") == "edgar"
    assert registry_prefix_owner("cvm-23264") == "cvm"
    assert registry_prefix_owner("dart-00126380") == "dart"
    assert registry_prefix_owner("asx-8") == "asx"
    # синтетические и legacy id без рыночного префикса — НЕ «чужой
    # рынок»: им отказывает прежний путь «идентификатора нет»
    assert registry_prefix_owner("issuer-cli-demo") is None
    assert registry_prefix_owner("i1") is None
    assert registry_prefix_owner(None) is None


def test_reporting_currency_table_covers_every_market_and_never_guesses():
    """CA и OTC лежат под `XXX` (ISO 4217 «валюты нет»): колонка NOT
    NULL, а валюта отчёта канадского или OTC-эмитента из площадки —
    догадка, которую ТЗ запрещает."""
    from rusterm.markets import (MARKET_CODES, REPORTING_CURRENCIES,
                                 reporting_currency)

    assert set(REPORTING_CURRENCIES) == set(MARKET_CODES)
    assert reporting_currency("US") == "USD"
    assert reporting_currency("BR") == "BRL"
    assert reporting_currency("KR") == "KRW"
    assert reporting_currency("AU") == "AUD"
    assert reporting_currency("CA") == "XXX"
    assert reporting_currency("OTC") == "XXX"
    assert reporting_currency("ZZ") is None


# ── add: префикс, standard, валюта ─────────────────────────────────────
def test_add_br_writes_cvm_prefix_ifrs_and_brl(capsys, monkeypatch):
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "AMBEV",
                     "--market", "BR", "--cik", "23264",
                     "--name", "Ambev S.A."]) == 0
        capsys.readouterr()
        row = _issuer_row(root, "cvm-23264")
        assert row is not None, _issuer_ids(root)
        assert row["registry_id"] == "23264"
        assert row["reporting_standard"] == "ifrs-full"
        assert row["reporting_currency"] == "BRL"
        assert _issuer_row(root, "cik-23264") is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_add_kr_keeps_the_leading_zeros_of_corp_code(capsys, monkeypatch):
    """`--cik` был `type=int`: DART-овский `00126380` превращался в
    `126380` и в базу ложился не тот идентификатор."""
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "00126380",
                     "--market", "KR", "--cik", "00126380",
                     "--name", "Sample Corp."]) == 0
        capsys.readouterr()
        row = _issuer_row(root, "dart-00126380")
        assert row is not None, _issuer_ids(root)
        assert row["registry_id"] == "00126380"
        assert row["reporting_standard"] == "ifrs-full"
        assert row["reporting_currency"] == "KRW"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_add_au_writes_asx_prefix_and_aud(capsys, monkeypatch):
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "FLT",
                     "--market", "AU", "--cik", "8",
                     "--name", "Fleet Ltd", "--fye", "06-30"]) == 0
        capsys.readouterr()
        row = _issuer_row(root, "asx-8")
        assert row is not None, _issuer_ids(root)
        assert row["reporting_currency"] == "AUD"
        assert row["fiscal_year_end"] == "06-30"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_add_us_and_otc_keep_cik_prefix_and_refuse_to_name_a_currency(
        capsys, monkeypatch):
    """US — USD (валюта снята с того же рынка, что и идентификатор),
    OTC — XXX: у площадки за OTC-тикером валюты отчёта нет, и придумать
    её программа не вправе."""
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "AAPL",
                     "--market", "US", "--cik", "320193",
                     "--name", "Apple Inc."]) == 0
        assert main(["--root", root, "add", "--ticker", "ZZZ",
                     "--market", "OTC", "--cik", "10456",
                     "--name", "Zed Corp."]) == 0
        capsys.readouterr()
        assert _issuer_row(root, "cik-320193")["reporting_standard"] \
            == "us-gaap"
        assert _issuer_row(root, "cik-320193")["reporting_currency"] \
            == "USD"
        assert _issuer_row(root, "cik-10456")["reporting_currency"] \
            == "XXX"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_add_refuses_a_corp_code_that_is_not_eight_digits(capsys,
                                                          monkeypatch):
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "126380",
                     "--market", "KR", "--cik", "126380",
                     "--name", "Short Code Corp."]) == 1
        err = capsys.readouterr().err
        assert "corp_code" in err and "8" in err, err
        assert _issuer_ids(root) == [], _issuer_ids(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_add_refuses_a_registry_id_that_is_not_digits(capsys, monkeypatch):
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "AAPL",
                     "--market", "US", "--cik", "0012AB",
                     "--name", "Apple Inc."]) == 1
        err = capsys.readouterr().err
        assert "cik" in err.lower(), err
        assert _issuer_ids(root) == [], _issuer_ids(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── двери сбора сверяют префикс своего провайдера ──────────────────────
def _sandbox(tmp_path):
    paths = AppPaths.from_root(str(tmp_path / "app"))
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    return paths, conn, RepoRegistry(conn, paths)


def test_refresh_refuses_a_foreign_prefix_with_zero_requests(tmp_path):
    """Эмитент Бразилии в списочном проходе: ноль запросов к SEC
    (посчитан транспортом) и причина, называющая провайдера, чужим
    для которого он стал."""
    paths, conn, repos = _sandbox(tmp_path)
    repos.instrument.upsert_issuer(Issuer(
        "cvm-23264", "Ambev S.A.", "BR", "23264", None,
        "ifrs-full", "BRL"))
    repos.instrument.upsert_instrument(Instrument(
        "BR-AMBEV", "cvm-23264", None, "common", "active", None))
    watchlist = WatchlistRepo(conn)
    watchlist.create_watchlist("c2", "смешанный", None, None)
    watchlist.new_version(str(uuid.uuid4()), "c2", 1, "create", None)
    vid = watchlist.current_version("c2")["watchlist_version_id"]
    watchlist.add_member(vid, "BR-AMBEV", None)

    log: list[str] = []

    class _CountingTransport:
        def __call__(self, url, headers):
            log.append(url)
            return 404, b"{}", {}

    built: list[int] = []

    def provider_factory(cik):
        built.append(cik)
        return EdgarProvider(gate=RequestGate(
            budget=Budget(max_requests=10),
            limiter=RateLimiter(per_second=10),
            gate=NetworkGate(environ={"RUSTERM_SEC_UA": FAKE_UA})),
            cik=cik, transport=_CountingTransport())

    try:
        results = refresh_watchlist(repos, provider_factory, "c2",
                                    "2026-09-18")
    finally:
        conn.close()

    assert log == [], f"чужой идентификатор ушёл в SEC: {log}"
    assert built == [], f"провайдер построен для чужого рынка: {built}"
    assert results[0].action == "error"
    assert results[0].reason == "unknown_issuer: registry is not edgar"
    assert is_known_reason(results[0].reason.split(":", 1)[0])


def test_ingest_edgar_door_refuses_a_cvm_issuer(capsys, monkeypatch):
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "AMBEV",
                     "--market", "BR", "--cik", "23264",
                     "--name", "Ambev S.A."]) == 0
        capsys.readouterr()
        assert main(["--root", root, "ingest", "--instrument",
                     "BR-AMBEV", "--source", "edgar"]) == 1
        err = capsys.readouterr().err
        assert "registry is not edgar" in err, err
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ingest_cvm_door_refuses_a_cik_issuer(capsys, monkeypatch):
    """Обратная сторона: legacy-строка `cik-` с бразильской юрисдикцией
    не должна уходить в CVM — отказ называет провайдера и отправляет к
    doctor, который такие строки ищет."""
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        conn = sqlite3.connect(f"{root}/rusterm.db", isolation_level=None)
        conn.execute(
            "INSERT INTO issuer (issuer_id, name, jurisdiction,"
            " registry_id, fiscal_year_end, reporting_standard,"
            " reporting_currency) VALUES "
            "('cik-23264', 'Legacy BR', 'BR', '23264', NULL,"
            " 'us_gaap', 'USD')")
        conn.execute(
            "INSERT INTO instrument (instrument_id, issuer_id, isin,"
            " class, status, superseded_by) VALUES"
            " ('BR-LEGACY', 'cik-23264', NULL, 'common', 'active', NULL)")
        conn.close()
        capsys.readouterr()
        assert main(["--root", root, "ingest", "--instrument",
                     "BR-LEGACY", "--source", "cvm"]) == 1
        err = capsys.readouterr().err
        assert "registry is not cvm" in err, err
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_ingest_ownership_door_refuses_a_cik_issuer(capsys, monkeypatch):
    """Третья дверь EDGAR — владение (Forms 3/4/5). Отказ тот же и по
    той же причине, но слово в сообщении своё: Form 4 по CIK чужого
    кода не существует, и спрашивать его у SEC не за чем."""
    _no_contact(monkeypatch)
    root = tempfile.mkdtemp()
    try:
        assert main(["--root", root, "init"]) == 0
        capsys.readouterr()
        assert main(["--root", root, "add", "--ticker", "AMBEV",
                     "--market", "BR", "--cik", "23264",
                     "--name", "Ambev S.A."]) == 0
        capsys.readouterr()
        assert main(["--root", root, "ingest", "--instrument",
                     "BR-AMBEV", "--source", "ownership"]) == 1
        err = capsys.readouterr().err
        assert "registry is not edgar" in err, err
        assert "Form 4" in err, err
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ── doctor называет legacy-строки ──────────────────────────────────────
def test_doctor_names_cik_issuers_outside_edgar_jurisdictions(tmp_path):
    """Эмитенты не переименовываются (ТЗ C2), поэтому единственная
    защита от «CIK = код CVM» — находка doctor-а."""
    paths, conn, repos = _sandbox(tmp_path)
    repos.instrument.upsert_issuer(Issuer(
        "cik-23264", "Legacy BR", "BR", "23264", None, "us_gaap", "USD"))
    repos.instrument.upsert_issuer(Issuer(
        "cik-320193", "Apple Inc.", "US", "320193", None,
        "us-gaap", "USD"))
    repos.instrument.upsert_issuer(Issuer(
        "cik-50000", "Canadian Filer", "CA", "50000", None,
        "ifrs-full", "XXX"))
    try:
        report = doctor_report(paths, conn)
        assert report["registry_prefix_mismatch"] == [
            {"issuer_id": "cik-23264", "jurisdiction": "BR",
             "registry_id": "23264"}], report["registry_prefix_mismatch"]
        assert any("cik-" in p and "BR" in p for p in report["problems"]), \
            report["problems"]
    finally:
        conn.close()


def test_doctor_stays_quiet_on_edgar_jurisdictions(tmp_path):
    """US и CA торгуются через EDGAR — CIK у них свой, находки нет."""
    paths, conn, repos = _sandbox(tmp_path)
    for iid, jur in (("cik-320193", "US"), ("cik-50000", "CA")):
        repos.instrument.upsert_issuer(Issuer(
            iid, f"Corp {jur}", jur, iid.split("-", 1)[1], None,
            "us-gaap", "USD"))
    try:
        report = doctor_report(paths, conn)
        assert report["registry_prefix_mismatch"] == []
        assert not any("cik-" in p for p in report["problems"]), \
            report["problems"]
    finally:
        conn.close()
