"""ТЗ-32 D2/D3 (ТЗ-25 P4): владение Forms 3/4/5 — сбор, разбор,
честный отказ.

- золотой разбор записанного payload (tests/data/edgar/ownership/):
  сделки сверяются со значениями, ВЫЧИТАННЫМИ ИЗ САМОГО payload;
- сбор идемпотентен: те же документы не пишутся второй раз;
- D3: эмитент без форм владения получает coverage missing с именованной
  причиной — никогда пустой успех;
- живой тест несёт маркер live и без RUSTERM_SEC_UA пропускается (N7).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from rusterm.cli import _ingest_edgar_ownership
from rusterm.parsers.ownership import parse_form4
from rusterm.providers.edgar import EdgarProvider
from rusterm.providers.budget import NetworkGate, RequestGate
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

_DATA = (Path(__file__).resolve().parents[1] / "tests" / "data"
         / "edgar" / "ownership")
FAKE_UA = "Synthetic Test t.invalid"

_SUBMISSIONS = {
    "filings": {"recent": {
        "form": ["4", "3"],
        "accessionNumber": ["0001140361-26-036226",
                            "0001140361-26-035359"],
        "primaryDocument": ["form4.xml", "form3.xml"],
        "reportDate": ["2026-09-08", "2026-09-01"],
        "filingDate": ["2026-09-10", "2026-09-03"],
    }},
}


def _payload(name: str) -> bytes:
    return (_DATA / name).read_bytes()


def _env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-o", "Apple Inc.", "US", "320193", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-OWN", "i-o", None, "common", "active", None))
    return conn, repos


def _fake_provider(submissions: dict, calls: list):
    """EdgarProvider с транспортом, отдающим записанные payload:
    submissions — по data.sec.gov, тела — по accession в URL."""

    def transport(url, headers):
        calls.append(url)
        if "submissions" in url:
            return 200, json.dumps(submissions).encode("utf-8"), {}
        if "000114036126036226/form4.xml" in url:
            return 200, _payload("000114036126036226_form4.xml"), {}
        if "000114036126035359/form3.xml" in url:
            return 200, _payload("000114036126035359_form3.xml"), {}
        return 404, b"not found", {}

    return EdgarProvider(gate=RequestGate(gate=NetworkGate(environ={
        "RUSTERM_SEC_UA": FAKE_UA})), cik=320193, transport=transport)


# ── золотой разбор: значения вычитаны из самого payload ────────────────

def test_golden_form4_transactions_hand_checked():
    """Файл 000114036126036226_form4.xml: Newstead Jennifer (officer,
    SVP GC) продала 1438 акции 2026-09-08 по 317.23 — каждый
    ассерт разрешается в записанный payload указателем."""
    filing = parse_form4(_payload("000114036126036226_form4.xml"))
    assert filing.document_type == "4"
    assert filing.period == "2026-09-08"
    assert filing.issuer_cik == "0000320193"
    assert filing.issuer_name == "Apple Inc."
    assert filing.insider == "Newstead Jennifer"
    assert filing.role == "officer"
    assert filing.officer_title == "SVP, GC and Government Affairs"
    assert len(filing.transactions) == 1
    tx = filing.transactions[0]
    assert tx.date == "2026-09-08"
    assert tx.direction == "disposed"
    assert tx.shares == 1438.0
    assert tx.price == 317.23
    assert tx.security == "Common Stock"
    # указатель внутрь payload: значение сидит в transactionAmounts
    raw = _payload("000114036126036226_form4.xml").decode("utf-8")
    pointer = ("/ownershipDocument/nonDerivativeTable/"
               "nonDerivativeTransaction/transactionAmounts/"
               "transactionShares/value")
    head, leaf = pointer.rsplit("/", 1)
    node = _walk(raw, head)
    assert leaf in node and "<value>1438</value>" in node


def _walk(xml_text: str, path: str) -> str:
    """Минимальный резолвер указателя для проверки, что ассерт
    разрешается внутрь записанного payload (не в воздух)."""
    tags = [t for t in path.split("/") if t]
    pos = 0
    for tag in tags:
        needle = f"<{tag}>"
        idx = xml_text.find(needle, pos)
        assert idx != -1, f"{needle} не найден после {pos}"
        pos = idx + len(needle)
    end = xml_text.find(f"</{tags[-1]}>", pos)
    return xml_text[pos:end]


def test_golden_form3_has_no_transactions():
    """Form 3 — первоначальная декларация владения: сделок нет, и это
    не сбой разбора (файл 000114036126035359_form3.xml)."""
    filing = parse_form4(_payload("000114036126035359_form3.xml"))
    assert filing.document_type == "3"
    assert filing.transactions == []


def test_parser_refuses_foreign_root():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        parse_form4(b"<html><body>x</body></html>")


# ── сбор: document + raw, идемпотентность ──────────────────────────────

def test_collector_collects_documents_and_is_idempotent(tmp_path):
    conn, repos = _env(tmp_path)
    calls: list[str] = []
    provider = _fake_provider(_SUBMISSIONS, calls)
    code = _ingest_edgar_ownership(repos, "US-OWN", "i-o",
                                   "2026-09-13", provider=provider)
    assert code == 0
    docs = repos.document.for_issuer("i-o")
    assert len(docs) == 2, docs
    assert docs[0][2] == "xml"  # for_issuer: (sha, filename, format, ...)
    cov = next(c for c in repos.coverage.for_instrument("US-OWN")
               if c["block"] == "ownership")
    assert (cov["status"], cov["reason"]) == ("ready", None), cov
    # повтор: те же документы не пишутся (sha-идемпотентность) и
    # тел не качаются (кеш по каноническому URL; submissions уже в
    # памяти провайдера) — число сетевых вызовов не растёт
    calls_after_first = len(calls)
    code = _ingest_edgar_ownership(repos, "US-OWN", "i-o",
                                   "2026-09-13", provider=provider)
    assert code == 0
    assert len(repos.document.for_issuer("i-o")) == 2
    assert len(calls) == calls_after_first, (
        "повторный сбор сходил в сеть", calls)
    conn.close()


# ── D3: отказ остаётся честным ─────────────────────────────────────────

def test_issuer_without_ownership_forms_gets_named_reason(tmp_path,
                                                          capsys):
    """Лента есть, форм 3/4/5 нет -> coverage missing с именованной
    причиной source_has_no_disclosure; код 0, но это НЕ пустой успех:
    причина названа и в выводе, и в покрытии."""
    conn, repos = _env(tmp_path)
    no_ownership = {"filings": {"recent": {
        "form": ["10-K", "10-Q"],
        "accessionNumber": ["0000320193-26-000001",
                            "0000320193-26-000002"],
        "primaryDocument": ["aapl-20260927.htm", "aapl-20260627.htm"],
        "reportDate": ["2026-09-27", "2026-06-27"],
        "filingDate": ["2026-10-30", "2026-07-31"],
    }}}
    provider = _fake_provider(no_ownership, calls := [])
    code = _ingest_edgar_ownership(repos, "US-OWN", "i-o",
                                   "2026-09-13", provider=provider)
    assert code == 0
    cov = next(c for c in repos.coverage.for_instrument("US-OWN")
               if c["block"] == "ownership")
    assert (cov["status"], cov["reason"]) == (
        "missing", "source_has_no_disclosure"), cov
    out = capsys.readouterr().out
    assert "source_has_no_disclosure" in out
    conn.close()


# ── живой канал (N7: без контакта пропускается чисто) ──────────────────

def _live_ua() -> str | None:
    from rusterm import env as env_module
    env_module.load_env()
    import os
    return os.environ.get("RUSTERM_SEC_UA")


@pytest.mark.integration
@pytest.mark.live
def test_live_ownership_collection_one_issuer(tmp_path):
    if not _live_ua():
        pytest.skip("SEC_UA UNSET — network path not exercised")
    import os
    import subprocess
    import sys
    root = str(tmp_path / "app")
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join(
               [str(Path(__file__).resolve().parents[1]),
                os.environ.get("PYTHONPATH", "")])}
    def run(*argv):
        return subprocess.run(
            [sys.executable, "-m", "rusterm.cli", "--root", root,
             *argv], capture_output=True, text=True, env=env)
    assert run("init").returncode == 0
    added = run("add", "--ticker", "AAPL", "--market", "US")
    assert added.returncode == 0, added.stderr
    got = run("ingest", "--instrument", "US-AAPL", "--source",
              "ownership")
    assert got.returncode == 0, got.stderr
    assert "собрано документов" in got.stdout


# ── ТЗ-33 E1: сделки хранятся, цвет считается из сохранённого ──────────

def test_collector_persists_transactions_with_tenb5(tmp_path):
    """Сделки ложатся в ownership_transaction (миграция 44): у
    записи form 4 флаг 10b5-1 поднят (сноска F1 упоминает план),
    форма 3 сделок не даёт."""
    conn, repos = _env(tmp_path)
    calls: list[str] = []
    provider = _fake_provider(_SUBMISSIONS, calls)
    code = _ingest_edgar_ownership(repos, "US-OWN", "i-o",
                                   "2026-09-13", provider=provider)
    assert code == 0
    rows = repos.ownership.for_issuer("i-o")
    newstead = [r for r in rows if r["insider"] == "Newstead Jennifer"]
    assert len(newstead) == 1
    tx = newstead[0]
    assert (tx["date"], tx["direction"], tx["shares"]) == \
        ("2026-09-08", "disposed", 1438.0)
    assert tx["tenb5_one"] == 1
    assert all(r["tenb5_one"] == 0
               for r in rows if r["insider"] != "Newstead Jennifer")
    conn.close()


def test_insider_resolver_arithmetic_and_honest_empty(tmp_path):
    """Числитель из сохранённых сделок (окно 365 дней), знаменатель —
    market_cap_total последнего снапшота; без сделок или без
    знаменателя входа нет — серость честная, число не выдумывается."""
    from rusterm.core.governance import insider_net, \
        insider_net_inputs_from_store
    from rusterm.parsers.ownership import OwnershipTransaction

    conn, repos = _env(tmp_path)
    # пока ни сделок, ни снапшота — входа нет
    assert insider_net_inputs_from_store(repos, "US-OWN", "i-o",
                                         "2026-09-13") == {}
    sha = repos.document.put(_payload("000114036126036226_form4.xml"),
                             filename="form4.xml", format="xml",
                             page_count=1, byte_len=3153,
                             issuer_id="i-o")
    assert sha
    repos.ownership.replace_for_document(sha, "i-o", [
        OwnershipTransaction(insider="A", role="officer",
                             officer_title=None, date="2026-09-01",
                             direction="acquired", shares=200.0,
                             price=None, security="Common Stock"),
        OwnershipTransaction(insider="B", role="director",
                             officer_title=None, date="2026-08-20",
                             direction="disposed", shares=500.0,
                             price=300.0, security="Common Stock",
                             tenb5_one=True),
    ])
    # сделки есть, знаменателя нет — входа нет (0/None не выдумывается)
    assert insider_net_inputs_from_store(repos, "US-OWN", "i-o",
                                         "2026-09-13") == {}
    repos.snapshot.create_snapshot("s-own", "US-OWN", 1, "2026-09-13",
                                   None, "none", "ready")
    repos.snapshot.add_block("s-own", "fundamentals", "ready", None)
    repos.snapshot.insert_measure(
        "m-mcap-own", "s-own", "issuer", "i-o", "market_cap_total",
        "1000000.0", "USD", "2026-09-13", "2026-09-13",
        "market_cap_total", "v1", None, None)
    spec = insider_net_inputs_from_store(repos, "US-OWN", "i-o",
                                         "2026-09-13")
    inputs = spec["insider_net"]["inputs"]
    assert inputs["net_ratio"] == pytest.approx(-300.0 / 1_000_000.0)
    assert inputs["tenb5_net"] == -500.0
    assert inputs["net_shares"] == -300.0
    assert "buys=200,sells=500,net=-300sh" in \
        spec["insider_net"]["lineage_ref"]
    # цвет с названной долей 10b5-1 (BACKLOG 11)
    a = insider_net("US-OWN", inputs["net_ratio"], "2026-09-13",
                    spec["insider_net"]["lineage_ref"],
                    tenb5_net=inputs["tenb5_net"],
                    net_shares=inputs["net_shares"])
    assert a.color == "yellow"
    assert "tenb5_net=-500sh (167% of net)" in a.reason
    conn.close()
