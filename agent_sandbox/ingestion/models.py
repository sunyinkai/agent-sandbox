from ast import Module
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedFile:
    repo_id: str
    file_path: Path
    source: str
    tree: Module


@dataclass(frozen=True)
class IngestionError:
    file_path: Path
    msg: str
    line_number: int | None
    error_type: str
    raw_messages: str


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    content_hash: str
    module_name: str
    file_path: Path
    start_line: int
    end_line: int
    line_count: int
    symbol_type: str  # eg. function
    symbol_name: str  # eg. c
    parent_symbol: str | None  # b
    qualified_name: str  # eg. a.b.c
    content: str
