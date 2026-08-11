import shutil
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

from agent_sandbox.tools.local_workspace import LocalWorkspace

source_project = "./fixtures/buggy_project"
with tempfile.TemporaryDirectory() as tmpdir:
    project_dir = Path(tmpdir) / "buggy_project"
    shutil.copytree(source_project, project_dir)

    print(f"project_dir: {project_dir}")
    subprocess.run(["git", "init"], cwd=project_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)

    workspace = LocalWorkspace(project_dir)
    print("===list_files===")
    print(workspace.list_files())
    print("===read_files===")
    print(workspace.read_file(Path("app/cart.py")))
    print("===run_tests 1===")
    passed, output, errors = workspace.run_tests()
    print(f"passed: {passed}, output: {output}, errors: {errors}")

    patch = dedent(
        """\
        diff --git a/app/cart.py b/app/cart.py
        --- a/app/cart.py
        +++ b/app/cart.py
        @@ -1,5 +1,5 @@
         def calculate_total(items):
             total = 0
             for item in items:
        -        total += item["price"]
        +        total += int(item["price"])
             return total
        diff --git a/app/config.py b/app/config.py
        --- a/app/config.py
        +++ b/app/config.py
        @@ -1,2 +1,2 @@
         def get_timeout(config):
        -    return config["timeout"]
        +    return config.get("timeout", 30)
        diff --git a/app/users.py b/app/users.py
        --- a/app/users.py
        +++ b/app/users.py
        @@ -1,2 +1,4 @@
         def get_user_name(user):
        +    if user is None:
        +        return "UNKNOWN"
             return user.name.upper()
        """
    )

    print("===git apply check===")
    check_result = workspace.git_apply(patch, check_only=True)
    print(check_result)
    if check_result.returncode != 0:
        raise RuntimeError(check_result.stderr)

    print("===git apply===")
    print(workspace.git_apply(patch_text=patch, check_only=False))

    print("===run tests 2===")
    passed, output, errors = workspace.run_tests()
    print(f"passed: {passed}, output: {output}, errors: {errors}")

    print("=== git diff ===")
    print(workspace.git_diff())
