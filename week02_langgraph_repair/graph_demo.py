from langgraph.graph import StateGraph, START, END
from operator import add
from typing import TypedDict, Annotated
import random


class MyState(TypedDict):
    attempts: int
    max_attempts: int
    passed: bool
    history: Annotated[list[str], add]


def greet_node(state: MyState) -> dict:
    print(f"greetings! I'm going to fix your code")
    return {"history": ["greeting finished\n"]}


def fix_node(state: MyState) -> dict:
    current_attempt = state["attempts"] + 1
    print(f"begin to fix, attempts {current_attempt}")
    return {"history": [f"try to fix, attempts {current_attempt} \n"]}


def test_node(state: MyState) -> dict:
    current_attempt = state["attempts"] + 1
    passed = random.random() < 1.0 / 3
    print(f"begin to test, attempts {current_attempt}")
    return {
        "history": [f"try to test, attempts {current_attempt} \n"],
        "passed": passed,
        "attempts": state["attempts"] + 1,
    }


def route_after_test(state: MyState) -> str:
    if state["passed"] or state["attempts"] >= state["max_attempts"]:
        return "done"
    else:
        return "retry"


builder = StateGraph(MyState)
builder.add_node("greet", greet_node)
builder.add_node("fix", fix_node)
builder.add_node("test", test_node)

builder.add_edge(START, "greet")
builder.add_edge("greet", "fix")
builder.add_edge("fix", "test")
builder.add_conditional_edges("test", route_after_test, {"done": END, "retry": "fix"})

graph = builder.compile()
result = graph.invoke(
    {"attempts": 0, "max_attempts": 3, "passed": False, "history": []}
)
print(f"result={result}\n")
