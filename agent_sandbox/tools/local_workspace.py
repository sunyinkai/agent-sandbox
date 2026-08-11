import subprocess
from pathlib import Path


class LocalWorkspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _check_path(self, path: Path) -> bool:
        if path.is_absolute():
            return False

        root = self.root.resolve()
        resolved_path = (root / path).resolve()
        return resolved_path.is_relative_to(root)

    def list_files(self, path: Path = Path(".")) -> list[str]:
        if not self._check_path(path):
            raise ValueError(f"Path is outside the workspace: {path}")

        directory = (self.root / path).resolve()
        if not directory.is_dir():
            raise NotADirectoryError(path)

        return sorted(
            f"{item.name}/" if item.is_dir() else item.name
            for item in directory.iterdir()
        )

    def read_file(self, path: Path) -> str:
        if not self._check_path(path):
            raise ValueError(f"Path is outside the workspace: {path}")
        return (self.root / path).read_text(encoding="utf-8")

    def write_file(self, path: Path, content: str) -> int:
        if not self._check_path(path):
            raise ValueError(f"Path is outside the workspace: {path}")
        target = self.root / path
        if not target.parent.is_dir():
            raise FileNotFoundError(f"Parent directory doesn't exist: {target.parent}")
        return target.write_text(content, encoding="utf-8")

    def get_current_branch(self) -> str:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            text=True,
            capture_output=True,
            check=False,
            cwd=self.root,
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr

    def run_git_apply(
        self, patch_text: str, check_only: bool = False
    ) -> subprocess.CompletedProcess[str]:
        project_dir = self.root
        args = ["git", "apply", "--recount"]
        if check_only:
            args.append("--check")

        # Here the Git root is agent-sandbox/, while this workspace root is
        # agent-sandbox/fixtures/buggy_project/. A patch refers to app/cart.py,
        # but from the Git root that file is fixtures/buggy_project/app/cart.py.
        # Run git apply at the Git root and use --directory=fixtures/buggy_project
        # to map workspace-relative patch paths to their real repository paths.
        repo_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            cwd=project_dir,
            check=False,
        )
        apply_cwd = project_dir

        if repo_result.returncode == 0:
            repo_root = Path(repo_result.stdout.strip()).resolve()
            relative_project_dir = project_dir.relative_to(repo_root)
            apply_cwd = repo_root
            if relative_project_dir != Path("."):
                args.append(f"--directory={relative_project_dir.as_posix()}")

        return subprocess.run(
            args,
            input=patch_text,
            text=True,
            capture_output=True,
            cwd=apply_cwd,
            check=False,
        )


if __name__ == "__main__":
    workspace = LocalWorkspace(Path("./fixtures/buggy_project"))
    print(workspace.list_files(Path("app")))
    print(workspace.read_file(Path("app/cart.py")))
    print(workspace.get_current_branch())
