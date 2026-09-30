"""ТЗ-104 P6: числитель `insider_net` — в деньгах, а не «акций на доллар».

Было (governance.v1). Числитель — «куплено минус продано» в акциях,
знаменатель — `market_cap_total` в деньгах. Отношение, которое сравнивается
с порогами §4 («чистые покупки больше 0,1% капитализации»), имеет
размерность «акций на доллар»: оно меняется, когда меняется цена, даже
если инсайдеры не сделали ничего, и при цене 250 недооценивает разгон
сделки в 250 раз. Записано в REPORT-103, «Спорное» 15; решение
координатора — числитель в деньгах (ТЗ-104, таблица решений, пункт 15).

Стало (governance.v2). Числитель — сумма «акции × close за ДАТУ сделки».
Close берётся по дате каждой сделки (`price_as_of`), поэтому котировка
более позднего дня в числитель не попадает. Валюта числителя — валюта
котировки, и она обязана совпасть с единицей `market_cap_total`: без
этого отношения сравнивались бы фунты с долларами. Нет цены на дату
сделки — ряд серый с именованной причиной: число не достраивается ни
последней котировкой, ни ценой из формы.

| зуб | было (v1) | стало (v2) |
|---|---|---|
| две сделки, цены 100 и 200, кэп 1 000 000 | `-0.0003` → yellow | `-0.08` → red |
| цены вдвое и кэп вдвое | `-0.00015` (отношение упало) | `-0.08` (то же) |
| цен нет вовсе | число из акций | `ownership_without_deal_price` |
| одна сделка из двух без цены | `+0.02` → green | `ownership_without_deal_price` |
| цены в GBP, кэп в USD | `-0.08` без оговорки | `insider_deal_currency_mismatch` |
| доля 10b5-1 | `tenb5_net=-100000sh` | `tenb5_net=-100000 (125% of net)` |
| версия метода | `governance.v1` | `governance.v2`, история v1 цела |
| цены удвоились, сделок нет | серый ряд | тот же серый ряд (Done when) |
"""
import sqlite3
from pathlib import Path

import pytest

from rusterm.cli import _build_parser
from rusterm.core.governance import (GREY_REASONS, INDICATORS, METHOD_VERSION,
                                     grey_closing, grey_reason_text,
                                     insider_net,
                                     insider_net_inputs_from_store,
                                     produce_assessments)
from rusterm.parsers.ownership import OwnershipTransaction
from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir
from rusterm.store.repos import Instrument, Issuer, RepoRegistry

CORE_ROOT = Path(__file__).resolve().parents[1]
_PAYLOAD = (CORE_ROOT / "tests" / "data" / "edgar" / "ownership"
            / "000114036126036226_form4.xml")
_THRESHOLDS_DOC = CORE_ROOT / "docs" / "adr" / "0026-insider-net-v-dengah.md"

_AS_OF = "2026-09-13"
_BUY_DATE = "2026-09-01"    # 200 акций куплено
_SELL_DATE = "2026-08-20"  # 500 акций продано по плану 10b5-1
_MCAP = "1000000.0"


def _env(tmp_path):
    paths = AppPaths.from_root(tmp_path / "app")
    ensure_app_dir(paths)
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    apply_migrations(conn)
    repos = RepoRegistry(conn, paths)
    repos.instrument.upsert_issuer(Issuer(
        "i-p6", "Apple Inc.", "US", "320193", None, "us_gaap", "USD"))
    repos.instrument.upsert_instrument(Instrument(
        "US-P6", "i-p6", None, "common", "active", None))
    return conn, repos


