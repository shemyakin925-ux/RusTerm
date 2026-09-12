"""ТЗ-22 J5: приёмка не зависит от человеческой памяти — workflow
существует, парсится, гоняет agent/acceptance.sh на 3.12 и 3.14, и в
конфигурации CI нет ни одного секрета.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML не установлен")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "acceptance.yml"


@pytest.fixture()
def parsed():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_parses_and_runs_acceptance(parsed):
    # PyYAML (YAML 1.1) читает ключ 'on' как True — это тот же ключ
    assert True in parsed or "on" in parsed
    job = parsed["jobs"]["acceptance"]
    steps = job["steps"]
    run_steps = [s.get("run", "") for s in steps]
    assert any("agent/acceptance.sh" in r for r in run_steps), run_steps


def test_matrix_covers_3_12_and_3_14(parsed):
    versions = parsed["jobs"]["acceptance"]["strategy"]["matrix"][
        "python-version"]
    assert "3.12" in versions and "3.14" in versions


def test_no_secrets_in_ci_configuration():
    """Ни одного секрета в конфигурации CI — ни по имени, ни по форме."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    for shape in ("RUSTERM_SEC_UA", "RUSTERM_LLM_API_KEY",
                  "RUSTERM_DART_KEY", "sk-or-"):
        assert shape not in text
