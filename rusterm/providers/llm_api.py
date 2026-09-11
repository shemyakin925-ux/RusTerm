"""OpenAI-совместимый клиент модели по API (ADR-0011 ②, TASK-19 F6).

HTTP живёт здесь, в провайдерах (проверка 8 приёмки). Вариант работы
с моделью ровно один — API; локальной модели в проекте нет (решение
пользователя 10.09.2026). Конфигурация из окружения:
RUSTERM_LLM_BASE_URL (по умолчанию OpenRouter), RUSTERM_LLM_MODEL,
RUSTERM_LLM_API_KEY — и только оттуда.

Ключ не печатается, не логируется, не попадает в аудит, отчёты,
фикстуры и git; в Authorization он обязан быть — это его единственная
поездка. Ключа нет — ConfigError значением и офлайн-путь (N2), не
исключение. Тесты не ходят к модели: транспорт инъектируется и
возвращает записанные тела; ни один тест не требует ключа.

Место реестра: rusterm.providers.get_provider("llm-api", gate) -> build.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping

from .base import ProviderError
from .budget import BudgetExceeded, ConfigError, HostLimit, RequestGate

BASE_URL_ENV = "RUSTERM_LLM_BASE_URL"
MODEL_ENV = "RUSTERM_LLM_MODEL"
KEY_ENV = "RUSTERM_LLM_API_KEY"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

_PROVIDER_NAME = "llm-api"


def _default_transport(url: str, headers: dict, payload: bytes) -> tuple:
    """Живой транспорт: (статус, тело, заголовки)."""
    request = urllib.request.Request(url, data=payload,
                                     headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


@dataclass
class LlmApiClient:
    """Клиент chat/completions OpenAI-совместимого эндпойнта.

    Контракт с core: complete(prompt) -> текст ответа или ошибка
    значением (ConfigError/BudgetExceeded) — исключения наружу не
    выходят. Ретраи и таймауты живого эндпойнта — TASK-20 L7.
    """

    base_url: str
    model: str
    api_key: str
    limit: HostLimit
    gate: RequestGate | None = None
    transport: Callable[[str, dict, bytes], tuple] = _default_transport

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None,
                 gate: RequestGate | None = None,
                 limit: HostLimit | None = None):
        """Сборка из окружения. Ключа нет — ConfigError('llm_key_unset')
        значением; ключ есть, модели нет — ConfigError('llm_model_unset')."""
        env = os.environ if environ is None else environ
        key = env.get(KEY_ENV, "")
        if not key:
            return ConfigError(reason="llm_key_unset")
        model = (env.get(MODEL_ENV) or "").strip()
        if not model:
            return ConfigError(reason="llm_model_unset")
        base = (env.get(BASE_URL_ENV) or "").strip() or DEFAULT_BASE_URL
        if limit is None:
            limit = HostLimit(host="openrouter.ai", per_second=1.0,
                              nightly_max=5000)
        return cls(base_url=base.rstrip("/"), model=model, api_key=key,
                   limit=limit, gate=gate)

    def complete(self, prompt: str) -> str | ConfigError | BudgetExceeded:
        """Один вызов модели. Без гейта модель не вызывается — та же
        дверь, что у всякого сетевого провайдера (TASK-8 U5)."""
        if self.gate is None:
            return ConfigError(reason="llm_provider_requires_gate")

        def send(headers: dict):
            merged = dict(headers)
            merged["Content-Type"] = "application/json"
            merged["Authorization"] = f"Bearer {self.api_key}"
            payload = json.dumps({
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }).encode("utf-8")
            return self.transport(self.base_url + "/chat/completions",
                                  merged, payload)

        result = self.gate.request(send, limit=self.limit)
        if isinstance(result, (ConfigError, BudgetExceeded)):
            return result
        status, body, _headers = result
        if status != 200:
            # статус без тела: тело чужого ответа может что угодно нести
            return ConfigError(reason=f"llm_http_{status}")
        try:
            parsed = json.loads(body.decode("utf-8"))
            text = parsed["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError,
                UnicodeDecodeError):
            return ConfigError(reason="llm_bad_response")
        if not isinstance(text, str):
            return ConfigError(reason="llm_bad_response")
        return text


def build(gate: RequestGate):
    """Контракт места провайдера (TASK-19 F5): get_provider('llm-api').
    Ключа нет — ConfigError значение; вызовы модели считаются гейтом по
    хосту источника, а не бюджетом SEC (TASK-19 F5)."""
    from rusterm.providers import host_limit
    return LlmApiClient.from_env(gate=gate,
                                 limit=host_limit(_PROVIDER_NAME))


__all__ = ["LlmApiClient", "build", "BASE_URL_ENV", "MODEL_ENV",
           "KEY_ENV"]
