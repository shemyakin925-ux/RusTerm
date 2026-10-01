"""ТЗ-97 Q4 (ТЗ-87 G3): эмитент 20-F, у которого в payload ДВА раздела.

Причина дыры названа по месту, а не по догадке. Живой ответ
`https://data.sec.gov/api/xbrl/companyfacts/CIK0001985487.json` (KSPI,
28.09.2026, 1 обращение из бюджета Q4) несёт `us-gaap` с ДВУМЯ тегами
(OtherAssets, OtherLiabilities — 4 строки, ни один не отображён) и
`ifrs-full` со 152 тегами (1015 строк, 924 из них в KZT). Парсер выбирал
ОДНУ таксономию на весь payload (`if "us-gaap" in facts_root: … elif
"ifrs-full"`), поэтому два мёртвых us-gaap-тега молча закрывали раздел
IFRS целиком: фактов отчётности у эмитента не рождалось ни одного, и все
меры отказывали. Тот же фильтр держал VALE (5 фактов вместо 48) и BHP.

Решение — не «усилить парсер», а две вещи, обе закреплены тестами:
1. разбираются ОБА финансовых раздела одного payload;
2. приоритет «us-gaap выигрывает» (TASK-18 §0.3 ruling 2) остаётся, но
   решает ПО КОНЦЕПТУ: ранги ifrs-full смещены на `_IFRS_RANK_OFFSET`
   (=100) между us-gaap (0) и обложкой dei (`_DEI_RANK_OFFSET`, =1000),
   а `_latest_canonical` на равных датах берёт минимальный ранг, а не
   первый попавшийся ряд — иначе источник входа зависел бы от порядка
   строк в базе.

Фикстура `companyfacts_q4_kspi.json` — настоящий ответ по тому же
рецепту, что и r3-набор: `tools/trim_companyfacts.trim` (теги карт,
годовые формы 20-F/40-F/6-K и 10-K, шесть свежих периодов на тег и
единицу), плюс раздел `us-gaap` БЕЗ фильтра по карте — те самые
OtherAssets и OtherLiabilities, из-за которых раздел IFRS и терялся, и
`dei` как подан (EntityCommonStockSharesOutstanding — вход
shares_outstanding, ТЗ-78 Y2). Регенерация даёт те же байты.

Что проверяется:
- байты и происхождение фикстуры, оба раздела в ней;
- парсер одного payload даёт факты всех трёх таксономий;
- на одном концепте us-gaap берёт верх над ifrs-full при равных датах
  (end-to-end: снапшот из синтетического payload с обоими разделами);
- KSPI: 76 фактов (us-gaap 4 / ifrs-full 69 / dei 3), 4 неотображённых,
  29 мер, из них девять со значением — ровно названные; «было» той же
  фикстурой без раздела ifrs-full: ни одна из названных мер;
- каждый отказ назван словом из словаря `rusterm.reasons`, а не пустой
  клеткой (Done when Q4);
- trim-инструмент держит оба раздела и форму 20-F, иначе фикстуру
  нельзя перегенерировать.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.normalize.concepts import (
    _DEI_RANK_OFFSET,
    _IFRS_RANK_OFFSET,
    canonical_for,
    priority_rank,
)
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.providers.budget import RequestGate
from rusterm.providers.twelvedata import TwelveDataProvider
from rusterm.reasons import is_known_reason
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry, persist_ingestion_results

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "data" / "edgar" / "companyfacts_q4_kspi.json"
FIXTURE_SHA256 = ("4333c899e4d89d78b8f476b901210ad1f16538099823921addda5a"
                  "e45675fafa")
CIK = "1985487"
# Второй герой Q4 — уже лежавшая в репозитории фикстура r3_VALE
VALE_CIK = "917851"
VALE_FIXTURE = REPO / "tests" / "data" / "edgar" / "companyfacts_r3_VALE.json"
# Дата pinned: числа эталона не должны стареть вместе с календарём —
# окно давности (ТЗ-55 Y1) иначе превратит valued-строки в stale_data.
AS_OF = "2026-09-28"

# Девять мер, которые KSPI получил из раздела ifrs-full. До правки — ни
# одной: фактов отчётности у эмитента не было. pe и ps в этом списке
# были до ТЗ-104 P1: они считались через валютный шов (цена USD, отчётность
# KZT) — теперь отказываются, и дыра закрыта (см.
# test_pe_and_ps_on_kspi_refuse_the_off_rate_quotient). gross_margin —
# ТЗ-104 P4: мера читает посчитанную gross_profit, поэтому KSPI, который
# GrossProfit не подаёт, получил и маржу.
KSPI_VALUED = {
    "asset_turnover", "effective_tax", "gross_margin", "gross_profit",
    "market_cap", "market_cap_total", "net_margin", "roe", "roe_incl_nci",
    # ТЗ-108 W1: по ряду цены, не по фактам отчётности
    "drawdown", "total_return",
}
# Меры, чьи входы — только факты отчётности: на «стороне было» (payload
# без раздела ifrs-full) они обязаны отказаться все до единой.
# gross_margin стоит здесь и после ТЗ-104 P4: цепочка ведёт к gross_profit,
# а тот без раздела IFRS не считается.
FACT_ONLY_MEASURES = ("asset_turnover", "effective_tax", "gross_margin",
                      "gross_profit", "net_margin", "roe", "roe_incl_nci")


def _forbidden_transport(url, headers):
    raise AssertionError(f"офлайн-тест не имеет права в сеть: {url[:40]}")


def _entry(value: float, accn: str, filed: str, instant: bool = False,
           form: str = "20-F", end: str = "2025-12-31") -> dict:
    """Запись companyfacts в формате ответа SEC; числа SYNTHETIC."""
    entry = {"val": value, "accn": accn, "form": form, "fy": 2025,
             "fp": "FY", "filed": filed, "end": end}
    if not instant:
        entry["start"] = f"{int(end[:4]) - 1}-01-01"
    return entry


def _two_section_doc(revenue_gaap: float, revenue_ifrs: float) -> dict:
    """SYNTHETIC payload с обоими разделами, закрывающими один концепт
    (`revenue`) на одну дату. Баланс подан одинаково в обоих разделах,
    чтобы мера различала именно выбор источника по revenue. Два accession
    — как у настоящего 10-K: сравнительный прошлый год в отдельной
    подаче, иначе `determine_basis` помечает его restated."""
    return {
        "cik": 2, "entityName": "SYNTHETIC two-section issuer",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [_entry(revenue_gaap, "A",
                                             "2026-02-15")]}},
                "Assets": {"units": {"USD": [
                    _entry(100.0, "A", "2026-02-15", instant=True),
                    _entry(100.0, "B", "2025-03-01", instant=True,
                           end="2024-12-31")]}},
            },
            "ifrs-full": {
                "Revenue": {"units": {
                    "USD": [_entry(revenue_ifrs, "A", "2026-02-15")]}},
                "Assets": {"units": {"USD": [
                    _entry(100.0, "A", "2026-02-15", instant=True),
                    _entry(100.0, "B", "2025-03-01", instant=True,
                           end="2024-12-31")]}},
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {"units": {
                    "shares": [_entry(5.0, "A", "2026-02-15",
                                      instant=True)]}},
            },
        },
    }


def _ingest(repos: RepoRegistry, raw: bytes, issuer_id: str) -> tuple:
    """Те же двери, что `ingest` вызывает после ответа: разбор -> карта
    концептов -> запись."""
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": issuer_id, "source_ref": "q4-sandbox"})
    rows = []
    unmapped = 0
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        unmapped += apply_concept_map(fact)
        rows.append(fact)
    persist_ingestion_results(repos.conn, rows, [])
    by_taxonomy: dict[str, int] = {}
    for row in rows:
        prefix = row["concept"].split(":", 1)[0]
        by_taxonomy[prefix] = by_taxonomy.get(prefix, 0) + 1
    return parsed, len(rows), by_taxonomy, unmapped


def _read_measures(root: Path, instrument_id: str) -> dict:
    db = sqlite3.connect(f"file:{root / 'rusterm.db'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    sid = db.execute(
        "SELECT snapshot_id FROM snapshot WHERE instrument_id=?"
        " AND status='ready' ORDER BY built_at DESC LIMIT 1",
        (instrument_id,)).fetchone()
    assert sid, "снапшот не собрался"
    out = {r["concept"]: (r["value"], r["null_reason"])
           for r in db.execute(
               "SELECT concept, value, null_reason FROM measure"
               " WHERE snapshot_id=? AND scope='issuer'",
               (sid["snapshot_id"],))}
    db.close()
    return out


def _sandbox(dir_path: Path, raw: bytes, ticker: str, with_prices: bool = True,
             cik: str = CIK) -> dict:
    """Чистая база под одним инструментом: facts -> (цена из raw-кеша) ->
    снапшот. Сети нет: транспорт, который умеет в сеть, не вызывается, а
    гейт фиксирует ноль обращений."""
    root = dir_path / "app"
    instrument_id = f"US-{ticker}"
    # module-фикстуры собираются до function-автозуки conftest, поэтому
    # изоляция окружения повторяется здесь явно (страж P7: каталог
    # пользователя не читается, путь к базе задан --root).
    old_env = os.environ.get("RUSTERM_ENV_FILE")
    os.environ["RUSTERM_ENV_FILE"] = "/nonexistent/rusterm.env"
    os.environ.pop("RUSTERM_DATA", None)
    try:
        assert cli.main(["--root", str(root), "init"]) == 0
        assert cli.main(["--root", str(root), "add", "--ticker", ticker,
                         "--market", "US", "--cik", cik,
                         "--name", f"{ticker} Q4 sandbox"]) == 0
        conn = sqlite3.connect(str(root / "rusterm.db"),
                               isolation_level=None)
        apply_migrations(conn)
        repos = RepoRegistry(conn, AppPaths.from_root(root))
        # Тикер обязан действовать на pinned AS_OF, а `rusterm add` ставит
        # valid_from = сегодня: без этой строки тест краснел на следующий
        # календарный день (проверка 11 приёмки пересекла полночь и выдала
        # «у 'US-KSPI' нет тикера на 2026-09-28»). Песочница объявляет
        # листинг с 2015-01-01 — как у живой бумаги, — и прогон перестаёт
        # зависеть от даты, в которой его запустили.
        repos.instrument.add_ticker_history(f"{instrument_id}-listing",
                                            ticker, "2015-01-01", None,
                                            "sandbox", None)
        repos.raw.put(raw, provider="edgar", block="fundamentals",
                      url=("https://data.sec.gov/api/xbrl/companyfacts/"
                           f"CIK{int(cik):010d}.json"),
                      instrument_id=instrument_id)
        _parsed, facts, by_taxonomy, unmapped = _ingest(
            repos, raw, f"cik-{int(cik)}")
        repos.coverage.upsert(instrument_id, "fundamentals", "ready")

        gate = RequestGate()
        if with_prices:
            hits = sorted((REPO / "tests" / "data" / "twelvedata").glob(
                f"time_series_r3_{ticker}_*.json"))
            assert len(hits) == 1, f"фикстура цены для {ticker} не одна"
            payload = json.loads(hits[0].read_text(encoding="utf-8"))
            provider = TwelveDataProvider(api_key="TESTONLY", gate=gate,
                                          transport=_forbidden_transport)
            url = provider.cache_url(ticker, None, AS_OF)
            repos.raw.put(json.dumps(payload, sort_keys=True,
                                     ensure_ascii=False).encode("utf-8"),
                          provider="twelvedata", block="prices", url=url,
                          instrument_id=instrument_id)
            rc = cli._ingest_twelvedata_prices(repos, instrument_id, AS_OF,
                                               provider=provider)
            assert rc == 0, rc
        assert gate.calls_made == 0, gate.calls_made

        assert cli.main(["--root", str(root), "snapshot",
                         "--instrument", instrument_id,
                         "--as-of", AS_OF]) == 0
        conn.close()
    finally:
        if old_env is None:
            os.environ.pop("RUSTERM_ENV_FILE", None)
        else:
            os.environ["RUSTERM_ENV_FILE"] = old_env

    return {"root": root, "facts": facts, "by_taxonomy": by_taxonomy,
            "unmapped": unmapped,
            "measures": _read_measures(root, instrument_id)}


@pytest.fixture(scope="module")
def fixture_doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def kspi_sandbox(tmp_path_factory):
    """KSPI на полной фикстуре — «стало»."""
    return _sandbox(tmp_path_factory.mktemp("q4-full"),
                    FIXTURE.read_bytes(), "KSPI")


@pytest.fixture(scope="module")
def kspi_without_ifrs(tmp_path_factory):
    """Тот же payload без раздела ifrs-full — «было»."""
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc["facts"].pop("ifrs-full")
    raw = json.dumps(doc, separators=(",", ":"),
                     sort_keys=True).encode("utf-8")
    return _sandbox(tmp_path_factory.mktemp("q4-nifr"), raw, "KSPI")


def test_fixture_bytes_are_the_recorded_response():
    """Байты фикстуры = запись живого ответа: повторная регенерация тем
    же рецептом даёт те же байты, и это закреплено здесь."""
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    doc = json.loads(raw)
    # cik в записи — строка «0001985487», как его отдаёт API; фикстура
    # не правится, чтобы не ронять sha256 записи
    assert int(doc["cik"]) == int(CIK)
    assert "KASPI" in doc["entityName"].upper()


@pytest.fixture(scope="module")
def vale_sandbox(tmp_path_factory):
    """VALE на уже лежавшей в репозитории r3-фикстуре: payload всегда нёс
    ifrs-раздел, не разбирался он."""
    return _sandbox(tmp_path_factory.mktemp("q4-vale"),
                    VALE_FIXTURE.read_bytes(), "VALE", cik=VALE_CIK)


def test_vale_lost_the_same_section_to_the_same_filter(vale_sandbox):
    """Тот же фильтр, тот же ущерб на VALE: 48 фактов вместо 5 и 11 мер
    со значением вместо 0 — строки отчётности, а не капитализация.

    Отказ M1 (число акций с обложки 2012-12-31) остаётся отказом: он
    назван здесь явно, чтобы рост `valued` нельзя было прочитать как
    «дверь давности сломалась».
    """
    assert vale_sandbox["facts"] == 48
    assert vale_sandbox["by_taxonomy"] == {"ifrs-full": 43, "dei": 5}
    measures = vale_sandbox["measures"]
    valued = {c for c, (v, _r) in measures.items() if v is not None}
    # ТЗ-108 W1: доходность и просадка — по ряду цены (миграция 48)
    assert valued == {"asset_turnover", "drawdown", "ebitda",
                      "effective_tax", "gross_margin", "gross_profit",
                      "interest_coverage", "net_margin", "nopat",
                      "operating_margin", "roe", "roe_incl_nci",
                      "total_return"}, sorted(valued)
    assert measures["market_cap"][1] == (
        "stale_input: shares_outstanding (2012-12-31)")
    assert measures["net_debt"][1] == ("missing_data: st_investments, "
                                       "total_debt")


def test_payload_carries_both_sections_and_the_two_dead_tags(fixture_doc):
    """Причина в фактах: us-gaap-раздел KSPI — два тега вне карты.

    Они и сбрасывали выбор парсера на us-gaap: ни revenue, ни net_income
    там нет, а раздел ifrs-full при этом не парсился вовсе.
    """
    facts = fixture_doc["facts"]
    assert set(facts) == {"dei", "ifrs-full", "us-gaap"}
    assert sorted(facts["us-gaap"]) == ["OtherAssets", "OtherLiabilities"]
    for tag in facts["us-gaap"]:
        assert canonical_for(tag, "us-gaap") is None
    assert "Revenue" in facts["ifrs-full"]
    assert "CostOfSales" in facts["ifrs-full"]
    assert "EntityCommonStockSharesOutstanding" in facts["dei"]


def test_parser_reads_every_financial_section_of_one_payload():
    """Один payload — оба финансовых раздела + обложка: ни один не
    отбрасывается (было: если us-gaap есть, ifrs-full не парсился)."""
    doc = _two_section_doc(1000.0, 999.0)
    parsed = CompanyFactsParser().parse(json.dumps(doc).encode("utf-8"),
                                        {"issuer_id": "cik-2"})
    taxonomies = {f["concept"].split(":", 1)[0] for f in parsed.facts}
    assert taxonomies == {"us-gaap", "ifrs-full", "dei"}
    assert parsed.unparsed == 0


def test_us_gaap_wins_the_concept_when_both_sections_close_it(tmp_path):
    """Ruling 2 сохранено по-новому: us-gaap берёт верх НАД ifrs-full по
    одному концепту, а не отбрасыванием всего раздела.

    Оба раздела закрывают `revenue` на одну дату разными числами. Если бы
    приоритет решался порядком строк в базе, мера была бы
    недетерминирована; выбирает источник ранг тега.
    """
    root = tmp_path / "prio"
    sandbox = _sandbox(root, json.dumps(_two_section_doc(1000.0, 999.0)
                                       ).encode("utf-8"), "SYNTH",
                       with_prices=False)
    assert sandbox["by_taxonomy"] == {"us-gaap": 3, "ifrs-full": 3,
                                      "dei": 1}
    value, reason = sandbox["measures"]["asset_turnover"]
    # us-gaap: 1000 / 100; ifrs-full дал бы 999 / 100 = 9.99
    assert reason is None, reason
    assert value is not None and abs(float(value) - 10.0) < 1e-9, value


def test_ifrs_only_concept_still_parses_and_maps(kspi_sandbox):
    """Раздел ifrs-full несёт меры, которых у эмитента в us-gaap нет
    вовсе: revenue/net_income/cogs приходят только из IFRS."""
    assert kspi_sandbox["facts"] == 76
    assert kspi_sandbox["by_taxonomy"] == {"us-gaap": 4, "ifrs-full": 69,
                                           "dei": 3}
    assert kspi_sandbox["unmapped"] == 4
    assert kspi_sandbox["measures"]["net_margin"][0] is not None


def test_rank_offsets_keep_taxonomy_order_documented():
    """us-gaap (0) < ifrs-full (_IFRS_RANK_OFFSET) < dei
    (_DEI_RANK_OFFSET) — на этом стоит выбор источника входа."""
    assert _IFRS_RANK_OFFSET == 100
    assert _DEI_RANK_OFFSET == 1000
    assert priority_rank("revenue",
                         "RevenueFromContractWithCustomerExcludingAssessedTax",
                         "us-gaap") == 0
    assert priority_rank("revenue", "Revenue", "ifrs-full") == _IFRS_RANK_OFFSET
    assert (priority_rank("total_equity_incl_nci", "Equity", "ifrs-full")
            == _IFRS_RANK_OFFSET)
    assert (priority_rank("shares_outstanding",
                          "EntityCommonStockSharesOutstanding", "dei")
            >= _DEI_RANK_OFFSET)


def test_kspi_measure_counts_and_named_refusals(kspi_sandbox):
    """29 мер, 9 со значением — ровно названные (Done when Q4: счёт
    «было → стало» закреплён тестом, а не только отчётом)."""
    measures = kspi_sandbox["measures"]
    assert len(measures) == 29
    valued = {c for c, (v, _r) in measures.items() if v is not None}
    assert valued == KSPI_VALUED, sorted(valued)
    # cogs <- CostOfSales из ifrs-full.v3: без него gross_profit
    # отказывал missing_data: cogs там, где себестоимость подана
    assert measures["gross_profit"][0] is not None


def test_kspi_without_the_ifrs_section_is_the_old_zero(kspi_without_ifrs):
    """Тот же payload без раздела ifrs-full — ровно то, что было до
    правки: меры, которым нужны факты отчётности, отказывают все до
    единой (в базе пользователя у KSPI было 3 факта и 0 мер со
    значением)."""
    measures = kspi_without_ifrs["measures"]
    assert kspi_without_ifrs["by_taxonomy"] == {"us-gaap": 4, "dei": 3}
    for concept in FACT_ONLY_MEASURES:
        value, reason = measures[concept]
        assert value is None, f"{concept} посчиталась без раздела IFRS"
        assert reason and is_known_reason(reason), reason
    # market_cap держится на обложке dei — он не из этого раздела и в
    # «было» тоже был числом
    assert measures["market_cap"][0] is not None


def test_every_refusal_is_a_word_from_the_dictionary(kspi_sandbox):
    """Done when Q4: пустой клетки нет ни в одном отказе, и причина —
    слово из словаря, а не выдуманная строка."""
    measures = kspi_sandbox["measures"]
    for concept, (value, reason) in sorted(measures.items()):
        if value is not None:
            continue
        assert reason, f"{concept}: пустой null_reason"
        assert is_known_reason(reason), f"{concept}: {reason}"
    assert measures["fcf"][1] == "missing_data: capex"
    assert measures["ebitda"][1] == "missing_data: operating_income"
    assert measures["net_debt"][1] == ("missing_data: st_investments, "
                                       "total_debt")


def test_pe_and_ps_on_kspi_refuse_the_off_rate_quotient(kspi_sandbox):
    """ТЗ-104 P1: дыра, которую этот файл держал как замер, закрыта.

    pe/ps считались, хотя цена в USD, а отчётность в KZT: частное
    off-rate в ~5 раз. K6 проверял валюту у pb/div_yield/roic, а у pe/ps
    такой проверки не было — дыра существовала до правки (на копии базы
    пользователя US-AMX: факты MXN, цена USD, pe и ps со значением) и
    Q4 расширила её на KSPI. Замер был записан в Disputed ТЗ-97 Q4 и
    разрешился правкой: обе меры отказывают, отказ называет обе валюты,
    а не одну из них.
    """
    db = sqlite3.connect(f"file:{kspi_sandbox['root'] / 'rusterm.db'}"
                         "?mode=ro", uri=True)
    fact_cur = {r[0] for r in db.execute(
        "SELECT DISTINCT currency FROM fact"
        " WHERE currency NOT IN ('shares', 'pure')")}
    price_cur = {r[0] for r in db.execute(
        "SELECT DISTINCT currency FROM price")}
    db.close()
    assert fact_cur == {"KZT"} and price_cur == {"USD"}
    for concept in ("pe", "ps"):
        value, reason = kspi_sandbox["measures"][concept]
        assert value is None, f"{concept} всё ещё делит USD на KZT"
        assert reason == "currency_mismatch: KZT, USD", (concept, reason)


def test_trim_tool_keeps_both_sections_and_the_20f_form():
    """Без этого фикстуру нельзя перегенерировать: обрезка держала одну
    таксономию и форму 10-K, то есть 20-F эмитента вырезалась в ноль."""
    sys.path.insert(0, str(REPO))
    from tools.trim_companyfacts import _FORMS_BY_TAXONOMY, trim

    doc = _two_section_doc(10.0, 11.0)
    doc["facts"]["us-gaap"]["RevenueFromContractWithCustomer"
                           "ExcludingAssessedTax"]["units"]["USD"][0][
        "form"] = "10-K"
    doc["facts"]["us-gaap"].pop("Assets")
    doc["facts"]["ifrs-full"].pop("Assets")
    out = trim(doc)
    assert sorted(out["facts"]) == ["ifrs-full", "us-gaap"]
    assert sorted(out["facts"]["ifrs-full"]) == ["Revenue"]
    assert "20-F" in _FORMS_BY_TAXONOMY["ifrs-full"]
    assert "40-F" in _FORMS_BY_TAXONOMY["ifrs-full"]
