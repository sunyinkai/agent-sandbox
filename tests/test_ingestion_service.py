import json
from pathlib import Path

from agent_sandbox.ingestion.service import IngestionService


def write_source(root: Path, relative_path: str, source: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_ingest_generates_chunks_from_python_files(tmp_path):
    write_source(
        tmp_path,
        "src/service.py",
        "class Service:\n"
        "    def run(self):\n"
        "        return True\n\n"
        "async def create_service():\n"
        "    return Service()\n",
    )

    chunks, errors = IngestionService(tmp_path, "test-repo").ingest()

    assert errors == []
    assert [chunk.qualified_name for chunk in chunks] == [
        "Service",
        "Service.run",
        "create_service",
    ]
    assert all(chunk.file_path == Path("src/service.py") for chunk in chunks)
    assert all(len(chunk.chunk_id) == 64 for chunk in chunks)


def test_ingest_keeps_valid_chunks_when_another_file_has_syntax_error(tmp_path):
    write_source(tmp_path, "src/valid.py", "def valid():\n    return 1\n")
    write_source(tmp_path, "src/broken.py", "def broken(:\n    pass\n")

    chunks, errors = IngestionService(tmp_path, "test-repo").ingest()

    assert [chunk.qualified_name for chunk in chunks] == ["valid"]
    assert len(errors) == 1
    assert errors[0].file_path == Path("src/broken.py")
    assert errors[0].error_type == "SyntaxError"


def test_ingest_empty_repository_returns_empty_results(tmp_path):
    chunks, errors = IngestionService(tmp_path, "test-repo").ingest()

    assert chunks == []
    assert errors == []


def test_ingest_excludes_virtual_environment_files(tmp_path):
    write_source(tmp_path, ".venv/lib/ignored.py", "def ignored():\n    pass\n")
    write_source(tmp_path, "src/included.py", "def included():\n    pass\n")

    chunks, errors = IngestionService(tmp_path, "test-repo").ingest()

    assert errors == []
    assert [chunk.qualified_name for chunk in chunks] == ["included"]
    assert [chunk.file_path for chunk in chunks] == [Path("src/included.py")]


def test_write_ingestion_result_creates_both_jsonl_files(tmp_path):
    repository = tmp_path / "repository"
    write_source(repository, "valid.py", 'def valid():\n    return "你好"\n')
    write_source(repository, "broken.py", "def broken(:\n    pass\n")
    service = IngestionService(repository, "test-repo")
    chunks, errors = service.ingest()
    output_dir = tmp_path / "artifacts" / "ingestion"

    service.write_ingestion_result(output_dir, chunks, errors)

    chunk_records = read_jsonl(output_dir / "ingestion_chunks.jsonl")
    error_records = read_jsonl(output_dir / "ingestion_errors.jsonl")
    assert len(chunk_records) == 1
    assert chunk_records[0]["qualified_name"] == "valid"
    assert chunk_records[0]["file_path"] == "valid.py"
    assert "你好" in chunk_records[0]["content"]
    assert len(error_records) == 1
    assert error_records[0]["file_path"] == "broken.py"
    assert error_records[0]["error_type"] == "SyntaxError"
