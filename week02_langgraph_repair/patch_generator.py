from week01_log_parser.openai_helper import get_client
from typing import Optional, Any
import json
from pathlib import Path
import os
import subprocess


def get_context(file_path: str) -> Optional[str]:
    return Path(file_path).read_text(encoding="utf-8")


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


def check_patch(patch_text: str, cwd: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "apply", "--check"],
        input=patch_text,
        text=True,
        capture_output=True,
        cwd=cwd,
    )
    return result.returncode == 0, result.stderr


def build_error_messages(parsed_errors: list[dict[str, Any]]) -> str:
    messages: list[str] = []

    for error in parsed_errors:
        file_path = error["file_path"]
        code_context = get_context(file_path=file_path)
        error_with_context = {**error, "code_context": code_context}
        messages.append(json.dumps(error_with_context, ensure_ascii=False, indent=2))

    return "\n\n".join(messages)


def build_input_messages(
    error_context: str,
    previous_patch_text: Optional[str] = None,
    previous_error: Optional[str] = None,
) -> list[dict[str, str]]:
    input_messages = [
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


def create_patch(
    parsed_errors: list[dict[str, Any]], project_dir: Path
) -> Optional[str]:
    error_context = build_error_messages(parsed_errors)
    client = get_client()

    previous_patch_text = None
    previous_error = None

    for _ in range(3):
        response = client.responses.parse(
            model=os.getenv("AZURE_DEPLOYMENT_NAME"),
            input=build_input_messages(
                error_context=error_context,
                previous_patch_text=previous_patch_text,
                previous_error=previous_error,
            ),
        )
        patch_text = normalize_patch_text(response.output_text)
        ok, error = check_patch(patch_text, cwd=str(project_dir))

        if ok:
            print("\nok:True\npatch_text:" + patch_text)
            return patch_text

        previous_patch_text = patch_text
        previous_error = error

    print("\nok:False\npatch_text:" + str(previous_patch_text))
    return None
