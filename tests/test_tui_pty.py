"""Страж связности экрана: клавиши нажимаются в настоящем терминале.

Дефекты, ради которых файл заведён (находки координатора 17.09.2026,
оба при 13/13 зелёной приёмки):

1. Карточка инструмента — 44 строки; на обычном терминале 80x24
   `addstr` за краем окна поднимал `_curses.error: addwstr() returned
   ERR`, и программа умирала с кодом 2. Тест, вызывающий функцию
   экрана напрямую, ширины окна не знает и этого не видит.
2. Экран разговора строился клиентом без метода `chat`, и первый же
   вопрос ронял программу. Тест подменял дверь фальшивкой, у которой
   `chat` есть.

Правило: экран проверяется настоящим `python3 -m rusterm.cli tui` в
pty заданного размера. Сети здесь нет — данные синтетические, ключа в
окружении нет (изоляция conftest).
"""
from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEYS = {"DOWN": "\x1b[B", "UP": "\x1b[A", "ENTER": "\r", "ESC": "\x1b"}
_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _cli(root: Path, *args: str) -> None:
    done = subprocess.run([sys.executable, "-m", "rusterm.cli",
                           "--root", str(root), *args],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, f"{args}: {done.stdout}{done.stderr}"


@pytest.fixture
def populated_root(tmp_path):
    """Каталог данных с одним инструментом в списке наблюдения."""
    root = tmp_path / "data"
    _cli(root, "init")
    _cli(root, "demo")
    _cli(root, "ingest", "--instrument", "US-CLI-DEMO")
    _cli(root, "snapshot", "--instrument", "US-CLI-DEMO")
    _cli(root, "watchlist", "create", "pty-list", "--name", "Прогон")
    _cli(root, "watchlist", "add", "pty-list", "--instrument", "US-CLI-DEMO")
    return root


def _drive(root: Path, keys: list[str], rows: int = 24,
           cols: int = 80) -> tuple[int, str]:
    """Запустить tui в pty размера rows x cols, нажать клавиши, выйти.

    Возвращает (код возврата, весь вывод без управляющих
    последовательностей). Размер окна задаётся ioctl — именно его
    видит curses; переменные LINES/COLUMNS на него не влияют.
    """
    argv = [sys.executable, "-m", "rusterm.cli", "--root", str(root), "tui"]
    env = dict(os.environ, TERM="xterm-256color")
    pid, fd = pty.fork()
    if pid == 0:  # pragma: no cover — дочерний процесс
        os.chdir(ROOT)
        os.execve(argv[0], argv, env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    chunks: list[str] = []

    def pump(seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if not ready:
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                return False
            if not data:
                return False
            chunks.append(data.decode("utf-8", "replace"))
        return True

    alive = pump(1.2)
    for key in keys:
        if not alive:
            break
        os.write(fd, KEYS.get(key, key).encode())
        alive = pump(0.8)
    if alive:
        os.write(fd, b"q")
        pump(0.5)
    try:
        os.close(fd)
    except OSError:
        pass
    _pid, status = os.waitpid(pid, 0)
    text = _CSI.sub("", "".join(chunks))
    return os.waitstatus_to_exitcode(status), text


@pytest.mark.parametrize("size", [(24, 80), (40, 140)])
def test_card_screen_survives_a_terminal_smaller_than_the_card(
        populated_root, size):
    """Карточка длиннее окна — прокрутка, а не гибель программы."""
    rows, cols = size
    code, text = _drive(populated_root, ["ENTER", "s", "ESC"],
                        rows=rows, cols=cols)
    assert "Traceback" not in text, text[-1500:]
    assert "addwstr" not in text, (
        f"{rows}x{cols}: экран вышел за край окна — "
        f"карточка обязана обрезаться и прокручиваться")
    assert code == 0, f"{rows}x{cols}: код возврата {code}\n{text[-1500:]}"


def test_chat_screen_answers_the_first_question(populated_root):
    """Клавиша «c», настоящий вопрос, Enter — названный отказ на
    экране, а не AttributeError в журнале."""
    code, text = _drive(populated_root,
                        ["c", "какая выручка", "ENTER", "ESC"])
    assert "Traceback" not in text, text[-1500:]
    assert "AttributeError" not in text, (
        "клиент двери не умеет того, что зовёт ChatSession.ask")
    assert code == 0, f"код возврата {code}\n{text[-1500:]}"
    assert "отказ" in text or "модель" in text, (
        f"разговор ничего не ответил на вопрос:\n{text[-800:]}")
