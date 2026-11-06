from pathlib import Path
import os
import stat
import tempfile

import re
import signal
import subprocess
import sys

def resolve_workspace_file(workspace, requested_path):

    # Resolve the trusted workspace
    workspace = Path(workspace).resolve(strict=True)

    if not workspace.is_dir():
        raise NotADirectoryError("Workspace must be a directory")

    # Convert requested path into Path object
    requested_path = Path(requested_path)

    # Reject absolute paths
    if requested_path.is_absolute():
        raise ValueError("Absolute paths are not allowed")

    # Resolve requested path and symlinks
    resolved_path = (workspace / requested_path).resolve(strict=True)

    # Ensure resolved path is inside workspace
    if not resolved_path.is_relative_to(workspace):
        raise ValueError("Access outside workspace is not allowed")

    # Ensure it is a regular file
    if not resolved_path.is_file():
        raise ValueError("Requested path must be a regular file")

    return resolved_path


def read_file(workspace, requested_path):

    safe_path = resolve_workspace_file(workspace, requested_path)

    return safe_path.read_text(encoding="utf-8")

def apply_patch(workspace, requested_path, old_text, new_text):
    """
    Replace exactly one occurrence of old_text with new_text.

    The original file is preserved if the precondition fails
    or if writing the temporary file fails.

    Returns:
        str: Success message.

    Raises:
        ValueError: If the old text is missing or ambiguous.
    """

    # 1. Resolve and validate the target using Stage 1
    target_path = resolve_workspace_file(workspace, requested_path)

    # 2. Read the current file content
    original_content = target_path.read_text(encoding="utf-8")

    # 3. Check the patch precondition
    occurrences = original_content.count(old_text)

    if occurrences != 1:
        raise ValueError(
            f"Patch rejected: expected exactly 1 occurrence, "
            f"found {occurrences}"
        )

    # 4. Prepare replacement content in memory
    new_content = original_content.replace(old_text, new_text, 1)

    # 5. Preserve original permission bits
    original_mode = stat.S_IMODE(target_path.stat().st_mode)

    # 6. Create a temporary file in the same directory
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target_path.parent,
            prefix=".patch_",
            suffix=".tmp",
            delete=False
        ) as temp_file:

            temp_path = Path(temp_file.name)

            # 7. Write complete replacement content
            temp_file.write(new_content)

            # Flush buffered data and request it be written to disk
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # 8. Restore original permissions
        os.chmod(temp_path, original_mode)

        # 9. Atomically replace original file
        os.replace(temp_path, target_path)

        return "Patch applied successfully"

    finally:
        # 10. Remove temporary file if it still exists
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def run_tests(workspace, timeout=30):
    """
    Run unittest discovery using a fixed command.

    The model cannot supply executable commands or arguments.

    Returns:
        dict: Test execution details.

    Raises:
        RuntimeError: If tests fail, are skipped, or no tests execute.
        TimeoutError: If the deadline is exceeded.
    """

    workspace = Path(workspace).resolve(strict=True)

    if not workspace.is_dir():
        raise NotADirectoryError("Workspace must be a directory")

    if timeout <= 0:
        raise ValueError("Timeout must be positive")

    # Application-owned command. Never accept commands from the model.
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-v",
    ]

    process = subprocess.Popen(
        command,
        cwd=str(workspace),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=(os.name == "posix"),
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)

    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()

        # Reap the process and collect any remaining output.
        stdout, stderr = process.communicate()

        raise TimeoutError(
            f"Tests exceeded the {timeout}-second deadline"
        )

    # The unittest summary is written to stderr by unittest.
    summary_matches = re.findall(
        r"^Ran\s+(\d+)\s+tests?\s+in\s+[\d.]+s\s*$",
        stderr,
        flags=re.MULTILINE,
    )

    # Require exactly one genuine final unittest summary.
    if len(summary_matches) != 1:
        raise RuntimeError(
            "Could not find exactly one unittest summary in stderr.\n"
            f"stderr:\n{stderr}\n"
            f"stdout:\n{stdout}"
        )

    tests_run = int(summary_matches[0])

    # Reject zero-test executions.
    if tests_run <= 0:
        raise RuntimeError("Test suite executed zero tests")

    # Reject skipped tests.
    skipped = re.search(
        r"\bskipped\s*=\s*(\d+)",
        stderr,
    )

    if skipped and int(skipped.group(1)) > 0:
        raise RuntimeError("Test suite contains skipped tests")

    # Reject failures, errors and unsuccessful exit codes.
    if process.returncode != 0:
        return {
            "success": False,
            "tests_run": tests_run,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode,
            "error": f"Tests failed with exit code {process.returncode}",
        }
    if not re.search(r"^OK\s*$", stderr, flags=re.MULTILINE):
        return {
            "success": False,
            "tests_run": tests_run,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode,
            "error": "Unittest did not report a successful result",
        }

    return {
        "success": True,
        "tests_run": tests_run,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": process.returncode,
    }
