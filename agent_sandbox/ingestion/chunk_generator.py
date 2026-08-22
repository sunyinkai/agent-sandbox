import ast
from pathlib import Path

from .models import CodeChunk, ParsedFile


class ChunkGenerator(ast.NodeVisitor):
    def __init__(self, parsed_file: ParsedFile) -> None:
        self.qualified_symbol = list[str]()
        self.chunks = list[CodeChunk]()
        self.file_path = parsed_file.file_path
        self.file_content = parsed_file.source.splitlines(keepends=True)
        super().__init__()

    def sort_chunks(self) -> None:
        self.chunks = sorted(self.chunks, key=lambda x: x.start_line)

    def generate_chunk(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> CodeChunk:
        parent_symbol = ".".join(self.qualified_symbol[:-1]) or None
        qualified_name = ".".join(self.qualified_symbol)
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)
        end_line = node.end_lineno
        if end_line is None:
            raise ValueError(f"Missing end_lineno for symbol: {node.name}")
        chunk = CodeChunk(
            file_path=self.file_path,
            start_line=start_line,
            end_line=end_line,
            content="".join(self.file_content[start_line - 1 : end_line]),
            symbol_type=type(node).__name__.removesuffix("Def"),
            symbol_name=node.name,
            parent_symbol=parent_symbol,
            qualified_name=qualified_name,
        )
        return chunk

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self.generate_chunk(node=node))

        self.qualified_symbol.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self.generate_chunk(node=node))

        self.qualified_symbol.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self.generate_chunk(node=node))

        self.qualified_symbol.pop()


if __name__ == "__main__":
    source = """class UserService:
    @hello()
    @world("123")
    @router.get("/users")
    def get_user(self):
        async def inner():
            print("get a user")

    @router.deactive("/users")
    def deactive_user(self):
        async def inner():
            print("deactive a user")"""
    tree = ast.parse(source=source, filename="unkown")
    parsed_file = ParsedFile(file_path=Path("unkown"), source=source, tree=tree)
    if type(parsed_file) is ParsedFile:
        chunk_generator = ChunkGenerator(parsed_file=parsed_file)
        chunk_generator.visit(parsed_file.tree)
        chunk_generator.sort_chunks()
        for chunk in chunk_generator.chunks:
            print(repr(chunk))
    else:
        print("parse python file error")
