import json
from pathlib import Path

from agent_sandbox.ingestion.models import CodeChunk, IngestionError
from agent_sandbox.ingestion.writer import Writer


def make_chunk(*, chunk_id: str = "chunk-1") -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        content_hash="content-hash",
        module_name="src.service",
        file_path=Path("src/service.py"),
        start_line=1,
        end_line=2,
        line_count=2,
        symbol_type="Function",
        symbol_name="greet",
        parent_symbol=None,
        qualified_name="greet",
        content='def greet():\n    return "你好"\n',
    )


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_write_outputs_one_json_object_per_line(tmp_path):
    output = tmp_path / "chunks.jsonl"
    chunks = [make_chunk(chunk_id="chunk-1"), make_chunk(chunk_id="chunk-2")]

    Writer(output).write(chunks)

    lines = output.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(lines) == 2
    assert [record["chunk_id"] for record in records] == ["chunk-1", "chunk-2"]
    assert records[0]["file_path"] == "src/service.py"
    assert records[0]["content"].endswith('return "你好"\n')


def test_write_serializes_ingestion_errors(tmp_path):
    output = tmp_path / "ingestion_errors.jsonl"
    errors = [
        IngestionError(
            file_path=Path("src/broken.py"),
            msg="invalid syntax",
            line_number=3,
            error_type="SyntaxError",
            raw_messages="invalid syntax (broken.py, line 3)",
        )
    ]

    Writer(output).write(errors)

    assert read_jsonl(output) == [
        {
            "file_path": "src/broken.py",
            "msg": "invalid syntax",
            "line_number": 3,
            "error_type": "SyntaxError",
            "raw_messages": "invalid syntax (broken.py, line 3)",
        }
    ]


def test_write_empty_iterable_creates_empty_file(tmp_path):
    output = tmp_path / "chunks.jsonl"

    Writer(output).write([])

    assert output.read_text(encoding="utf-8") == ""


def test_write_mode_overwrites_existing_content(tmp_path):
    output = tmp_path / "chunks.jsonl"
    output.write_text("old content\n", encoding="utf-8")

    Writer(output, "w").write([make_chunk()])

    assert read_jsonl(output) == [json.loads(output.read_text(encoding="utf-8"))]
    assert "old content" not in output.read_text(encoding="utf-8")


def test_append_mode_preserves_existing_records(tmp_path):
    output = tmp_path / "chunks.jsonl"
    Writer(output).write([make_chunk(chunk_id="chunk-1")])

    Writer(output, "a").write([make_chunk(chunk_id="chunk-2")])

    assert [record["chunk_id"] for record in read_jsonl(output)] == [
        "chunk-1",
        "chunk-2",
    ]
