# Week 05 项目记录

> 本周为 Agent Sandbox 增加 Python 源码 ingestion 层，使用 AST 按符号切分源码，
> 并保留文件路径、符号名称和源码行号等 metadata。

## AST 定义

AST（Abstract Syntax Tree，抽象语法树）是 Python 源码的结构化表示。源码中的模块、
类、函数、语句和表达式都会成为不同类型的节点，例如：

- `ast.Module`：整个 Python 文件的根节点。
- `ast.ClassDef`：类定义。
- `ast.FunctionDef`：同步函数或方法定义。
- `ast.AsyncFunctionDef`：异步函数或方法定义。
- `ast.Return`：`return` 语句。
- `ast.Name`：变量名。

AST 保留程序的语法结构，但不会完整保留注释和空行等原始文本信息。

## AST 树结构与遍历

AST 是一棵嵌套树。例如一个类包含方法，方法包含参数和 `return` 语句：

```text
Module
└── ClassDef: UserService
	└── FunctionDef: get_user
		├── arguments
		└── Return
			└── Name: user_id
```

`ast.walk(tree)` 会平铺遍历整棵树，适合查找特定类型的节点：

```python
for node in ast.walk(tree):
	if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
		print(node.name, node.lineno, node.end_lineno)
```

`ast.NodeVisitor` 适合需要感知嵌套关系的遍历。它通常按深度优先方式访问节点，后续可以
配合符号栈生成 `UserService.get_user` 这样的 qualified name。

### NodeVisitor 工作原理

- `visit(node)`：统一入口，根据节点类型选择处理方法。
- `visit_XXX(node)`：处理指定类型，例如 `ClassDef` 对应 `visit_ClassDef()`。
- `generic_visit(node)`：遍历当前节点的子节点，并对每个子节点再次调用 `visit()`。

核心循环是：

```text
visit(node)
	↓ 按节点类型分发
visit_XXX(node) 或 generic_visit(node)
	↓
generic_visit(node) 找到子节点
	↓
对子节点再次调用 visit(child)
	↓
重复以上过程
```

以 `Module` 根节点为例：

```text
visit(Module)
	↓ 没有 visit_Module()
generic_visit(Module)
	↓ 查看 Module.body
找到 ClassDef、FunctionDef、Import、Assign 等子节点
	↓
对每个子节点调用 visit(child)
	↓
分发到对应的 visit_XXX()，没有专用方法则再次 generic_visit()
```

`generic_visit(Module)` 不会跳过 Module；它使用默认方式处理 Module：查看 `Module.body`，
再把其中每个子节点交回 `visit()` 继续分发。

`visit()` 的分发逻辑可以简化理解为：

```python
method_name = f"visit_{type(node).__name__}"
method = getattr(self, method_name, self.generic_visit)
method(node)
```

如果没有定义对应的 `visit_XXX()`，默认调用 `generic_visit()`。如果已经定义专用方法，
框架只执行该方法；需要继续访问内部节点时，要在方法中主动调用：

```python
def visit_ClassDef(self, node: ast.ClassDef) -> None:
	print(node.name)
	self.generic_visit(node)
```

标准入口是 `visitor.visit(tree)`。直接调用 `generic_visit(tree)` 会跳过根节点自身可能存在的
`visit_XXX()`，只遍历它的子节点。

## AST 遍历顺序

`ast.walk()` 接近广度优先遍历：先访问当前节点，再访问它的直接子节点，然后继续访问
下一层。因此它的输出不一定符合源码行号顺序。

```text
Module
├── ClassDef: UserService
│   └── FunctionDef: get_user
└── FunctionDef: create_service
```

上面的遍历顺序可能是 `Module`、`UserService`、`create_service`、`get_user`。需要按源码
顺序处理定义时，应根据 `lineno` 排序。

对每个 `ast.walk()` 节点调用 `ast.dump(node)` 会重复打印它包含的子树。观察完整树时，
只需对根节点调用一次 `ast.dump(tree)`；观察遍历顺序时，只打印当前节点的类型和行号。

## AST 常见方法与属性

