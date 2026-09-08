"""M5 — реальная модель за предохранителем (TASK-9 V7).

Без RUSTERM_LLM_API_KEY пропускется чисто: путь не симулируется,
фальшивый клиент не выдаётся за веху. С ключом — максимум 2 вызова,
каждое числовое утверждение с цитатой, массовая операция ничего
не исполняет.
"""
from __future__ import annotations

import pytest

from rusterm import env as env_module


def test_m5_real_model_skips_without_key():
    env_module.load_env()
    if not __import__("os").environ.get("RUSTERM_LLM_API_KEY"):
        pytest.skip("LLM key unset — M5 not exercised")
    pytest.fail("ключ задан, а живой путь M5 не реализован — "
                "реализуйте по контракту TASK-7 T16 (V7)")
