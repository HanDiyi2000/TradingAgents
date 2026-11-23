"""D7: approval precedes implementation; safety and log rules fail closed."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/course_gates.py"
spec = importlib.util.spec_from_file_location("course_gates", SCRIPT)
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)
TEST = "test/offline/test_example.py"
SOURCE = "src/tradingagents/agents/context.py"
ADR = "docs/architecture/adr/004-context.md"
LOG = "docs/ai-use-log.yaml"


def test_prior_approval_and_adr_admit_candidate():
    history = [("tests", [TEST]), ("build", [SOURCE, LOG, ADR])]
    assert gates.inspect_change(history, {"tests", "build"}, "build") == []


@pytest.mark.parametrize("history,approved,reason", [
    ([("both", [TEST, SOURCE, ADR, LOG])], {"both"}, "before implementation"),
    ([("t", [TEST]), ("impl", [SOURCE, ADR, LOG]), ("edit", [TEST])],
     {"t", "edit"}, "approved tests changed"),
    ([("t", [TEST]), ("b", [SOURCE, ADR])], {"t", "b"}, "AI-use log"),
    ([("t", [TEST]), ("b", [SOURCE, LOG])], {"t", "b"}, "ADR"),
    ([("t", [TEST]), ("b", [SOURCE, LOG, ADR])], {"t"}, "human review"),
])
def test_noncompliant_change_is_blocked(history, approved, reason):
    assert any(reason in error for error in gates.inspect_change(history, approved, history[-1][0]))
