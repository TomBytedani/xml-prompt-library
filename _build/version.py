#!/usr/bin/env python3
"""Version control operations for the Prompt Library Maintainer.

Provides: auto-commit, section history, rollback, and stable tagging.

Usage:
    python3 version.py history <section-name>
    python3 version.py rollback <section-name> <hash> [--confirm]
    python3 version.py rollback <section-name> --to-stable [--confirm]
    python3 version.py tag <recipe-name> [label]
    python3 version.py tags
    python3 version.py diff <section-name> [hash]
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_config, resolve_root, resolve_sections_dir, resolve_recipes_dir
from build import build_all, find_recipes_using_section
import git_ops


def _root() -> Path:
    return resolve_root()


def _ensure_git() -> Path:
    """Ensure we're in a git repo, return root path."""
    root = _root()
    if not git_ops.is_git_repo(root):
        print("Error: not a git repository. Run 'git init' first.", file=sys.stderr)
        sys.exit(1)
    return root


# ---------------------------------------------------------------------------
# Auto-commit
# ---------------------------------------------------------------------------

def auto_commit_if_changed(config: dict | None = None) -> str | None:
    """Stage _sections/ and _recipes/ changes and commit if anything changed.

    Returns the commit hash if a commit was made, None otherwise.
    """
    root = _root()
    if not git_ops.is_git_repo(root):
        return None

    if config is None:
        config = load_config()

    tracked_paths = [config["sections_dir"], config["recipes_dir"]]

    if not git_ops.has_changes(root, tracked_paths):
        return None

    git_ops.stage_files(root, tracked_paths)

    # Build a descriptive commit message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_hash = git_ops.commit(root, f"Auto-commit: sections/recipes updated ({timestamp})")
    print(f"  [versioned] Committed changes ({commit_hash})")
    return commit_hash


# ---------------------------------------------------------------------------
# Section history
# ---------------------------------------------------------------------------

def section_history(section_name: str, config: dict | None = None, max_entries: int = 10) -> list[dict]:
    """Get version history for a section file.

    Searches across all group directories for the section.
    """
    root = _ensure_git()
    if config is None:
        config = load_config()

    section_path = _find_section_path(section_name, config)
    if not section_path:
        print(f"Error: section '{section_name}' not found.", file=sys.stderr)
        return []

    rel_path = str(section_path.relative_to(root))
    return git_ops.file_log(root, rel_path, max_entries)


def _find_section_path(section_name: str, config: dict) -> Path | None:
    """Find a section file by name across all group directories."""
    sections_dir = resolve_sections_dir(config)
    if not sections_dir.is_dir():
        return None

    # Search all group directories
    for group_dir in sorted(sections_dir.iterdir()):
        if group_dir.is_dir():
            candidate = group_dir / f"{section_name}.md"
            if candidate.is_file():
                return candidate
    return None


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def rollback_section(
    section_name: str,
    target_hash: str,
    config: dict | None = None,
    confirm: bool = False,
) -> bool:
    """Rollback a section to a specific commit, rebuild affected recipes, and auto-commit.

    Returns True if rollback was performed.
    """
    root = _ensure_git()
    if config is None:
        config = load_config()

    section_path = _find_section_path(section_name, config)
    if not section_path:
        print(f"Error: section '{section_name}' not found.", file=sys.stderr)
        return False

    rel_path = str(section_path.relative_to(root))

    # Show what will change
    old_content = git_ops.file_show(root, rel_path, target_hash)
    if old_content is None:
        print(f"Error: section '{section_name}' not found at commit {target_hash}.", file=sys.stderr)
        return False

    current_content = section_path.read_text(encoding="utf-8")
    if current_content == old_content:
        print(f"Section '{section_name}' is already at the target state.")
        return False

    # Impact analysis
    affected_recipes = find_recipes_using_section(section_name, config)
    print(f"\nRolling back '{section_name}' to {target_hash}")
    print(f"Affected recipes: {', '.join(affected_recipes) if affected_recipes else '(none)'}")
    print(f"Current: {len(current_content)} chars → Target: {len(old_content)} chars")

    if not confirm:
        choice = input("\nProceed? [y/N] ").strip().lower()
        if choice != "y":
            print("Aborted.")
            return False

    # Perform rollback
    git_ops.checkout_file(root, rel_path, target_hash)
    print(f"  [restored] {rel_path}")

    # Rebuild affected recipes
    if affected_recipes:
        print("  Rebuilding affected recipes...")
        build_all(config)

    # Auto-commit
    git_ops.stage_files(root, [config["sections_dir"], config["recipes_dir"], "."])
    commit_hash = git_ops.commit(
        root, f"Rollback: {section_name} reverted to {target_hash}"
    )
    print(f"  [versioned] Rollback committed ({commit_hash})")
    return True


