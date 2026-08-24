from pathlib import Path

from .chunker import Chunker
from .models import CodeChunk, IngestionError, ParsedFile
from .source_loader import SourceLoader
from .writer import Writer


class IngestionService:
    def __init__(self, root: Path, repo_id: str) -> None:
        self.root = root
        self.repo_id = repo_id

    def ingest(self) -> tuple[list[CodeChunk], list[IngestionError]]:
        loader = SourceLoader(root=self.root)
        files = loader.scan_repository()
        ingestion_errors = []
        chunks: list[CodeChunk] = []
        for file in files:
            parsed = loader.parse_python_file(repo_id=self.repo_id, file=file)
            if isinstance(parsed, ParsedFile):
                chunks.extend(Chunker(parsed_file=parsed).generate())
            else:
                ingestion_errors.append(parsed)
        return chunks, ingestion_errors

    def write_ingestion_result(
        self, output_dir: Path, chunks: list[CodeChunk], errors: list[IngestionError]
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = output_dir / Path("ingestion_chunks.jsonl")
        erros_path = output_dir / Path("ingestion_errors.jsonl")

        writer = Writer(chunks_path, "w")
        writer.write(chunks)

        writer = Writer(erros_path, "w")
        writer.write(errors)


if __name__ == "__main__":
    root = Path(__file__).parent
    repo_id = Path(__file__).parent.parts[-1]
    service = IngestionService(root=root, repo_id=repo_id)
    chunks, errors = service.ingest()
    service.write_ingestion_result(output_dir=root, chunks=chunks, errors=errors)
