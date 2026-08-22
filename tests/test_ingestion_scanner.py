from pathlib import Path

import pytest

from agent_sandbox.ingestion.source_loader import SourceLoader


def create_file(root: Path, relative_path: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_scan_repository_returns_sorted_relative_python_paths(tmp_path):
    create_file(tmp_path, "tests/test_user.py")
    create_file(tmp_path, "src/user/service.py")
    create_file(tmp_path, "main.py")
    create_file(tmp_path, "src/auth/service.py")
    create_file(tmp_path, "README.md")
    create_file(tmp_path, "src/config.json")
    create_file(tmp_path, "src/module.pyc")

    paths = SourceLoader(tmp_path).scan_repository()

    assert paths == [
        Path("main.py"),
        Path("src/auth/service.py"),
        Path("src/user/service.py"),
        Path("tests/test_user.py"),
    ]
    assert all(not path.is_absolute() for path in paths)


@pytest.mark.parametrize(
    "excluded_directory",
    [
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "build",
        "dist",
        "site-packages",
    ],
)
def test_scan_repository_excludes_ignored_directories(tmp_path, excluded_directory):
    create_file(tmp_path, f"{excluded_directory}/ignored.py")
    create_file(tmp_path, "src/included.py")

    paths = SourceLoader(tmp_path).scan_repository()

    assert paths == [Path("src/included.py")]


def test_scan_repository_returns_empty_list_for_empty_directory(tmp_path):
    assert SourceLoader(tmp_path).scan_repository() == []


def test_scan_repository_returns_empty_list_for_missing_root(tmp_path):
    missing_root = tmp_path / "missing"

    assert SourceLoader(missing_root).scan_repository() == []
