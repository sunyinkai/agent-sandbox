from langgraph.graph import StateGraph, START, END
from operator import add
from typing import TypedDict, Annotated


class MyState(TypedDict):
    id: int
    file: str
    step: int
    messages: Annotated[list[str], add]


def greet_node(state: MyState) -> dict:
    step = state.get("step", 0)
    print(f"greetings! your file is {state['file']}")
    return {"step": step + 1, "messages": ["greeting finished\n"]}


def compile_node(state: MyState) -> dict:
    print(f"begin to compile {state['file']}")
    return {"step": state["step"] + 1, "messages": ["compile finished\n"]}


def fix_node(state: MyState) -> dict:
    print(f"begin to fix {state['file']}")
    return {"step": state["step"] + 1, "messages": ["fix finished\n"]}


builder = StateGraph(MyState)
builder.add_node("greet", greet_node)
builder.add_node("compile", compile_node)
builder.add_node("fix", fix_node)

builder.add_edge(START, "greet")
builder.add_edge("greet", "compile")
builder.add_edge("compile", "fix")
builder.add_edge("fix", END)

graph = builder.compile()
result = graph.invoke({"id": 0, "file": "hello.py", "step": 0, "messages": []})
print(f"result={result}")