def rollback_to_stable(section_name: str, config: dict | None = None, confirm: bool = False) -> bool:
    """Rollback a section to the last stable tag state."""
    if config is None:
        config = load_config()

    # Find which recipes use this section
    affected_recipes = find_recipes_using_section(section_name, config)
    if not affected_recipes:
        print(f"Warning: no recipes reference section '{section_name}'.")

    # Find the most recent stable tag for any affected recipe
    root = _ensure_git()
    latest_tag = None
    for recipe_name in affected_recipes:
        tag = find_last_stable_tag(recipe_name)
        if tag:
            latest_tag = tag
            break

    if not latest_tag:
        print(f"Error: no stable tag found for recipes using '{section_name}'.", file=sys.stderr)
        return False

    # Get the commit hash for this tag
    result = git_ops._run(["rev-list", "-1", latest_tag], cwd=root, check=False)
    if result.returncode != 0:
        print(f"Error: could not resolve tag '{latest_tag}'.", file=sys.stderr)
        return False

    tag_hash = result.stdout.strip()
    print(f"Reverting to stable tag: {latest_tag} ({tag_hash[:7]})")
    return rollback_section(section_name, tag_hash, config, confirm)


# ---------------------------------------------------------------------------
# Tagging
# ---------------------------------------------------------------------------

def tag_stable(recipe_name: str, label: str | None = None) -> str | None:
    """Create a stable tag for a recipe.

    Tag format: stable/{recipe_name}/{label_or_timestamp}
    Returns the tag name if created, None otherwise.
    """
    root = _ensure_git()

    if label is None:
        label = datetime.now().strftime("%Y%m%d-%H%M%S")

    tag_name = f"stable/{recipe_name}/{label}"
    current_hash = git_ops.get_current_hash(root)

    git_ops.create_tag(root, tag_name, f"Stable: {recipe_name} at {current_hash}")
    print(f"  [tagged] {tag_name}")
    return tag_name


def find_last_stable_tag(recipe_name: str) -> str | None:
    """Find the most recent stable tag for a recipe."""
    root = _root()
    if not git_ops.is_git_repo(root):
        return None

    tags = git_ops.list_tags(root, f"stable/{recipe_name}/*")
    return tags[0] if tags else None


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def show_diff(section_name: str, commit_hash: str | None = None, config: dict | None = None) -> str:
    """Show diff for a section, optionally at a specific commit."""
    root = _ensure_git()
    if config is None:
        config = load_config()

    section_path = _find_section_path(section_name, config)
    if not section_path:
        print(f"Error: section '{section_name}' not found.", file=sys.stderr)
        return ""

    rel_path = str(section_path.relative_to(root))
    return git_ops.file_diff(root, rel_path, commit_hash)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Version control for Prompt Library sections and recipes."
    )
    sub = parser.add_subparsers(dest="command")

    # history
    p_hist = sub.add_parser("history", help="Show version history for a section")
    p_hist.add_argument("section", help="Section name")
    p_hist.add_argument("-n", type=int, default=10, help="Max entries")

    # rollback
    p_roll = sub.add_parser("rollback", help="Rollback a section to a previous version")
    p_roll.add_argument("section", help="Section name")
    p_roll.add_argument("hash", nargs="?", help="Target commit hash")
    p_roll.add_argument("--to-stable", action="store_true", help="Rollback to last stable tag")
    p_roll.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")

    # tag
    p_tag = sub.add_parser("tag", help="Tag current state as stable for a recipe")
    p_tag.add_argument("recipe", help="Recipe name")
    p_tag.add_argument("label", nargs="?", help="Optional label (default: timestamp)")

    # tags
    sub.add_parser("tags", help="List all stable tags")

    # diff
    p_diff = sub.add_parser("diff", help="Show diff for a section")
    p_diff.add_argument("section", help="Section name")
    p_diff.add_argument("hash", nargs="?", help="Commit hash (default: working changes)")

    args = parser.parse_args()
    config = load_config()

    if args.command == "history":
        entries = section_history(args.section, config, args.n)
        if entries:
            for e in entries:
                print(f"  {e['short_hash']}  {e['date'][:10]}  {e['message']}")
        else:
            print(f"No history found for '{args.section}'.")

    elif args.command == "rollback":
        if args.to_stable:
            rollback_to_stable(args.section, config, args.confirm)
        elif args.hash:
            rollback_section(args.section, args.hash, config, args.confirm)
        else:
            print("Error: provide a commit hash or --to-stable", file=sys.stderr)
            sys.exit(1)

    elif args.command == "tag":
        tag_stable(args.recipe, args.label)

    elif args.command == "tags":
        root = _ensure_git()
        tags = git_ops.list_tags(root, "stable/*")
        if tags:
            for t in tags:
                print(f"  {t}")
        else:
            print("No stable tags found.")

    elif args.command == "diff":
        diff_output = show_diff(args.section, args.hash, config)
        if diff_output:
            print(diff_output)
        else:
            print(f"No changes found for '{args.section}'.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
