"""TASK-12 Y6: секции отчёта — машинная проверка вместо прозы.

Три задачи подряд просили в прозе писать споры в `## Disputed` — и три
раза раздел оставался пустым при живых спорах в других местах. Теперь
проверяет машина: отчёт, названный в agent/STATE.json ("report"),
обязан нести все пять секций; строки, начинающиеся с DISPUTED, живут
только внутри `## Disputed`; в `## HANDOFF` не осталось шаблонных
заполнителей. Пустой `## Disputed` легитимен — ловится перемещённый
спор, а не его отсутствие.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

REQUIRED_SECTIONS = ("Done", "Blocked", "What not to trust", "Disputed",
                     "HANDOFF")


def _report_text() -> str:
    state = json.loads(
        (REPO / "agent" / "STATE.json").read_text(encoding="utf-8"))
    return (REPO / state["report"]).read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, list[str]]:
    """{имя секции '## X': строки до следующего '## '} — кроме строк
    самой шапки до первой секции."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        header = re.match(r"^## (.+?)\s*$", line)
        if header:
            current = header.group(1).strip()
            sections.setdefault(current, [])
        elif current is not None:
            sections[current].append(line)
    return sections


def test_report_carries_every_required_section():
    sections = _sections(_report_text())
    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    assert not missing, f"нет секций: {missing}"


def test_disputed_lines_live_only_in_disputed_section():
    """Строка, начинающаяся с DISPUTED (без учёта регистра, после
    снятия маркеров списка), допустима только внутри ## Disputed.
    Вынести спор — значит записать его в секцию; пункт Done может
    ссылаться на него, но не тащить спор в себе."""
    text = _report_text()
    sections = _sections(text)
    current: str | None = None
    misplaced: list[str] = []
    for line in text.splitlines():
        header = re.match(r"^## (.+?)\s*$", line)
        if header:
            current = header.group(1).strip()
            continue
        marker = line.lstrip(" -*").strip()
        if marker.upper().startswith("DISPUTED") and current != "Disputed":
            misplaced.append(line)
    assert not misplaced, (
        f"DISPUTED вне ## Disputed (перенесите в секцию): {misplaced}; "
        f"в самой секции сейчас {len(sections.get('Disputed', []))} строк")


def test_handoff_carries_real_values_not_placeholders():
    handoff = "\n".join(_sections(_report_text()).get("HANDOFF", []))
    assert handoff.strip(), "секция ## HANDOFF пуста"
    for placeholder in ("N passed", "M skipped", "<"):
        assert placeholder not in handoff, (
            f"шаблонный заполнитель {placeholder!r} остался в HANDOFF")
