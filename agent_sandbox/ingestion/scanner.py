from pathlib import Path


class Scanner:
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


if __name__ == "__main__":
    print(*Scanner(Path("./")).scan_repository(), sep="\n")
