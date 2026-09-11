"""OTC Markets Group (US-OTC) — индекс и метаданные бесплатны, тела
документов нет (ADR-0010, ТЗ-20 L4).

Канал без договора (ADR-0010 §5): заголовки — ровно те, что нужны для
ответа (браузерный набор Origin/Referer/Sec-Fetch), вежливый темп 1/с,
никакой массовой выкачки, никакого наращивания заголовков ради
преодоления блоков. 403/429/406 — source_unreachable и стоп (N4).

Замер канала (REPORT-MARKETS + запись L4 11.09): otcapi/company/SYM/
financial-report отвечает 200 JSON со списком раскрытий и их
метаданными; маршрут /content документа — закрыт (в замере 09.09 —
200 с HTML-заглушкой 2 КБ; 11.09 — уже HTTP 406: форма блокировки
дрейфует, блок — стоп, не головоломка). ~882 OTC-эмитента, отчитывающихся
в SEC, уже работают через edgar — этот провайдер покрывает только
OTC-only эмитентов на доступную глубину: индекс и метаданные.

Тела записаны в tests/data/otcmarkets/ (живая выкачка 11.09,
3 запроса).
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate
from .disclosures import (
    DocumentList,
    DocumentMeta,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)

_BASE = "https://backend.otcmarkets.com/otcapi"
_LIMIT = HostLimit(host="backend.otcmarkets.com", per_second=1.0,
                   nightly_max=5000)
_EXTRA_HEADERS = {
    "Origin": "https://www.otcmarkets.com",
    "Referer": "https://www.otcmarkets.com",
    "Accept": "application/json",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


def _default_transport(url: str, headers: dict) -> tuple:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass
class OtcMarketsProvider:
    gate: RequestGate
    transport: Callable[[str, dict], tuple] = _default_transport
    source_name: str = "otcmarkets"

    @classmethod
    def from_env(cls, gate: RequestGate, environ=None):
        # ключа у канала нет: строится всегда, сеть через гейт
        return cls(gate=gate)

    def _get(self, path: str, params: dict | None = None):
        url = f"{_BASE}{path}"
        if params:
            url += "?" + urlencode(params)

        def send(headers: dict):
            merged = dict(headers)
            merged.update(_EXTRA_HEADERS)
            status, body, _hdr = self.transport(url, merged)
            return status, body

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status in (403, 406, 429):
            # блок — стоп, не головоломка (N4); 406 = закрытый /content
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        if status == 404:
            return ProviderError(reason="unknown_issuer")
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ProviderError(reason="otc_bad_response")

    def can_auto_ingest(self, identifier: str) -> bool | ProviderError:
        """ADR-0010 §3 для OTC-only эмитента: список раскрытий отвечает
        200 — индекс и метаданные достижимы (True). Тела документов
        недостижимы, но это не меняет доступности эмитента как таковой:
        факты с метаданных не строятся, документ даёт ручной импорт.
        Неизвестный тикер — unknown_issuer."""
        symbol = (identifier or "").strip().upper()
        if not symbol:
            return ProviderError(reason="unknown_issuer")
        answer = self._get(f"/company/{symbol}/financial-report",
                           {"symbol": symbol, "statusId": "A",
                            "pageSize": 1})
        if isinstance(answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return answer
        return True

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError | ConfigError:
        """Страница вселенной торгуемых бумаг: cursor — номер страницы
        (строкой). Один запрос — одна страница; pageSize=5, серверный
        потолок 50 (замер сообщества, не наш)."""
        page = int(cursor) if cursor and cursor.isdigit() else 1
        answer = self._get("/market-data/active/current",
                           {"tierGroup": "ALL", "page": page,
                            "pageSize": 5})
        if isinstance(answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return answer
        records = []
        for row in answer.get("results", []) or []:
            symbol = str(row.get("symbol", "")).upper()
            if symbol:
                records.append(IndexRecord(
                    cursor=str(page),
                    issuer_id=symbol,
                    doc_type="otc-profile",
                    period="",
                    url=f"otcsym:{symbol}",
                    published_at="",
                ))
        return IndexPoll(records=tuple(records), cursor=str(page + 1))

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError | ConfigError:
        symbol = issuer_id.upper()
        answer = self._get(f"/company/{symbol}/financial-report",
                           {"symbol": symbol, "statusId": "A",
                            "pageSize": 50})
        if isinstance(answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return answer
        docs = []
        for row in answer.get("results", []) or []:
            meta = DocumentMeta(
                issuer_id=symbol,
                doc_type=str(row.get("reportType", "")),
                period=str(row.get("periodDate", "")),
                url=f"otcdoc:{row.get('documentId', '')}",
                published_at=str(row.get("releaseDate", "")),
            )
            if doc_type is not None and meta.doc_type != doc_type:
                continue
            if period is not None and meta.period != period:
                continue
            docs.append(meta)
        return DocumentList(tuple(docs))

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError | ConfigError:
        """Тело раскрытия недостижимо бесплатным каналом (блок /content,
        в замерах — HTML-заглушка или 406). Честный ответ называет
        подачу для ручного импорта (ADR-0011); ретрая и обхода нет."""
        if not url.startswith("otcdoc:"):
            return ProviderError(reason=f"otc_bad_url:{url[:32]}")
        doc_id = url.split(":", 1)[1]
        return ProviderError(
            reason=f"manual_import_required:otcdoc:{doc_id}")


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('otcmarkets', gate)."""
    return OtcMarketsProvider.from_env(gate)


__all__ = ["OtcMarketsProvider", "build"]