- `ast.parse(source, filename=...)`：把源码解析为 AST。
- `ast.dump(tree, indent=2)`：以可读形式打印 AST 结构。
- `ast.walk(tree)`：平铺遍历节点。
- `ast.iter_child_nodes(node)`：只遍历一个节点的直接子节点。
- `ast.get_source_segment(source, node)`：获取节点对应的原始源码片段。
- `ast.get_docstring(node)`：获取模块、类或函数的 docstring。
- `lineno`、`end_lineno`：节点的 1-based 起止行号，结束行包含在范围内。
- `col_offset`、`end_col_offset`：节点在起止行中的列偏移。
- `name`：类或函数等定义节点的符号名。
- `decorator_list`：类或函数定义上的装饰器节点列表。

### ast.parse() 的 source 与 filename

`source` 是真正被解析的源码字符串；`filename` 只是这段源码的来源标签，不负责读取文件，
也不改变 AST 的语法结构：

```python
tree = ast.parse(
	source=source,
	filename=file_path.as_posix(),
)
```

不传 `filename` 时默认显示为 `<unknown>`。传入后，`SyntaxError` 会包含更明确的来源：

```text
File "src/service.py", line 12
```

即使 `filename` 指向一个不存在的文件，只要 `source` 合法，`ast.parse()` 仍然可以成功，
因为它不会打开该路径。成功生成的 `ast.Module` 也不会自动保存 `filename`，所以 Chunk 的
`file_path` 仍需由 `ParsedFile` 单独保存。

在 ingestion 中建议传仓库相对 POSIX 路径，既方便定位错误，也避免错误信息携带本机绝对
目录。

## Python 源码读取

### tokenize.open()

`tokenize.open()` 按照 Python 源文件的编码规则打开文件：检查 UTF-8 BOM 和文件前两行的
编码声明，没有声明时默认使用 UTF-8。

```python
import tokenize


with tokenize.open(path) as source_file:
	source = source_file.read()
```

它可以正确读取实际使用对应编码保存的源码，例如：

```python
# -*- coding: latin-1 -*-
name = "café"
```

`Path.read_text(encoding="utf-8")` 始终按指定编码读取，不会自动遵循 Python 源文件的编码
声明。因此 ingestion 读取 Python 文件时更适合使用 `tokenize.open()`。

`tokenize.open()` 只负责检测编码并返回文本文件对象，不负责生成 AST。读取后的源码仍需
交给 `ast.parse()`：

```python
with tokenize.open(path) as source_file:
	source = source_file.read()

tree = ast.parse(source, filename=file_path.as_posix())
```

常见失败包括 `SyntaxError`（非法或冲突的编码声明）、`UnicodeDecodeError`（字节无法按
检测到的编码解码）和 `OSError`（文件不存在、权限不足等）。

### splitlines(keepends=True)

`splitlines()` 将多行字符串拆成每行一个元素。默认会移除换行符，传入 `keepends=True`
则保留每行末尾的 `\n`、`\r\n` 或 `\r`：

```python
source = "first line\nsecond line\n"

source.splitlines()
# ["first line", "second line"]

source.splitlines(keepends=True)
# ["first line\n", "second line\n"]
```

生成 Chunk 时保留换行符，可以在按行切片后通过 `"".join()` 恢复原始源码格式：

```python
source_lines = source.splitlines(keepends=True)
content = "".join(source_lines[start_line - 1 : end_line])
```

如果文件最后一行原本没有换行符，`splitlines(keepends=True)` 也不会额外添加，因此比
手动使用 `"\n".join(...)` 更忠实于原文件。

## 扫描器中的 Python 语法

### 方法对象与方法调用

只写方法名会得到方法对象，加上括号才会真正调用方法并取得返回值：

```python
path.is_file     # 方法对象
path.is_file()   # 调用方法，返回 bool

path.as_posix     # 方法对象
path.as_posix()   # 调用方法，返回 str
```

### getattr() 获取对象属性

`getattr()` 根据属性名读取对象属性，三参数形式可以在属性不存在时返回默认值：

```python
getattr(object, "attribute_name", default)
```

例如，不同异常对象不一定都有 `lineno`：

```python
line_number = getattr(error, "lineno", None)
```

- `error` 有 `lineno` 时，返回它的值。
- `error` 没有 `lineno` 时，返回 `None`。
- 如果省略默认值且属性不存在，会抛出 `AttributeError`。

