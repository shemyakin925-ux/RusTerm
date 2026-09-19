"""ТЗ-48 Q2: тест не пишет по пути, общему для рабочих копий.

Круг 56: маркер демонстрации I5 лежал в общем /tmp с фиксированным
именем — приёмка координатора в соседнем подключённом дереве
перезаписывала его своим session, и sentinel в дереве исполнителя
краснел от чужого следа. Случай починен (5e050a4, маркер в git-каталоге
через git rev-parse --git-path); этот страж закрывает КЛАСС: запись в
путь, построенный от tempfile.gettempdir(), литерала /tmp или TMPDIR,
когда путь не получен из tmp_path/tmp_path_factory pytest и не идёт
через git rev-parse --git-path, — красная с файлом и строкой.

Сужение (объявлено, не молчание): tempfile.mkdtemp()/mkstemp()/
TemporaryDirectory() БЕЗ dir= не красные — общий корень, но имя
возвращается машинно-уникальным, классу столкновения фиксированных
имён они не принадлежат (таких мест в tests/ больше трёх десятков,
переводить их на tmp_path незачем). Чистые вычисления пути без записи
(manifest_path_for(Path("/tmp/m"), ts), AppPaths.from_root("/tmp/..."))
страж не смотрит: он ловит только запись.

Измерение до сужения (текущее дерево, 17.09.2026): один красный —
tests/test_i5_guard_source.py:258, протухший замок с фиксированным
именем в /tmp, наследство круга 56, machinery его уже не читает;
переведён на tmp_path тем же коммитом, что и страж. После сужения и
перевода: 0 на дереве. Красный случай доказан прогоном на временном
файле.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

_WRITE_METHODS = {"write_text", "write_bytes", "mkdir"}
_WRITE_FUNCS = {"open", "makedirs", "copy", "copytree", "move"}


def _is_gettempdir(node: ast.expr) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "gettempdir"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "tempfile")


def _is_git_path_call(node: ast.expr) -> bool:
    if not (isinstance(node, ast.Call) and node.args):
        return False
    literals = [a.value for a in node.args
                if isinstance(a, ast.Constant)]
    return "rev-parse" in literals and "--git-path" in literals


def _has_tmp_path(node: ast.expr) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in ("tmp_path",
                                                    "tmp_path_factory"):
            return True
    return False


def _classify(expr: ast.expr) -> str:
    """suspect | safe | unknown — для выражения-пути."""
    for sub in ast.walk(expr):
        if _is_gettempdir(sub) or _is_git_path_call(sub):
            return "suspect" if _is_gettempdir(sub) else "safe"
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                and sub.value.startswith("/tmp"):
            return "suspect"
        if isinstance(sub, ast.Subscript) and "TMPDIR" in ast.dump(sub):
            return "suspect"
        if _has_tmp_path(sub):
            return "safe"
    return "unknown"


def _shared_writes(tree: ast.Module) -> list[tuple[int, str]]:
    # одноступенчатые псевдонимы: p = <выражение>
    alias: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name, verdict = node.targets[0].id, _classify(node.value)
            if verdict != "unknown":
                alias[name] = verdict
    bad: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        path_exprs: list[ast.expr] = []
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in _WRITE_METHODS:
                path_exprs.append(node.func.value)
            if isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "shutil" \
                    and node.func.attr in _WRITE_FUNCS:
                path_exprs.extend(node.args[:2])
        elif isinstance(node.func, ast.Name):
            if node.func.id == "open" and node.args:
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1],
                                                     ast.Constant):
                    mode = str(node.args[1].value)
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value,
                                                       ast.Constant):
                        mode = str(kw.value.value)
                if mode and not any(c in mode for c in "wax+"):
                    continue
                path_exprs.append(node.args[0])
        for expr in path_exprs:
            verdict = _classify(expr)
            if verdict == "unknown" and isinstance(expr, ast.Name):
                verdict = alias.get(expr.id, "unknown")
            if verdict == "suspect":
                bad.append((node.lineno,
                            f"запись в общий путь: {ast.dump(expr)[:60]}"))
    return bad


def _scan(root: Path) -> list[str]:
    import warnings

    findings: list[str] = []
    for path in sorted(root.rglob("test_*.py")):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, what in _shared_writes(tree):
            findings.append(f"{path.relative_to(root)}:{lineno}: {what}")
    return findings


def test_tests_tree_writes_no_shared_tmp_paths():
    findings = _scan(TESTS)
    assert findings == [], "\n".join(findings)


def test_write_to_gettempdir_named_by_file_and_line(tmp_path):
    """Красный случай ТЗ-48 Q2: запись по пути от gettempdir()
    названа по файлу и строке."""
    target = tmp_path / "test_probe.py"
    target.write_text(
        "import tempfile\n"
        "from pathlib import Path\n"
        "def test_probe():\n"
        "    p = Path(tempfile.gettempdir()) / 'fixed-name.lock'\n"
        "    p.write_text('x')\n",
        encoding="utf-8")
    findings = _scan(tmp_path)
    assert len(findings) == 1, findings
    assert findings[0].startswith("test_probe.py:5: запись в общий путь"), \
        findings


def test_tmp_path_and_git_path_writes_stay_green(tmp_path):
    """Сужение: tmp_path и git rev-parse --git-path — законные
    получатели пути, страж их не красит."""
    target = tmp_path / "test_ok.py"
    target.write_text(
        "import subprocess\n"
        "def test_ok(tmp_path):\n"
        "    (tmp_path / 'a').write_text('x')\n"
        "    out = subprocess.run(['git', 'rev-parse', '--git-path', 'm'])\n"
        "    assert out\n",
        encoding="utf-8")
    assert _scan(tmp_path) == []
