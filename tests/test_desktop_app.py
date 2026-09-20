"""TASK-C10.4: smoke-тест сборки — собранное .app стартует и
закрывается с кодом 0.

В ОБЫЧНОМ ПРОГОНЕ ТЕСТ ПРОПУСКАЕТСЯ: он живёт только при двух
условиях сразу — сборка dist/EquityLab.app существует и переменная
RUSTERM_APP_SMOKE=1 выставлена рукой запускающего (маркер прогона
сборки). Сеть на тест не тратится; каталог данных — tmp_path.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_BINARY = ROOT / "dist" / "EquityLab.app" / "Contents" / "MacOS" \
    / "EquityLab"

pytestmark = pytest.mark.skipif(
    not APP_BINARY.exists() or os.environ.get("RUSTERM_APP_SMOKE") != "1",
    reason="smoke сборки: нужен собранный dist/EquityLab.app и "
           "RUSTERM_APP_SMOKE=1 (маркер прогона сборки); в обычном "
           "прогоне пропускается")


def test_built_app_starts_and_exits_zero(tmp_path):
    empty_root = tmp_path / "data"
    empty_root.mkdir()
    result = subprocess.run(
        [str(APP_BINARY), "--root", str(empty_root)],
        env=dict(os.environ, RUSTERM_APP_SMOKE="1",
                 QT_QPA_PLATFORM="offscreen"),
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    # каталога не было — окно сказало словами и ничего не создало
    assert not (empty_root / "rusterm.db").exists()
