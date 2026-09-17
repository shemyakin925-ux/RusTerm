"""ТЗ-48 Q1: утверждение, истинное при любом входе, — красное.

Дефект, ради которого страж заведён (находка исполнителя в ТЗ-46 N3,
пункт стал ТЗ-48 Q1): `assert (... in [...]) or True` числился
покрытием три ночи — строка assert СУЩЕСТВОВАЛА, поэтому страж P1
(ловящий только удалённые assert) её пропускал, а пустой её видел
только человек. Второй такой случай — `assert True` в конце теста,
который печатали WARNING (tests/test_repos.py, починен координатором
17.09.2026 в 2c6be05 — Q1b).

Страж разбирает tests/ через ast и называет тавтологии:
- `assert <что угодно> or True` — дизъюнкт с истинной константой;
- `assert True` / `assert 1` / `assert "текст"` — истинный литерал;
- сравнение выражения с самим собой (`x == x`, `x is x`).
Законное не-сужение: `assert True in parsed or "on" in parsed`
(tests/test_j5_ci.py:24) — это проверка вхождения: оба дизъюнкта —
сравнения, не литералы. Строковые `assert True` внутри литералов
стражей (tests/test_d5_p1_rule.py:107, tests/test_j3_p6_relay_commit.py:87)
для ast — данные, не код: не путаются по построению.

Исключения объявлены списком, а не молчанием (ровно один):
- tests/test_smoke.py::test_pytest_runs — дымовой тест честно
  утверждает, что pytest работает.

Измерение до сужения (текущее дерево, 17.09.2026): наивный проход по
всем assert находит 1 тавтологию — тот самый test_smoke.py:5, он и
есть объявленное исключение. Случаев «or True» и сравнений с собой
на дереве нет: Q1b починен раньше стража. Красный случай доказан
прогоном на временном файле.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

# ТЗ-48 Q1: единственные законные тавтологии, объявленные списком.
EXEMPT: set[str] = {
    "test_smoke.py::test_pytest_runs",
}


def _truthy_constant(node: ast.expr) -> bool:
    return (isinstance(node, ast.Constant)
            and bool(node.value)
            and not isinstance(node.value, (bytes, tuple, list, dict, set)))


def _tautologies(tree: ast.Module) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            if any(_truthy_constant(v) for v in test.values):
                bad.append((node.lineno, "or True"))
                continue
        if _truthy_constant(test):
            bad.append((node.lineno, "истинный литерал"))
            continue
        if (isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], (ast.Eq, ast.Is))
                and ast.dump(test.left) == ast.dump(test.comparators[0])):
            bad.append((node.lineno, "сравнение с самим собой"))
    return bad


def _scan(root: Path) -> list[str]:
    import warnings

    findings: list[str] = []
    for path in sorted(root.rglob("test_*.py")):
        # чужой источник может нести невалидные escape-последовательности
        # (test_intent.py:97) — разбор стража не их судит
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, kind in _tautologies(tree):
            findings.append(f"{path.relative_to(root)}:{lineno}: {kind}")
    return findings


def test_tests_tree_has_no_undeclared_tautologies():
    raw = _scan(TESTS)
    undeclared = []
    for finding in raw:
        file_line, kind = finding.split(": ", 1)
        fname, lineno = file_line.rsplit(":", 1)
        tree = ast.parse((TESTS / fname).read_text(encoding="utf-8"))
        owner = _owning_test(tree, int(lineno))
        if f"{fname}::{owner}" not in EXEMPT:
            undeclared.append(finding)
    assert not undeclared, (
        "пустые утверждения (красное по ТЗ-48 Q1):\n  "
        + "\n  ".join(undeclared))


def _owning_test(tree: ast.Module, lineno: int) -> str | None:
    owner = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.lineno <= lineno \
                and (node.end_lineno or 0) >= lineno:
            owner = node.name
    return owner


def test_assert_in_membership_is_not_a_tautology():
    """ТЗ-48 Q1: `assert True in parsed or "on" in parsed`
    (tests/test_j5_ci.py:24) — проверка вхождения, оба дизъюнкта
    сравнения. Страж обязан оставить её зелёной."""
    target = TESTS / "test_j5_ci.py"
    tree = ast.parse(target.read_text(encoding="utf-8"))
    hits = [line for line, _ in _tautologies(tree) if line == 24]
    assert hits == [], hits


def test_assert_or_true_named_by_file_and_line(tmp_path):
    """Красный случай ТЗ-48 Q1: временный файл с `assert x or True`
    назван по файлу и строке."""
    target = tmp_path / "test_probe.py"
    target.write_text(
        "def test_probe():\n"
        "    x = 1\n"
        "    assert x or True\n",
        encoding="utf-8")
    findings = _scan(tmp_path)
    assert findings == ["test_probe.py:3: or True"], findings
