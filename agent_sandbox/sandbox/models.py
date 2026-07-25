from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum


class ExecutionRequest(BaseModel):
    project_dir: Path = Field(description="project path", min_length=1)
    commands: list[str] = Field(description="commands list", min_length=1)

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
    RUNTIME_ERROR = "runtime_error"
    SYNTAX_ERROR = "syntax_error"
    ASSERTION_FAILURE = "assertion_failure"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    UNKNOWN = "unknown"


class ExecutionResult(BaseModel):
    exit_code: int
    error_category: ErrorCategory
    # compiler output
    stdout: str
    stderr: str
    # system output
    infra_err: str | None
    duration_ms: int
    container_id: str | None
