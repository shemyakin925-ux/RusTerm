"""Twelve Data — котировки (ТЗ-23 K2, ADR-0014, ADR-0018).

Бесплатный тариф по вендору: 8 запросов/мин, 800/день (ТЗ-28 R3) —
оба числа объявлены и в реестре, и здесь, в рабочем _LIMIT. Ключ —
только из RUSTERM_TWELVEDATA_KEY; нет ключа — ConfigError-значение и
офлайн-путь (N2). Ключ не печатается: repr маскирует (ТЗ-29 A4),
в канонический URL кеша он не входит. 429 — стоп значением, а не
головоломка (N4); ретраев на отказ вендора нет.

Ежедневная серия одним запросом /time_series: close обязателен,
adjusted_close (вендорский) идёт как есть, если эндпойнт его отдал, —
наша корректировка считается своей функцией (K3), вендорская — только
сверка. Разбор payload вынесен в parse_series: золотой тест гоняет
его по записанному обрезанному payload офлайн.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlencode

from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate
from .base import ProviderError

KEY_ENV = "RUSTERM_TWELVEDATA_KEY"
DEFAULT_BASE_URL = "https://api.twelvedata.com"

# Рабочее объявление (ТЗ-19 F5 / закрепление TASK-21 Q2): тот же
# вендорский потолок, что и в реестре — 8/мин, 800/день.
_LIMIT = HostLimit(host="api.twelvedata.com", per_second=8.0 / 60.0,
                   nightly_max=800)

READ_TIMEOUT = 30
INTERVAL = "1day"
OUTPUTSIZE = 5000


def _default_transport(url: str, headers: dict) -> tuple:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass
class TwelveDataProvider:
    """Клиент /time_series. Ошибки — значения (§7);Transport-исключения
    гасятся в значения здесь, наружу не выходят."""

    gate: RequestGate
    api_key: str
    transport: Callable[[str, dict], tuple] = _default_transport
    source_name: str = "twelvedata"
    limit: HostLimit = _LIMIT

    def __repr__(self) -> str:
        """api_key не печатается никогда (ТЗ-29 A4)."""
        return (f"TwelveDataProvider(gate={self.gate!r}, api_key='***', "
                f"source_name={self.source_name!r})")

    @classmethod
    def from_env(cls, gate: RequestGate,
                 environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        key = (env.get(KEY_ENV) or "").strip()
        if not key:
            return ConfigError(reason="twelvedata_key_unset")
        return cls(gate=gate, api_key=key)

    # ── канонические параметры и ключ кеша: без apikey ──────────────────

    @staticmethod
    def params_for(symbol: str, start: str | None = None,
                   end: str | None = None) -> dict:
        params = {"symbol": symbol, "interval": INTERVAL,
                  "outputsize": str(OUTPUTSIZE)}
        if start:
            params["start_date"] = start
        if end:
            params["end_date"] = end
        return params

    @classmethod
    def cache_url(cls, symbol: str, start: str | None = None,
                  end: str | None = None) -> str:
        """Канонический URL без ключа: индекс кеша в raw_object.url.
        Повтор сбор того же диапазона находит объект по этому полю и
        тратит ноль запросов (K2, ADR-0003)."""
        return f"{DEFAULT_BASE_URL}/time_series?{urlencode(cls.params_for(symbol, start, end))}"

    # ── один запрос через дверь ─────────────────────────────────────────

    def time_series(self, symbol: str, start: str | None = None,
                    end: str | None = None) -> dict | ConfigError | \
            BudgetExceeded | ProviderError:
        params = self.params_for(symbol, start, end)
        url = f"{DEFAULT_BASE_URL}/time_series?{urlencode(params)}" \
              f"&apikey={self.api_key}"

        def send(headers: dict):
            status, body, _hdr = self.transport(url, headers)
            return status, body

        try:
            outcome = self.gate.request(send, limit=self.limit)
        except OSError:
            # тайм-аут/обрыв транспорта — значение, не исключение (§7)
            return ProviderError(reason="source_unreachable:transport")
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status == 429:
            # N4: стоп, не головоломка — темп и потолок не поднимаем
            return ProviderError(reason="vendor_rate_limited")
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ProviderError(reason="twelvedata_bad_response")
        if parsed.get("status") == "error":
            code = str(parsed.get("code", "unknown"))
            return ProviderError(reason=f"twelvedata_error:{code}")
        return parsed

    # ── чистый разбор записанного payload ───────────────────────────────

    @staticmethod
    def parse_series(payload: dict) -> list[dict]:
        """payload /time_series -> строки PriceRepo.put_rows:
        {date, close, adjusted?, currency?, volume?}. adjusted берётся
        из вендорского adjusted_close, если тот отдан; volume — целым."""
        meta = payload.get("meta", {}) or {}
        currency = meta.get("currency") or None
        rows: list[dict] = []
        for v in payload.get("values", []) or []:
            close = v.get("close")
            if close in (None, ""):
                continue
            row: dict = {"date": v["datetime"], "close": float(close),
                         "currency": currency}
            adjusted = v.get("adjusted_close")
            if adjusted not in (None, ""):
                row["adjusted"] = float(adjusted)
            volume = v.get("volume")
            if volume not in (None, ""):
                row["volume"] = int(float(volume))
            rows.append(row)
        rows.sort(key=lambda r: r["date"])
        return rows


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('twelvedata', gate)."""
    return TwelveDataProvider.from_env(gate)


__all__ = ["TwelveDataProvider", "build", "KEY_ENV", "DEFAULT_BASE_URL"]
