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

### dataclass vs TypedDict:
`TypedDict` 和 `dataclass` 都可以描述一组字段，但它们适合的场景不一样。

`TypedDict` 本质上还是普通 dict，只是给类型检查器看的结构说明：
```python
from typing import TypedDict

class PytestErrorDict(TypedDict):
    test_name: str
    error_type: str
    message: str
```

使用时还是 dict 访问：
```python
error["test_name"]
error["message"]
```

适合场景：
- 数据本来就是 JSON / dict。
- 只是想标注字段结构。
- 不需要方法。
- 需要和外部 API 的 dict 数据直接对接。

`dataclass` 会创建真正的 Python 对象：
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PytestError:
    test_name: str
    error_type: str
    message: str
    file_path: str | None
    line_number: int | None
```

使用时是属性访问：
```python
error.test_name
error.message
```

适合场景：
- 这个数据已经是领域对象，不只是临时 dict。
- 想给对象加方法。
- 想让字段更明确，访问更舒服。
- 想用 `frozen=True` 表达“创建后不应该被修改”。

例如今天的 `PytestError` 一开始只是结构化 pytest JSON，可以用 `TypedDict`。  
但后来它需要负责把自己转成 LLM 看的文本：
```python
def to_log_string(self) -> str:
    return "\n".join(
        [
            f"Test: {self.test_name}",
            f"Error type: {self.error_type}",
            f"Message: {self.message}",
            f"File path: {self.file_path}",
            f"Line number: {self.line_number}",
        ]
    )
```

这时 `dataclass` 更自然，因为“错误如何格式化成日志文本”属于 `PytestError` 自己的行为。

简单记法：
- 只是描述 dict 形状：用 `TypedDict`。
- 数据需要行为或方法：用 `dataclass`。
- 数据来自 JSON，准备继续当 JSON/dict 传来传去：用 `TypedDict`。
- 数据进入业务逻辑，成为代码里的明确对象：用 `dataclass`。
- 需要运行时校验、序列化、复杂约束：考虑 Pydantic `BaseModel`。

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

### pytest 格式化:
pytest 默认输出是给人看的文本报告，适合直接阅读，但不适合程序稳定解析。

常用输出格式控制：
```bash
python -m pytest -q --tb=short
```

含义：
- `python -m pytest`：用当前 Python 环境里的 pytest，避免 venv 不一致。
- `-q`：减少无关输出。
- `--tb=short`：使用短 traceback，保留关键失败位置。

如果需要给 repair graph 或 LLM 使用，推荐额外生成结构化报告：
```bash
python -m pytest -q --tb=short --json-report --json-report-file=pytest-report.json
```

需要安装：
```bash
pip install pytest-json-report
```

JSON report 里常用字段：
- `tests`：每个测试用例的结果。
- `nodeid`：测试名，例如 `tests/test_cart.py::test_xxx`。
- `outcome`：测试结果，例如 `passed` / `failed`。
- `call.crash.message`：异常消息。
- `call.crash.path`：异常发生文件。
- `call.crash.lineno`：异常发生行号。

可以把 JSON 里的失败信息整理成一个对象：
```python
@dataclass(frozen=True)
class PytestError:
    test_name: str
    error_type: str
    message: str
    file_path: str | None
    line_number: int | None
```

如果后面要传给 LLM，可以再提供一个文本格式化方法：
```python
def to_log_string(self) -> str:
    return "\n".join(
        [
            f"Test: {self.test_name}",
            f"Error type: {self.error_type}",
            f"Message: {self.message}",
            f"File path: {self.file_path}",
            f"Line number: {self.line_number}",
        ]
    )
```

简单记法：
- 人看：保留 pytest 原始 `stdout`。
- 程序看：解析 JSON report。
- LLM 看：把结构化 error 转成简洁文本。

### Python import path:
Python 的 import 跟“从哪里启动脚本”有关。

如果直接运行某个文件：
```bash
python week02_langgraph_repair/repair_graph.py
```
Python 会优先把这个文件所在目录加入 `sys.path`。
所以同目录里的 `test_runner.py` 容易 import 成功，但项目根目录下的 `week01_log_parser` 可能找不到。

临时解决方式是手动把项目根目录加入 `sys.path`：
```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

这里：
- `__file__`：当前 Python 文件路径。
- `Path(__file__).resolve()`：当前文件的绝对路径。
- `parents[0]`：当前文件所在目录。
- `parents[1]`：上一级目录，也就是当前项目根目录。

更正规的方式是从项目根目录用 module 方式运行：
```bash
python -m week02_langgraph_repair.repair_graph
```

然后 import 尽量统一写成从项目根目录开始的包路径：
```python
from week01_log_parser.schemas import ParsedError
from week01_log_parser.llm_parser import parse_with_llm
from week02_langgraph_repair.test_runner import PytestError, run_pytest
```

简单记法：
- demo 阶段：`PROJECT_ROOT + sys.path.insert` 比较方便。
- 正规项目：优先用 `python -m package.module` 和统一的包导入。
