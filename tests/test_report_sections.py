"""TASK-12 Y6: секции отчёта — машинная проверка вместо прозы.

Три задачи подряд просили в прозе писать споры в `## Disputed` — и три
раза раздел оставался пустым при живых спорах в других местах. Теперь
проверяет машина: отчёт, названный в agent/STATE.json ("report"),
обязан нести все пять секций; строки, начинающиеся с DISPUTED, живут
только внутри `## Disputed`; в `## HANDOFF` не осталось шаблонных
заполнителей. Пустой `## Disputed` легитимен — ловится перемещённый
спор, а не его отсутствие.

ТЗ-46 N1: заполнители ищутся в ПОСЛЕДНЕЙ секции, чей заголовок
начинается с HANDOFF, — финальный блок может называться
«## HANDOFF (FINAL …)», и именно он решает; промежуточный блок без
суффикса стража не устраивает.

ТЗ-62 G4 (BACKLOG B38): последний HANDOFF не должен ПРОТИВОРЕЧИТЬ
ветке. Если он называет пункт несделанным («Items not done», «не
сделан»), а коммит с этим пунктом на ветке есть — красный с именами
пункта и коммита. Правило одной строкой живёт в agent/PROTOCOL.md §5.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

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
            # ТЗ-76 W2: повторённый заголовок «## HANDOFF» — НОВАЯ
            # секция, а не продолжение прежней. setdefault сливал все
            # промежуточные HANDOFF в один список, и правило «решает
            # последний» работало лишь через уникальный суффикс
            # (FINAL …). Одноимённые блоки нумеруются, чтобы
            # _handoff_section видел именно последний из них.
            name = header.group(1).strip()
            current = name
            dup = 2
            while current in sections:
                current = f"{name} #{dup}"
                dup += 1
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _handoff_section(text: str) -> list[str]:
    """ТЗ-46 N1: последняя секция, чей заголовок НАЧИНАЕТСЯ с HANDOFF
    (регистр как есть). Финальный HANDOFF может нести суффикс
    «(FINAL …)» — проверять надо именно его, а не промежуточный блок
    без суффикса: иначе смена может закончиться блоком из одних
    заполнителей, и страж этого не увидит."""
    found: list[str] = []
    for name, lines in _sections(text).items():
        if name.startswith("HANDOFF"):
            found = lines
    return found


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
    handoff = "\n".join(_handoff_section(_report_text()))
    assert handoff.strip(), "секция ## HANDOFF пуста"
    for placeholder in ("N passed", "M skipped", "<"):
        assert placeholder not in handoff, (
            f"шаблонный заполнитель {placeholder!r} остался в HANDOFF")


def test_final_handoff_full_of_placeholders_reds_the_guard(monkeypatch):
    """ТЗ-46 N1, красный случай (временный текст, не живой отчёт):
    промежуточный ## HANDOFF заполнен честно, финальный
    ## HANDOFF (FINAL …) — из одних заполнителей. Страж обязан
    краснеть по финальному блоку и называть заполнитель."""
    text = (
        "# REPORT\n"
        "## Done\n"
        "- ok\n"
        "## HANDOFF\n"
        "Status: PARTIAL, всё честно, 12 passed\n"
        "## HANDOFF (FINAL — supersedes the interim values above)\n"
        "Status: N passed, M skipped\n"
        "Items done: <fill me>\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "_report_text",
                        lambda: text)
    with pytest.raises(AssertionError) as exc:
        test_handoff_carries_real_values_not_placeholders()
    message = str(exc.value)
    # страж падает на ПЕРВОМ заполнителе финального блока и зовёт его
    assert "N passed" in message, message


def test_honest_final_handoff_after_interim_passes(monkeypatch):
    """ТЗ-46 N1, зелёный случай того же разреза: промежуточный блок и
    честный финальный — страж зеленеет, interim-блок не проверяется."""
    text = (
        "# REPORT\n"
        "## HANDOFF\n"
        "Status: PARTIAL\n"
        "## HANDOFF (FINAL — supersedes the interim values above)\n"
        "Status: DONE, всё доведено до коммита\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "_report_text",
                        lambda: text)
    test_handoff_carries_real_values_not_placeholders()


# ── ТЗ-62 G4: последний HANDOFF не противоречит ветке ───────────────────

def _claimed_undone_ids(handoff: str) -> list[str]:
    """Пункты, которые последний HANDOFF называет несделанными:
    строки «Items not done» / «не сделан», идентификаторы вида буква
    + номер (E1, F2, G4...)."""
    ids: list[str] = []
    for line in handoff.splitlines():
        low = line.lower()
        if "items not done" in low or "не сделан" in low:
            ids += re.findall(r"\b[A-Z]\d+\b", line)
    return ids


def _commit_for_items(ids: list[str], round_no: int) -> dict[str, str]:
    """Коммиты ЭТОГО круга, в теме которых стоит пункт:
    {'F2': '<sha> <тема>'}. Круг ограничивает обзор: границы — коммит
    эстафеты «Эстафета: круг <N>», номера не уникальны между задачами
    (ТЗ-35 тоже имела G4/G5)."""
    if not ids:
        return {}
    proc = subprocess.run(
        ["git", "log", "--format=%h %s"], cwd=REPO,
        capture_output=True, text=True, check=True)
    lines = proc.stdout.splitlines()
    marker = f"Эстафета: круг {round_no},"
    end = next((i for i, ln in enumerate(lines) if marker in ln), None)
    if end is None:
        return {}
    found: dict[str, str] = {}
    for line in lines[:end]:
        sha, _, subject = line.partition(" ")
        for iid in ids:
            if iid not in found and re.search(rf"\b{iid}\b", subject):
                found[iid] = line
    return found


def _baton_round() -> int:
    baton = json.loads((REPO / "agent" / "BATON.json").read_text(
        encoding="utf-8"))
    return int(baton.get("round", 0))


def test_last_handoff_does_not_call_committed_items_undone():
    """G4: если последний HANDOFF называет пункт несделанным, а
    коммит с этим пунктом на ветке есть — красный с именами пункта
    и коммита. Соглашение «последний HANDOFF отменяет предыдущие» —
    PROTOCOL §5 (B38)."""
    handoff = "\n".join(_handoff_section(_report_text()))
    committed = _commit_for_items(_claimed_undone_ids(handoff),
                                  _baton_round())
    assert not committed, (
        "последний HANDOFF зовёт несделанным то, что уже закоммичено "
        f"в этом круге: {committed}")


def test_stale_report61_handoff_reds_the_guard():
    """Красная демонстрация на настоящей лжи круга 76: interim-HANDOFF
    REPORT-61 называл F2-F4 несделанными, пока они коммитились тем же
    кругом. Текст зафиксирован литералом — живой отчёт уже починен."""
    stale = ("Status: PARTIAL (F1 done; F2-F4 ahead)\n"
             "Arrival state: task taken round 76 on 008aded, selfcheck green\n"
             "Items done: F1\n"
             "Items not done: F2 three-face cross-check, F3 window at "
             "volume, F4 KR door\n")
    ids = _claimed_undone_ids(stale)
    assert sorted(ids) == ["F2", "F3", "F4"], ids
    committed = _commit_for_items(ids, 76)
    assert set(committed) == {"F2", "F3", "F4"}, committed


def test_done_items_have_code_commits_in_round():
    """ТЗ-66 L3: пункт из «Items done» обязан быть назван коммитом
    круга, который трогает не только tests/ — отчёт отвечает за свои
    слова реализацией, а не декларацией."""
    handoff = "\n".join(_handoff_section(_report_text()))
    done_ids: list[str] = []
    for line in handoff.splitlines():
        if "items done" in line.lower():
            done_ids += re.findall(r"\b[A-Z]\d+\b", line)
    if not done_ids:
        pytest.skip("в отчёте нет пунктов Items done")
    # ТЗ-76 W1: делит РАЗДЕЛИТЕЛЬ, а не пустая строка. `--name-only`
    # ставит пустую строку МЕЖДУ темой и списком файлов, поэтому
    # split("\n\n") резал блок ровно по теме: первой строкой
    # следующего блока оказывалось ИМЯ ФАЙЛА, и тема не совпадала
    # никогда. Страж проходил только через staged-фолбэк — то есть в
    # обычном прогоне не проверял ничего, а на чистом дереве краснел
    # (ТЗ-75, Disputed: приёмка 11/13). %x1e начинает каждый коммит
    # своим байтом, и тема снова первая строка блока.
    log = subprocess.run(
        ["git", "log", "--format=%x1e%h %s", "--name-only"],
        cwd=REPO, capture_output=True, text=True, check=True)
    named: dict[str, bool] = {}
    for block in log.stdout.split("\x1e"):
        lines_ = [l for l in block.strip().splitlines() if l.strip()]
        if not lines_:
            continue
        sha_subject = lines_[0]
        files = [l for l in lines_[1:] if l and not l.startswith("Эстафета")]
        for iid in done_ids:
            if re.search(rf"\b{iid}\b", sha_subject):
                named[iid] = named.get(iid, False) or any(
                    not f.startswith("tests/") for f in files if "/" in f
                    or f.endswith(".py") or f.endswith(".md"))
    missing = [iid for iid in done_ids if not named.get(iid)]
    if missing:
        # ТЗ-66 L2: пункт materializуется ЭТИМ же коммитом — staged
        # дифф, трогающий не только tests/, честно закрывает претензию
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], cwd=REPO,
            capture_output=True, text=True).stdout.splitlines()
        if any(not f.startswith("tests/") for f in staged):
            missing = []
    assert not missing, (
        f"пункты {missing} объявлены сделанными, но коммита круга с "
        f"реализацией (не только tests/) не найдено")
