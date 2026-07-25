from .models import ExecutionRequest, ExecutionResult


class SecuritySandboxBackend:
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise NotImplementedError
