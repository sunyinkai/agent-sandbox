import time
from pathlib import Path
from textwrap import dedent

import docker
from docker.errors import DockerException
from requests.exceptions import ConnectionError as RequestsConnectionError

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
                mem_limit=f"{request.memory_limit_mb}m",
                memswap_limit=f"{request.memory_limit_mb}m",
                pids_limit=request.pids_limit,
                network_disabled=not request.network_enabled,
                read_only=True,
                user="65534:65534",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                volumes={
                    str(request.project_dir.resolve()): {
                        "bind": "/workspace",
                        "mode": "ro" if request.read_only_workspace else "rw",
                    }
                },
                working_dir="/workspace",
                environment={
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUNBUFFERED": "1",
                },
            )
            container_id = container.attrs["Id"]

            try:
                result = container.wait(timeout=request.timeout_seconds)
            except RequestsConnectionError:
                container.kill()
                return ExecutionResult(
                    exit_code=None,
                    error_category=ErrorCategory.TIMEOUT,
                    duration_seconds=time.perf_counter() - start_clock,
                    container_id=container_id,
                )

            container.reload()
            error_category = ErrorCategory.NONE
            if container.attrs["State"]["OOMKilled"]:
                return ExecutionResult(
                    exit_code=result["StatusCode"],
                    error_category=ErrorCategory.OUT_OF_MEMORY,
                    duration_seconds=time.perf_counter() - start_clock,
                    container_id=container_id,
                    stdout=container.logs(stdout=True, stderr=False).decode(),
                    stderr=container.logs(stdout=False, stderr=True).decode(),
                )

            return ExecutionResult(
                exit_code=result["StatusCode"],
                error_category=error_category,
                duration_seconds=time.perf_counter() - start_clock,
                container_id=container_id,
                stdout=container.logs(stdout=True, stderr=False).decode(),
                stderr=container.logs(stdout=False, stderr=True).decode(),
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
    code_block = dedent(
        """
        import time
        time.sleep(60)
    """
    ).strip()
    req = ExecutionRequest(
        project_dir=Path("."),
        commands=[
            "python",
            "-c",
            code_block,
        ],
    )
    result = DockerSandbox().execute(req)
    print(result)