def _deals(repos):
    """Две сделки через тот же репозиторий, что пишет сборщик: 200
    акций куплено, 500 продано по плану 10b5-1."""
    sha = repos.document.put(_PAYLOAD.read_bytes(), filename="form4.xml",
                             format="xml", page_count=1, byte_len=3153,
                             issuer_id="i-p6")
    repos.ownership.replace_for_document(sha, "i-p6", [
        OwnershipTransaction(insider="A", role="officer",
                             officer_title=None, date=_BUY_DATE,
                             direction="acquired", shares=200.0,
                             price=None, security="Common Stock"),
        OwnershipTransaction(insider="B", role="director",
                             officer_title=None, date=_SELL_DATE,
                             direction="disposed", shares=500.0,
                             price=300.0, security="Common Stock",
                             tenb5_one=True),
    ])
    return sha


def _mcap(repos, value=_MCAP, unit="USD"):
    repos.snapshot.create_snapshot("s-p6", "US-P6", 1, _AS_OF, None,
                                   "none", "ready")
    repos.snapshot.add_block("s-p6", "fundamentals", "ready", None)
    repos.snapshot.insert_measure(
        "m-p6", "s-p6", "issuer", "i-p6", "market_cap_total", value, unit,
        _AS_OF, _AS_OF, "market_cap_total", "v1", None, None)


def _prices(repos, *, buy_close=None, sell_close=None, later_close=None,
            currency="USD"):
    """Котировки ровно на те даты, которые названы: `later_close` —
    цена дня, более позднего, чем обе сделки (в числитель она попасть
    не имеет права)."""
    rows = []
    for day, close in ((_BUY_DATE, buy_close), (_SELL_DATE, sell_close),
                       (_AS_OF, later_close)):
        if close is not None:
            rows.append({"date": day, "close": close, "adjusted": close,
                         "currency": currency})
    return repos.price.put_rows("US-P6", "twelvedata", rows) if rows else 0


def _spec(repos):
    return insider_net_inputs_from_store(repos, "US-P6", "i-p6", _AS_OF)[
        "insider_net"]


def _row(repos, spec):
    """Ряд insider_net из того же входа, что даёт продюсеру фабрика
    снапшота: цвет и деталь считаются ядром, не тестом."""
    inputs = spec["inputs"]
    return insider_net("US-P6", inputs["net_ratio"], _AS_OF,
                       spec["lineage_ref"], tenb5_net=inputs["tenb5_net"],
                       net_value=inputs["net_value"])


# ── Done when: цена вдвое, сделок нет — ряд тот же самый ────────────────
def test_price_that_doubles_without_deals_changes_nothing(tmp_path):
    """Пункт «Done when» дословно. Ряд считается по сделкам, и если их
    нет, удвоение котировок не имеет права ни перекрасить строку, ни
    сдвинуть её причину или lineage: знаменатель для серости неспросим."""
    conn_a, a = _env(tmp_path / "a")
    conn_b, b = _env(tmp_path / "b")
    for repos, closes in ((a, (100.0, 200.0)), (b, (200.0, 400.0))):
        repos.coverage.upsert("US-P6", "ownership", "ready", reason=None)
        _mcap(repos)
        _prices(repos, buy_close=closes[0], sell_close=closes[1])
    assert [r["close"] for r in a.price.series("US-P6")] != \
        [r["close"] for r in b.price.series("US-P6")], "цены не удвоились"
    spec_a, spec_b = _spec(a), _spec(b)
    assert spec_a == spec_b, (spec_a, spec_b)
    assert spec_a["gray"] == "no_deals_in_window", spec_a
    produced_a = produce_assessments(a.governance, "US-P6", _AS_OF,
                                     {"insider_net": spec_a})
    produced_b = produce_assessments(b.governance, "US-P6", _AS_OF,
                                     {"insider_net": spec_b})
    assert [(r.indicator, r.color, r.reason, r.lineage_ref)
            for r in produced_a] == \
        [(r.indicator, r.color, r.reason, r.lineage_ref)
         for r in produced_b]
    insider = [r for r in produced_a if r.indicator == "insider_net"][0]
    assert (insider.color, insider.reason) == \
        ("gray", "no_data:no_deals_in_window")
    conn_a.close()
    conn_b.close()


