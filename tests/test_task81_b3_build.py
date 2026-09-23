"""ТЗ-81 B3: сборка .app воспроизводится из репозитория.

ТЗ-C10 засчитал сборку структурно: `app_entry.py` и smoke-тест есть, а
spec-файл, из которого она собирается, был в `.gitignore` — то есть
собрать `.app` из клона было нельзя («существует только как локальный
артефакт»). Здесь проверяются именно те три вещи, которые нельзя
вычитать из наличия исходников: файл сборки лежит в репозитории и не
игнорируется, окно в нём — без консоли (двойной щелчок не рождает
терминал), и каталог данных находится при запуске без шелла.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rusterm import env as env_module
from rusterm.store.paths import default_root

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "EquityLab.spec"


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT),
                          capture_output=True, text=True)


def test_build_spec_lives_in_the_repository_and_is_not_ignored():
    """Строка `EquityLab.spec` из `.gitignore` снята: файл отслеживается
    git, и `check-ignore` его не прячет. `build/` и `dist/` — остаются
    игнорируемыми: мусор сборки по-прежнему красил бы страж
    неотслеживаемых файлов (проверено здесь, а не на веру)."""
    assert SPEC.exists(), "спеки нет в репозитории — сборка не воспроизводится"
    tracked = _git("ls-files", "--error-unmatch", "EquityLab.spec")
    assert tracked.returncode == 0, tracked.stderr[-300:]
    ignored = _git("check-ignore", "-q", "EquityLab.spec")
    assert ignored.returncode != 0, "файл сборки снова спрятан в .gitignore"
    for artifact in ("build/x", "dist/y"):
        assert _git("check-ignore", "-q", artifact).returncode == 0, artifact


def test_spec_builds_a_windowed_app_named_equitylab():
    """«Без единого окна терминала» — это `console=False` в EXE и
    `BUNDLE(... name='EquityLab')`; ключ назван явно, а не подразумевается."""
    text = SPEC.read_text(encoding="utf-8")
    assert "console=False" in text, "без console=False рядом с окном живёт терминал"
    assert "--windowed" in text, "эквивалент ключа назван в спеке комментарием"
    assert "app_entry.py" in text, "точка входа сборки — rusterm/desktop/app_entry.py"
    assert "name='EquityLab'" in text or 'name="EquityLab"' in text


def test_data_catalog_is_found_without_a_shell(tmp_path, monkeypatch):
    """Двойной щелчок — это пустое окружение: RUSTERM_DATA не придёт из
    шелла. Каталог должен читаться из того же файла, из которого программа
    берёт ключи (~/.rusterm.env, имя переопределяется RUSTERM_ENV_FILE),
    иначе окно откроет ~/.rusterm и назовёт цифрами чужую базу."""
    catalog = tmp_path / "equitylab"
    catalog.mkdir()
    env_file = tmp_path / "rusterm.env"
    env_file.write_text(f"RUSTERM_DATA={catalog}\n", encoding="utf-8")
    env_file.chmod(0o600)
    monkeypatch.setenv("RUSTERM_ENV_FILE", str(env_file))
    monkeypatch.delenv("RUSTERM_DATA", raising=False)
    env_module.load_env()
    assert os.environ.get("RUSTERM_DATA") == str(catalog), \
        "env-файл не доносит каталог данных до запущенного без шелла окна"
    assert Path(default_root()) == catalog


def test_one_documented_command_builds_from_the_committed_spec():
    """README и GUIDE называют команду сборки, и она смотрит в spec,
    который лежит в репозитории, — а не в локальный файл, которого нет
    ни в одном клоне (именно так сборка и перестала быть воспроизводимой)."""
    docs = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "GUIDE.md") if (ROOT / name).exists())
    assert "EquityLab.spec" in docs, "команда сборки не названа в README/GUIDE"
    assert "PyInstaller" in docs or "pyinstaller" in docs
    assert "--windowed" in docs or "console=False" in docs, \
        "почему рядом нет терминала, должно быть сказано вслух"
