from pathlib import Path


def resolve_active_log_files(active_log_path: str | Path) -> tuple[Path | None, list[Path]]:
    """Resolve active log files without recursing into legacy archives.

    Rules:
    - If a concrete file is passed, use only that file.
    - If a directory is passed and it contains `active_times_*.jsonl`, use those files.
    - Otherwise, if the directory contains `new_server/active_times_*.jsonl`, use that folder.
    - Never recurse into nested subdirectories such as `legacy/`.
    """
    path = Path(active_log_path)
    if not path.exists():
        return None, []

    if path.is_file():
        return path.parent, [path]

    direct_files = sorted(path.glob("active_times_*.jsonl"))
    if direct_files:
        return path, direct_files

    new_server_dir = path / "new_server"
    if new_server_dir.exists() and new_server_dir.is_dir():
        new_server_files = sorted(new_server_dir.glob("active_times_*.jsonl"))
        if new_server_files:
            return new_server_dir, new_server_files

    return path, []
