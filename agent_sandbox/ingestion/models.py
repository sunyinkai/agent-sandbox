from ast import Module
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedFile:
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
    file_path: Path
    start_line: int
    end_line: int
    content: str
    symbol_type: str  # eg. function
    symbol_name: str  # eg. c
    parent_symbol: str | None  # b
    qualified_name: str  # eg. a.b.c
