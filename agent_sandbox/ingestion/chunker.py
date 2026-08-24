import ast
from hashlib import sha256
from pathlib import Path

from .models import CodeChunk, ParsedFile


class Chunker(ast.NodeVisitor):
    def __init__(self, parsed_file: ParsedFile) -> None:
        self.repo_id = parsed_file.repo_id
        self.qualified_symbol = list[str]()
        self.chunks = list[CodeChunk]()
        self.file_path = parsed_file.file_path
        self.file_content = parsed_file.source.splitlines(keepends=True)
        self.tree = parsed_file.tree
        super().__init__()

    def _generate_chunk(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> CodeChunk:
        parent_symbol = ".".join(self.qualified_symbol[:-1]) or None
        qualified_name = ".".join(self.qualified_symbol)

        # get the decorators
        start_line = node.lineno
        for decorator in node.decorator_list:
            start_line = min(start_line, decorator.lineno)

        end_line = node.end_lineno
        if end_line is None:
            raise ValueError(f"Missing end_lineno for symbol: {node.name}")

        content = "".join(self.file_content[start_line - 1 : end_line])
        content_hash = sha256(content.encode("utf-8")).hexdigest()

        symbol_type = type(node).__name__.removesuffix("Def")
        identity = (
            f"{self.repo_id}_{self.file_path.as_posix()}_{symbol_type}_{qualified_name}"
        )
        chunk_id = sha256(identity.encode("utf-8")).hexdigest()
        chunk = CodeChunk(
            chunk_id=chunk_id,
            content_hash=content_hash,
            file_path=self.file_path,
            module_name=self.file_path.with_suffix("").as_posix().replace("/", "."),
            start_line=start_line,
            end_line=end_line,
            line_count=end_line - start_line + 1,
            content=content,
            symbol_type=symbol_type,
            symbol_name=node.name,
            parent_symbol=parent_symbol,
            qualified_name=qualified_name,
        )
        return chunk

    def generate(self) -> tuple[CodeChunk, ...]:
        self.chunks.clear()
        self.qualified_symbol.clear()
        self.visit(self.tree)
        self.chunks.sort(key=lambda chunk: chunk.start_line)
        return tuple(self.chunks)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self._generate_chunk(node=node))

        self.qualified_symbol.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self._generate_chunk(node=node))

        self.qualified_symbol.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.qualified_symbol.append(node.name)

        self.generic_visit(node)
        self.chunks.append(self._generate_chunk(node=node))

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
    parsed_file = ParsedFile(
        file_path=Path("unkown"), source=source, tree=tree, repo_id="test"
    )
    if type(parsed_file) is ParsedFile:
        chunk_generator = Chunker(parsed_file=parsed_file)
        chunks = chunk_generator.generate()
        for chunk in chunks:
            print(repr(chunk))
    else:
        print("parse python file error")