这适合处理 `SyntaxError`、`UnicodeDecodeError`、`OSError` 等结构不完全相同的对象。
它大致等价于：

```python
if hasattr(error, "lineno"):
	line_number = error.lineno
else:
	line_number = None
```

### dataclass 与 frozen=True

`@dataclass` 适合主要负责保存数据的类。Python 会根据字段声明自动生成 `__init__()`、
`__repr__()` 和 `__eq__()` 等常用方法：

```python
from dataclasses import dataclass


@dataclass
class ParsedFile:
	file_path: Path
	source: str
	tree: ast.Module
```

它大致省去了手动编写构造函数和字段赋值的样板代码。普通 dataclass 的类型标注主要供
类型检查器使用，默认不会像 Pydantic 一样进行运行时类型校验和自动转换。

`__repr__()` 返回面向开发者的对象表示，常用于调试、REPL、日志以及显示 list 中的对象。
dataclass 自动生成的结果通常类似：

```text
ParsedFile(file_path=PosixPath('app/users.py'), source='...', tree=<ast.Module ...>)
```

如果源码或 AST 太大，可以使用标准库 `field(repr=False)` 隐藏这些字段：

```python
from dataclasses import dataclass, field


@dataclass
class ParsedFile:
	file_path: Path
	source: str = field(repr=False)
	tree: ast.Module = field(repr=False)
```

`print(object)` 的显示顺序是：优先使用 `object.__str__()`；如果没有自定义 `__str__()`，
通常回退到 `object.__repr__()`。`repr(object)` 则直接使用 `__repr__()`：

```python
print(parsed_file)  # 优先 __str__，否则使用 __repr__
repr(parsed_file)   # 使用 __repr__
```

f-string 中的 `!r` 表示对值调用 `repr()`，会保留字符串的引号和转义字符，适合调试：

```python
text = "hello\nworld"

f"{text}"    # 实际包含换行
f"{text!r}"  # "'hello\\nworld'"
```

手动实现 `__repr__()` 时，常用 `!r` 显示字段：

```python
def __repr__(self) -> str:
	return f"User(name={self.name!r})"
```

`frozen=True` 表示对象创建后不能重新给字段赋值：

```python
@dataclass(frozen=True)
class ParsedFile:
	file_path: Path
	source: str
	tree: ast.Module
```

下面的修改会抛出 `FrozenInstanceError`：

```python
parsed_file.file_path = Path("other.py")
```

`frozen=True` 不是深度不可变。它禁止替换字段，但如果字段保存的是 list、dict 或 AST 等
可变对象，仍然可能修改对象内部内容。

简单选型原则：

- 内部领域对象、不需要 JSON 和复杂校验：优先考虑 dataclass。
- API、配置或需要 JSON 序列化和运行时校验的数据：优先考虑 Pydantic。
- `ParsedFile` 包含 `ast.Module`，适合使用 dataclass。
- `IngestionError` 后续需要输出 JSONL，适合使用 Pydantic。

### 列表推导式

列表推导式是一种简化 `for + if + append` 的语法，可以在遍历时转换和过滤元素：

```python
paths = [
	path.relative_to(root)
	for path in root.rglob("*.py")
	if path.is_file()
]
```

它大致等价于：

```python
paths = []
for path in root.rglob("*.py"):
	if path.is_file():
		paths.append(path.relative_to(root))
```

通用结构是：

```python
[expression for item in iterable if condition]
```

执行顺序是：从 iterable 取得元素、检查条件、计算 expression，最后立即生成完整列表。
列表推导式会消费可迭代对象，但它的结果是 `list`，不是迭代器。

### 生成器表达式

将方括号改为圆括号会得到生成器表达式：

```python
paths = (
	path.relative_to(root)
	for path in root.rglob("*.py")
	if path.is_file()
)
```

创建生成器时不会立即计算全部元素。`for`、`next()`、`list()`、`sorted()` 等操作向它
请求下一个值时，它才继续执行到下一个结果，这称为惰性求值：

```python
numbers = (number * 2 for number in range(3))

next(numbers)  # 0
next(numbers)  # 2
next(numbers)  # 4
```

生成器会记录当前迭代位置。元素耗尽后会抛出 `StopIteration`，不能像列表一样从头再次
遍历：

```python
numbers = (number for number in range(3))
list(numbers)  # [0, 1, 2]
list(numbers)  # []，生成器已经耗尽
```

