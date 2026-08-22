import ast
from pathlib import Path

import pytest

from agent_sandbox.ingestion.models import IngestionError, ParsedFile
from agent_sandbox.ingestion.source_loader import SourceLoader


def write_source(root: Path, relative_path: str, source: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_parse_python_file_returns_parsed_file(tmp_path):
    source = "def greet():\n    return 'hello'\n"
    write_source(tmp_path, "src/greet.py", source)

    result = SourceLoader(tmp_path).parse_python_file(Path("src/greet.py"))

    assert isinstance(result, ParsedFile)
    assert result.file_path == Path("src/greet.py")
    assert result.source == source
    assert isinstance(result.tree, ast.Module)
    assert len(result.tree.body) == 1


def test_parse_python_file_accepts_empty_file(tmp_path):
    write_source(tmp_path, "empty.py", "")

    result = SourceLoader(tmp_path).parse_python_file(Path("empty.py"))

    assert isinstance(result, ParsedFile)
    assert result.source == ""
    assert result.tree.body == []


def test_parse_python_file_preserves_utf8_source(tmp_path):
    source = '# 中文注释\nmessage = "你好"\n'
    write_source(tmp_path, "chinese.py", source)

    result = SourceLoader(tmp_path).parse_python_file(Path("chinese.py"))

    assert isinstance(result, ParsedFile)
    assert result.source == source


def test_parse_python_file_honors_encoding_declaration(tmp_path):
    source = '# -*- coding: latin-1 -*-\nname = "café"\n'
    path = tmp_path / "latin1.py"
    path.write_bytes(source.encode("latin-1"))

    result = SourceLoader(tmp_path).parse_python_file(Path("latin1.py"))

    assert isinstance(result, ParsedFile)
    assert result.source == source
    assert isinstance(result.tree, ast.Module)


def test_parse_python_file_returns_syntax_error(tmp_path):
    write_source(tmp_path, "broken.py", "async def broken:\n    pass\n")

    result = SourceLoader(tmp_path).parse_python_file(Path("broken.py"))

    assert isinstance(result, IngestionError)
    assert result.file_path == Path("broken.py")
    assert result.error_type == "SyntaxError"
    assert result.line_number == 1
    assert result.msg
    assert result.raw_messages


def test_parse_python_file_returns_decode_error(tmp_path):
    path = tmp_path / "invalid_encoding.py"
    path.write_bytes(b'# coding: ascii\nname = "\xff"\n')

    result = SourceLoader(tmp_path).parse_python_file(Path("invalid_encoding.py"))

    assert isinstance(result, IngestionError)
    assert result.error_type == "UnicodeDecodeError"
    assert result.line_number is None
    assert result.msg


def test_parse_python_file_returns_error_for_missing_file(tmp_path):
    result = SourceLoader(tmp_path).parse_python_file(Path("missing.py"))

    assert isinstance(result, IngestionError)
    assert result.file_path == Path("missing.py")
    assert result.error_type == "FileNotFoundError"
    assert result.line_number is None
    assert "missing.py" in result.raw_messages


def test_parse_python_file_rejects_path_outside_repository(tmp_path):
    with pytest.raises(ValueError, match="Invalid path"):
        SourceLoader(tmp_path).parse_python_file(Path("../outside.py"))


def test_parse_python_file_failure_does_not_stop_other_files(tmp_path):
    write_source(tmp_path, "first.py", "first = 1\n")
    write_source(tmp_path, "broken.py", "def broken(:\n    pass\n")
    write_source(tmp_path, "second.py", "second = 2\n")
    loader = SourceLoader(tmp_path)

    results = [
        loader.parse_python_file(file_path)
        for file_path in (Path("first.py"), Path("broken.py"), Path("second.py"))
    ]

    assert isinstance(results[0], ParsedFile)
    assert isinstance(results[1], IngestionError)
    assert isinstance(results[2], ParsedFile)
