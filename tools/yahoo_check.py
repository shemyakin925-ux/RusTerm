"""Сверка карточки с Yahoo Finance (PRODUCT.md, «Контрольная десятка»).

    python3 tools/yahoo_check.py --root <каталог данных> [--cache DIR] [US-DELL …]

Наши числа — из той же карточки, что видит пользователь (`card.card_view`,
только чтение базы). Эталон — бесплатный ряд годовой отчётности Yahoo
(`fundamentals-timeseries`, без ключа, ADR-0018). Это внешняя проверка, а
не путь данных продукта, поэтому HTTP живёт здесь, в tools/, а не в
rusterm/providers/ (I9 касается rusterm/).

Сравнение: последние три года, где есть оба числа; совпадение — разница
не больше 5 %. Код выхода 0, если совпадает ≥ 95 % пар. Ответы Yahoo
кешируются в --cache: повторный прогон сети не трогает.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from rusterm.desktop import card, data
from rusterm.store.repos import RepoRegistry

CONTROL_TEN = ("US-JPM", "US-BAC", "US-DELL", "US-HPQ", "US-AAPL",
               "US-MSFT", "US-T", "US-AA", "US-FCX", "US-ORCL")
TOLERANCE = 0.05
TARGET = 0.95
YEARS = 3

# концепт карточки → ряд Yahoo. Знак капзатрат у Yahoo отрицательный —
# сравнение по модулю. Долг Yahoo включает аренду — расхождение там
# сначала проверяется на методику, потом считается дефектом.
YAHOO = {
    "revenue": "annualTotalRevenue",
    "gross_profit": "annualGrossProfit",
    "operating_income": "annualOperatingIncome",
    "ebitda": "annualEBITDA",
    # прибыль акционеров материнской компании ДО привилегированных
    # дивидендов — как «Чистая прибыль» карточки (NetIncomeLoss)
    "net_income": "annualNetIncome",
    "eps_diluted": "annualDilutedEPS",
    "total_assets": "annualTotalAssets",
    "total_equity": "annualStockholdersEquity",
    # долг без аренды — как total_debt карточки; TotalDebt Yahoo включает
    # обязательства по аренде, поэтому складывается из двух рядов ниже
    "total_debt": None,
    "cash": "annualCashAndCashEquivalents",
    "ocf": "annualOperatingCashFlow",
    "capex": "annualCapitalExpenditure",
    "fcf": "annualFreeCashFlow",
    "market_cap_total": "annualMarketCap",
}
ABSOLUTE = {"capex"}
# в зачёт идёт список PRODUCT.md: выручка, чистая прибыль, капитализация,
# P/E, ROE, долг (к EBITDA), FCF. Остальное печатается справочно: у Yahoo
# операционная прибыль и EBITDA «нормализованы» (без разовых списаний),
# отчёт 10-K и наша карточка — как поданы (AT&T 2024: 19,05 млрд в 10-K)
SCORED = {"revenue", "net_income", "market_cap_total", "pe", "roe",
          "total_debt", "fcf"}
DEBT_PARTS = ("annualLongTermDebt", "annualCurrentDebt")
# показатель, производный от рядов Yahoo тем же правилом, что у нас
DERIVED = ("roe", "pe")
URL = ("https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/"
       "finance/timeseries/{symbol}?type={types}&period1=1420070400"
       "&period2={now}")


def fetch(symbol: str, cache: Path | None) -> dict:
    """{ряд: {год: значение}} — из кеша или одним запросом."""
    path = cache / f"{symbol}.json" if cache else None
    if path and path.is_file():
        payload = json.loads(path.read_text())
    else:
        kinds = [k for k in YAHOO.values() if k] + list(DEBT_PARTS)
        url = URL.format(symbol=symbol, types=",".join(kinds),
                         now=int(time.time()))
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload))
        time.sleep(1.0)  # вежливость: не чаще раза в секунду
    series: dict[str, dict[str, float]] = {}
    for result in payload.get("timeseries", {}).get("result") or []:
        kind = result["meta"]["type"][0]
        for point in result.get(kind) or []:
            if point and point.get("reportedValue"):
                series.setdefault(kind, {})[point["asOfDate"][:4]] = \
                    float(point["reportedValue"]["raw"])
    return series


def ours(repos, instrument_id: str) -> dict[str, dict[str, float]]:
    """{концепт: {год: значение}} — клетки карточки, как в окне."""
    info = data.measure_table_rows(repos, instrument_id, card.CARD_YEARS)
    view = card.card_view(repos, info, show_empty=True)
    years = view["columns"][:-1]
    out: dict[str, dict[str, float]] = {}
    for row in view["rows"]:
        if row["kind"] == "section":
            continue
        out[row["concept"]] = {
            year: cell["value"] for year, cell in zip(years, row["cells"])
            if cell["value"] is not None}
    return out


def derived(theirs: dict[str, dict[str, float]]) -> dict[str, dict]:
    """ROE = прибыль / средний капитал, P/E = капитализация / прибыль —
    из рядов Yahoo тем же правилом, что в rusterm/formulas.py."""
    income = theirs.get(YAHOO["net_income"], {})
    equity = theirs.get(YAHOO["total_equity"], {})
    cap = theirs.get(YAHOO["market_cap_total"], {})
    roe, pe = {}, {}
    for year, value in income.items():
        prior = str(int(year) - 1)
        if year in equity and prior in equity and \
                equity[year] + equity[prior] > 0:
            roe[year] = value / ((equity[year] + equity[prior]) / 2)
        if year in cap and value > 0:
            pe[year] = cap[year] / value
    return {"roe": roe, "pe": pe}


def compare(mine: dict, theirs: dict) -> list[tuple]:
    """[(концепт, год, наше, их, отклонение)] за последние YEARS лет."""
    rows = []
    reference = {concept: theirs.get(kind, {})
                 for concept, kind in YAHOO.items() if kind}
    long_debt, short_debt = (theirs.get(k, {}) for k in DEBT_PARTS)
    reference["total_debt"] = {
        year: long_debt[year] + short_debt.get(year, 0.0)
        for year in long_debt}
    reference.update(derived(theirs))
    for concept, their_years in reference.items():
        my_years = mine.get(concept, {})
        common = sorted(set(my_years) & set(their_years))[-YEARS:]
        for year in common:
            a, b = my_years[year], their_years[year]
            if concept in ABSOLUTE:
                a, b = abs(a), abs(b)
            base = max(abs(a), abs(b))
            diff = 0.0 if base == 0 else abs(a - b) / base
            rows.append((concept, year, a, b, diff))
    return rows


def _short(value: float) -> str:
    for limit, word in ((1e12, "трлн"), (1e9, "млрд"), (1e6, "млн")):
        if abs(value) >= limit:
            return f"{value / limit:.2f} {word}"
    return f"{value:.4g}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--cache", default=None)
    parser.add_argument("instruments", nargs="*")
    args = parser.parse_args(argv)
    paths, conn = data.open_readonly(args.root)
    if conn is None:
        print(f"базы нет: {args.root}")
        return 1
    repos = RepoRegistry(conn, paths)
    cache = Path(args.cache) if args.cache else None
    total = matched = 0
    misses, info = [], []
    for instrument_id in args.instruments or CONTROL_TEN:
        symbol = instrument_id.split("-", 1)[1]
        every = compare(ours(repos, instrument_id), fetch(symbol, cache))
        info += [(instrument_id, *r) for r in every
                 if r[0] not in SCORED and r[4] > TOLERANCE]
        rows = [r for r in every if r[0] in SCORED]
        good = sum(1 for r in rows if r[4] <= TOLERANCE)
        total += len(rows)
        matched += good
        share = good / len(rows) if rows else 0.0
        print(f"{instrument_id:10} {good}/{len(rows)} = {share:.0%}")
        misses += [(instrument_id, *r) for r in rows if r[4] > TOLERANCE]
    share = matched / total if total else 0.0
    print(f"ИТОГ {matched}/{total} = {share:.0%} в пределах "
          f"{TOLERANCE:.0%} (цель {TARGET:.0%})")
    for instrument_id, concept, year, a, b, diff in sorted(
            misses, key=lambda m: -m[5]):
        print(f"  {instrument_id[3:]:5} {concept:18} {year}  наше "
              f"{_short(a):>12}  Yahoo {_short(b):>12}  {diff:6.1%}")
    if info:
        print("справочно (вне зачёта, методика Yahoo):")
        for instrument_id, concept, year, a, b, diff in sorted(
                info, key=lambda m: -m[5]):
            print(f"  {instrument_id[3:]:5} {concept:18} {year}  наше "
                  f"{_short(a):>12}  Yahoo {_short(b):>12}  {diff:6.1%}")
    conn.close()
    return 0 if share >= TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
