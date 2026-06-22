from pathlib import Path
from dataclasses import dataclass
import json
import subprocess
import sys
import tempfile


@dataclass(frozen=True)
class PytestError:
    test_name: str
    error_type: str
    message: str
    file_path: str | None
    line_number: int | None

    def to_log_string(self) -> str:
        return "\n".join(
            [
                f"Test: {self.test_name}",
                f"Error type: {self.error_type}",
                f"Message: {self.message}",
                f"File path: {self.file_path}",
                f"Line number: {self.line_number}",
            ]
        )


def parse_pytest_errors(report: dict) -> list[PytestError]:
    errors: list[PytestError] = []

    for test in report.get("tests", []):
        if test.get("outcome") != "failed":
            continue

        call = test.get("call", {})
        crash = call.get("crash", {})
        message = crash.get("message", "")
        error_type = message.split(":", 1)[0] if message else "UnknownError"

        errors.append(
            PytestError(
                test_name=test.get("nodeid", ""),
                error_type=error_type,
                message=message,
                file_path=crash.get("path"),
                line_number=crash.get("lineno"),
            )
        )

    return errors


def run_pytest(project_dir: Path) -> tuple[bool, str, list[PytestError]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "pytest-report.json"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--tb=short",
                "--json-report",
                f"--json-report-file={report_path}",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        output = "stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr
        passed = result.returncode == 0
        errors = []

        if report_path.exists():
            report = json.loads(report_path.read_text())
            errors = parse_pytest_errors(report)

        return passed, output, errors


if __name__ == "__main__":
    project_dir = Path(__file__).parent / "buggy_project"

    passed, output, errors = run_pytest(project_dir)

    print(f"passed={passed}")
    print("output:")
    print(output)
    print("errors:")
    print(errors)
