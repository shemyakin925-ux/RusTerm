"""CVM open data (Бразилия) — провайдер наборов регулятора (ADR-0010,
ТЗ-20 L2).

Единица сбора — НАБОР ДАННЫХ, не документ: dados.cvm.gov.br отдаёт
годовые ZIP/CSV (DFP/ITR/CAD), публичного API до 2026–2028 нет
(REPORT-MARKETS). Набор DFP-2024 — это индекс подач + ведомые
файлы отчётности (DRE — прибыли/убытки, BPP — баланс, ...).

HEAD перед GET — всегда: 13 МБ тела никогда не качаются ради ответа
«изменилось ли»; сравнение по Last-Modified/Content-Length, и при
неизменности возвращается значение DatasetState (не качаем), а GET
не выполняется вовсе — тест доказывает ноль GET счётом вызовов
транспорта. Скачанные архивы в git не попадают (N5) — только
нарезанные строки под tests/data/cvm/.

Ключа у канала нет; 404 — ответ источника значением (не ошибка
транспорта), 403/429 — source_unreachable и стоп (N4). Темп 1/с —
из замера, объёмные файлы; без гейта провайдер не строится (U5).
"""
from __future__ import annotations

import csv
import io
import os
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Callable, Mapping

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate
from .disclosures import (
    DocumentList,
    DocumentMeta,
    FetchedDocument,
    IndexPoll,
    IndexRecord,
)

_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
_LIMIT = HostLimit(host="dados.cvm.gov.br", per_second=1.0, nightly_max=5000)

CAD_URL = f"{_BASE}/CAD/DADOS/cad_cia_aberta.csv"
DFP_URL = f"{_BASE}/DOC/DFP/DADOS/dfp_cia_aberta_{{year}}.zip"


