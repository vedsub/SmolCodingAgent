from pathlib import Path
import os
import stat
import tempfile


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