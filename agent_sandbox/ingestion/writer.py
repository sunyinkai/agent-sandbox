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
    from .chunk_generator import ChunkGenerator
    from .source_loader import SourceLoader

    root = Path(__file__).parent.parent
    loader = SourceLoader(root=root)
    files = loader.scan_repository()
    parsed_files = [loader.parse_python_file("agent_sandbox", file) for file in files]

    chunks: list[CodeChunk] = []
    errors: list[IngestionError] = []
    for result in parsed_files:
        if isinstance(result, IngestionError):
            errors.append(result)
        else:
            chunks.extend(ChunkGenerator(result).generate())
    writer = Writer(Path(__file__).with_name("code_chunks.jsonl"), "w")
    writer.write(chunks)
    writer = Writer(Path(__file__).with_name("ingestion_error.jsonl"), "w")
    writer.write(errors)
