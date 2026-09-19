"""ТЗ-47 O2: приёмка видит несвязанный код — рассогласование вызова
и сигнатуры по числу позиционных аргументов.

Второй случай одной породы (первый — дверь make_intent_client, ТЗ-27
N1): место построено, покрыто тестами и падает на первом же вызове —
_chat_screen звали с четырьмя позиционными аргументами против трёх
параметров (ТЗ-46 N2), приёмка была 13/13. test_single_door ловит
только объявленные двери; рассогласование ВНУТРИ пакета не ловил
никто.

Страж статический (ast), разрешение имён ограничено пакетом:
- голое имя — объявление ТОГО ЖЕ файла, иначе связка из импорта
  (`from rusterm.x import name as alias`);
- `self.method(...)` — методы с этим именем того же файла;
- `модуль.func(...)` — приёмник разрешается через импорты пакета
  (`import rusterm.core.chat` / `from rusterm.core import chat`);
- всё прочее (приёмник — параметр или атрибут чужого объекта:
  `repos.snapshot.insert_measure`, методы Path/set/decimal) — вне
  предмета стража: у простого ast-стража нет выведения типов, и эти
  вызовы считаются неразрешёнными, не красными.

Границы сигнатуры: min — позиционных без значений по умолчанию, max —
до *args; у метода self при вызове через атрибут не считается.
Вызов со *args не проверяется вовсе; при keywords проверяется только
перебор; явный недобор (без keywords/**kwargs) — красный. Имя
краснеет, только если вызов не укладывается НИ В ОДНО разрешённое
объявление. Динамические вызовы через реестр по имени
(TOOLS[name](...)) имеют func-Subscript и остаются зелёными по
построению.

Измерение (текущее дерево): строгий проход ДО сужения — голая
глобальная таблица имён без разрешения импортов — красит 61 вызов из
1590 разрешённых, и все 61 ложные: имена вроде exists/add/sub/resolve
носят и методы Path и set, и методы репозиториев. После сужения
(разрешение внутри пакета) на текущем дереве 0 находок при 695
вызовах, разрешённых до объявления. Красный случай — восстановленный
вызов _chat_screen с четырьмя аргументами — страж называет файл,
строку и «ожидалось 3, передано 4».
"""
from __future__ import annotations

import ast
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "rusterm"


@dataclass
class _Def:
    file: Path
    lineno: int
    name: str
    min_pos: int          # обязательных позиционных (с self, если метод)
    max_pos: int | None   # None — есть *args, потолка нет
    is_method: bool       # первый параметр self/cls


@dataclass
class _Module:
    path: Path
    defs_by_name: dict[str, list[_Def]] = field(default_factory=dict)
    imports: dict[str, str] = field(default_factory=dict)
    """привязка имени -> «модуль:имя» или «модуль:» (сам модуль)."""


