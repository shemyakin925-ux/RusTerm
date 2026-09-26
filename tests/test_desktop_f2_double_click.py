"""ТЗ-95 F2: двойной щелчок проверяет машина, а не человек.

Прошлый smoke-тест (ТЗ-81 B3) собирал бинарь без экрана и падения не
видел: у пользователя окно не появилось вообще, и узнали это только со
слов. Здесь проверяется ровно та дверь, которой пользуется человек —
`open`, то есть запуск из Finder: у процесса нет окружения терминала,
каталог выбирается правилами из ТЗ-90 A5, и никаких RUSTERM_DATA в
потомках не остаётся.

Зубы: процесс обязан быть жив через 5 секунд после запуска и молчать в
stderr. На дереве ДО ТЗ-95 F1 второй случай красен — замер приведён в
agent/REPORT-95.md (строка `no such table: chat_transcript`).

Сборка и каталоги:
- `.app` собирается этим же кодом (`python3 -m PyInstaller
  EquityLab.spec --noconfirm`), dist/work уходят в песочницу теста, чтобы
  не плодить следы в дереве клона;
- каталог со свежей схемой строится миграциями, каталог со старой —
  настоящая база схемы 44 из tests/data/upgrade (тот же файл, что у
  test_upgrade_path и test_desktop_f1_stale_schema).

В обычном наборе тест не гоняется (pyproject addopts снимает firsthour),
явный вызов: `python3 -m pytest -m firsthour tests/test_desktop_f2_double_click.py`.
На экране на несколько секунд появляется настоящее окно — это и есть
проверяемый запуск.
"""
from __future__ import annotations

import gzip
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rusterm.store.db import apply_migrations
from rusterm.store.paths import AppPaths, ensure_app_dir

pytestmark = pytest.mark.firsthour

REPO = Path(__file__).resolve().parents[1]
STALE_FIXTURE = REPO / "tests" / "data" / "upgrade" / "schema44.sqlite.gz"

# Сколько секунд ждём перед проверкой живости: меньше — не увидим
# падение на старте, больше — тянет прогон ради ничего.
ALIVE_SECONDS = 5.0


def _app_dir(app: Path) -> Path:
    return app / "Contents" / "MacOS"


def _build_app(work: Path) -> Path:
    """Собрать .app той же командой, что названа в GUIDE.md."""
    if importlib.util.find_spec("PyInstaller") is None:
        pytest.skip("PyInstaller не установлен — сборку не проверить")
    done = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "EquityLab.spec",
         "--noconfirm", "--distpath", str(work / "dist"),
         "--workpath", str(work / "build")],
        cwd=REPO, capture_output=True, text=True, timeout=900)
    tail = (done.stdout[-2000:] + done.stderr[-2000:])
    assert done.returncode == 0, f"сборка не вышла: {tail}"
    app = work / "dist" / "EquityLab.app"
    assert app.is_dir(), f"сборка не оставила {app}: {tail}"
    return app


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    return _build_app(tmp_path_factory.mktemp("f2-build"))


def _current_catalog(root: Path) -> Path:
    root.mkdir()
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    conn = _connect(paths)
    apply_migrations(conn)
    conn.close()
    return root


def _stale_catalog(root: Path) -> Path:
    """База схемы 44: без таблицы разговоров — тот каталог, на котором
    окно умирало."""
    root.mkdir()
    (root / "rusterm.db").write_bytes(
        gzip.open(STALE_FIXTURE, "rb").read())
    paths = AppPaths.from_root(root)
    ensure_app_dir(paths)
    return root


def _connect(paths: AppPaths):
    import sqlite3
    conn = sqlite3.connect(str(paths.db_path), timeout=30,
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _pids(app: Path) -> set[str]:
    """Процессы ЭТОЙ сборки: узор — абсолютный путь бинаря внутри
    песочницы теста, чужие окна EquityLab под него не попадают."""
    done = subprocess.run(["pgrep", "-f", str(_app_dir(app) / "EquityLab")],
                          capture_output=True, text=True)
    return {p for p in done.stdout.split()}


def _launch_like_finder(app: Path, root: Path, log_dir: Path) -> tuple[
        bool, str]:
    """Запуск через `open` — та же дверь, что двойной щелчок. Возвращает
    (жив ли процесс через ALIVE_SECONDS, что он написал в stderr)."""
    stdout = log_dir / "stdout.txt"
    stderr = log_dir / "stderr.txt"
    for f in (stdout, stderr):
        f.write_text("", encoding="utf-8")
    before = _pids(app)
    launcher = subprocess.Popen(
        ["open", "-n", "-W", "--stdout", str(stdout), "--stderr",
         str(stderr), str(app), "--args", "--root", str(root)])
    time.sleep(ALIVE_SECONDS)
    mine = _pids(app) - before
    alive = bool(mine)
    print(f"[f2] launch root={root.name} alive_after_{ALIVE_SECONDS}s="
          f"{len(mine)} stderr_bytes={stderr.stat().st_size}", flush=True)
    if alive:
        # закрываем за собой: сигнал процессу сборки, потом — лоадеру
        for pid in sorted(mine):
            subprocess.run(["kill", pid], check=False)
        deadline = time.time() + 10
        while time.time() < deadline and (_pids(app) - before):
            time.sleep(0.5)
        left = _pids(app) - before
        for pid in sorted(left):
            subprocess.run(["kill", "-9", pid], check=False)
        assert not (_pids(app) - before), f"окно не закрылось: {left}"
    assert launcher.wait(timeout=120) == 0, "open не дождался процесса"
    return alive, stderr.read_text(encoding="utf-8", errors="replace")


# ── 1. свежая база: двойной щелчок открывает окно ───────────────────────

def test_double_click_on_a_current_catalog_keeps_the_process_alive(
        bundle, tmp_path):
    root = _current_catalog(tmp_path / "current")
    alive, err = _launch_like_finder(bundle, root, tmp_path)
    assert alive, f"процесс умер за {ALIVE_SECONDS} с:\n{err[-2500:]}"
    assert "Traceback" not in err, err[-2500:]


# ── 2. старая база: то же окно, только словами ───────────────────────────

def test_double_click_on_a_stale_schema_keeps_the_process_alive(
        bundle, tmp_path):
    """На дереве до ТЗ-95 F1 этот случай красен: процесс не доживает до
    проверки, а stderr кончается строкой
    `no such table: chat_transcript`."""
    root = _stale_catalog(tmp_path / "stale44")
    alive, err = _launch_like_finder(bundle, root, tmp_path)
    assert alive, (f"окно на отставшей базе не запустилось — "
                   f"двойной щелчок молчит:\n{err[-2500:]}")
    assert "no such table" not in err, err[-2500:]
    assert "Traceback" not in err, err[-2500:]
