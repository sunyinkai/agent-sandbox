import ast
import tokenize
from pathlib import Path

from .models import IngestionError, ParsedFile


class SourceLoader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.folder_exclusion_set = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            "build",
            "dist",
            "site-packages",
        }

    def scan_repository(self) -> list[Path]:
        return sorted(
            [
                path.relative_to(self.root)
                for path in self.root.rglob("*.py")
                if path.is_file()
                and set(path.relative_to(self.root).parts).isdisjoint(
                    self.folder_exclusion_set
                )
            ]
        )

    def parse_python_file(self, file: Path) -> ParsedFile | IngestionError:
        root_resolved = self.root.resolve()
        path_resolved = (self.root / file).resolve()
        if not path_resolved.is_relative_to(root_resolved):
            raise ValueError(f"Invalid path {file}, absolution path {path_resolved}")
        try:
            with tokenize.open(path_resolved) as source_file:
                source = source_file.read()
                tree = ast.parse(source=source, filename=file)
                return ParsedFile(file_path=file, source=source, tree=tree)
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            error_type = type(error).__name__
            message = error.msg if isinstance(error, SyntaxError) else str(error)
            line_number = getattr(error, "lineno", None)
            return IngestionError(
                file_path=file,
                msg=message,
                line_number=line_number,
                error_type=error_type,
                raw_messages=str(error),
            )

if __name__ == "__main__":
    print(*SourceLoader(Path("./")).scan_repository(), sep="\n")
