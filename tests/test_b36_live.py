"""B36 (ТЗ-58 C2): живая модель через четыре read-only инструмента,
ни одно число мимо гварда цитат.

МАРКЕР: живой прогон — только с RUSTERM_LIVE=1 и ключом в окружении;
обычный набор тест пропускает (нет сети, нет ключа — зелено).

Пять вопросов на записанных ответах EDGAR (tests/data/edgar, офлайн
данные, сеть идёт только к модели): два с полными данными (CNQ
net_margin, CNQ roe_incl_nci), два с серой мерой (CNQ roe —
missing_data: total_equity; CNQ fcf — stale_data), один заведомо без
данных (эмитент без снапшота). Для каждого зафиксировано, что
вернулось: ответ с цитатой, отказ с причиной, или отказ гварда.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

import pytest

from rusterm.core.chat import ChatSession, save_transcript
from rusterm.core.snapshot import SnapshotBuilder
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import (Instrument, Issuer, RawRepo,
                                 RepoRegistry,
                                 persist_ingestion_results)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RUSTERM_LIVE") != "1",
        reason="живой прогон: только с RUSTERM_LIVE=1 (маркер); "
               "обычный набор не тратит сеть и не требует ключа"),
]

DATA = Path(__file__).resolve().parents[1] / "tests" / "data" / "edgar"

QUESTIONS = [
    # (вопрос, ожидание: full | gray | void)
    ("Какая чистая маржа (net_margin) у CNQ? Назови число и период.",
     "full"),
    ("Какой roe_incl_nci у CNQ? Назови значение.", "full"),
    ("Какой roe у CNQ?", "gray"),
    ("Какой свободный денежный поток (fcf) у CNQ?", "gray"),
    ("Какая выручка у эмитента с тикером VOID на рынке US?", "void"),
]

MAX_CALLS_BUDGET = 40


@pytest.fixture(scope="module")
def live_env(tmp_path_factory):
    from rusterm import env as env_module
    # conftest герметичен: RUSTERM_ENV_FILE указывает на пустышку.
    # Живой маркерный прогон — единственное место, где читается
    # настоящий ~/.rusterm.env (та же дверь, что у CLI)
    os.environ["RUSTERM_ENV_FILE"] = str(
        Path.home() / ".rusterm.env")
    env_module.load_env()
    if not os.environ.get("RUSTERM_LLM_API_KEY"):
        pytest.skip("ключа модели нет в окружении")
    paths = AppPaths.from_root(tmp_path_factory.mktemp("b36") / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    for ticker, issuer_market in (("CNQ", "CA"), ("NGGTF", "US")):
        payload = (DATA / f"companyfacts_m6_{ticker}.json").read_bytes()
        cik = json.loads(payload)["cik"]
        repos.instrument.upsert_issuer(Issuer(
            f"i-{ticker}", ticker, issuer_market, str(cik), None,
            "ifrs-full", "CAD" if issuer_market == "CA" else "USD"))
        repos.instrument.upsert_instrument(Instrument(
            f"in-{ticker}", f"i-{ticker}", None, "common", "active",
            None))
        # резолвер тикера живёт на листинге + истории: без них
        # resolve_ticker честно отвечает not_found и вопрос не доходит
        # до данных
        from rusterm.store.repos import Listing
        repos.instrument.upsert_listing(Listing(
            f"l-in-{ticker}", f"in-{ticker}", "NASDAQ", "USD", 1,
            None, None))
        repos.instrument.add_ticker_history(
            f"l-in-{ticker}", ticker, "2000-01-01", None, None, None)
        url = (f"https://data.sec.gov/api/xbrl/companyfacts/"
               f"CIK{cik:010d}.json")
        obj = RawRepo(paths, repos.conn).put(
            payload, provider="edgar", block="fundamentals", url=url)
        parsed = CompanyFactsParser().parse(
            payload, {"issuer_id": f"i-{ticker}",
                      "source_ref": obj.sha256})
        fact_dicts = []
        for fact in parsed.facts:
            fact = dict(fact)
            fact["fact_id"] = str(uuid.uuid4())
            apply_concept_map(fact)
            fact_dicts.append(fact)
        persist_ingestion_results(repos.conn, fact_dicts, [])
        builder = SnapshotBuilder(repos.snapshot, repos.peer_set,
                                  coverage_repo=repos.coverage)
        builder.build(f"in-{ticker}", f"i-{ticker}", "2026-09-09")
    # заведомо пустой эмитент: инструмент есть, снапшота нет
    repos.instrument.upsert_issuer(Issuer(
        "i-VOID", "Void Corp", "US", "999", None, "us-gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-VOID", "i-VOID", None, "common", "active", None))
    yield repos, paths, conn
    conn.close()


def test_b36_live_five_questions(live_env, tmp_path):
    repos, paths, conn = live_env
    from rusterm import env as env_module
    env_module.load_env()
    from rusterm.core.llm import make_chat_client
    # conftest (function-scope) возвращает пустой RUSTERM_ENV_FILE —
    # живому прогону нужен настоящий; ключ уже загружен фикстурой
    os.environ["RUSTERM_ENV_FILE"] = str(Path.home() / ".rusterm.env")
    from rusterm import env as env_module
    env_module.load_env()  # conftest вычистил имена — грузим заново
    client = make_chat_client()
    reason = getattr(client, "_reason", None)
    if reason:
        pytest.skip(f"модель недоступна: {reason}")

    session = ChatSession(repos, client)
    session_id = "b36-live"
    results = []
    for question, kind in QUESTIONS:
        result = session.ask(question)
        if result.get("rejected"):
            reason_text = result.get("reason") or ""
            token = reason_text.split(":", 1)[0]
            assert token == "guard_rejected_uncited_number" or \
                is_known_reason(token) or token == "no_data", \
                (question, reason_text)
            results.append({"question": question, "kind": kind,
                            "outcome": "refusal",
                            "reason": reason_text})
        else:
            answer = result.get("answer") or ""
            citations = result.get("citations") or []
            import re
            numbers = re.findall(r"\d[\d.,]*", answer)
            if numbers:
                assert citations, (question, answer,
                                   "число без цитаты")
            results.append({"question": question, "kind": kind,
                            "outcome": "answer",
                            "answer_head": answer[:160],
                            "citations": citations[:3]})
        save_transcript(repos, session, session_id)
    # результаты пишутся ДО ассертов: падение не прячет измерения
    (tmp_path / "b36_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("B36_RESULTS:", tmp_path / "b36_results.json")
    assert len(results) == 5
    for r in results:
        if r["kind"] == "full" and r["outcome"] == "answer":
            import re
            digits = re.findall(r"\d[\d.,]*", r.get("answer_head", ""))
            # ответ с цифрами обязан нести цитаты; без цифр цитаты не нужны
            if digits:
                assert r["citations"], r
    totals = repos.chat_transcript.calls_totals()
    print("B36_TOTALS:", json.dumps(totals))
    assert totals["calls_total"] <= MAX_CALLS_BUDGET, \
        "бюджет ТЗ-58 C2 (до 40 вызовов) превышен"