# ── размерность числителя ───────────────────────────────────────────────
def test_numerator_is_money_at_the_close_of_each_deal_date(tmp_path):
    """200 акций по 100 против 500 акций по 200: числитель — деньги
    (-80 000), а не -300 акций, и каждая сделка по своей дате."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos)
    assert _prices(repos, buy_close=100.0, sell_close=200.0) == 2
    spec = _spec(repos)
    assert "gray" not in spec, spec
    inputs = spec["inputs"]
    assert inputs["net_value"] == pytest.approx(200 * 100.0 - 500 * 200.0)
    assert inputs["net_ratio"] == pytest.approx(-80_000.0 / 1_000_000.0)
    assert inputs["tenb5_net"] == pytest.approx(-500 * 200.0)
    assert "net=-80000" in spec["lineage_ref"], spec["lineage_ref"]
    row = _row(repos, spec)
    # в акциях на доллар это же выглядело как жёлтое «в пределах 0,1%»
    assert (row.color, row.reason.startswith("net_sales>")) == \
        ("red", True), (row.color, row.reason)
    conn.close()


def test_doubling_prices_and_capitalisation_leaves_the_ratio(tmp_path):
    """Зуб размерности: цены и капитализация выросли вдвое, сделки те
    же — отношение обязано остаться тем же. Числитель в акциях делился
    на удвоенный доллар и терял половину сигнала."""
    conn_a, a = _env(tmp_path / "a")
    conn_b, b = _env(tmp_path / "b")
    for repos, closes, cap in ((a, (100.0, 200.0), _MCAP),
                               (b, (200.0, 400.0), "2000000.0")):
        _deals(repos)
        _mcap(repos, value=cap)
        _prices(repos, buy_close=closes[0], sell_close=closes[1])
    inputs_a = _spec(a)["inputs"]
    spec_b = _spec(b)
    assert "gray" not in spec_b, spec_b
    inputs_b = spec_b["inputs"]
    assert inputs_b["net_value"] == pytest.approx(2 * inputs_a["net_value"])
    assert inputs_b["net_ratio"] == pytest.approx(inputs_a["net_ratio"])
    assert _row(b, spec_b).color == _row(a, _spec(a)).color
    conn_a.close()
    conn_b.close()


# ── чего ядро не выдумывает ────────────────────────────────────────────
def test_a_deal_older_than_the_price_history_stays_gray(tmp_path):
    """Котировка есть только позже обеих сделок: числителю не на что
    опереться, и ряд говорит об этом словом, а не тянет цену из
    будущего."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos)
    assert _prices(repos, later_close=1000.0) == 1
    spec = _spec(repos)
    assert spec["gray"] == "ownership_without_deal_price", spec
    assert "transactions=2" in spec["lineage_ref"], spec["lineage_ref"]
    assert "unpriced=2" in spec["lineage_ref"], spec["lineage_ref"]
    assert "не описана" not in grey_reason_text(spec["gray"])
    conn.close()


def test_one_priced_deal_of_two_does_not_make_a_half_number(tmp_path):
    """Половина сделок в деньгах, половина без цены: считать только
    посчитанное значило бы недооценить продажу — ряд серый целиком."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos)
    assert _prices(repos, buy_close=100.0) == 1
    spec = _spec(repos)
    assert spec["gray"] == "ownership_without_deal_price", spec
    assert "unpriced=1" in spec["lineage_ref"], spec["lineage_ref"]
    assert "inputs" not in spec, spec
    conn.close()


def test_deals_priced_in_another_currency_than_the_capital_refuse(tmp_path):
    """Числитель в фунтах, знаменатель в долларах: отношение сравняло
    бы пороги §4 с чем попало. Смешение валют отрицает число, а не
    прячет его."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos, unit="USD")
    assert _prices(repos, buy_close=100.0, sell_close=200.0,
                   currency="GBP") == 2
    spec = _spec(repos)
    assert spec["gray"] == "insider_deal_currency_mismatch", spec
    assert "GBP" in spec["lineage_ref"], spec["lineage_ref"]
    assert "USD" in spec["lineage_ref"], spec["lineage_ref"]
    assert "не описана" not in grey_reason_text(spec["gray"])
    conn.close()


