from langgraph.graph import StateGraph, START, END
from operator import add
from typing import Any, TypedDict, Annotated
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from week01_log_parser.llm_parser import parse_with_llm
from test_runner import PytestError, run_pytest


class RepairState(TypedDict):
    attempts: int
    max_attempts: int
    passed: bool
    history: Annotated[list[str], add]
    project_dir: Path
    pytest_errors: list[PytestError]
    parsed_errors: list[dict[str, Any]]


def run_test_scripts(state: RepairState) -> dict:
    passed, output, errors = run_pytest(state["project_dir"])
    return {
        "passed": passed,
        "pytest_errors": errors,
        "history": [output],
    }


def analyze_error(state: RepairState) -> dict:
    if state["passed"]:
        return {"history": ["no pytest errors, return directly\n"]}
    errors = state["pytest_errors"]
    parsed_errors: list[dict[str, Any]] = []
    for error in errors:
        error_log = error.to_log_string()
        parsed_error = parse_with_llm(error_log)
        if parsed_error:
            parsed_errors.append(parsed_error.model_dump())
        else:
            print(f"failed to parse error {error}")
    return {"parsed_errors": parsed_errors}


def build_graph():
    builder = StateGraph(RepairState)
    builder.add_node("run_test_scripts", run_test_scripts)
    builder.add_node("analyze_error", analyze_error)

    builder.add_edge(START, "run_test_scripts")
    builder.add_edge("run_test_scripts", "analyze_error")
    builder.add_edge("analyze_error", END)

    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke(
        {
            "attempts": 0,
            "max_attempts": 3,
            "passed": False,
            "history": [],
            "project_dir": Path(__file__).parent / "buggy_project",
            "pytest_errors": [],
            "parsed_errors": [],
        }
    )
    print(result)
