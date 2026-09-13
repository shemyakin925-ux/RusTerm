"""M5 — реальная модель за предохранителем (TASK-9 V7).

ТЗ-29 A3: растяжка больше не ловит наличие ключа в default-прогоне —
тест несёт маркер live и по умолчанию не собирается (addopts
-m "not live"). Контракт сохранён: явный прогон -m live с ключом
падает, пока живой путь M5 не реализован; сам долг записан в
agent/BACKLOG.md поимённо (B36). Без ключа — чистый пропуск: путь не
симулируется, фальшивый клиент не выдаётся за веху.
"""
from __future__ import annotations

import pytest

from rusterm import env as env_module


@pytest.mark.live
def test_m5_real_model_skips_without_key():
    env_module.load_env()
    if not __import__("os").environ.get("RUSTERM_LLM_API_KEY"):
        pytest.skip("LLM key unset — M5 not exercised")
    pytest.fail("ключ задан, а живой путь M5 не реализован — "
                "реализуйте по контракту TASK-7 T16 (V7)")
