"""Open DART (FSS, Корея) — первый провайдер вне EDGAR (ADR-0010,
ТЗ-20 L1).

Канал замерен (REPORT-MARKETS, повторно L1): engopendart.fss.or.kr
без ключа отвечает 200 и {"status":"100","message":"Authentication
Keys is missing."} — записанный payload лежит в
tests/data/dart/engapi_list_unkeyed.json, и разбор статуса '100'
тестируется на настоящих байтах.

Ключ — только из RUSTERM_DART_KEY (N2); нет ключа — ConfigError
значением и офлайн-путь. Словарь статусов DART: '000' — успех;
'013' — данных нет (для corp_code это unknown_issuer); остальные —
отказ источника значением ProviderError, не исключением.

Документ DART отдаёт запакованным (zip с XML): провайдер возвращает
сырые байты и sha256, не разбирая их — разбор принадлежит парсеру,
провайдер о хранилище не знает (I10). Хост объявления — engopendart
(замер); реестровая строка F5 держит имя провайдера и допуск, а свой
HostLimit провайдер несёт здесь и передаёт гейту сам.

Темп 2/с — из замера; потолок ночи — проектные 5000 до замера
настоящего.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate
from .disclosures import (
    DocumentList,
    DocumentMeta,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)

KEY_ENV = "RUSTERM_DART_KEY"
_BASE = "https://engopendart.fss.or.kr/engapi"
_LIMIT = HostLimit(host="engopendart.fss.or.kr", per_second=2.0,
                   nightly_max=5000)
_OK = "000"
_NOT_FOUND = "013"


def _default_transport(url: str, headers: dict) -> tuple:
    """Живой транспорт: (статус, тело, заголовки), как у edgar."""
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass
class DartProvider:
    """Провайдер раскрытий Кореи: списки подач (list.json), карточка
    компании (company.json), тело документа (documentDownload.nav).

    Ключ не печатается и не попадает в URL-логи — гейт пишет только
    имена; в запрос он уходит параметром crtfc_key, который наружу
    не логируется (проверка журналов — T13 scrub).
    """

    gate: RequestGate
    api_key: str
    transport: Callable[[str, dict], tuple] = _default_transport
    source_name: str = "dart"

    @classmethod
    def from_env(cls, gate: RequestGate,
                 environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        key = (env.get(KEY_ENV) or "").strip()
        if not key:
            return ConfigError(reason="dart_key_unset")
        return cls(gate=gate, api_key=key)

    # ── внутреннее: один запрос через дверь ─────────────────────────────

    def _get_json(self, path: str, params: dict):
        from urllib.parse import urlencode
        url = f"{_BASE}/{path}?" + urlencode(
            {"crtfc_key": self.api_key, **params})

        def send(headers: dict):
            status, body, _hdr = self.transport(url, headers)
            return status, body

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return ProviderError(reason="dart_bad_response")
        code = str(parsed.get("status", ""))
        if code == _OK:
            return parsed
        if code == _NOT_FOUND:
            return ProviderError(reason="unknown_issuer")
        return ProviderError(reason=f"source_unreachable:dart_{code}")

    # ── DisclosuresProvider ─────────────────────────────────────────────

    def can_auto_ingest(self, identifier: str) -> bool | ProviderError:
        """ADR-0010 §3: corp_code известен рынку — company.json отвечает
        '000' (True) или '013' (unknown_issuer). Ответственный ответ до
        создания эмитента (TASK-19 F3)."""
        if not identifier:
            return ProviderError(reason="unknown_issuer")
        answer = self._get_json("company.json", {"corp_code": identifier})
        if isinstance(answer, (ProviderError, ConfigError,
                               BudgetExceeded)):
            return answer
        return True

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError | ConfigError:
        """Индекс подач за окно дат: cursor — последняя видимая дата
        YYYYMMDD; сегодня, если пусто. Записей нет — курсор не движется."""
        end = _today_yyyymmdd()
        answer = self._get_json("list.json",
                                {"bgn_de": cursor or end, "end_de": end})
        if isinstance(answer, (ConfigError, ProviderError)):
            return answer
        records = []
        newest = cursor or end
        for row in answer.get("list", []):
            published = str(row.get("rcept_dt", newest))
            newest = max(newest, published)
            records.append(IndexRecord(
                cursor=published,
                issuer_id=str(row.get("corp_code", "")),
                doc_type=str(row.get("report_tp", "")),
                period=str(row.get("business_year", "")),
                url=f"document:{row.get('rcept_no', '')}",
                published_at=published,
            ))
        return IndexPoll(records=tuple(records), cursor=newest)

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError | ConfigError:
        """Перечень подач эмитента: list.json не фильтруется источником
        по corp_code, поэтому страница берётся целиком и фильтруется
        здесь; честный вопрос объёма — на живой прогон с ключом."""
        end = _today_yyyymmdd()
        answer = self._get_json("list.json",
                                {"bgn_de": "19990101", "end_de": end,
                                 "corp_code": issuer_id})
        if isinstance(answer, (ConfigError, ProviderError)):
            return answer
        docs = []
        for row in answer.get("list", []):
            if str(row.get("corp_code", "")) != issuer_id:
                continue
            row_type = str(row.get("report_tp", ""))
            row_period = str(row.get("business_year", ""))
            if doc_type is not None and row_type != doc_type:
                continue
            if period is not None and row_period != period:
                continue
            docs.append(DocumentMeta(
                issuer_id=issuer_id, doc_type=row_type,
                period=row_period,
                url=f"document:{row.get('rcept_no', '')}",
                published_at=str(row.get("rcept_dt", "")),
            ))
        return DocumentList(tuple(docs))

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError | ConfigError:
        """Тело подачи по rcept_no ('document:<rcept_no>'). DART отдаёт
        запакованный документ — байты как есть, sha256 по ним."""
        if not url.startswith("document:"):
            return ProviderError(reason=f"dart_bad_url:{url[:32]}")
        rcept_no = url.split(":", 1)[1]
        from urllib.parse import urlencode
        full = ("https://engopendart.fss.or.kr/api/documentDownload.nav?"
                + urlencode({"crtfc_key": self.api_key, "rcept_no": rcept_no}))

        def send(headers: dict):
            status, body, _hdr = self.transport(full, headers)
            return status, body

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        return FetchedDocument(url=url, content=body,
                              sha256=hashlib.sha256(body).hexdigest(),
                              content_type="application/zip")


def _today_yyyymmdd() -> str:
    import datetime as _dt
    return _dt.date.today().strftime("%Y%m%d")


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('dart', gate)."""
    return DartProvider.from_env(gate)


__all__ = ["DartProvider", "build", "KEY_ENV"]
