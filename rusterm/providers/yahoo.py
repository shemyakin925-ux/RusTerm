"""Yahoo Finance chart — бесплатные котировки без ключа (ADR-0029).

Решение пользователя 01.10.2026: ключ Twelve Data с 24.09 отвечает
«неверный», а сплиты и дивиденды у Twelve Data только на платном тарифе
(ADR-0018 запрещает платное). Один запрос /v8/finance/chart отдаёт
дневные close, adjclose, сплиты и дивиденды — без ключа и регистрации.
Интерфейс тот же, что у TwelveDataProvider: time_series / splits /
dividends, канонический URL кеша, parse_series / parse_splits /
parse_dividends, — поэтому сбор в CLI меняет только имя источника.

Оговорка: это неофициальный интерфейс без договора. Ответ не того вида —
значение `yahoo_bad_response`, а не исключение (§7).

Суммы дивидендов и close у Yahoo — в сегодняшней базе акций (с учётом
сплитов), как у Twelve Data (ADR-0020): отношение дивиденд/close
инвариантно к базе.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate

DEFAULT_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
# Бережный темп: 1 запрос в секунду, 2000 за сутки — с запасом к
# 44 бумагам, по одному запросу на бумагу.
_LIMIT = HostLimit(host="query1.finance.yahoo.com", per_second=1.0,
                   nightly_max=2000)
READ_TIMEOUT = 30
HISTORY_START = "1990-01-01"
_USER_AGENT = "Mozilla/5.0 (EquityLab personal research)"


def _default_transport(url: str, headers: dict) -> tuple:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


def _epoch(day: str) -> int:
    return int(_dt.datetime.fromisoformat(day).replace(
        tzinfo=_dt.timezone.utc).timestamp())


def _day(ts: int, gmtoffset: int) -> str:
    return _dt.datetime.fromtimestamp(
        int(ts) + int(gmtoffset or 0), tz=_dt.timezone.utc).date().isoformat()


def _result(payload: dict) -> dict:
    results = ((payload or {}).get("chart") or {}).get("result") or []
    return results[0] if results else {}


@dataclass
class YahooProvider:
    gate: RequestGate
    transport: Callable[[str, dict], tuple] = _default_transport
    source_name: str = "yahoo"
    limit: HostLimit = _LIMIT

    # ── канонические параметры и ключ кеша ──────────────────────────────

    @staticmethod
    def params_for(start: str | None = None, end: str | None = None) -> dict:
        start = start or HISTORY_START
        # period2 — конец дня `end`: Yahoo отдаёт [period1, period2)
        end_ts = (_epoch(end) + 86400) if end else None
        params = {"period1": str(_epoch(start)), "interval": "1d",
                  "events": "div,split", "includeAdjustedClose": "true"}
        if end_ts is not None:
            params["period2"] = str(end_ts)
        return params

    @classmethod
    def cache_url(cls, symbol: str, start: str | None = None,
                  end: str | None = None) -> str:
        """Канонический URL — индекс кеша (ADR-0003). Дата сбора в нём,
        поэтому следующий день — новый запрос, а не вечная заморозка."""
        return (f"{DEFAULT_BASE_URL}/{quote(symbol)}?"
                f"{urlencode(cls.params_for(start, end))}")

    @classmethod
    def cache_url_ca(cls, kind: str, symbol: str, as_of: str) -> str:
        """Сплиты и дивиденды приходят в том же ответе chart: ключ кеша —
        тот же URL полной истории до `as_of`."""
        if kind not in ("splits", "dividends"):
            raise ValueError(f"kind {kind!r} вне ('splits','dividends')")
        return cls.cache_url(symbol, None, as_of)

    # ── один запрос через гейт ──────────────────────────────────────────

    def _chart(self, symbol: str, start: str | None, end: str | None):
        url = self.cache_url(symbol, start, end)

        def send(headers: dict):
            # контакт пользователя (заголовок SEC) Yahoo не нужен и не
            # отдаётся: свой браузерный User-Agent
            merged = dict(headers)
            merged["User-Agent"] = _USER_AGENT
            status, body, _hdr = self.transport(url, merged)
            return status, body

        try:
            outcome = self.gate.request(send, limit=self.limit)
        except OSError:
            return ProviderError(reason="source_unreachable:transport")
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status == 429:
            return ProviderError(reason="vendor_rate_limited")
        if status == 404:
            return ProviderError(reason="unknown_issuer")
        if status != 200:
            return ProviderError(reason=f"source_unreachable:http_{status}")
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ProviderError(reason="yahoo_bad_response")
        error = (parsed.get("chart") or {}).get("error")
        if error:
            return ProviderError(
                reason=f"yahoo_error:{(error or {}).get('code', 'unknown')}")
        if not _result(parsed):
            return ProviderError(reason="yahoo_bad_response")
        return parsed

    def time_series(self, symbol: str, start: str | None = None,
                    end: str | None = None):
        return self._chart(symbol, start, end)

    def splits(self, symbol: str, as_of: str):
        return self._chart(symbol, None, as_of)

    def dividends(self, symbol: str, as_of: str):
        return self._chart(symbol, None, as_of)

    # ── чистый разбор записанного payload ───────────────────────────────

    @staticmethod
    def parse_series(payload: dict) -> list[dict]:
        """payload chart -> строки PriceRepo.put_rows:
        {date, close, adjusted?, currency, volume?}."""
        r = _result(payload)
        meta = r.get("meta") or {}
        currency = meta.get("currency") or None
        offset = meta.get("gmtoffset") or 0
        stamps = r.get("timestamp") or []
        ind = r.get("indicators") or {}
        quote_ = ((ind.get("quote") or [{}])[0]) or {}
        closes = quote_.get("close") or []
        volumes = quote_.get("volume") or []
        adjs = (((ind.get("adjclose") or [{}])[0]) or {}).get("adjclose") \
            or []
        rows: dict[str, dict] = {}
        for i, ts in enumerate(stamps):
            close = closes[i] if i < len(closes) else None
            if close is None:
                continue
            row = {"date": _day(ts, offset), "close": float(close),
                   "currency": currency}
            adj = adjs[i] if i < len(adjs) else None
            if adj is not None:
                row["adjusted"] = float(adj)
            vol = volumes[i] if i < len(volumes) else None
            if vol is not None:
                row["volume"] = int(vol)
            rows[row["date"]] = row  # одна строка на дату
        return [rows[d] for d in sorted(rows)]

    @staticmethod
    def parse_splits(payload: dict) -> tuple[list[dict], int]:
        r = _result(payload)
        offset = (r.get("meta") or {}).get("gmtoffset") or 0
        out, skipped = [], 0
        for s in ((r.get("events") or {}).get("splits") or {}).values():
            try:
                k = float(s["numerator"]) / float(s["denominator"])
                ex_date = _day(s["date"], offset)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                skipped += 1
                continue
            out.append({"ex_date": ex_date, "kind": "split", "factor": k,
                        "amount": None})
        out.sort(key=lambda row: row["ex_date"])
        return out, skipped

    @staticmethod
    def parse_dividends(payload: dict) -> tuple[list[dict], str, int]:
        r = _result(payload)
        meta = r.get("meta") or {}
        offset = meta.get("gmtoffset") or 0
        out, skipped = [], 0
        for d in ((r.get("events") or {}).get("dividends") or {}).values():
            try:
                amount = float(d["amount"])
                ex_date = _day(d["date"], offset)
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            out.append({"ex_date": ex_date, "kind": "dividend",
                        "factor": None, "amount": amount})
        out.sort(key=lambda row: row["ex_date"])
        return out, meta.get("currency") or None, skipped


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('yahoo', gate)."""
    return YahooProvider(gate=gate)


__all__ = ["YahooProvider", "build", "DEFAULT_BASE_URL"]
