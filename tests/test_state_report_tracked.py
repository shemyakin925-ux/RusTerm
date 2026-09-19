"""ТЗ-47 O3: отчёт, названный в STATE.json, обязан быть в этом коммите.

Три круга ушло на диагноз, который должен занимать одну строку вывода:
STATE.json называет отчёт, которого ещё нет, test_report_sections.py
падает голым FileNotFoundError, и непонятно, ЧТО делать. Правило
(вердикт по вопросу 1 ТЗ-45 в машинной форме): новый отчёт называется
в agent/STATE.json тем же коммитом, который его создаёт. Страж
говорит это прямо: имя отчёта и что его нет в git ls-files ЭТОГО
коммита.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_state_report_is_tracked_in_this_commit():
    state = json.loads(
        (REPO / "agent" / "STATE.json").read_text(encoding="utf-8"))
    report = state.get("report")
    assert report, "в agent/STATE.json нет поля report"
    listing = subprocess.run(
        ["git", "ls-files", "--", report], cwd=REPO,
        capture_output=True, text=True, check=True).stdout.split()
    assert report in listing, (
        f"agent/STATE.json называет отчёт {report!r}, которого нет в "
        "git ls-files этого коммита — новый отчёт обязан появиться тем "
        "же коммитом, который переводит на него STATE.json")
