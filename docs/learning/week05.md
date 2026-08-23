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

### type(value) is SomeClass 与 isinstance()

`type(value)` 返回对象的实际类型。使用 `is` 比较时，只接受完全相同的类型：

```python
type(value) is SomeClass
```

`isinstance()` 判断对象是否属于指定类型，并且也接受该类型的子类：

```python
isinstance(value, SomeClass)
```

两者在没有继承关系时结果通常相同：

```python
value = 123

type(value) is int       # True
isinstance(value, int)   # True
```

存在继承关系时，区别会变得明显：

```python
class Animal:
	pass


class Dog(Animal):
	pass


dog = Dog()

type(dog) is Dog          # True
type(dog) is Animal       # False，只检查精确类型
isinstance(dog, Dog)      # True
isinstance(dog, Animal)   # True，Dog 是 Animal 的子类
```

因此，业务代码通常优先使用 `isinstance()`。它支持继承和多态，不会因为以后增加子类而
意外拒绝合法对象。只有明确要求“必须是这个精确类型，不能是任何子类”时，才使用：

```python
type(value) is SomeClass
```

`isinstance()` 的第二个参数也可以是类型组成的 tuple，用于一次判断多个类型：

```python
isinstance(value, (str, int))
```

它等价于：

```python
isinstance(value, str) or isinstance(value, int)
```

`isinstance()` 只检查类型，不会转换对象：

```python
value = "123"

isinstance(value, int)  # False
number = int(value)     # 显式转换为 int
```

在 ingestion 中，`parse_python_file()` 返回 union 类型：

```python
ParsedFile | IngestionError
```

可以使用 `isinstance()` 区分成功结果和错误结果：

```python
for result in parsed_files:
	if isinstance(result, IngestionError):
		errors.append(result)
	else:
		chunks.extend(ChunkGenerator(result).generate())
```

这个判断还会帮助类型检查器进行 type narrowing（类型缩小）：

```text
判断前：result 是 ParsedFile | IngestionError
if 分支：result 是 IngestionError
else 分支：result 是 ParsedFile
```

相比之下，下面的判断表达的是“只要它的精确类型不是 `IngestionError` 就当作成功结果”，
语义不够明确，也不能正确识别 `IngestionError` 的子类：

```python
if type(result) is not IngestionError:
	chunks.extend(ChunkGenerator(result).generate())
```

更推荐直接说明想接受的类型，或先处理明确的错误类型：

```python
if isinstance(result, ParsedFile):
	chunks.extend(ChunkGenerator(result).generate())
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

### tuple 与 tuple 类型标注

`tuple`（元组）和 `list` 一样，都可以按顺序保存多个元素，并支持遍历、索引和切片。
它们最主要的区别是：list 是可变序列，tuple 是不可变序列。

tuple 通常使用圆括号创建：

```python
names = ("class", "function", "async_function")

names[0]       # "class"
names[1:]      # ("function", "async_function")
len(names)     # 3
```

只有一个元素的 tuple 必须保留末尾逗号，否则圆括号只表示普通的表达式分组：

```python
single = ("function",)  # tuple[str]
not_tuple = ("function")  # str
empty = ()               # 空 tuple
```

tuple 创建后不能增加、删除或替换元素：

```python
chunks = (chunk_a, chunk_b)

chunks[0] = chunk_c      # TypeError，不能替换元素
chunks.append(chunk_c)   # AttributeError，没有 append()
chunks.clear()           # AttributeError，没有 clear()
```

`+=` 看起来像修改 tuple，实际会创建一个新 tuple，再让变量指向新对象：

```python
original = (1, 2)
numbers = original
numbers += (3,)

original  # (1, 2)
numbers   # (1, 2, 3)
```

和 `frozen=True` 类似，tuple 也是浅层不可变。tuple 自身不能替换元素，但元素指向的对象
如果可变，仍然可以修改对象内部：

```python
values = ([1, 2], [3, 4])

values[0] = [5]       # TypeError，不能替换 tuple 元素
values[0].append(5)   # 可以，内部 list 变为 [1, 2, 5]
```

`tuple(iterable)` 是运行时的构造函数，可以把 list、生成器等可迭代对象转换为 tuple：

```python
chunk_list = [chunk_a, chunk_b]
chunk_tuple = tuple(chunk_list)

# chunk_tuple == (chunk_a, chunk_b)
```

这个转换会创建一个新的 tuple。之后修改原 list 的结构，不会改变已经创建的 tuple：

```python
chunk_list.append(chunk_c)

