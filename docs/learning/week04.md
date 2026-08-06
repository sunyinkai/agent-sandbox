# Week 04 项目记录

> 本周为 Agent Sandbox 整理统一的本地工具层，使上层流程能够通过稳定接口读取项目、修改代码、运行测试并查看 Git diff。

### 使用 `pathlib` 遍历工作区文件

```python
def list_files(self) -> list[str]:
    return sorted(
        str(path.relative_to(self.root))
        for path in self.root.rglob("*")
        if path.is_file()
    )
```

这是生成器表达式：`rglob("*")` 递归遍历路径，`is_file()` 过滤目录，`relative_to()` 转为工作区相对路径，最后由 `sorted()` 生成排序后的列表。它等价于逐个遍历、过滤并 `append` 的普通 `for` 循环。文件遍历直接使用 `pathlib`，不需要启动子进程。

### `Path` 拼接与工作区边界

`Path` 重载了 `/` 运算符，可以直接拼接路径：
```python
root = Path("/home/yinkai/project")
path = Path("app/cart.py")
root / path
# Path("/home/yinkai/project/app/cart.py")
```

如果右侧是绝对路径，左侧会被忽略，例如 `Path("/workspace") / Path("/etc/passwd")` 的结果是 `/etc/passwd`。因此工具层要先拒绝绝对路径，再检查最终路径是否仍位于工作区：
```python
def _check_path(self, path: Path) -> bool:
    if path.is_absolute():
        return False
    root = self.root.resolve()
    resolved_path = (root / path).resolve()
    return resolved_path.is_relative_to(root)
```

`resolve()` 会解析 `..` 和 symlink，`is_relative_to(root)` 再确认真实路径没有逃出工作区。因此 `app/cart.py` 可以通过，而 `../README.md` 和指向外部文件的 symlink 会被拒绝。