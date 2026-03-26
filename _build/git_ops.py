"""Low-level git subprocess wrappers for the Prompt Library Maintainer."""

import subprocess
from pathlib import Path


def _run(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def is_git_repo(cwd: Path) -> bool:
    """Check if cwd is inside a git repository."""
    result = _run(["rev-parse", "--is-inside-work-tree"], cwd=cwd, check=False)
    return result.returncode == 0 and result.stdout.strip() == "true"


def has_changes(cwd: Path, paths: list[str] | None = None) -> bool:
    """Check if there are uncommitted changes (staged or unstaged) in given paths."""
    args = ["status", "--porcelain"]
    if paths:
        args.append("--")
        args.extend(paths)
    result = _run(args, cwd=cwd)
    return bool(result.stdout.strip())


def stage_files(cwd: Path, paths: list[str]) -> None:
    """Stage specific files or directories."""
    _run(["add"] + paths, cwd=cwd)


def commit(cwd: Path, message: str) -> str:
    """Create a commit and return the short hash."""
    _run(["commit", "-m", message], cwd=cwd)
    result = _run(["rev-parse", "--short", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def file_log(cwd: Path, path: str, max_entries: int = 10) -> list[dict]:
    """Get git log for a specific file. Returns list of {hash, short_hash, date, message}."""
    fmt = "%H%n%h%n%aI%n%s"
    result = _run(
        ["log", f"-{max_entries}", f"--format={fmt}", "--follow", "--", path],
        cwd=cwd, check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    lines = result.stdout.strip().split("\n")
    entries = []
    for i in range(0, len(lines), 4):
        if i + 3 < len(lines):
            entries.append({
                "hash": lines[i],
                "short_hash": lines[i + 1],
                "date": lines[i + 2],
                "message": lines[i + 3],
            })
    return entries


def file_diff(cwd: Path, path: str, commit_hash: str | None = None) -> str:
    """Get diff for a file. If commit_hash, show diff at that commit; otherwise show working changes."""
    if commit_hash:
        result = _run(["diff", f"{commit_hash}~1", commit_hash, "--", path], cwd=cwd, check=False)
    else:
        result = _run(["diff", "HEAD", "--", path], cwd=cwd, check=False)
    return result.stdout


def file_show(cwd: Path, path: str, commit_hash: str) -> str | None:
    """Show file content at a specific commit."""
    result = _run(["show", f"{commit_hash}:{path}"], cwd=cwd, check=False)
    if result.returncode != 0:
        return None
    return result.stdout


def checkout_file(cwd: Path, path: str, commit_hash: str) -> None:
    """Restore a file to its state at a specific commit."""
    _run(["checkout", commit_hash, "--", path], cwd=cwd)


def create_tag(cwd: Path, tag_name: str, message: str | None = None) -> None:
    """Create a git tag."""
    if message:
        _run(["tag", "-a", tag_name, "-m", message], cwd=cwd)
    else:
        _run(["tag", tag_name], cwd=cwd)


def list_tags(cwd: Path, pattern: str | None = None) -> list[str]:
    """List git tags, optionally filtered by pattern."""
    args = ["tag", "-l"]
    if pattern:
        args.append(pattern)
    args.append("--sort=-creatordate")
    result = _run(args, cwd=cwd, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return result.stdout.strip().split("\n")


def diff_stat(cwd: Path, from_ref: str, to_ref: str = "HEAD") -> str:
    """Get diff stat between two refs."""
    result = _run(["diff", "--stat", from_ref, to_ref], cwd=cwd, check=False)
    return result.stdout


def get_current_hash(cwd: Path) -> str:
    """Get the current HEAD short hash."""
    result = _run(["rev-parse", "--short", "HEAD"], cwd=cwd)
    return result.stdout.strip()
