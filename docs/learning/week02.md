# Week 02 学习笔记

> 本文记录重构前的学习过程，因此正文中的 `week01_log_parser/` 和
> `week02_langgraph_repair/` 路径保留为历史上下文。当前对应关系是：
> `agent_sandbox/parsing/`、`agent_sandbox/repair/` 和
> `fixtures/buggy_project/`；当前命令见仓库根目录 README。

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

### git apply、Git 工作树和 patch 路径:

`git apply` 读取 standard Git/unified diff，根据路径和上下文找到目标代码，删除 `-` 行并插入 `+` 行。它只修改工作树，不会自动 commit 或加入暂存区。patch 可以来自文件，也可以通过 `subprocess.run(input=patch_text)` 从 stdin 传入。

#### Git 工作树是什么
工作树（working tree）是实际编辑代码的目录：
```text
agent-sandbox/                                  <- 工作树根目录
├── .git/
└── week02_langgraph_repair/buggy_project/      <- project_dir
```

Git 从当前目录向上识别所属仓库。不要自己搜索 `.git`，直接让 Git 返回工作树根目录：
```bash
git rev-parse --show-toplevel
```

本项目返回：
```text
/home/yinkaisun/agent-sandbox
```

#### cwd 不一定是 Git 工作树根目录
即使在 `buggy_project` 启动 Git：
```python
subprocess.run(["git", "apply"], cwd=project_dir)
```

Git 仍会发现外层仓库：
```text
进程 cwd        = week02_langgraph_repair/buggy_project
工作树根目录     = agent-sandbox
```

`cwd` 只是进程启动位置，不会把 `buggy_project` 变成独立仓库。在仓库子目录运行 `git apply` 时，不在当前子目录范围内的 patch 路径可能被跳过。

这次 LLM 生成的路径是：
```diff
diff --git a/app/cart.py b/app/cart.py
--- a/app/cart.py
+++ b/app/cart.py
```

去掉 `a/`、`b/` 后是 `app/cart.py`。LLM 认为它相对于 `buggy_project`，但 Git 使用外层工作树的路径体系，因此原命令输出：
```text
Skipped patch 'app/cart.py'.
```

Git 仍可能返回退出码 0，所以只检查 `returncode` 会产生 `applied: True` 的假象。

#### --directory 的原理
先计算项目相对于工作树的位置：
```python
relative_project_dir = project_dir.relative_to(repo_root)
```

得到：
```text
week02_langgraph_repair/buggy_project
```

再让 `--directory` 给所有 patch 路径添加该前缀：
```bash
--directory=week02_langgraph_repair/buggy_project
```

```text
app/cart.py
-> week02_langgraph_repair/buggy_project/app/cart.py
```

真正修复路径问题的是 `--directory`。当前代码还把 `cwd` 设为 `repo_root`，让命令基准与仓库相对路径一致；已有正确 `--directory` 时，保留 `cwd=project_dir` 也能工作。如果项目本身就是工作树根目录，则不需要 `--directory`；如果不属于 Git 仓库，则直接在 `project_dir` 执行。

#### git apply --check
`--check` 检查 patch 格式、目标路径和上下文，但不写文件，也不判断业务逻辑。检查和实际应用应复用同一个 helper，确保二者使用相同的 `--directory` 和 `--recount`；应用后仍要运行 pytest。

### unified diff、hunk 和 --recount:

一个 unified diff hunk：
```diff
diff --git a/app/cart.py b/app/cart.py
--- a/app/cart.py
+++ b/app/cart.py
@@ -1,5 +1,5 @@
 def calculate_total(items):
     total = 0
     for item in items:
-        total += item["price"]
+        total += int(item["price"])
     return total
```

hunk 是修改行和周围上下文组成的代码块。header 格式：
```text
@@ -旧文件起始行,旧文件覆盖行数 +新文件起始行,新文件覆盖行数 @@
```

| 前缀 | 含义 | 计入旧文件 | 计入新文件 |
|---|---|---:|---:|
| 空格 | 未修改的上下文行 | 是 | 是 |
| `-` | 从旧文件删除的行 | 是 | 否 |
| `+` | 向新文件添加的行 | 否 | 是 |

例子中真正修改的是 1 行；另外 4 行是定位用的上下文。因此旧侧为“4 个上下文 + 1 个删除 = 5”，新侧为“4 个上下文 + 1 个新增 = 5”，header 是 `@@ -1,5 +1,5 @@`。这里的 5 表示 hunk 覆盖范围，不是修改了 5 行。

#### --recount 的原理
LLM 可能把上例误写成 `@@ -1,4 +1,4 @@`。`--recount` 不相信 header 中的行数，而是根据空格、`-`、`+` 重新计算为 5 和 5。它只修复 hunk 行数元数据，不能修复业务逻辑、文件路径或错误上下文。

#### normalize_patch_text 和 --recount 的区别
| 机制 | 解决的问题 |
|---|---|
| `normalize_patch_text()` | 整个 patch 的最后一行缺少 `\n` |
| `git apply --recount` | hunk header 中的行数与 hunk 正文不一致 |

最终流程：
```text
LLM 生成 patch
    -> normalize_patch_text 补末尾换行
    -> git apply --recount --check 检查格式、路径和上下文
    -> git apply --recount 真正写入目标文件
    -> pytest 检查业务行为
```

### OpenAI Responses API messages:
`client.responses.parse(...)` 的 `input` 可以传多条 message：
```python
response = client.responses.parse(
    model=os.getenv("AZURE_DEPLOYMENT_NAME"),
    input=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": error_context},
        {"role": "assistant", "content": previous_patch_text},
        {"role": "user", "content": retry_feedback},
    ],
)
```

这不是一条一条分别发送到远端，而是一次 API 请求把整个 `input` 数组一起发过去。  
远端模型会按数组顺序读取这些 message，把它们当作一段带 role 标记的对话上下文。

可以近似理解成：
```text
system: 你必须只输出 git patch
user: 这是当前 pytest 错误和代码上下文
assistant: 这是你上一轮生成的 patch
user: 这个 patch 没通过 git apply --check，错误是 xxx，请重新生成
```

顺序有影响。越靠后的 user message 通常越像“当前这一步真正要做什么”。  
所以 retry 时推荐顺序是：
1. `system`：固定规则，例如只输出 git diff，不要解释。
2. `user`：当前任务上下文，例如 pytest 错误和相关代码。
3. `assistant`：上一轮模型生成的 patch。
4. `user`：上一轮 patch 的失败原因，以及要求重新生成。

为什么上一轮 patch 放在 `assistant`：  
因为它语义上是模型上一轮的输出，不是用户说的话。把它作为 `assistant` history，模型更容易理解“这是我之前生成的答案”。

失败原因和修正要求放在新的 `user` message：  
因为这是当前用户/程序给模型的新反馈，例如：
```python
retry_feedback = json.dumps(
    {
        "previous_patch_failed": True,
        "git_apply_check_error": previous_error,
        "instruction": "The previous patch failed git apply --check. Generate a corrected git unified diff. Output only the patch.",
    },
    ensure_ascii=False,
    indent=2,
)
```

简单记法：
- 多条 message 是一次请求整体发送，不是多次请求。
- 模型按顺序读 message，role 会影响语义。
- `system` 放全局规则。
- `user` 放当前任务和反馈。
- `assistant` 放模型历史输出。
- patch retry 时，把 `previous_patch_text` 放进 `assistant`，把 `previous_error` 放进新的 `user`。
