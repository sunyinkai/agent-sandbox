import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from openai.types.responses import ResponseInputParam

from agent_sandbox.integrations.openai_client import get_client
from agent_sandbox.tools.local_workspace import LocalWorkspace


def resolve_project_file(file_path: str, project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    reported_path = PurePosixPath(file_path)

    if reported_path.is_relative_to("/workspace"):
        reported_path = reported_path.relative_to("/workspace")
    elif reported_path.is_absolute():
        raise ValueError(f"File path is outside the project: {file_path}")

    resolved_path = (project_dir / Path(*reported_path.parts)).resolve()
    if not resolved_path.is_relative_to(project_dir):
        raise ValueError(f"File path is outside the project: {file_path}")
    return resolved_path


# coordinate the file path between container and local
def get_context(file_path: str, project_dir: Path) -> str:
    return resolve_project_file(file_path, project_dir).read_text(encoding="utf-8")


SYSTEM_PROMPT = """
Generate a valid git unified diff that can be checked with `git apply --check`.

Rules:
- Output only the git patch.
- Do not include markdown fences.
- Do not explain.
- Do not use "*** Begin Patch" / "*** Update File" / "*** End Patch".
- Use standard unified diff format with `diff --git`, `---`, `+++`, and `@@ -a,b +c,d @@` hunk headers.
- Paths must be relative to the project root.
- Do not modify tests.
- Keep changes minimal.
- Fix the failing pytest errors.
"""


def normalize_patch_text(patch_text: str) -> str:
    if not patch_text.endswith("\n"):
        patch_text += "\n"
    return patch_text


def check_patch(patch_text: str, project_dir: Path) -> tuple[bool, str]:
    result = LocalWorkspace(root=project_dir).git_apply(patch_text, check_only=True)
    return result.returncode == 0, result.stderr


def build_error_messages(parsed_errors: list[dict[str, Any]], project_dir: Path) -> str:
    messages: list[str] = []

    for error in parsed_errors:
        file_path = error["file_path"]
        code_context = get_context(file_path=file_path, project_dir=project_dir)
        error_with_context = {**error, "code_context": code_context}
        messages.append(json.dumps(error_with_context, ensure_ascii=False, indent=2))

    return "\n\n".join(messages)


def build_input_messages(
    error_context: str,
    previous_patch_text: str | None = None,
    previous_error: str | None = None,
) -> ResponseInputParam:
    input_messages: ResponseInputParam = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": error_context},
    ]

    if previous_patch_text is not None and previous_error is not None:
        retry_context = {
            "previous_patch_failed": True,
            "git_apply_check_error": previous_error,
            "instruction": "The previous patch failed git apply --check. Generate a corrected git unified diff. Output only the patch.",
        }
        input_messages.extend(
            [
                {"role": "assistant", "content": previous_patch_text},
                {
                    "role": "user",
                    "content": json.dumps(retry_context, ensure_ascii=False, indent=2),
                },
            ]
        )

    return input_messages


def create_patch(parsed_errors: list[dict[str, Any]], project_dir: Path) -> str | None:
    error_context = build_error_messages(parsed_errors, project_dir)
    client = get_client()
    deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")
    if client is None or not deployment_name:
        raise RuntimeError("OpenAI client or deployment name is not configured")

    previous_patch_text = None
    previous_error = None

    for _ in range(3):
        response = client.responses.parse(
            model=deployment_name,
            input=build_input_messages(
                error_context=error_context,
                previous_patch_text=previous_patch_text,
                previous_error=previous_error,
            ),
        )
        patch_text = normalize_patch_text(response.output_text)
        ok, error = check_patch(patch_text, project_dir)

        if ok:
            print("\nok:True\npatch_text:" + patch_text)
            return patch_text

        previous_patch_text = patch_text
        previous_error = error

    print("\nok:False\npatch_text:" + str(previous_patch_text))
    return None