def _default_transport(url: str, headers: dict, method: str) -> tuple:
    request = urllib.request.Request(url, headers=dict(headers),
                                     method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass(frozen=True)
class DatasetState:
    """Состояние набора по HEAD: адрес, метка изменения, размер. Не
    «изменилось» и не ошибка — ответ на вопрос «надо ли качать» (U5
    инкрементальности, ТЗ-12)."""

    url: str
    last_modified: str
    content_length: int
    url_field: str = ""

    @property
    def unchanged_marker(self) -> str:
        return self.last_modified


@dataclass
class CvmProvider:
    gate: RequestGate
    transport: Callable[[str, dict, str], tuple] = _default_transport
    source_name: str = "cvm"

    @classmethod
    def from_env(cls, gate: RequestGate, environ=None):
        # ключа у канала нет: строится всегда, сеть всё равно через гейт
        return cls(gate=gate)

    # ── наборы: HEAD -> GET только при изменении ────────────────────────

    def dataset_state(self, url: str):
        """HEAD набора. DatasetState — можно сверять с известным;
        ProviderError — источник недоступен/нет пути (404 значением)."""
        def send(headers: dict):
            status, body, hdr = self.transport(url, headers, "HEAD")
            return status, hdr

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, hdr = outcome
        if status == 404:
            return ProviderError(reason=f"cvm_not_found:{url[-48:]}")
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        return DatasetState(
            url=url,
            last_modified=hdr.get("Last-Modified", ""),
            content_length=int(hdr.get("Content-Length", "0") or 0),
        )

    def dataset_if_changed(self, url: str,
                           known_last_modified: str | None):
        """HEAD, затем GET ровно при изменении. DatasetState — набор не
        изменился, байты не запрашивались; bytes — новое тело набора."""
        state = self.dataset_state(url)
        if isinstance(state, (ConfigError, ProviderError)):
            return state
        if known_last_modified is not None \
                and state.last_modified == known_last_modified:
            return state
        return self._dataset_get(url)

    def _dataset_get(self, url: str):
        def send(headers: dict):
            status, body, _hdr = self.transport(url, headers, "GET")
            return status, body

        outcome = self.gate.request(send, limit=_LIMIT)
        if isinstance(outcome, (ConfigError, BudgetExceeded)):
            return outcome
        status, body = outcome
        if status != 200:
            return ProviderError(
                reason=f"source_unreachable:http_{status}")
        return body

    # ── кадастр: can_auto_ingest и поиск кода ───────────────────────────

    def can_auto_ingest(self, identifier: str, cadastro: bytes | None = None):
        """ADR-0010 §3 для набора: эмитент ищется в кадастровом индексе.
        identifier — CD_CVM (числовой код, дополнение не требуется) или
        подстрока DENOM_SOCIAL. cadastro — точка инъекции записанных
        байтов для тестов; в бою байты даёт dataset_if_changed."""
        if cadastro is None:
            data = self.dataset_if_changed(CAD_URL, None)
            if isinstance(data, (ConfigError, ProviderError,
                                 BudgetExceeded)):
                return data
            cadastro = data
        rows = _read_csv(cadastro)
        ident = identifier.strip().upper()
        for row in rows:
            if row.get("CD_CVM", "").lstrip("0") == ident.lstrip("0") \
                    or ident in (row.get("DENOM_SOCIAL") or "").upper():
                return True
        return ProviderError(reason="unknown_issuer")

    # ── строки отчётности из набора DFP ─────────────────────────────────

    def dfp_members(self, zip_bytes: bytes) -> dict[str, bytes]:
        """Распаковать набор DFP в память: имя члена -> байты CSV.
        На диск ничего не пишется; zip читается zipfile'ом без
        исполнения путей из архива."""
        out: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith(".csv"):
                    out[name] = zf.read(name)
        return out

    def rows_for(self, csv_bytes: bytes, cd_cvm: str) -> list[dict]:
        """Строки одного эмитента из ведомого CSV (CD_CVM в источнике
        дополнен нулями до 6 цифр — сравниваем без ведущих нулей)."""
        code = cd_cvm.lstrip("0")
        return [r for r in _read_csv(csv_bytes)
                if r.get("CD_CVM", "").lstrip("0") == code]

    # ── DisclosuresProvider поверх наборов ──────────────────────────────

    def poll_index(self, cursor: str) -> IndexPoll | ProviderError | ConfigError:
        """Курсор набора — метка Last-Modified DFP текущего года:
        изменился набор — записи есть, не изменился — NotModified-ответ
        значением (пустой кортеж, курсор на месте)."""
        year = cursor[:4] if cursor and cursor[:4].isdigit() else \
            _today_year()
        url = DFP_URL.format(year=year)
        state = self.dataset_state(url)
        if isinstance(state, (ConfigError, ProviderError)):
            return state
        if cursor and state.last_modified == cursor:
            return IndexPoll(records=(), cursor=cursor)
        return IndexPoll(records=(), cursor=state.last_modified)

    def list_documents(self, issuer_id: str, doc_type: str | None = None,
                       period: str | None = None) -> DocumentList | ProviderError | ConfigError:
        """Метаданные подач эмитента из индекса DFP (запись под данными
        уже есть у вызывающего; здесь — точка инъекции для тестов)."""
        return ProviderError(reason="cvm_index_needs_dataset")

    def fetch_document(self, url: str) -> FetchedDocument | ProviderError | ConfigError:
        """Документ CVM — структурированные строки, не PDF; тело набора
        качает вызывающий через dataset_if_changed. Прямой RAD-портал
        вне канала (REPORT-MARKETS: timeout), 404 значением."""
        return ProviderError(reason=f"cvm_not_a_document:{url[:40]}")


def _read_csv(data: bytes) -> list[dict]:
    text = data.decode("latin-1")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def _today_year() -> str:
    import datetime as _dt
    return str(_dt.date.today().year)


def build(gate: RequestGate):
    """Контракт места (TASK-19 F5): get_provider('cvm', gate)."""
    return CvmProvider.from_env(gate)


__all__ = ["CvmProvider", "DatasetState", "build", "CAD_URL", "DFP_URL"]
