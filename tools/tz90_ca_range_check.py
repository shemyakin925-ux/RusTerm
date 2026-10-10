"""ТЗ-90 A1: живой замер вендора перед выбором ветки для /splits и
/dividends.

Вопрос один: возвращает ли Twelve Data те же корпоративные события по
датированному диапазону (`start_date=1900-01-01&end_date=<as_of>`), что
и по `range=full`? Если да — канонический URL кеша получает дату и
сбор refreshing (иначе `range=full` остаётся, а свежесть проверяется по
`fetched_at`). Если нет — датированный вариант запрещён, потому что
он молча теряет события.

Запросов ровно четыре (два эндпойнта по два варианта), и печатается
фактический счётчик гейта. Ключ в вывод не попадает: печатаются только
канонические URL без ключа и разборы.

    python3 tools/tz90_ca_range_check.py AAPL 2026-09-23
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rusterm.env import load_env
from rusterm.providers import get_provider
from rusterm.providers.budget import RequestGate
from rusterm.providers.twelvedata import DEFAULT_BASE_URL

START_ALL = "1900-01-01"


def _events(provider, kind: str, params: dict):
    """Один запрос и его разбор тем же парсером, что у сбора."""
    outcome = provider._request(f"/{kind}", params)
    if not isinstance(outcome, dict):
        return None, outcome
    if kind == "splits":
        parsed, skipped = provider.parse_splits(outcome)
        return [(e["ex_date"], f'{e["factor"]}') for e in parsed], skipped
    parsed, currency, skipped = provider.parse_dividends(outcome)
    return [(e["ex_date"], str(e["amount"]), currency)
            for e in parsed], skipped


def main(symbol: str, as_of: str) -> int:
    load_env()
    gate = RequestGate()
    provider = get_provider("twelvedata", gate=gate)
    if hasattr(provider, "reason"):
        print(f"twelvedata недоступен: {provider.reason}", file=sys.stderr)
        return 1

    rows = []
    for kind in ("dividends", "splits"):
        full_params = {"symbol": symbol, "range": "full"}
        dated_params = {"symbol": symbol, "start_date": START_ALL,
                        "end_date": as_of}
        for label, params in (("range=full", full_params),
                              ("dated", dated_params)):
            url = f"{DEFAULT_BASE_URL}/{kind}?{urlencode(params)}"
            events, extra = _events(provider, kind, params)
            rows.append((kind, label, url, events, extra))

    print(f"{symbol} / as_of {as_of} / запросов: {gate.calls_made} из 4 "
          f"({gate.host_usage()})")
    for kind, label, url, events, extra in rows:
        n = "отказ" if events is None else f"{len(events)} событий"
        print(f"{kind:9s} {label:10s} {n:12s} неразобрано: {extra}\n"
              f"              {url}")
    rc = 0
    for kind in ("dividends", "splits"):
        full = next(e for k, l, u, e, x in rows
                    if k == kind and l == "range=full")
        dated = next(e for k, l, u, e, x in rows
                     if k == kind and l == "dated")
        if full is None or dated is None:
            print(f"{kind}: замер неполный — вендор отказал, ветку не выбираем")
            rc = 1
            continue
        only_full, only_dated = set(full) - set(dated), set(dated) - set(full)
        same = not only_full and not only_dated
        print(f"{kind}: совпадают = {same}; "
              f"только в full = {sorted(only_full)}; "
              f"только в dated = {sorted(only_dated)}")
        if not same:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
