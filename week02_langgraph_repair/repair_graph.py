from langgraph.graph import StateGraph, START, END
from operator import add
from typing import Any, TypedDict, Annotated, Optional
from pathlib import Path
import sys
import json
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from week01_log_parser.llm_parser import parse_with_llm
from week02_langgraph_repair.patch_generator import create_patch
from week02_langgraph_repair.test_runner import PytestError, run_pytest


class RepairState(TypedDict):
    attempts: int
    max_attempts: int
    passed: bool
    history: Annotated[list[str], add]
    project_dir: Path
    pytest_errors: list[PytestError]
    parsed_errors: list[dict[str, Any]]
    proposed_patch: Optional[str]
    patch_valid: bool
    patch_applied: bool
    patch_apply_output: Optional[str]


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


def generate_patch(state: RepairState) -> dict:
    proposed_patch = create_patch(state["parsed_errors"], state["project_dir"])
    return {"proposed_patch": proposed_patch, "patch_valid": proposed_patch is not None}


def apply_patch(state: RepairState) -> dict:
    patch = state["proposed_patch"]

    if not patch:
        return {
            "patch_applied": False,
            "patch_apply_output": "No patch to apply.",
            "history": ["apply_patch: no patch to apply\n"],
        }

    if not state["patch_valid"]:
        return {
            "patch_applied": False,
            "patch_apply_output": "Patch is not valid; skipped apply.",
            "history": ["apply_patch: skipped invalid patch\n"],
        }

    result = subprocess.run(
        ["git", "apply"],
        input=patch,
        text=True,
        capture_output=True,
        cwd=state["project_dir"],
    )

    output = result.stdout + "\n" + result.stderr
    applied = result.returncode == 0

    print("\n\napply_apptch output: " + output + "applied: " + str(applied))

    return {
        "patch_applied": applied,
        "patch_apply_output": output,
        "attempts": state["attempts"] + 1,
        "history": [f"apply_patch: patch_applied={applied}\n"],
    }


def route_after_generate_patch(state: RepairState) -> str:
    if state["patch_valid"] and state["proposed_patch"]:
        return "apply_patch"
    else:
        return "end"


def route_after_run_test_scripts(state: RepairState) -> str:
    if state["passed"] or state["attempts"] >= state["max_attempts"]:
        return "end"
    else:
        return "analyze_error"


def build_graph():
    builder = StateGraph(RepairState)
    builder.add_node("run_test_scripts", run_test_scripts)
    builder.add_node("analyze_error", analyze_error)
    builder.add_node("generate_patch", generate_patch)
    builder.add_node("apply_patch", apply_patch)

    builder.add_edge(START, "run_test_scripts")
    builder.add_conditional_edges(
        "run_test_scripts",
        route_after_run_test_scripts,
        {"end": END, "analyze_error": "analyze_error"},
    )
    builder.add_edge("analyze_error", "generate_patch")
    builder.add_conditional_edges(
        "generate_patch",
        route_after_generate_patch,
        {"end": END, "apply_patch": "apply_patch"},
    )
    builder.add_edge("apply_patch", "run_test_scripts")

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
            "proposed_patch": None,
            "patch_valid": False,
            "patch_applied": False,
            "patch_apply_output": None,
        }
    )
    print(json.dumps(result, default=str))
