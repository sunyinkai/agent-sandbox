from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    # input related
    project_dir: Path = Field(description="project path")
    commands: list[str] = Field(description="commands list", min_length=1)

    # output related
    report_dir: Path | None = None

    # resource limitation
    timeout_seconds: float = Field(default=5, description="execution time limit", gt=0)
    memory_limit_mb: int = Field(
        default=256, description="execution memory limit", gt=0
    )
    pids_limit: int = Field(default=64, description="pid limit", gt=0)
    network_enabled: bool = Field(default=False, description="network enable")
    read_only_workspace: bool = Field(
        default=True, description="only allow read commands"
    )


class ErrorCategory(Enum):
    NONE = "none"

    TIMEOUT = "timeout"
    OUT_OF_MEMORY = "out_of_memory"
    INFRASTRUCTURE_ERROR = "infrastructure_error"

    SYNTAX_ERROR = "syntax_error"
    RUNTIME_ERROR = "runtime_error"
    ASSERTION_FAILURE = "assertion_failure"

    UNKNOWN = "unknown"


class ExecutionResult(BaseModel):
    # system output
    # 0: process completed successfully; non-zero: process ran but failed;
    # None: no process exit code exists because execution never started.
    exit_code: int | None = None
    error_category: ErrorCategory
    infra_err: str | None = None
    duration_seconds: float
    container_id: str | None = None
    # compiler/interpreter output
    stdout: str | None = None
    stderr: str | None = None
