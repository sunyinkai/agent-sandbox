import json

import pytest

from agent_sandbox.repair.patch_generator import build_error_messages


def test_build_error_messages_resolves_workspace_path(tmp_path):
    source_file = tmp_path / "app" / "cart.py"
    source_file.parent.mkdir()
    source_file.write_text("def total():\n    return 0\n", encoding="utf-8")

    message = build_error_messages(
        [{"file_path": "/workspace/app/cart.py", "error_type": "TypeError"}],
        tmp_path,
    )

    payload = json.loads(message)
    assert payload["file_path"] == "/workspace/app/cart.py"
    assert payload["code_context"] == "def total():\n    return 0\n"


def test_build_error_messages_rejects_path_outside_project(tmp_path):
    with pytest.raises(ValueError, match="outside the project"):
        build_error_messages(
            [{"file_path": "../secret.py", "error_type": "TypeError"}],
            tmp_path,
        )
