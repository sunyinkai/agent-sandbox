import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from agent_sandbox.sandbox.backend_protocol import ExecutionBackend
from agent_sandbox.sandbox.docker_backend import DockerSandbox
from agent_sandbox.sandbox.models import ExecutionRequest


@dataclass(frozen=True)
class PytestError:
    test_name: str
    error_type: str
    message: str
    file_path: str | None
    line_number: int | None
    failure_details: str

    def to_log_string(self) -> str:
        return "\n".join(
            [
                f"Test: {self.test_name}",
                f"Error type: {self.error_type}",
                f"Message: {self.message}",
                f"File path: {self.file_path}",
                f"Line number: {self.line_number}",
                f"Failure details:\n{self.failure_details}",
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
                failure_details=str(call.get("longrepr", "")),
            )
        )

    return errors


def run_pytest(
    project_dir: Path, backend: ExecutionBackend | None = None
) -> tuple[bool, str, list[PytestError]]:
    if backend is None:
        backend = DockerSandbox()
    with tempfile.TemporaryDirectory(prefix="agent-sandbox-reports-") as tmpdir:
        report_dir = Path(tmpdir)
        report_path = report_dir / "pytest-report.json"
        os.chmod(report_dir, 0o777)

        commands = [
            "python",
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--json-report",
            "--json-report-file=/reports/pytest-report.json",
        ]
        request = ExecutionRequest(
            project_dir=project_dir, commands=commands, report_dir=report_dir
        )
        execution = backend.execute(request=request)

        passed = execution.exit_code == 0
        output = f"stdout:\n{execution.stdout or ''}\nstderr:\n{execution.stderr or ''}"

        errors = []
        if report_path.exists():
            report = json.loads(report_path.read_text())
            errors = parse_pytest_errors(report)
        return passed, output, errors
