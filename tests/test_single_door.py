"""Страж: у двери есть посетители, а в обход двери не ходят.

Дефект, ради которого страж заведён (находка координатора 11.09.2026,
пункт N1 ТЗ-27): ТЗ-19 F6 построило селектор
`rusterm.core.llm.make_intent_client` — единственное место, где
решается, работать через API или детерминированным RuleClient. Место
построено, покрыто тестами и **не вызывается ниоткуда**: `cmd_ops`
по-прежнему конструирует `RuleClient()` на месте вызова. Ключ в
окружении пользователя не менял ничего, и приёмка 13 из 13 этого не
видела: она проверяет строение, а не связность.

Сплошной страж «всякая непубличная функция должна иметь вызов» здесь
непригоден — он красит двадцать отраслевых функций и все формулы,
которые достаются из реестра по имени (измерено: 109 срабатываний из
170 функций). Поэтому страж узкий: дверь объявляется явно, и у неё
проверяется ровно две вещи.

Правило для исполнителя: дверь закрывается **удалением строки из
PENDING**, а не добавлением исключения. Запись в PENDING обязана
называть пункт ТЗ, который её закроет, и становится красной, как
только дверь заработала, — тогда строку нужно снять.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "rusterm"

# Дверь: (модуль двери, имя селектора, реализации за ней).
DOORS = (
    ("rusterm/core/llm.py", "make_intent_client",
     ("RuleClient", "LlmApiClient")),
)

# Двери, ещё не подключённые. Строка обязана называть пункт ТЗ.
# Снимается, когда дверь заработала, — страж этого требует.
PENDING = {
    "make_intent_client": "TASK-27 N1 — cmd_ops берёт клиента напрямую",
}

_TASK_RE = re.compile(r"\bTASK-\d+\b")


def _module_files() -> list[Path]:
    return sorted(PKG.rglob("*.py"))


def _calls_to(name: str, *, skip: str) -> list[str]:
    """Места вызова `name` в rusterm/, кроме модуля самой двери."""
    found = []
    for path in _module_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == skip:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            hit = (isinstance(func, ast.Name) and func.id == name) or (
                isinstance(func, ast.Attribute) and func.attr == name)
            if hit:
                found.append(f"{rel}:{node.lineno}")
    return found


def test_every_pending_entry_names_a_task():
    for door, reason in PENDING.items():
        assert _TASK_RE.search(reason), (
            f"{door}: запись в PENDING без пункта ТЗ — так долг становится"
            f" бессрочным: {reason!r}")


def test_pending_entries_are_stale_once_the_door_works():
    """Дверь заработала — строку из PENDING обязаны снять."""
    for module, door, _impls in DOORS:
        if door not in PENDING:
            continue
        callers = _calls_to(door, skip=module)
        assert not callers, (
            f"{door} уже вызывается из {', '.join(callers)} — удалите строку"
            f" из PENDING в {Path(__file__).name}, дверь больше не долг")


def test_door_has_callers_or_a_named_debt():
    for module, door, _impls in DOORS:
        callers = _calls_to(door, skip=module)
        assert callers or door in PENDING, (
            f"{door} не вызывается ниоткуда и не числится долгом:"
            f" либо подключите дверь, либо назовите пункт ТЗ в PENDING")


def test_implementations_are_built_only_behind_their_door():
    """В обход двери реализацию не конструируют — кроме самой двери.

    Пока дверь числится в PENDING, обход существует: он и есть
    содержание долга, и страж держит его видимым и адресным. Как
    только обходов не осталось, дверь подключена — строку из PENDING
    снимают, и правило переворачивается в запрет.
    """
    for module, door, impls in DOORS:
        bypass: list[str] = []
        for impl in impls:
            bypass += [f"{impl} @ {site}"
                       for site in _calls_to(impl, skip=module)]
        if door in PENDING:
            assert bypass, (
                f"ни одна реализация за {door} больше не конструируется"
                f" напрямую — дверь подключили: снимите строку из PENDING"
                f" в {Path(__file__).name}")
            continue
        assert not bypass, (
            f"реализация конструируется в обход {door}:"
            f" {', '.join(bypass)} — единственная дверь на то и"
            f" единственная")
