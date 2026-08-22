import ast
from pathlib import Path
from typing import Any


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.qualified_symbol = list[str]()
        super().__init__()

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        print(node.name)
        print(node.lineno)
        print(node.end_lineno)
        self.qualified_symbol.append(node.name)
        print(f"qualified name: {'.'.join(self.qualified_symbol)}")
        self.generic_visit(node)
        self.qualified_symbol.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        print(node.name)
        print(node.lineno)
        print(node.end_lineno)
        if node.decorator_list:
            print("has decorators")
            print(f"line: {node.decorator_list[0].lineno}")
        self.qualified_symbol.append(node.name)
        print(f"qualified name: {'.'.join(self.qualified_symbol)}")
        self.generic_visit(node)
        self.qualified_symbol.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        print(node.name)
        print(node.lineno)
        print(node.end_lineno)
        self.generic_visit(node)


if __name__ == "__main__":
    file = Path(__file__).with_name("ast_sample.py")
    source = file.read_text()
    tree = ast.parse(source=source, filename=file)
    analyzer = CodeAnalyzer()
    print("tree is: ")
    print(ast.dump(tree, indent=2, include_attributes=True))
    print()
    analyzer.visit(tree)
