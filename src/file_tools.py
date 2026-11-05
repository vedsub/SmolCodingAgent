from pathlib import Path


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