len(chunk_list)   # 3
len(chunk_tuple)  # 2
```

`tuple[CodeChunk, ...]` 不是创建 tuple 的代码，而是类型标注，表示“长度不固定，且每个元素
都是 `CodeChunk` 的 tuple”。其中 `...` 表示可以有任意数量的同类型元素：

```python
def generate() -> tuple[CodeChunk, ...]:
	...
```

以下值都符合 `tuple[CodeChunk, ...]`：

```python
()
(chunk_a,)
(chunk_a, chunk_b)
(chunk_a, chunk_b, chunk_c)
```

如果类型标注中列出了不同位置的类型，则表示固定长度和固定位置：

```python
location: tuple[str, int] = ("service.py", 12)
```

这里要求 tuple 正好包含两个元素：第一个是 `str`，第二个是 `int`。因此：

- `tuple[CodeChunk, ...]`：任意数量的 `CodeChunk`。
- `tuple[str, int]`：固定两个元素，类型依次是 `str` 和 `int`。
- `tuple[()]`：空 tuple 的类型。

Chunk Generator 中的返回值把运行时转换和类型标注结合起来：

```python
def generate(self) -> tuple[CodeChunk, ...]:
	self.visit(self.tree)
	self.chunks.sort(key=lambda chunk: chunk.start_line)
	return tuple(self.chunks)
```

这里 `self.chunks` 在类内部是 `list[CodeChunk]`，方便遍历过程中使用 `append()` 和排序；
完成生成后，`tuple(self.chunks)` 返回一个新的不可变结果，调用方不能通过返回值增删或
替换 Chunk。`CodeChunk` 本身又使用 `@dataclass(frozen=True)`，因此外层 tuple 和内层
frozen dataclass 共同限制了意外修改。

### SHA-256 与 Chunk 哈希

SHA-256 是一种哈希算法。Python 通过标准库 `hashlib` 提供公开接口：

```python
from hashlib import sha256
```

编辑器中可能会跳转到 `_hashlib.openssl_sha256`。它是 Python 借助 OpenSSL 提供的底层
实现，业务代码不应直接依赖 `_hashlib`，继续使用稳定的公开接口 `hashlib.sha256` 即可。

SHA-256 接收字节数据，并生成固定长度的摘要：

```python
text = "hello"
hash_object = sha256(text.encode("utf-8"))
hash_value = hash_object.hexdigest()
```

处理过程可以理解为：

```text
str
	↓ encode("utf-8")
bytes
	↓ sha256(...)
哈希对象
	↓ hexdigest()
64 个十六进制字符
```

`sha256()` 不能直接处理 `str`，因为哈希算法操作的是字节：

```python
sha256(text)                  # TypeError
sha256(text.encode("utf-8"))  # 正确
```

哈希对象常用的两种输出方式是：

```python
hash_object.digest()     # 返回 32 字节的 bytes
hash_object.hexdigest()  # 返回 64 字符的十六进制 str
```

JSON、日志和数据库键通常更适合使用 `hexdigest()`，因为字符串更容易存储和查看。

SHA-256 的主要特点包括：

- 相同输入总会产生相同结果。
- 输入发生细微变化时，输出通常会完全不同。
- 输出长度固定，不随输入长度变化。
- 很难从哈希值反推出原始输入。
- 不同输入理论上可能产生相同结果，但在当前 Chunk 场景中碰撞概率可以忽略。

哈希不是加密。它没有密钥和对应的解密过程，不应把哈希理解为可以恢复原文的密文。

`content_hash` 只由 Chunk 的源码内容计算：

```python
content_hash = sha256(content.encode("utf-8")).hexdigest()
```

相同源码得到相同的 `content_hash`；即使只修改一个字符，哈希值通常也会完全变化。它可以
用于：

- 判断 Chunk 内容是否变化。
- 跳过未变化 Chunk 的 embedding 或索引更新。
- 查找内容完全相同的 Chunk。
- 比较两次 ingestion 的结果。

`chunk_id` 应由稳定的身份字段计算，而不是由源码内容计算：

```python
identity = "\0".join(
		[
				repo_id,
				file_path.as_posix(),
				symbol_type,
				qualified_name,
		]
)
chunk_id = sha256(identity.encode("utf-8")).hexdigest()
```

这里使用 `"\0"` 分隔字段，避免普通字符拼接产生边界歧义。例如用下划线拼接时，
`["a_b", "c"]` 和 `["a", "b_c"]` 都可能得到 `a_b_c`；使用明确分隔符后，两组输入
仍然不同。

`repo_id` 应使用稳定的仓库标识，例如仓库名称或配置的 ID，不应直接使用本机绝对路径。
否则仓库从一个目录移动到另一个目录后，所有 `chunk_id` 都会改变。

两个哈希字段的语义不同：

```text
chunk_id      = 它是谁
content_hash  = 它当前是什么内容
```

理想行为是：

- 只修改函数内部源码：`chunk_id` 不变，`content_hash` 改变。
- 修改 `qualified_name`、`file_path` 或 `symbol_type`：`chunk_id` 改变。
- 只移动源码行号但身份和内容不变：两个哈希都不变。
- 相同输入重复运行 ingestion：两个哈希都保持稳定。

行号适合定位源码，但不应作为主要身份字段。把行号加入 `chunk_id` 后，在文件顶部插入一行
无关代码就会改变后续所有 Chunk 的 ID，不利于增量处理。

### JSON 与 JSONL

JSON（JavaScript Object Notation）可以保存一个完整的结构化值。多个对象通常放在一个
数组中：

```json
[
  {"chunk_id": "a", "file_path": "src/a.py"},
  {"chunk_id": "b", "file_path": "src/b.py"}
]
```

JSONL（JSON Lines）是一种逐行保存 JSON 对象的文本格式：

```jsonl
{"chunk_id": "a", "file_path": "src/a.py"}
{"chunk_id": "b", "file_path": "src/b.py"}
```

JSONL 的规则是：

- 没有包住全部记录的最外层 `[]`。
- 每一行都是一个可以独立解析的合法 JSON 值，通常是 object。
- 每条记录末尾写入换行符 `\n`。
- 空文件可以表示没有记录，通常不额外写入 `[]`。

JSON 适合配置文件、API 响应和需要整体读取的嵌套数据。JSONL 适合日志、Chunk 数据集和
批处理结果，主要优点包括：

- 可以逐条写入，不必先把所有记录组成一个大数组。
- 可以逐行读取，不必一次把整个文件加载到内存。
- 容易追加新记录。
- 单行损坏时，其他行仍可能继续处理。
- 适合流式处理和命令行工具。

#### dump() 与 dumps()

Python 标准库 `json` 提供两组常用操作：

```python
import json

