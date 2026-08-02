# Week 03 项目记录

> 本周为 Agent Sandbox 增加 Docker 执行层，使代码能够在临时容器中运行，
> 并向上层返回结构化执行结果。

### 执行数据模型:
`ExecutionRequest` 用来描述一次沙盒执行请求，目前包含项目目录、命令和资源限制：
```python
class ExecutionRequest(BaseModel):
    project_dir: Path
    commands: list[str] = Field(min_length=1)
    timeout_seconds: float = Field(default=5, gt=0)
    memory_limit_mb: int = Field(default=256, gt=0)
    pids_limit: int = Field(default=64, gt=0)
    network_enabled: bool = False
    read_only_workspace: bool = True
```

Pydantic 的 `Field` 可以直接表达常见约束：
- `min_length=1`：列表或字符串不能为空。
- `gt=0`：数值必须大于零。
- `default=...`：调用方不传值时使用默认值。

`X | None` 表示字段允许为 `None`，但不代表字段可以省略。只有提供默认值后，字段才可以不传：
```python
infra_err: str | None          # 必填，但值可以是 None
infra_err: str | None = None   # 可以省略，默认是 None
```

`ExecutionResult` 负责保存执行结果，包括退出码、错误分类、运行时间、容器 ID、标准输出、标准错误和基础设施错误。

`ErrorCategory` 使用枚举限制错误类型，避免在不同模块中使用容易拼错的字符串：
```python
class ErrorCategory(Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    OUT_OF_MEMORY = "out_of_memory"
    RUNTIME_ERROR = "runtime_error"
    SYNTAX_ERROR = "syntax_error"
    ASSERTION_FAILURE = "assertion_failure"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    UNKNOWN = "unknown"
```

其中，超时、OOM 和基础设施错误属于容器执行层；语法错误、运行时错误和断言失败需要结合 pytest 报告或程序输出进一步判断。

### Backend 接口与模块边界:
`ExecutionBackend` 使用 `Protocol` 定义执行接口：
```python
class ExecutionBackend(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
```

`Protocol` 是结构化接口。一个类不需要显式继承 `ExecutionBackend`，只要提供签名匹配的 `execute()` 方法，静态类型检查器就会认为它满足该接口。

这里的 `...` 是 `Ellipsis`，用于表示接口只声明方法签名，不提供实现。

当前模块职责如下：
- `models.py`：请求、结果和错误分类等数据模型。
- `backend_protocol.py`：执行后端的稳定接口。
- `docker_backend.py`：依赖 Docker SDK 的具体实现。

上层代码依赖 `ExecutionBackend`，而不是直接依赖 Docker SDK。这样可以替换具体执行后端，也可以在测试中提供 fake backend。

### Docker 运行环境:
Docker 由几个核心部分组成：
- image：只读的容器模板，例如 `python:3.12-slim`。
- container：镜像启动后的运行实例。
- daemon：负责拉取镜像、创建和管理容器的后台服务。
- CLI：`docker` 命令行客户端，向 daemon 发出请求。

当前执行环境使用 `python:3.12-slim`。`slim` 基于精简的 Debian，体积比完整 Python 镜像小，同时比 Alpine 有更好的 Python 包兼容性。

常用命令：
```bash
docker pull python:3.12-slim
docker run --rm python:3.12-slim python -c "print('hello')"
docker run --rm -it python:3.12-slim bash
```

`--rm` 表示容器退出后自动删除。`docker exec` 会在运行中的容器内启动一个新进程；`docker attach` 连接的是容器主进程的输入输出，通常不用于进入容器调试。

官方 Python 镜像的默认 `CMD` 是 Python，因此不指定命令时会进入 Python REPL。调试时可以用 `docker run --rm -it IMAGE sh` 覆盖默认命令；backend 传入的 `command` 同样会覆盖镜像默认 `CMD`。

在 WSL 中，终端设置的代理环境变量只对当前 shell 及其子进程生效。拉取镜像由 Docker daemon 完成，因此 daemon 需要单独配置代理。

### Docker Python SDK:
项目使用 docker-py 操作 Docker：
```python
import docker

client = docker.from_env()
container = client.containers.run(
    "python:3.12-slim",
    command=["python", "-c", "print('hello')"],
    detach=True,
)
```

`detach=True` 让 `run()` 立即返回 `Container` 对象。后续可以通过该对象管理完整生命周期：
```python
result = container.wait()
stdout = container.logs(stdout=True, stderr=False)
stderr = container.logs(stdout=False, stderr=True)
container.reload()
container.remove(force=True)
```

