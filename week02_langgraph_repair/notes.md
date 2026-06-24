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
Python 的 `import` 本质是在 `sys.path` 这个列表里按顺序找模块。

可以用下面的代码观察当前 Python 到底会去哪些目录找模块：
```python
import sys
print(sys.path)
```

直接运行脚本时：
```bash
python week02_langgraph_repair/repair_graph.py
```
Python 通常会把脚本所在目录放到 `sys.path[0]`：
```text
/home/yinkai/agent-sandbox/week02_langgraph_repair
```

所以这种同目录裸导入可能成功：
```python
from patch_generator import create_patch
from test_runner import run_pytest
```

因为 Python 可以在 `week02_langgraph_repair/` 里找到：
```text
patch_generator.py
test_runner.py
```

但是这种写法依赖启动位置，换一种运行方式就容易坏。

如果在项目根目录运行：
```bash
cd /home/yinkai/agent-sandbox
python week02_langgraph_repair/repair_graph.py
```
当前工作目录是项目根目录，脚本目录是 `week02_langgraph_repair/`。

为了让跨目录导入稳定，建议 import 都从项目根目录开始写：
```python
from week01_log_parser.llm_parser import parse_with_llm
from week01_log_parser.openai_helper import get_client
from week02_langgraph_repair.patch_generator import create_patch
from week02_langgraph_repair.test_runner import PytestError, run_pytest
```

这时路径和文件结构一一对应：
```text
week01_log_parser/openai_helper.py
=> from week01_log_parser.openai_helper import get_client

week02_langgraph_repair/patch_generator.py
=> from week02_langgraph_repair.patch_generator import create_patch
```

如果在 `week02_langgraph_repair` 目录里运行：
```bash
cd /home/yinkai/agent-sandbox/week02_langgraph_repair
python repair_graph.py
```
默认情况下，Python 主要能看到当前目录：
```text
/home/yinkai/agent-sandbox/week02_langgraph_repair
```

它能找到同目录文件，但不一定能找到上一层的：
```text
/home/yinkai/agent-sandbox/week01_log_parser
```

所以项目里用了一个实用兜底：手动把项目根目录加入 `sys.path`：
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

加上这段后，即使从 `week02_langgraph_repair/` 里运行，Python 也能找到项目根目录下的包。

相对导入也可以写：
```python
from .openai_helper import get_client
```

但它更适合用 module 方式运行：
```bash
python -m week01_log_parser.llm_parser
```

如果直接运行文件：
```bash
python week01_log_parser/llm_parser.py
```
相对导入可能报错：
```text
ImportError: attempted relative import with no known parent package
```

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
- 如果固定从项目根目录运行，import 从项目根目录开始写。
- 同目录裸导入如 `from test_runner import ...` 适合小脚本，但跨目录时容易混乱。
- demo 阶段：`PROJECT_ROOT + sys.path.insert` 比较方便。
- 正规项目：优先用 `python -m package.module` 和统一的包导入。

### git apply --check:
`git apply --check` 用来检查一个 patch 能不能干净地应用到当前工作区。

常见用法是传 patch 文件：
```bash
git apply --check fix.patch
```

也可以不传文件，让 `git apply` 从 stdin 读取 patch 内容：
```bash
printf '%s\n' "$PATCH" | git apply --check
```

Python 里可以直接把字符串传给 stdin：
```python
import subprocess


def check_patch(patch_text: str, cwd: str) -> tuple[bool, str]:
    if not patch_text.endswith("\n"):
        patch_text += "\n"

    result = subprocess.run(
        ["git", "apply", "--check"],
        input=patch_text,
        text=True,
        capture_output=True,
        cwd=cwd,
    )
    return result.returncode == 0, result.stderr
```

这里不传 patch 文件名时，`git apply --check` 会从标准输入读取 `patch_text`。

`cwd` 很重要。patch 里的路径是相对于 `cwd` 解析的。
例如 patch 里是：
```diff
diff --git a/app/cart.py b/app/cart.py
--- a/app/cart.py
+++ b/app/cart.py
```

那 `cwd` 应该是包含 `app/` 的目录：
```text
week02_langgraph_repair/buggy_project
```

`git apply` 接收的是标准 git/unified diff，不接收 `apply_patch` 工具格式。

正确格式类似：
```diff
diff --git a/app/cart.py b/app/cart.py
--- a/app/cart.py
+++ b/app/cart.py
@@ -1,5 +1,5 @@
 def calculate_total(items):
     total = 0
     for item in items:
-        total += item["price"]
+        total += float(item["price"])
     return total
```

错误格式类似：
```diff
*** Begin Patch
*** Update File: app/cart.py
@@
-old
+new
*** End Patch
```

这种是某些工具自己的 patch 格式，`git apply` 不认识，通常会报：
```text
error: No valid patches in input
```

unified diff 的 hunk header 行数也必须正确：
```diff
@@ -1,5 +1,5 @@
```

含义是：
- 旧文件从第 1 行开始，这个 hunk 覆盖 5 行旧内容。
- 新文件从第 1 行开始，这个 hunk 覆盖 5 行新内容。

如果 header 写成 `@@ -1,4 +1,4 @@`，但下面实际有 5 行旧内容和 5 行新内容，`git apply` 可能会报：
```text
error: corrupt patch at line ...
```

diff 是按行解析的文本格式，每一行最好都以 `\n` 结束，包括最后一行。
LLM 返回的 patch 字符串有时最后没有换行，例如最后是：
```python
'+    return user.name.upper()'
```

更稳的是补成：
```python
'+    return user.name.upper()\n'
```

所以在传给 `git apply --check` 前，建议统一做一次规范化：
```python
if not patch_text.endswith("\n"):
    patch_text += "\n"
```

`git apply --check` 只检查 patch 是否能应用，不检查业务逻辑是否正确。
例如它能通过下面这种 patch：
```diff
+    if user is None:
+        return None
```

但如果测试期望的是：
```python
assert get_user_name(None) == "UNKNOWN"
```

那 patch 虽然能 apply，测试还是会失败。

简单记法：
- `git apply --check`：检查 patch 格式、路径和上下文能不能应用。
- `git apply --check` 不会跑测试，也不知道修复是否正确。
- patch 字符串可以通过 stdin 传入，不一定要写临时文件。
- LLM 生成的 patch 要补最后的 `\n`，避免最后一行被解析成不完整行。
- 真正验证修复：在临时副本里 `git apply` 后跑 `pytest`。