text = json.dumps(data)  # 序列化为 str
data = json.loads(text)  # 从 str 反序列化

json.dump(data, file)   # 直接序列化并写入文件对象
data = json.load(file)  # 从文件对象读取并反序列化
```

名称末尾的 `s` 可以理解为 string：

- `dumps()`：Python 对象变成 JSON 字符串。
- `loads()`：JSON 字符串变成 Python 对象。
- `dump()`：Python 对象直接写入文件。
- `load()`：从文件读取一个完整 JSON 值。

JSONL 不是一个完整的 JSON 数组，因此不能对整个 JSONL 文件直接调用一次 `json.load()`。
它需要逐行读取，再对每一行调用 `json.loads()`：

```python
with path.open("r", encoding="utf-8") as file:
	records = [json.loads(line) for line in file if line.strip()]
```

#### 写入 JSONL

写入 JSONL 时，需要对每个对象单独调用一次 `json.dump()`，然后补一个换行符：

```python
with path.open("w", encoding="utf-8") as file:
	for item in items:
		json.dump(item, file, ensure_ascii=False)
		file.write("\n")
```

下面的写法输出的是包含所有元素的一个 JSON 数组，不是 JSONL：

```python
json.dump(items, file)
```

#### dataclass 与 Path 的序列化

标准库 `json` 只能直接处理 `dict`、`list`、`str`、`int`、`float`、`bool` 和 `None` 等
基础类型，不能直接处理 dataclass 或 `Path`：

```python
json.dumps(code_chunk)       # TypeError，CodeChunk 是 dataclass
json.dumps(Path("src/a.py"))  # TypeError，Path 不是 JSON 基础类型
```

可以使用 `dataclasses.asdict()` 先把 dataclass 递归转换成字典：

```python
from dataclasses import asdict

data = asdict(code_chunk)
```

字典中的 `Path` 仍需转换成字符串。一种简便方式是给 `json.dump()` 传入 `default=str`：

```python
json.dump(data, file, ensure_ascii=False, default=str)
```

遇到 JSON 不认识的对象时，`default=str` 会调用 `str(object)`。它可以处理 `Path`，但也会
把其他意外类型静默转换成字符串。需要严格控制输出 schema 时，更适合显式转换：

```python
data = asdict(code_chunk)
data["file_path"] = code_chunk.file_path.as_posix()
json.dump(data, file, ensure_ascii=False)
```

`ensure_ascii=False` 让中文等非 ASCII 字符直接写入文件：

```json
{"content": "你好"}
```

默认的 `ensure_ascii=True` 也会生成合法 JSON，但中文会显示为 Unicode 转义：

```json
{"content": "\u4f60\u597d"}
```

当前 dataclass Writer 的基本结构可以写成：

```python
from collections.abc import Iterable


