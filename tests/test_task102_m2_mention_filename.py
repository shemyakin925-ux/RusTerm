"""ТЗ-102 M2: барьер упоминания матчит имя файла стража, а не токен.

Решение координатора по пункту 3 из спорных REPORT-97: сообщение коммита,
которое упоминает правило протокола («(P1: удалённых 0)»), не обязано нести
`agent/p1_rule.sh` — страж не менялся и обещан не был. Нести он обязан
ровно то, что названо его именем файла.

Зубы пишут черновики в tmp_path: соседний модуль test_l1_mention.py
оставляет свои черновики в tests/ под git, и второй паре файлов там не
место.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

CHECK = Path(__file__).resolve().parents[1] / "agent" / "check_mention.sh"
NO_GUARD = ["tests/test_x.py", "rusterm/core/snapshot.py"]


def _run(tmp_path: Path, message: str,
         files: list[str]) -> subprocess.CompletedProcess:
    msg = tmp_path / "msg.txt"
    lst = tmp_path / "files.txt"
    msg.write_text(message, encoding="utf-8")
    lst.write_text("\n".join(files) + "\n", encoding="utf-8")
    return subprocess.run(["bash", str(CHECK), str(msg), str(lst)],
                          capture_output=True, text=True)


def test_bare_rule_token_without_the_guard_is_green(tmp_path):
    """Ложный красный круга 137: в сообщении упомянуты правила P1 и P6,
    стражей в коммите нет и не должно быть — барьер молчит."""
    result = _run(tmp_path,
                  "ТЗ-97 Q12 (1): страж упоминаний — ложный красный "
                  "(P1: удалённых 0), P6-проверка не тронута\n", NO_GUARD)
    assert result.returncode == 0, result.stdout


def test_file_name_mention_without_the_guard_is_red(tmp_path):
    """Сообщение называет `p6_rule.sh` — страж обязан в составе коммита."""
    result = _run(tmp_path,
                  "ТЗ-102 M2: ремонт p6_rule.sh — матч по имени файла\n",
                  NO_GUARD)
    assert result.returncode != 0
    assert "agent/p6_rule.sh" in result.stdout, result.stdout


def test_file_name_mention_with_the_guard_is_green(tmp_path):
    result = _run(tmp_path,
                  "ТЗ-102 M2: ремонт p6_rule.sh — матч по имени файла\n",
                  NO_GUARD + ["agent/p6_rule.sh"])
    assert result.returncode == 0, result.stdout


def test_each_guard_is_checked_for_itself(tmp_path):
    """Назван `p1_rule.sh`, а в коммите уехал соседний страж: обещание
    без исполнения. Барьер попарный, а не «любой страж»."""
    result = _run(tmp_path,
                  "ТЗ-44 L1: p1_rule.sh читает индекс коммита\n",
                  NO_GUARD + ["agent/p6_rule.sh"])
    assert result.returncode != 0
    assert "agent/p1_rule.sh" in result.stdout, result.stdout


def test_path_prefix_does_not_change_the_verdict(tmp_path):
    """`agent/p6_rule.sh` и голое `p6_rule.sh` — одно и то же имя."""
    red = _run(tmp_path, "правка agent/p6_rule.sh\n", NO_GUARD)
    green = _run(tmp_path, "правка agent/p6_rule.sh\n",
                 NO_GUARD + ["agent/p6_rule.sh"])
    assert red.returncode != 0, red.stdout
    assert green.returncode == 0, green.stdout
