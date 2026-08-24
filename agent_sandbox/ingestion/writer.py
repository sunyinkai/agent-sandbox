import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from .models import CodeChunk, IngestionError


class Writer:
    def __init__(self, file_name: Path, mode: Literal["w", "a"] = "w") -> None:
        self.file_name = file_name
        self.mode = mode

    def write(self, content: Iterable[IngestionError | CodeChunk]) -> None:
        with open(self.file_name, self.mode, encoding="utf-8") as f:
            for item in content:
                data = asdict(item)
                json.dump(data, f, ensure_ascii=False, default=str)
                f.write("\n")


if __name__ == "__main__":
    chunks = [
        CodeChunk(
            chunk_id="1",
            content_hash="2",
            module_name="3",
            file_path=Path(__file__),
            start_line=1,
            end_line=1,
            line_count=1,
            symbol_type="function",
            symbol_name="hello",
            parent_symbol=None,
            qualified_name="a.b.c",
            content="hello world",
        )
    ]
    errors = [
        IngestionError(
            file_path=Path(__file__),
            msg="test error",
            line_number=12,
            error_type="unkown",
            raw_messages="errors for test",
        )
    ]
    writer = Writer(Path(__file__).with_name("code_chunks.jsonl"), "w")
    writer.write(chunks)
    writer = Writer(Path(__file__).with_name("ingestion_error.jsonl"), "w")
    writer.write(errors)
