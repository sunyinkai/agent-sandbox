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


def create_patch(
    parsed_errors: list[dict[str, Any]], project_dir: Path
) -> Optional[str]:
    messages: list[str] = []
    for error in parsed_errors:
        file_path = error["file_path"]
        code_context = get_context(file_path=file_path)
        error_with_context = {**error, "code_context": code_context}
        messages.append(json.dumps(error_with_context, ensure_ascii=False, indent=2))
    client = get_client()
    response = client.responses.parse(
        model=os.getenv("AZURE_DEPLOYMENT_NAME"),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(messages)},
        ],
    )
    patch_text = normalize_patch_text(response.output_text)
    ok, error = check_patch(patch_text, cwd=str(project_dir))
    print("\nok:" + str(ok) + "\nerror:" + error)
    print(patch_text)

    return patch_text if ok else None
