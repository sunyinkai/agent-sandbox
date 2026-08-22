import argparse
import ast
from pathlib import Path

DEFINITION_TYPES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def get_symbol_type(node: ast.AST) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    if isinstance(node, ast.FunctionDef):
        return "function"
    raise TypeError(f"Unsupported node type: {type(node).__name__}")


def inspect_file(path: Path, show_dump: bool = False) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    print(type(tree))

    if show_dump:
        print("=======dump tree========")
        print(ast.dump(tree, indent=2, include_attributes=True))
        print()

    print("==========walk tree=========")
    for index, node in enumerate(ast.walk(tree)):
        print(f"========== node {index} ==========")
        print(ast.dump(node=node, indent=2, include_attributes=True))

    print()
    print("=========filter node========")
    definitions = (
        node for node in ast.walk(tree) if isinstance(node, DEFINITION_TYPES)
    )
    for node in sorted(definitions, key=lambda item: item.lineno):
        symbol_type = get_symbol_type(node)
        print(f"{symbol_type} {node.name}: {node.lineno}-{node.end_lineno}")


def main() -> None:
    default_sample = Path(__file__).with_name("ast_sample.py")
    parser = argparse.ArgumentParser(description="Inspect Python AST definitions.")
    parser.add_argument("path", nargs="?", type=Path, default=default_sample)
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Print the complete AST before the symbol summary.",
    )
    args = parser.parse_args()

    inspect_file(args.path, show_dump=args.dump)


if __name__ == "__main__":
    main()
