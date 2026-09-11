"""ASX (Австралия) — открытые эндпойнты без договора (ADR-0010 §5,
ТЗ-20 L3).

**Канал без договора.** asx.api.markitdigital.com не заявлен как
публичный API. Правила канала: вежливый темп (1/с из замера), только
те заголовки, что нужны для ответа, никакой массовой выкачки, никакой
обходной маневр при отказе. 403/429 — source_unreachable и стоп (N4).

Записанные тела (живая выкачка 11.09, budget 7 из 15):
tests/data/asx/header_{CBA,BHP,TLS}.json и announcements_*.json.
Несуществующий код — HTTP 400 значением (не 404: так отвечает
источник).

Рынок access=partial (ADR-0010 §2): программа обязана различать
эмитентов ДО создания. Исходы can_auto_ingest: 200 с данными — True;
200 с пустыми/недоступными анонсами — False (эмитент известен, раскрытия
машинно недоступны -> manual_import_required); 400/404 —
unknown_issuer. Тела документов по бесплатному каналу недостижимы:
двухшаговая PDF-цепочка не проверена нами живьём и остаётся вне канала
— fetch_document отвечает manual_import_required с именем подачи.
Рыночного индекса изменений у канала нет — poll_index отвечает
значением-отказом; инкрементальность для AU — по эмитенту.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate
from .disclosures import (
    DocumentList,
    DocumentMeta,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)

_BASE = "https://asx.api.markitdigital.com/asx-research/1.0/companies"
_LIMIT = HostLimit(host="asx.api.markitdigital.com", per_second=1.0,
                   nightly_max=5000)


def _default_transport(url: str, headers: dict) -> tuple:
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass
class AsxProvider:
    gate: RequestGate
    transport: Callable[[str, dict], tuple] = _default_transport
    source_name: str = "asx"

    @classmethod
    def from_env(cls, gate: RequestGate, environ=None):
        # ключа у канала нет: строится всегда, сеть через гейт
        return cls(gate=gate)

    def _get(self, code: str, what: str):
        def send(headers: dict):
            status, body, _hdr = self.transport(
                f"{_BASE}/{code}/{what}", headers)
            return status, body

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status in (400, 404):
            return ProviderError(reason="unknown_issuer")
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ProviderError(reason="asx_bad_response")

    def can_auto_ingest(self, identifier: str) -> bool | ProviderError:
        """ADR-0010 §3 для partial-рынка: 200/данные — True; 200, но
        раскрытий не видно — False (manual_import_required наверху);
        400/404 — unknown_issuer. До создания эмиттера, не после."""
        code = (identifier or "").strip().upper()
        if not code:
            return ProviderError(reason="unknown_issuer")
        header = self._get(code, "header")
        if isinstance(header, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return header
        announcements = self._get(code, "announcements")
        if isinstance(announcements, ProviderError):
            if announcements.reason == "unknown_issuer":
                return announcements
            # эмитент известен, анонсы недостижимы — честное False
            return False
        if isinstance(announcements, (ConfigError, BudgetExceeded)):
            return announcements
        return bool((announcements.get("data") or {}).get("items"))

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError | ConfigError:
        return ProviderError(reason="asx_no_marketwide_index")

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError | ConfigError:
        answer = self._get(issuer_id.upper(), "announcements")
        if isinstance(answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return answer
        docs = []
        for item in (answer.get("data") or {}).get("items", []):
            if doc_type is not None \
                    and item.get("announcementType") != doc_type:
                continue
            docs.append(DocumentMeta(
                issuer_id=issuer_id.upper(),
                doc_type=item.get("announcementType", ""),
                period="",
                url=f"asxdoc:{item.get('documentKey', '')}",
                published_at=item.get("date", ""),
            ))
        return DocumentList(tuple(docs))

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError | ConfigError:
        """Тела документов бесплатным каналом не добываются (двухшаговая
        PDF-цепочка не проверена живьём). Честный ответ называет подачу,
        чтобы пользователь импортировал файл вручную (ADR-0011)."""
        if not url.startswith("asxdoc:"):
            return ProviderError(reason=f"asx_bad_url:{url[:32]}")
        return ProviderError(
            reason=f"manual_import_required:asxdoc:{url.split(':', 1)[1]}")


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('asx', gate)."""
    return AsxProvider.from_env(gate)


__all__ = ["AsxProvider", "build"]