def write(self, content: Iterable[IngestionError | CodeChunk]) -> None:
	with self.file_name.open("w", encoding="utf-8") as file:
		for item in content:
			data = asdict(item)
			json.dump(data, file, ensure_ascii=False, default=str)
			file.write("\n")
```

#### list 的不变性与 Iterable 的协变

假设 Writer 的参数声明为：

```python
def write(self, content: list[IngestionError | CodeChunk]) -> None:
	...
```

而调用方有一个只允许保存 `CodeChunk` 的列表：

```python
chunks: list[CodeChunk] = []
writer.write(chunks)
```

直觉上，`CodeChunk` 属于 `IngestionError | CodeChunk`，似乎应该可以传入。但 `list` 是
可变容器，`write()` 理论上可以向参数中添加 `IngestionError`：

```python
def write(self, content: list[IngestionError | CodeChunk]) -> None:
	content.append(some_ingestion_error)
```

如果类型检查器允许传入 `chunks`，调用结束后，声明为 `list[CodeChunk]` 的列表中就会出现
`IngestionError`，破坏原来的类型保证：

```text
调用前：chunks 只能保存 CodeChunk
传给 write()：参数允许保存 CodeChunk 或 IngestionError
write() 添加错误对象
调用后：chunks 中出现 IngestionError
```

即使当前 `write()` 实现没有调用 `append()`，参数类型写成 `list[...]` 就表示函数拥有修改
这个列表的能力。类型检查器必须按这个接口承诺进行判断，不能只依赖当前函数体碰巧没有
修改列表。

Writer 实际只需要使用 `for` 读取元素，不需要修改调用方的容器，因此参数应声明为：

```python
from collections.abc import Iterable


def write(self, content: Iterable[IngestionError | CodeChunk]) -> None:
	for item in content:
		...
```

`Iterable` 只承诺对象可以被遍历，没有 `append()`、`clear()` 等修改接口。于是下面这些
参数都可以安全传入：

```python
chunks: list[CodeChunk]
errors: list[IngestionError]
chunk_tuple: tuple[CodeChunk, ...]

writer.write(chunks)
writer.write(errors)
writer.write(chunk_tuple)
```

可以先用下面的方式记忆：

```text
list[T]     = 可以读取，也可以修改
Iterable[T] = 只承诺可以逐个读取
Sequence[T] = 只读序列接口，还支持 len()、索引和切片
```

专业术语如下：

- **泛型（generic）**：`list[T]`、`Iterable[T]` 这类可以接收元素类型参数的类型。
- **类型参数（type parameter）**：上面泛型中的 `T`；例如 `list[CodeChunk]` 的元素类型参数
  是 `CodeChunk`。
- **联合类型（union type）**：`IngestionError | CodeChunk`，表示值可以是两种类型之一。
- **不变（invariant）**：即使 `CodeChunk` 是 union 的一部分，`list[CodeChunk]` 也不能作为
  `list[IngestionError | CodeChunk]` 使用。`list` 的元素类型参数是不变的。
- **协变（covariant）**：如果较具体的元素类型可以安全替代较宽泛的元素类型，就称该类型
  参数协变。只提供读取能力的 `Iterable` 和 `Sequence` 对元素类型是协变的。
- **类型缩小（type narrowing）**：通过 `isinstance()` 等判断，把 union 类型在不同分支中
  缩小为更具体的类型。

因此，这个 Pylance 报错并不是说 `CodeChunk` 不属于 union，而是在防止函数通过可变列表
向 `list[CodeChunk]` 中放入 `IngestionError`。当函数只读取输入时，接收 `Iterable` 既能
表达真实需求，也能避免这个类型冲突。

#### 文件模式与类型标注

常见文本文件模式包括：

- `"w"`：写入并覆盖原文件，适合每次生成一份完整 ingestion 结果。
- `"a"`：在文件末尾追加，重复运行时可能产生重复记录。
- `"r"`：只读，不能用于 Writer 写入。

下面的写法不正确：

```python
mode: str = "w" | "r"
```

`|` 在类型标注中可以表示 union，例如 `str | None`；但这里左右两边是运行时字符串值，
Python 会尝试计算 `"w" | "r"` 并抛出 `TypeError`。如果只想设置默认值，应写成：

```python
mode: str = "w"
```

如果想限制允许的字符串值，可以使用 `Literal`：

```python
from typing import Literal


def __init__(self, file_name: Path, mode: Literal["w", "a"] = "w") -> None:
	self.file_name = file_name
	self.mode = mode
```

对每次完整生成 artifacts 的 Writer，固定使用 `"w"` 通常最简单；只有明确需要增量追加时
才开放 `"a"`。

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
