"""ТЗ-58 C5: живая проба цепочки «объявление → тело документа» (AU).

МАРКЕР: RUSTERM_LIVE=1 (как у B36) — обычный набор пропускает. Бюджет
ТЗ-58 C5: до 15 запросов через RequestGate. Проба: анонсы CBA живьём,
затем перебор известных публичных форм URL тела документа; каждый шаг
записан (статус, content-type, первые байты). Исход — либо пойманное
тело (сохраняется как записанный ответ), либо точный отказ: код, форма
URL, что именно закрыто.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RUSTERM_LIVE") != "1",
        reason="живая проба AU: только с RUSTERM_LIVE=1; обычный набор "
               "не тратит сеть"),
]

BASE = "https://asx.api.markitdigital.com/asx-research/1.0/companies"
BODY_URL_FORMS = [
    "https://www.asx.com.au/asx/1/file/{key}",
    "https://www.asx.com.au/asxpdf/{key}/pdf/0x0{key}.pdf",
    "https://www.asx.com.au/asx/1/file/{key}.pdf",
]


def _get(url: str):
    """Прямой GET пробы: (status, bytes, headers)."""
    import urllib.request
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read(), dict(response.headers)


def test_c5_asx_announcement_body_chain(tmp_path):
    from rusterm.providers.asx import AsxProvider
    from rusterm.providers.budget import NetworkGate, RequestGate

    # conftest вычистил RUSTERM_* — живой прогон читает настоящий
    # ~/.rusterm.env (SEC UA обязателен для транспорта)
    os.environ["RUSTERM_ENV_FILE"] = str(Path.home() / ".rusterm.env")
    from rusterm import env as env_module
    env_module.load_env()
    gate = RequestGate(gate=NetworkGate(dict(os.environ)))
    provider = AsxProvider(gate=gate)

    announcements = provider.announcements_raw("CBA")
    assert isinstance(announcements, (bytes, bytearray)), announcements
    items = (json.loads(announcements.decode("utf-8")).get("data")
             or {}).get("items") or []
    assert items, "анонсов нет — цепочке не с чего начинать"
    key = items[0].get("documentKey", "")
    assert key, items[0]

    attempts = []
    body = None
    for form in BODY_URL_FORMS:
        url = form.format(key=key)
        try:
            status, payload, headers = _get(url)
        except Exception as exc:  # точный отказ сети — тоже измерение
            attempts.append({"url": url, "error": repr(exc)[:120]})
            continue
        head = payload[:8]
        attempts.append({"url": url, "status": status,
                         "content_type": headers.get("Content-Type", ""),
                         "bytes": len(payload),
                         "head": head.decode("latin-1")})
        if status == 200 and head.startswith(b"%PDF"):
            body = payload
            break
    (Path("/tmp") / "c5_attempts.json").write_text(
        json.dumps(attempts, ensure_ascii=False, indent=1),
        encoding="utf-8")
    assert gate.calls_made <= 15, gate.calls_made

    if body is None:
        # исход по Done-when №2: точный отказ назван (каждая попытка —
        # статус/ошибка, URL-форма, что закрыто) и оформлен причиной
        # из словаря; провайдер остаётся на manual_import_required
        from rusterm.providers import ProviderError
        outcome = provider.fetch_document(f"asxdoc:{key}")
        assert isinstance(outcome, ProviderError)
        assert outcome.reason.startswith("manual_import_required:asxdoc:")
        assert attempts, "попыток не было — это не измерение"
        print("C5_REFUSAL:", json.dumps(attempts, ensure_ascii=False))
    else:
        target = Path(__file__).resolve().parents[1] / "tests" / "data" \
            / "asx" / f"body_{key}.pdf"
        target.write_bytes(body)
        print("BODY_SAVED:", target, len(body))
