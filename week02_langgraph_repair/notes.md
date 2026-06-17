### langraph:
- State：整张图共享的状态。
- Node：处理步骤，本质是一个函数。
- Edge：节点之间的执行顺序。
- START / END：图的开始和结束。
- StateGraph：用 state schema 构建图。
- add_conditional_edge:
```python
def route_after_test(state: MyState) -> str:
    if state["passed"] or state["attempts"] >= state["max_attempts"]:
        return "done"
    else:
        return "retry"
```
然后配合 path_map：
```python
builder.add_conditional_edges(
    "test",
    route_after_test,
    {"done": END, "retry": "fix"},
)
```
path_map 不是必须的，但可以让返回值更语义化  
如果 route 函数直接返回节点名，可以不写 path_map：  

### Annotated:
`Annotated` 来自 Python 的类型系统，用来给类型附加额外 metadata。
基本形式：
```python
from typing import Annotated
field: Annotated[原始类型, 额外信息]
```

Annotated 本身不会改变 Python 行为，真正起作用的是框架读取了这些 metadata。  
例如 Pydantic 会读取  
age: Annotated[int, Field(gt=0)]
然后把 Field(gt=0) 当作校验规则。

LangGraph 会读取：  
messages: Annotated[list[str], add]  
然后把 add 当作 reducer，用来合并 state 更新。  

### pytest:
- 是 Python 测试框架，核心就是：发现测试 + 执行 + 报告结果。
- 常见入口：`pytest` 或 `python -m pytest`（后者更明确用当前解释器）。
- 约定：文件名 `test_*.py`，函数名 `test_*`。
- 断言：直接用 `assert`，失败时会给出更详细的差异信息（assert rewriting）。
- fixture：做测试前准备和测试后清理；通过参数注入到测试函数。
- parametrize：一套测试逻辑跑多组输入。

最小示例：
```python
import pytest

@pytest.mark.parametrize("a,b,expected", [(1, 2, 3), (2, 3, 5)])
def test_add(a, b, expected):
    assert a + b == expected
```

常用命令速记：
- `pytest -q`：简洁输出。
- `pytest -k "xxx"`：按名字筛选。
- `pytest -x`：首个失败即停止。
- `pytest -vv`：更详细日志。
