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

## 扫描器中的 Python 语法

### 方法对象与方法调用

只写方法名会得到方法对象，加上括号才会真正调用方法并取得返回值：

```python
path.is_file     # 方法对象
path.is_file()   # 调用方法，返回 bool

path.as_posix     # 方法对象
path.as_posix()   # 调用方法，返回 str
```

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
