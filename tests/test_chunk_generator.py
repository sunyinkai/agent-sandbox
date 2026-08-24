import ast
from pathlib import Path

from agent_sandbox.ingestion.chunker import Chunker
from agent_sandbox.ingestion.models import CodeChunk, ParsedFile


def generate_chunks(
    source: str,
    *,
    repo_id: str = "test-repo",
    file_path: Path = Path("src/service.py"),
) -> tuple[CodeChunk, ...]:
    parsed_file = ParsedFile(
        repo_id=repo_id,
        file_path=file_path,
        source=source,
        tree=ast.parse(source, filename=file_path.as_posix()),
    )
    generator = Chunker(parsed_file)
    return generator.generate()


def test_generate_chunks_extracts_symbols_and_nested_metadata():
    source = """class UserService:
    def get_user(self):
        async def fetch():
            return "user"
        return fetch

async def create_service():
    return UserService()
"""

    chunks = generate_chunks(source)

    assert [chunk.symbol_name for chunk in chunks] == [
        "UserService",
        "get_user",
        "fetch",
        "create_service",
    ]
    assert [chunk.symbol_type for chunk in chunks] == [
        "Class",
        "Function",
        "AsyncFunction",
        "AsyncFunction",
    ]
    assert [chunk.qualified_name for chunk in chunks] == [
        "UserService",
        "UserService.get_user",
        "UserService.get_user.fetch",
        "create_service",
    ]
    assert [chunk.parent_symbol for chunk in chunks] == [
        None,
        "UserService",
        "UserService.get_user",
        None,
    ]
    assert all(chunk.file_path == Path("src/service.py") for chunk in chunks)


def test_generate_chunk_includes_all_decorators_and_exact_source():
    source = """@first
@second("value")
def decorated():
    return 1
"""

    [chunk] = generate_chunks(source)

    assert chunk.start_line == 1
    assert chunk.end_line == 4
    assert chunk.content == source


def test_generate_chunk_preserves_missing_final_newline():
    source = "def no_final_newline():\n    return True"

    [chunk] = generate_chunks(source)

    assert chunk.content == source
    assert not chunk.content.endswith("\n")


def test_generate_sorts_chunks_and_does_not_accumulate_results():
    source = """class Container:
    def method(self):
        def nested():
            return None
        return nested
"""
    file_path = Path("src/service.py")
    parsed_file = ParsedFile(
        repo_id="test-repo",
        file_path=file_path,
        source=source,
        tree=ast.parse(source, filename=file_path.as_posix()),
    )
    generator = Chunker(parsed_file)
    first_result = generator.generate()
    second_result = generator.generate()

    assert [chunk.symbol_name for chunk in first_result] == [
        "Container",
        "method",
        "nested",
    ]
    assert second_result == first_result


def test_generate_chunk_adds_hashes_line_count_and_module_name():
    source = "def greet():\n    return 'hello'\n"

    [chunk] = generate_chunks(source)

    assert len(chunk.chunk_id) == 64
    assert len(chunk.content_hash) == 64
    assert chunk.line_count == 2
    assert chunk.module_name == "src.service"


def test_content_change_preserves_chunk_id_and_changes_content_hash():
    [original] = generate_chunks("def greet():\n    return 'hello'\n")
    [changed] = generate_chunks("def greet():\n    return 'goodbye'\n")

    assert changed.chunk_id == original.chunk_id
    assert changed.content_hash != original.content_hash


def test_identity_change_changes_chunk_id():
    source = "def greet():\n    return 'hello'\n"
    [original] = generate_chunks(source)
    [different_repo] = generate_chunks(source, repo_id="other-repo")
    [different_file] = generate_chunks(
        source,
        file_path=Path("src/other_service.py"),
    )

    assert different_repo.chunk_id != original.chunk_id
    assert different_file.chunk_id != original.chunk_id
