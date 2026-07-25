from typing import Protocol

from .models import ExecutionRequest, ExecutionResult


class ExecutionBackend(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
