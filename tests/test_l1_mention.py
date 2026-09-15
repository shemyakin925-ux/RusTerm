"""ТЗ-44 L1: барьер «сообщение называет страж — страж в коммите».

Оба исхода на скрипте agent/check_mention.sh:
- сообщение упоминает p6_rule.sh, файла нет в списке — красный;
- сообщение упоминает p6_rule.sh, файл в списке — зелёный;
- сообщение без упоминания — зелёный при любом списке.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "agent" / "check_mention.sh"


def _run(message: str, files: list[str]) -> subprocess.CompletedProcess:
    tmp = Path(__file__).resolve().parent
    msg = tmp / "l1-msg.txt"
    lst = tmp / "l1-files.txt"
    msg.write_text(message, encoding="utf-8")
    lst.write_text("\n".join(files) + "\n", encoding="utf-8")
    return subprocess.run(["bash", str(CHECK), str(msg), str(lst)],
                          capture_output=True, text=True)


def test_mention_without_file_is_red():
    result = _run("ТЗ-43 K1: p6 — пропуск коммита эстафеты\n",
                  ["tests/test_x.py"])
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout


def test_mention_with_file_is_green():
    result = _run("ТЗ-43 K1: p6 — пропуск коммита эстафеты\n",
                  ["tests/test_x.py", "agent/p6_rule.sh"])
    assert result.returncode == 0


def test_no_mention_is_green_with_any_files():
    result = _run("ТЗ-42: правка chat.py\n",
                  ["tests/test_x.py", "rusterm/core/chat.py"])
    assert result.returncode == 0