# ── деталь цвета и версия метода ────────────────────────────────────────
def test_the_tenb5_detail_is_a_share_of_money(tmp_path):
    """BACKLOG 11 обещал называть долю плановых продаж; с деньгами в
    числителе и доля обязана быть денежной — «ш» в детали больше не
    единица измерения."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos)
    _prices(repos, buy_close=100.0, sell_close=200.0)
    spec = _spec(repos)
    row = _row(repos, spec)
    assert row.reason.endswith("tenb5_net=-100000 (125% of net)"), row.reason
    assert "sh" not in row.reason, row.reason
    conn.close()


def test_method_version_is_v2_and_the_v1_history_survives(tmp_path):
    """Смена размерности — новая версия метода (ADR-0001): пороги §4 те
    же, но число стало другим, и прошлые оценки остаются в таблице со
    своей версией, а не переписываются."""
    conn, repos = _env(tmp_path)
    _deals(repos)
    _mcap(repos)
    _prices(repos, buy_close=100.0, sell_close=200.0)
    repos.governance.record({
        "instrument_id": "US-P6", "indicator": "insider_net",
        "color": "yellow", "method_version": "governance.v1",
        "as_of": _AS_OF, "lineage_ref": "ownership:net=-300sh",
        "reason": "within_pm_0.1pct"})
    produced = produce_assessments(repos.governance, "US-P6", _AS_OF,
                                   {"insider_net": _spec(repos)})
    assert len(produced) == len(INDICATORS)
    assert {a.method_version for a in produced} == {METHOD_VERSION} == \
        {"governance.v2"}
    versions = [r["method_version"] for r in
                repos.governance.for_instrument("US-P6")
                if r["indicator"] == "insider_net"]
    assert versions == ["governance.v1", "governance.v2"], versions
    assert repos.governance.latest("US-P6", "insider_net")[
        "method_version"] == "governance.v2"
    conn.close()


def test_the_documented_method_names_the_version_the_code_uses():
    """Документ методов — источник порогов; если версия в нём отстаёт от
    `METHOD_VERSION`, читатель сверяет ряд не по тому методу."""
    text = _THRESHOLDS_DOC.read_text(encoding="utf-8")
    assert "governance.v2" in text, "документ остался на governance.v1"
    assert "0,1%" in text and "0,5%" in text, "пороги §4 из документа пропали"
    assert "governance.v1" in text, "из документа исчез след прежней версии"


def test_new_grey_rows_name_the_channel_that_fills_them():
    """P8: серому ряду мало причины — нужна команда, которой он
    закрывается. Обе новые причины про цены, поэтому дверь у них —
    канал котировок, а не формы владения; для прочих причин insider_net
    дверь остаётся прежней."""
    for token in ("ownership_without_deal_price",
                  "insider_deal_currency_mismatch"):
        assert token in GREY_REASONS, token
        words = grey_reason_text(f"no_data:{token}")
        assert words and "не описана" not in words, token
        door = grey_closing("insider_net", "US-P6", f"no_data:{token}")
        argv = _build_parser().parse_args(door.split()[1:])
        assert (argv.command, argv.source, argv.instrument) == \
            ("ingest", "twelvedata", "US-P6"), door
    assert grey_closing("insider_net", "US-P6") == \
        "rusterm ingest --source ownership --instrument US-P6"
    assert grey_closing("insider_net", "US-P6",
                        "no_data:ownership_without_market_cap") == \
        "rusterm ingest --source ownership --instrument US-P6"