各方法的作用：
- `wait()`：等待容器主进程结束，并返回 `StatusCode`。
- `logs()`：读取日志，返回值是 `bytes`，需要调用 `.decode()`。
- `reload()`：从 daemon 刷新容器状态和 `attrs`。
- `attrs["State"]["OOMKilled"]`：判断容器是否因为 OOM 被终止。
- `remove(force=True)`：强制删除容器。

### 容器安全限制:
当前 Docker 执行参数同时限制资源、网络、权限和文件系统：
```python
container = client.containers.run(
    "python:3.12-slim",
    mem_limit=f"{request.memory_limit_mb}m",
    memswap_limit=f"{request.memory_limit_mb}m",
    pids_limit=request.pids_limit,
    network_disabled=not request.network_enabled,
    read_only=True,
    user="65534:65534",
    cap_drop=["ALL"],
    security_opt=["no-new-privileges"],
    tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
)
```

资源限制：
- `mem_limit="256m"`：限制容器最多使用 256 MB 内存。Docker SDK 接收整数时按字节解释，因此模型中的 MB 数值需要显式加上 `m`。
- `memswap_limit="256m"`：内存与 memory+swap 总上限相同，不允许容器额外使用 swap。
- `pids_limit=64`：限制容器可创建的进程数量，降低无限创建进程的风险。
- `network_disabled=True`：禁用容器网络。镜像和依赖必须提前准备，运行阶段不能依赖在线安装。

权限限制：
- `user="65534:65534"`：使用非 root 用户运行容器进程。
- `cap_drop=["ALL"]`：删除 Linux capabilities，阻止挂载文件系统、修改网络和跟踪其他进程等特权操作。
- `security_opt=["no-new-privileges"]`：禁止子进程通过 setuid、setgid 等方式获得额外权限。

文件系统限制：
- `read_only=True`：将容器根文件系统设为只读，不能修改 `/usr`、`/etc`、`/var` 等镜像内容。
- `/workspace:ro`：项目目录默认只读挂载，避免测试修改宿主机代码。
- `tmpfs`：在只读容器中为 `/tmp` 提供受限的临时可写空间。

`tmpfs` 是临时内存文件系统：
```text
/                  只读
/workspace         默认只读
/tmp               可写，最大 64 MB，容器删除后消失
```

`tmpfs` 参数含义：
- `rw`：允许读写临时文件。
- `noexec`：禁止操作系统直接执行 `/tmp` 中的二进制文件。
- `nosuid`：忽略 setuid/setgid 权限位，避免借此提权。
- `size=64m`：限制临时目录最多占用 64 MB。

普通 Python 计算、读取项目文件和 pytest 通常不受这些限制。需要额外处理的写入行为包括：
- 设置 `PYTHONDONTWRITEBYTECODE=1`，避免 Python 创建 `__pycache__` 和 `.pyc`。
- pytest 使用 `-p no:cacheprovider`，避免在只读工作区创建 `.pytest_cache`。
- 测试需要临时文件时使用 `/tmp` 或 pytest 的 `tmp_path`。
- 不能在容器启动后执行 `pip install`；测试依赖需要预先构建到镜像中。

`PYTHONUNBUFFERED=1` 让 stdout 和 stderr 立即输出，便于在超时或异常终止时保留尽可能完整的日志。

### Python 字节码与 `__pycache__`:
“Python 逐行运行”是对程序执行效果的简化描述。CPython 实际会先解析源码并将其编译为 Python 字节码，再由 Python 虚拟机逐条执行字节码指令：
```text
.py 源代码
    -> 词法与语法分析
    -> Python 字节码
    -> Python 虚拟机执行
```

这里的编译结果不是 CPU 直接执行的机器码。一行源码可能对应多条字节码指令，函数体也要等函数被调用时才执行。提前编译可以避免循环或函数每次执行时都重新解析源码，并能在程序真正运行前发现语法错误。

导入模块时，Python 可能把字节码缓存到 `__pycache__` 目录中的 `.pyc` 文件：
```text
app/cart.py
app/__pycache__/cart.cpython-312.pyc
```

`.pyc` 可以安全删除，Python 会在需要时重新编译。项目通常应忽略这些运行时缓存：
```gitignore
__pycache__/
*.py[cod]
```

字节码的代码对象会保留编译时的源码路径。当前项目曾在宿主机生成 pytest 字节码，其中记录的路径为：
```text
/home/yinkai/agent-sandbox/fixtures/buggy_project/tests/test_cart.py
```

同一项目挂载到容器后位于 `/workspace`。容器读取宿主机生成的 `.pyc` 后，pytest 会按照字节码中的宿主路径查找源码；该路径在容器内不存在，因此 traceback 的对应源码行显示为 `???`，但测试执行和错误定位信息仍然有效。