生成器表达式适合用一条表达式描述转换和过滤。逻辑较复杂时，可以编写包含 `yield` 的
生成器函数；调用生成器函数同样会返回生成器对象：

```python
def even_numbers(limit):
	for number in range(limit):
		if number % 2 == 0:
			yield number
```

生成器不保存完整结果，因此处理大量数据或只需要消费一次时更节省内存。需要重复遍历、
随机索引或保存完整结果时，应使用列表。

`sorted()` 可以直接接收生成器，并最终返回列表：

```python
paths = sorted(
	path.relative_to(root)
	for path in root.rglob("*.py")
	if path.is_file()
)
```

当生成器表达式是函数调用的唯一位置参数时，可以省略额外的一层圆括号。上面的写法等价于：

```python
paths = sorted(
	(
		path.relative_to(root)
		for path in root.rglob("*.py")
		if path.is_file()
	)
)
```

因此，`[x for x in y]` 是列表推导式，结果是列表；`(x for x in y)` 是生成器表达式，
结果是生成器。两者都会通过迭代协议遍历 `y`。

### Path 的路径部分

`path.parts` 会把路径拆成 tuple，适合判断某个完整目录名是否存在：

```python
Path("src/__pycache__/module.py").parts
# ("src", "__pycache__", "module.py")
```

`path.relative_to(root)` 返回相对于项目根目录的路径；`path.as_posix()` 返回使用 `/` 的
路径字符串。

### Path.absolute() 与 Path.resolve()

`Path()` 构造对象时通常会去掉单个 `.`，但会保留可能影响路径含义的 `..`：

```python
Path("./examples/ast_sample.py")
# Path("examples/ast_sample.py")

Path("examples/../examples/ast_sample.py")
# Path("examples/../examples/ast_sample.py")
```

`absolute()` 的主要作用是把相对路径转换成绝对路径。它不会解析符号链接，也不保证消除
路径中的 `..`：

```python
Path("examples/../examples/ast_sample.py").absolute()
# Path("/home/yinkai/agent-sandbox/examples/../examples/ast_sample.py")
```

`resolve()` 会生成规范化的绝对路径，消除 `..`，并把符号链接解析为它最终指向的目标：

```python
Path("examples/../examples/ast_sample.py").resolve()
# Path("/home/yinkai/agent-sandbox/examples/ast_sample.py")
```

如果 `link.txt` 指向 `target.txt`，两者的结果不同：

```text
link.absolute() -> /project/link.txt
link.resolve()  -> /project/target.txt
```

现代 Python 中，`resolve()` 默认使用 `strict=False`，即目标不存在时仍可返回规范化路径。
要求路径及其目标必须存在时使用：

```python
path.resolve(strict=True)
```

两者的区别可以总结为：

| 方法 | 转为绝对路径 | 消除 `..` | 解析符号链接 | 可要求目标存在 |
|---|---:|---:|---:|---:|
| `absolute()` | 是 | 不保证 | 否 | 否 |
| `resolve()` | 是 | 是 | 是 | `strict=True` |

只需要显示当前工作目录下的绝对位置时可以使用 `absolute()`；需要知道路径最终指向哪里，
或者进行仓库边界检查时应使用 `resolve()`：

```python
root = repository_root.resolve()
target = (root / file_path).resolve()

if not target.is_relative_to(root):
	raise ValueError("File path is outside the repository")
```

这里不能用 `absolute()` 代替，因为 `..` 或指向仓库外部的符号链接可能绕过只基于路径文本
的检查。对外保存的 metadata 仍应使用仓库相对路径；解析后的绝对路径只用于内部读取和
安全检查。

### 集合无交集判断

`set.isdisjoint()` 用于判断两个集合是否没有共同元素：

```python
set(path.parts).isdisjoint(folder_exclusion_set)
```

没有排除目录时返回 `True`，路径可以保留；只要命中一个排除目录就返回 `False`。

### 排序与打印列表

`sorted()` 返回一个新的有序列表，使扫描结果不受文件创建顺序影响：

```python
paths = sorted(paths)
```

`*` 可以把列表解包成多个位置参数，`sep="\n"` 让每个元素单独占一行：

```python
print(*paths, sep="\n")
```