def _module_path(dotted: str) -> Path | None:
    """rusterm.core.chat -> файл пакета; None — не про пакет."""
    parts = dotted.split(".")
    if not parts or parts[0] != "rusterm":
        return None
    base = PKG.joinpath(*parts[1:])
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _collect(root: Path) -> dict[Path, _Module]:
    modules: dict[Path, _Module] = {}
    for path in sorted(root.rglob("*.py")):
        mod = _Module(path=path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = node.args
                positional = list(a.posonlyargs) + list(a.args)
                required = len(positional) - len(a.defaults)
                is_method = bool(positional) and positional[0].arg in (
                    "self", "cls")
                max_pos = None if a.vararg else len(positional)
                mod.defs_by_name.setdefault(node.name, []).append(_Def(
                    file=path, lineno=node.lineno, name=node.name,
                    min_pos=required, max_pos=max_pos,
                    is_method=is_method))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = _module_path(alias.name)
                    if target is not None:
                        bound = alias.asname or alias.name.split(".")[0]
                        mod.imports[bound] = str(target)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    target = _module_path(node.module)
                elif node.level > 0:
                    rel = "." * node.level + (node.module or "")
                    target = _relative_module(path, rel)
                else:
                    target = None
                if target is None:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname or alias.name
                    mod.imports[bound] = f"{target}:{alias.name}"
        modules[path] = mod
    return modules


def _relative_module(path: Path, dots: str) -> Path | None:
    """`from . import chat` в rusterm/core/x.py -> rusterm/core."""
    up = len(dots) - len(dots.lstrip("."))
    tail = dots.lstrip(".")
    base = path.parent
    for _ in range(up - 1):
        base = base.parent
    if tail:
        base = base / tail.replace(".", "/")
    for candidate in (base.with_suffix(".py"), base / "__init__.py",
                      base):
        if candidate.is_file():
            return candidate
    return base if base.is_dir() else None


def _positional_count(call: ast.Call) -> int:
    return len(call.args) - sum(isinstance(x, ast.Starred)
                                for x in call.args)


def _fits(d: _Def, n: int, via_attribute: bool, has_keywords: bool,
          has_starargs: bool) -> bool:
    lo, hi = d.min_pos, d.max_pos
    if d.is_method and via_attribute:
        lo -= 1
        if hi is not None:
            hi -= 1
    if hi is not None and n > hi:
        return False
    if n < lo and not has_keywords and not has_starargs:
        return False
    return True


def _candidates_for(mod: _Module, node: ast.Call) -> list[_Def] | None:
    """Разрешённые объявления для этого вызова; None — вызов не
    разрешается (вне предмета стража)."""
    func = node.func
    if isinstance(func, ast.Name):
        local = mod.defs_by_name.get(func.id)
        if local:
            return local
        binding = mod.imports.get(func.id)
        if binding and ":" in binding:
            target, _, name = binding.partition(":")
            other = _collect_cache.get(Path(target))
            if other:
                return other.defs_by_name.get(name, [])
        return None  # builtin или чужое имя
    if isinstance(func, ast.Attribute):
        receiver = func.value
        if isinstance(receiver, ast.Name) and receiver.id == "self":
            return mod.defs_by_name.get(func.attr, [])
        # приёмник-имя: модуль, импортированный пакетный
        if isinstance(receiver, ast.Name):
            binding = mod.imports.get(receiver.id)
            if binding:
                target = binding.partition(":")[0]
                other = _collect_cache.get(Path(target))
                if other:
                    return other.defs_by_name.get(func.attr, [])
        return None
    return None  # Subscript (реестр по имени) и пр. — вне предмета


_collect_cache: dict[Path, _Module] = {}


def _scan(root: Path) -> list[str]:
    """Красные находки по всему дереву: файл:строка: имя: текст."""
    _collect_cache.clear()
    _collect_cache.update(_collect(root))
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        mod = _collect_cache[path]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            candidates = _candidates_for(mod, node)
            if not candidates:
                continue
            if any(isinstance(x, ast.Starred) for x in node.args):
                continue
            has_keywords = bool(node.keywords)
            via_attribute = isinstance(node.func, ast.Attribute)
            n = _positional_count(node)
            if any(_fits(d, n, via_attribute, has_keywords, False)
                   for d in candidates):
                continue
            d = candidates[0]
            lo, hi = d.min_pos, d.max_pos
            if d.is_method and via_attribute:
                lo -= 1
                if hi is not None:
                    hi -= 1
            call_name = (node.func.attr if via_attribute
                         else node.func.id)
            if hi is not None and n > hi:
                findings.append(
                    f"{path.relative_to(root)}:{node.lineno}: {call_name}: "
                    f"ожидалось {hi}, передано {n}")
            else:
                findings.append(
                    f"{path.relative_to(root)}:{node.lineno}: {call_name}: "
                    f"ожидалось минимум {lo}, передано {n}")
    return findings


def _measure_raw(root: Path) -> tuple[int, int]:
    """Строгий проход ДО сужений: голая глобальная таблица имён без
    разрешения импортов и без уступок. Возвращает (срабатываний,
    разрешённых вызовов)."""
    table: dict[str, list[_Def]] = {}
    for mod in _collect(root).values():
        for name, defs in mod.defs_by_name.items():
            table.setdefault(name, []).extend(defs)
    flagged = examined = 0
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            candidates = table.get(name)
            if not candidates or any(isinstance(x, ast.Starred)
                                     for x in node.args):
                continue
            examined += 1
            n = _positional_count(node)
            ok = any(
                n <= (d.max_pos if d.max_pos is not None else 10 ** 9)
                and n >= (d.min_pos - (1 if d.is_method else 0))
                for d in candidates)
            if not ok:
                flagged += 1
    return flagged, examined


def test_repo_is_green_on_call_arity():
    """Текущее дерево: ни одного рассогласования среди разрешённых
    вызовов. Динамические вызовы через реестры по имени в пакете есть
    и остаются зелёными — по построению не разрешаются."""
    findings = _scan(PKG)
    assert findings == [], "\n".join(findings)


def test_four_positional_args_against_three_named_by_guard(tmp_path):
    """Красный случай ТЗ-47 O2 на временной копии: восстановленный
    вызов _chat_screen(stdscr, repos, make_intent_client(), None) —
    страж называет файл, строку и «ожидалось 3, передано 4»."""
    work = tmp_path / "rusterm"
    shutil.copytree(PKG, work,
                    ignore=shutil.ignore_patterns("__pycache__"))
    app = work / "tui" / "app.py"
    source = app.read_text(encoding="utf-8")
    assert "_chat_screen(stdscr, repos, None)" in source
    app.write_text(source.replace(
        "_chat_screen(stdscr, repos, None)",
        "_chat_screen(stdscr, repos, make_intent_client(), None)"),
        encoding="utf-8")
    findings = _scan(work)
    assert len(findings) == 1, findings
    finding = findings[0]
    assert "app.py" in finding and "ожидалось 3, передано 4" in finding, \
        finding


def test_strict_pass_without_narrowing_flags_shadowed_names():
    """Измерение до сужения воспроизводимо: строгий проход по голой
    таблице имён красит перегруженные чужие имена (методы Path/set
    против методов пакета), сужения убирают их — но сама стрелка
    «до/после» обязана оставаться правдой."""
    flagged, examined = _measure_raw(PKG)
    assert flagged > 0 and examined > flagged
