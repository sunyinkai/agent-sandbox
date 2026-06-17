from pathlib import Path
import subprocess


def run_pytest(project_dir: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["pytest"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    output = result.stdout + "\n" + result.stderr
    passed = result.returncode == 0
    return passed, output


if __name__ == "__main__":
    project_dir = Path(__file__).parent / "buggy_project"

    passed, output = run_pytest(project_dir)

    print(f"passed={passed}")
    print("output:")
    print(output)
