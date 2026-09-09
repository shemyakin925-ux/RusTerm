"""SEC EDGAR — провайдер раскрытий (TASK-8 U5, module-contracts.md §3).

Единственный сетевой источник (N1). Весь HTTP — здесь, через
RequestGate из budget.py: лимит 5/с, потолок 5000/ночь, без
RUSTERM_SEC_UA — ConfigError-значение до всякого запроса (N2/N3).
Транспорт инъектируется: тесты гоняются офлайн на записанных ответах
(tests/data/edgar/, настоящие, обрезанные), живой прогон — на urllib.

Формы ответов сняты с живых запросов 2026-09-08 и совпали с ожидаемыми
в ТЗ: company_tickers.json — вся карта тикер->CIK одним запросом;
submissions/CIK — filings.recent параллельными массивами;
companyfacts/CIK — facts.us-gaap.<concept>.units.<unit>[].
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from .base import ProviderError
from .budget import ConfigError, RequestGate
from .disclosures import (
    DocumentList,
    DocumentMeta,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/{document}"


@dataclass(frozen=True)
class NotModified:
    """304 по валидатору кеша: не новая порция данных и не ошибка (U5)."""
    url: str


def _default_transport(url: str, headers: dict) -> tuple:
    """Живой транспорт: (статус, тело, заголовки). 304 не исключение."""
    request = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise  # N4: стоп, не головоломка — наверх как ExternalError
        if e.code == 304:
            return 304, b"", dict(e.headers or {})
        raise


@dataclass
class EdgarProvider:
    """Провайдер раскрытий одного эмитента: EDGAR не имеет общего фида
    изменений, инкрементальность держится на submissions/CIK (один
    запрос на эмитента-источник) и полной карте тикеров одним запросом.
    Отличие от идеала ТЗ зафиксировано в Disputed отчёта."""

    gate: RequestGate
    cik: Optional[int] = None
    needs_network: bool = True
    source_name: str = "edgar"
    transport: Callable = _default_transport

    _tickers: Optional[dict] = None  # {ticker: (cik, title)}
    _submissions: Optional[dict] = None

    def _fetch_json(self, url: str) -> dict | ConfigError | NotModified:
        def send(headers: dict):
            status, body, resp_headers = self.transport(url, headers)
            if status == 304:
                return NotModified(url)
            return json.loads(body.decode("utf-8"))

        return self.gate.request(send)

    def _fetch_json_conditional(self, url: str,
                                validators: Optional[dict] = None):
        """Условный GET (TASK-13 Z1): валидаторы ответа (ETag,
        Last-Modified) приходят от вызывающего значением и возвращаются
        в результате — провайдер состояния не хранит (I10). 304 —
        NotModified, ноль байт тела; запрос при этом считается в
        RequestGate: он был. 200 — (документ, свежие валидаторы)."""
        validators = validators or {}

        def send(headers: dict):
            merged = dict(headers)
            if validators.get("etag"):
                merged["If-None-Match"] = validators["etag"]
            if validators.get("last_modified"):
                merged["If-Modified-Since"] = validators["last_modified"]
            status, body, resp_headers = self.transport(url, merged)
            if status == 304:
                return NotModified(url)
            doc = json.loads(body.decode("utf-8"))
            fresh = {key.lower(): resp_headers[key]
                     for key in ("ETag", "Last-Modified")
                     if resp_headers.get(key)}
            return doc, fresh

        return self.gate.request(send)

    def fetch_companyfacts_conditional(self, validators=None):
        """companyfacts условным запросом (TASK-13 Z1/Z2). Форма
        результата — как у _fetch_json_conditional."""
        return self._fetch_json_conditional(
            COMPANYFACTS_URL.format(cik=self.cik), validators)

    def latest_filing_date(self):
        """Дата последней поданной отчётности из submissions (один
        запрос, ответ кэшируется в провайдере); ProviderError/
        ConfigError — значением. None — фид без отчётностей."""
        data = self._load_submissions()
        if isinstance(data, (ProviderError, ConfigError)):
            return data
        recent = data.get("filings", {}).get("recent", {})
        dates = recent.get("filingDate") or []
        return max(dates) if dates else None

    # ── Карта тикеров: один запрос на весь рынок ────────────────────────

    def _ticker_map(self) -> dict | ConfigError | NotModified:
        if self._tickers is None:
            data = self._fetch_json(TICKERS_URL)
            if isinstance(data, (ConfigError, NotModified)):
                return data
            # (cik, title): имя эмитента доступно там же, где и CIK
            self._tickers = {
                str(row["ticker"]).upper(): (int(row["cik_str"]),
                                             row.get("title", ""))
                for row in data.values()
            }
        return self._tickers

    def resolve(self, ticker: str, market: str, as_of: str):
        """Тикер -> CIK по кэшированной карте; N тикеров — один запрос.
        Не найден — ProviderError-значение; дата обязательна (ADR-0005).
        Тикер, встречающийся в фиде дважды (смена класса, релейстинг),
        НЕ ошибка неоднозначности: побеждает последняя строка фида —
        карта строится по порядку строк company_tickers.json; поведение
        зафиксировано тестом (B17), смена — только отдельным пунктом
        задания (§0.2.4: пользовательский контракт меняет задание)."""
        del market, as_of  # EDGAR — только US; дата проверяется вызывающим
        if not ticker:
            return ProviderError("resolve_empty_ticker")
        mapping = self._ticker_map()
        if isinstance(mapping, (ConfigError, NotModified, ProviderError)):
            return mapping
        record = mapping.get(ticker.upper())
        if record is None:
            return ProviderError(f"not_found:{ticker}")
        cik, title = record
        return {"ticker": ticker.upper(), "cik": cik, "title": title}

    # ── submissions/CIK: фид изменений эмитента ─────────────────────────

    def _load_submissions(self):
        if self._submissions is not None:
            return self._submissions
        if self.cik is None:
            return ProviderError("edgar_without_cik")
        data = self._fetch_json(SUBMISSIONS_URL.format(cik=self.cik))
        if isinstance(data, (ConfigError, NotModified, ProviderError)):
            return data
        self._submissions = data
        return data

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError | ConfigError:
        """Новые раскрытия эмитента с даты курсора (filingDate > cursor)."""
        data = self._load_submissions()
        if isinstance(data, (ProviderError, ConfigError)):
            return data
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        records: list[IndexRecord] = []
        new_cursor = cursor
        for i, form in enumerate(forms):
            filed = recent["filingDate"][i]
            if cursor and filed <= cursor:
                continue
            records.append(IndexRecord(
                cursor=filed,
                issuer_id=str(data.get("cik", self.cik)),
                doc_type=form,
                period=recent["reportDate"][i] or "",
                url=ARCHIVES_URL.format(
                    cik=self.cik,
                    accn_nodash=recent["accessionNumber"][i].replace("-", ""),
                    document=recent["primaryDocument"][i] or ""),
                published_at=filed,
            ))
        if records:
            new_cursor = max(r.cursor for r in records)
        return IndexPoll(records=tuple(records), cursor=new_cursor)

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError:
        """Метаданные документов из уже загруженного submissions — без тел
        и без новых запросов."""
        data = self._load_submissions()
        if isinstance(data, (ProviderError, ConfigError)):
            return ProviderError(data.reason)
        recent = data.get("filings", {}).get("recent", {})
        docs: list[DocumentMeta] = []
        for i, form in enumerate(recent.get("form", [])):
            if doc_type is not None and form != doc_type:
                continue
            report_date = recent["reportDate"][i] or ""
            if period is not None and period not in report_date:
                continue
            docs.append(DocumentMeta(
                issuer_id=issuer_id, doc_type=form, period=report_date,
                url=ARCHIVES_URL.format(
                    cik=self.cik,
                    accn_nodash=recent["accessionNumber"][i].replace("-", ""),
                    document=recent["primaryDocument"][i] or ""),
                published_at=recent["filingDate"][i]))
        return DocumentList(tuple(docs))

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError \
            | ConfigError | NotModified:
        """Скачать тело документа. Идемпотентно: тот же url — тот же sha256.
        304 по валидаторам кеша — NotModified, не новый объект."""
        import hashlib

        def send(headers: dict):
            status, body, _ = self.transport(url, headers)
            if status == 304:
                return NotModified(url)
            return body

        outcome = self.gate.request(send)
        if isinstance(outcome, (ConfigError, NotModified)):
            return outcome
        if not isinstance(outcome, bytes):
            return ProviderError(f"unexpected_response:{url}")
        return FetchedDocument(
            url=url,
            content=outcome,
            sha256=hashlib.sha256(outcome).hexdigest(),
            content_type="text/html")

    # ── companyfacts: вход для реального XBRL-парсера (U6) ─────────────

    def fetch_companyfacts(self) -> dict | ConfigError | NotModified \
            | ProviderError:
        """Все XBRL-концепты эмитента одним запросом."""
        if self.cik is None:
            return ProviderError("edgar_without_cik")
        return self._fetch_json(COMPANYFACTS_URL.format(cik=self.cik))
