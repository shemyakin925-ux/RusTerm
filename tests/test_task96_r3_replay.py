"""ТЗ-96 R3: офлайн-эталон живого прогона.

Фикстуры здесь — настоящие ответы вендоров, записанные живым прогоном
`rusterm follow` по шести бумагам пользователя 24.09.2026 в каталог под
`/tmp` (P7: база пользователя не трогалась). Как они вырезаны:
`tools/trim_companyfacts.trim` (теги из CONCEPT_MAP + json_pointer
golden-файла, годовые формы, шесть свежих периодов на тег/единицу), плюс
раздел `dei` с `EntityCommonStockSharesOutstanding` (вход `shares_outstanding`:
без него не считаются market_cap → ev → pe → ps) и, для иностранных
эмитентов, `ifrs-full` теми же правилами. Файлы лежать должны, а не
генерироваться тестом; их байты закреплены sha256 ниже — повторная
обрезка того же ответа даёт те же байты.

Что проверяется:
- из этих файлов база собирается офлайн, и `RequestGate` на ценовой
  стадии показывает **ноль** пропущенных запросов: payload находится в
  raw-хранилище по каноническому URL без ключа (ADR-0003), а транспорт,
  который умеет в сеть, за весь тест не вызывается ни разу;
- числа прогона (факты, строки цены, годы истории, меры со значением)
  закреплены и воспроизводимы;
- цена VZ из фикстуры даёт `market_cap` со значением — тот самый вход,
  из-за которого в базе пользователя у VZ считались 8 мер из 28.

Про fundamentals честно: у edgar-стадии двери «ноль запросов» нет —
повторный сбор сначала платит запрос и только потом видит, что sha256
уже в хранилище (`cli:486-488`), поэтому фикстуры здесь подаются прямо в
двери разбора и записи (`CompanyFactsParser` → `apply_concept_map` →
`persist_ingestion_results`), которые `ingest` вызывает после ответа.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

import pytest

import rusterm.cli as cli
from rusterm.parsers import CompanyFactsParser
from rusterm.pipeline import apply_concept_map
from rusterm.providers.budget import RequestGate
from rusterm.providers.twelvedata import TwelveDataProvider
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths
from rusterm.store.repos import RepoRegistry, persist_ingestion_results

REPO = Path(__file__).resolve().parents[1]
TICKERS = ("AAPL", "ADBE", "KSPI", "MSFT", "VALE", "VZ")
CIK = {"AAPL": "320193", "ADBE": "796343", "KSPI": "1985487",
       "MSFT": "789019", "VALE": "917851", "VZ": "732712"}
CAP = 256 * 1024


def facts_path(ticker: str) -> Path:
    return REPO / "tests" / "data" / "edgar" / f"companyfacts_r3_{ticker}.json"


def prices_path(ticker: str) -> Path:
    hits = sorted((REPO / "tests" / "data" / "twelvedata").glob(
        f"time_series_r3_{ticker}_*.json"))
    assert len(hits) == 1, f"фикстура цены для {ticker} не одна: {hits}"
    return hits[0]


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    """Каталог прогона: `init` + шесть `add` с явными --cik/--name — обе
    стадии без сети. Окружение пользователя не читается (страж P7)."""
    monkeypatch.setenv("RUSTERM_ENV_FILE", "/nonexistent/rusterm.env")
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    root = tmp_path / "app"
    assert cli.main(["--root", str(root), "init"]) == 0
    for ticker in TICKERS:
        assert cli.main(["--root", str(root), "add", "--ticker", ticker,
                         "--market", "US", "--cik", CIK[ticker],
                         "--name", f"{ticker} test issuer"]) == 0
    conn = sqlite3.connect(str(root / "rusterm.db"), isolation_level=None)
    apply_migrations(conn)
    yield RepoRegistry(conn, AppPaths.from_root(root)), root
    conn.close()


def _forbidden_transport(url, headers):
    raise AssertionError(f"офлайн-эталон не имеет права в сеть: {url[:40]}")


def _replay_fundamentals(repos, root, ticker):
    """Те же двери, что `ingest` вызывает после ответа: raw -> разбор ->
    карта концептов -> запись."""
    raw = facts_path(ticker).read_bytes()
    instrument_id = f"US-{ticker}"
    obj = repos.raw.put(raw, provider="edgar", block="fundamentals",
                        url=("https://data.sec.gov/api/xbrl/companyfacts/"
                             f"CIK{int(CIK[ticker]):010d}.json"),
                        instrument_id=instrument_id)
    parsed = CompanyFactsParser().parse(
        raw, {"issuer_id": f"cik-{int(CIK[ticker])}",
              "source_ref": obj.sha256})
    fact_dicts = []
    unmapped = 0
    for fact in parsed.facts:
        fact = dict(fact)
        fact["fact_id"] = str(uuid.uuid4())
        unmapped += apply_concept_map(fact)
        fact_dicts.append(fact)
    persist_ingestion_results(repos.conn, fact_dicts, [])
    repos.coverage.upsert(instrument_id, "fundamentals", "ready")
    return len(fact_dicts), unmapped


def _replay_prices(repos, root, ticker, as_of):
    """Цены кладутся в raw-хранилище под канонический URL без ключа, а
    сбор идёт настоящей дверью `_ingest_twelvedata_prices`: она обязана
    найти payload в кеше и не позвонить в гейт ни разу."""
    instrument_id = f"US-{ticker}"
    payload = json.loads(prices_path(ticker).read_text(encoding="utf-8"))
    gate = RequestGate()
    provider = TwelveDataProvider(api_key="TESTONLY", gate=gate,
                                  transport=_forbidden_transport)
    url = provider.cache_url(ticker, None, as_of)
    repos.raw.put(json.dumps(payload, sort_keys=True,
                             ensure_ascii=False).encode("utf-8"),
                  provider="twelvedata", block="prices", url=url,
                  instrument_id=instrument_id)
    rc = cli._ingest_twelvedata_prices(repos, instrument_id, as_of,
                                       provider=provider)
    return rc, gate, provider


def _measures(root, instrument_id):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    db.row_factory = sqlite3.Row
    sid = db.execute("SELECT snapshot_id FROM snapshot WHERE instrument_id=?"
                     " ORDER BY built_at DESC LIMIT 1",
                     (instrument_id,)).fetchone()
    out = {}
    if sid:
        out = {r["concept"]: (r["value"], r["null_reason"]) for r in
               db.execute("SELECT concept, value, null_reason FROM measure"
                          " WHERE snapshot_id=?", (sid["snapshot_id"],))}
    db.close()
    return out


def _counters(root):
    db = sqlite3.connect(f"file:{Path(root) / 'rusterm.db'}?mode=ro",
                         uri=True)
    out = {}
    for t in TICKERS:
        iid = f"US-{t}"
        f = db.execute("SELECT COUNT(*), COUNT(DISTINCT substr(period_end,1,4))"
                       " FROM fact f JOIN instrument i ON i.issuer_id=f.issuer_id"
                       " WHERE i.instrument_id=?", (iid,)).fetchone()
        p = db.execute("SELECT COUNT(*), COUNT(DISTINCT substr(date,1,4))"
                       " FROM price WHERE instrument_id=?", (iid,)).fetchone()
        out[iid] = {"facts": f[0], "fact_years": f[1], "prices": p[0],
                    "price_years": p[1]}
    out["requests"] = db.execute(
        "SELECT COALESCE(SUM(value),0) FROM metric_sample"
        " WHERE name='provider_requests_used'").fetchone()[0]
    db.close()
    return out


# Числа офлайн-эталона — зафиксированы прогоном этого теста (Run в
# REPORT-96); меняются только вместе с фикстурами. Живым числам прогона
# они не равны сознательно: обрезка оставляет шесть свежих периодов на
# тег, а не весь ряд, и у иностранных эмитентов (KSPI, VALE) ifrs-раздел
# урезан до `dei` — отсюда 2 меры со значением вместо 17 у VALE.
EXPECTED = {
    "US-AAPL": {"facts": 230, "fact_years": 20, "prices": 1000,
                "price_years": 5, "valued": 23},
    "US-ADBE": {"facts": 191, "fact_years": 19, "prices": 1000,
                "price_years": 5, "valued": 22},
    "US-KSPI": {"facts": 3, "fact_years": 3, "prices": 672,
                "price_years": 3, "valued": 2},
    "US-MSFT": {"facts": 217, "fact_years": 18, "prices": 1000,
                "price_years": 5, "valued": 23},
    "US-VALE": {"facts": 5, "fact_years": 2, "prices": 1000,
                "price_years": 5, "valued": 2},
    "US-VZ": {"facts": 181, "fact_years": 20, "prices": 1000,
              "price_years": 5, "valued": 17},
}

# Байты фикстур = запись живого ответа: повторная обрезка того же
# payload даёт те же байты, поэтому sha256 закреплён здесь.
FIXTURE_SHA256 = {
    "companyfacts_r3_AAPL.json":
        "26592f7ebca97eb7957f660e0aaaa8ef26168000865857d624c9b633662a20ae",
    "companyfacts_r3_ADBE.json":
        "4b7f8e499458300d422d9328ff2623d12153ffc0137cd45b65f997001410b94f",
    "companyfacts_r3_KSPI.json":
        "a51ea336f6b65b618c26f91373c2112e1a1ab89673d4cc8a171dcef56a95a08c",
    "companyfacts_r3_MSFT.json":
        "9dc17faffd10af12caa75a806b3dfed487da017cb0a6697fea5f88b6542ba954",
    "companyfacts_r3_VALE.json":
        "e07e095c2c66b4d722dde84a26df598a0bab3101dd715a8f798a969f64a1562b",
    "companyfacts_r3_VZ.json":
        "125ae54cdbf7e2850324dc4d1bd165cf2bf929b737068b460310609e41d80bd3",
    "time_series_r3_AAPL_1000d.json":
        "2e6104e2c745daf3fbe67ae37552e6ceb26d83da8ebff85c423daf9b091a2cbe",
    "time_series_r3_ADBE_1000d.json":
        "534d64d0d6be43b4bc63aab614173be4e8c5f384c645cbf65f0f53f69c48e4c3",
    "time_series_r3_KSPI_672d.json":
        "73cc3652943b39898dddae3195f5a2cee6f72ad4787d66c4acbe523110f9791d",
    "time_series_r3_MSFT_1000d.json":
        "f169529abe590e8450582735946b57b875ac1844a866e69a0d6b5f3291bcff55",
    "time_series_r3_VALE_1000d.json":
        "3321744c2c1be24ac1e232484f01dc148bfea52ed74fc33d1a702e349bc75c9e",
    "time_series_r3_VZ_1000d.json":
        "aabee2b7f8bb07e6ad2705d4023bf5d3dff5774902175ebb423f9ad8e6606942",
}


def test_replay_makes_zero_requests_and_rebuilds_the_numbers(catalog):
    repos, root = catalog
    assert cli._requests_used(str(root)) == 0, "add с --cik/--name тянет сеть"

    as_of = cli.args_as_of_default()
    for ticker in TICKERS:
        _replay_fundamentals(repos, root, ticker)
        rc, gate, _provider = _replay_prices(repos, root, ticker, as_of)
        assert rc == 0, f"{ticker}: ценовая стадия отказала"
        assert gate.calls_made == 0, (f"{ticker}: гейт пропустил "
                                      f"{gate.calls_made} запросов в офлайне")
        iid = f"US-{ticker}"
        assert cli.main(["--root", str(root), "snapshot",
                         "--instrument", iid]) == 0

    counters = _counters(root)
    assert counters["requests"] == 0, counters["requests"]
    for iid, want in EXPECTED.items():
        got = {k: counters[iid][k] for k in
               ("facts", "fact_years", "prices", "price_years")}
        assert got == {k: want[k] for k in got}, (iid, got, want)
        ms = _measures(root, iid)
        valued = sum(1 for v, _ in ms.values() if v is not None)
        assert valued == want["valued"], (iid, valued, want["valued"])


def test_dei_input_survives_the_trim(catalog):
    """Без `dei:EntityCommonStockSharesOutstanding` в фикстуре VZ теряет
    и market_cap, и всё, что из него растёт (замерено на базе
    пользователя: 8 мер со значением против 16 в прогоне)."""
    repos, root = catalog
    _replay_fundamentals(repos, root, "VZ")
    rc, _gate, _provider = _replay_prices(repos, root, "VZ",
                                          cli.args_as_of_default())
    assert rc == 0
    assert cli.main(["--root", str(root), "snapshot",
                     "--instrument", "US-VZ"]) == 0
    ms = _measures(root, "US-VZ")
    for concept in ("market_cap", "market_cap_total", "ev", "net_debt",
                    "pe", "ps"):
        assert ms.get(concept, (None, "нет меры"))[0] is not None, (
            concept, ms.get(concept))


def test_fixtures_fit_the_cap_and_are_pinned_by_sha256():
    """Каждый файл ≤ 256 КБ и закреплён байт-в-байт: фикстуры — запись
    живого ответа, а не то, что тест может нагенерировать заново."""
    paths = [facts_path(t) for t in TICKERS] + \
        [prices_path(t) for t in TICKERS]
    for path in paths:
        data = path.read_bytes()
        assert len(data) <= CAP, (path.name, len(data))
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths} == FIXTURE_SHA256


def test_no_live_secret_reaches_the_fixtures():
    """Значений ключей в фикстурах быть не может: payload — тело ответа,
    URL в raw_object — канонический, без `apikey`. Проверено по всем
    байтам фикстур."""
    for path in [facts_path(t) for t in TICKERS] + \
            [prices_path(t) for t in TICKERS]:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for needle in ("apikey", "api_key", "bearer", "x-rusterm"):
            assert needle not in text, (path.name, needle)