`PYTHONDONTWRITEBYTECODE=1` 只禁止 Python 写入新的 `.pyc`，不会禁止读取已经存在的缓存。因此，送入沙盒的项目不应包含 `__pycache__`，或者应为容器配置独立的字节码缓存目录。

### 容器生命周期管理:
当前执行路径为：
```text
连接 daemon
    -> 创建并启动容器
    -> 等待命令结束
    -> 刷新容器状态
    -> 收集退出码和日志
    -> 构造 ExecutionResult
    -> 删除容器
```

容器清理放在 `finally` 中，保证成功、命令失败或 Docker SDK 抛出异常时都会尝试删除容器：
```python
container = None
try:
    container = client.containers.run(...)
    ...
finally:
    if container is not None:
        container.remove(force=True)
```

`container` 必须在 `try` 前初始化。如果 `docker.from_env()` 或 `containers.run()` 提前失败，`finally` 仍然可以安全判断，不会因为引用未定义变量而掩盖原始异常。

### 执行结果与错误处理:
容器内程序的错误和 Docker 基础设施错误需要分开处理：

- 程序错误：容器成功启动，但命令以非零状态码退出；错误信息通常在 `stderr`。
- 基础设施错误：daemon 无法连接、镜像不存在或容器创建失败；此时可能没有有效的容器 ID 和退出码。
- OOM：容器状态中的 `OOMKilled` 为 `True`。

Docker SDK 的基础异常可以显式导入：
```python
from docker.errors import DockerException
```

基础设施错误应该映射为结构化 `ExecutionResult`，不能伪装成用户代码的运行时错误，否则上层 repair graph 可能错误地调用 LLM 修改代码。

运行时长使用 `time.perf_counter()` 测量：
```python
start_clock = time.perf_counter()
duration_seconds = time.perf_counter() - start_clock
```

字段名称需要与实际单位一致。保存秒时使用 `duration_seconds`；保存毫秒时应乘以 `1000` 并使用 `duration_ms`。

### Python 工程配置:
Python 不要求预先声明变量，因此变量只在部分分支中赋值时，可能出现 `NameError` 或 possibly unbound 警告。减少这类问题的方法包括：
- 缩小变量作用域，在赋值后尽快使用。
- 每条成功或失败路径直接构造并返回 `ExecutionResult`。
- 必须跨越 `try/finally` 的变量提前设置默认值。
- 使用 Pylance `basic` 模式进行静态检查。

字典和对象的访问方式不同：
```python
result_data["exit_code"]  # 字典
execution_result.exit_code  # 对象属性
```

把字典展开为 Pydantic 构造参数时使用 `**`：
```python
ExecutionResult(**result_data)
```

向 `python -c` 传递多行代码时，可以使用 `textwrap.dedent()` 删除代码块各行共同的前导缩进：
```python
from textwrap import dedent

oom_code = dedent(
    """
    chunks = []

    while True:
        chunks.append(bytearray(10 * 1024 * 1024))
    """
).strip()

commands = ["python", "-c", oom_code]
```

三引号字符串会保留源文件中的缩进。如果直接传给 `python -c`，顶层语句可能因为多余空格触发 `IndentationError: unexpected indent`。`dedent()` 删除共同缩进，同时保留 `while` 循环体内部的相对缩进；`.strip()` 用于删除代码块首尾空行。

项目使用 Ruff 进行代码格式化、import 排序和 lint。Python 3.10 以上使用 `X | None` 替代 `Optional[X]`，可以减少额外 import，并保持类型标注统一。

文件路径描述磁盘上的位置，模块路径描述代码在 Python 包结构中的名称：
```text
文件路径：agent_sandbox/sandbox/docker_backend.py
模块路径：agent_sandbox.sandbox.docker_backend
```

直接按文件路径运行时：
```bash
python agent_sandbox/sandbox/docker_backend.py
```

Python 会把它当作独立脚本，通常无法确定它所属的包，`__package__` 可能是 `None`。此时 `from .models import ...` 中的 `.` 没有明确的当前包，因此相对导入可能失败。

包含相对导入的模块应从项目根目录使用 module 方式运行：
```bash
python -m agent_sandbox.sandbox.docker_backend
```

`-m` 会先通过 Python import 系统查找完整模块，再以 `__main__` 身份执行。查找过程中 Python 会建立包上下文：
```python
__name__ == "__main__"
__package__ == "agent_sandbox.sandbox"
```

因此 `from .models import ...` 可以根据 `__package__` 解析为 `agent_sandbox.sandbox.models`。关键不是简单地把点号转换成斜杠，而是先确认模块的完整包身份，再执行模块。

`python -m` 解决的是 Python import 上下文，不会改变 `Path("file.txt")` 等普通相对文件路径；这些路径仍然以当前工作目录为基准。
