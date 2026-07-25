import time
from pathlib import Path

import docker
from docker.errors import DockerException

from .models import ErrorCategory, ExecutionRequest, ExecutionResult


class DockerSandbox:
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        start_clock = time.perf_counter()
        container = None
        try:
            client = docker.from_env()
            container = client.containers.run(
                "python:3.12-slim",
                command=request.commands,
                detach=True,
            )
            result = container.wait()
            container.reload()
            container_id = container.attrs["Id"]

            error_category = ErrorCategory.NONE
            if container.attrs["State"]["OOMKilled"]:
                return ExecutionResult(
                    exit_code=result["StatusCode"],
                    error_category=ErrorCategory.OUT_OF_MEMORY,
                    container_id=container_id,
                    duration_seconds=time.perf_counter() - start_clock,
                )

            exit_code = result["StatusCode"]
            stdout = container.logs(stdout=True, stderr=False).decode()
            stderr = container.logs(stdout=False, stderr=True).decode()

            return ExecutionResult(
                exit_code=exit_code,
                error_category=error_category,
                duration_seconds=time.perf_counter() - start_clock,
                container_id=container_id,
                stdout=stdout,
                stderr=stderr,
            )
        except DockerException as e:
            return ExecutionResult(
                exit_code=None,
                error_category=ErrorCategory.INFRASTRUCTURE_ERROR,
                duration_seconds=time.perf_counter() - start_clock,
                infra_err=str(e),
            )
        finally:
            if container is not None:
                container.remove(force=True)


if __name__ == "__main__":
    req = ExecutionRequest(
        project_dir=Path("."),
        commands=["python", "-c", "raise RuntimeError('boom')"],
    )
    result = DockerSandbox().execute(req)
    print(result)
