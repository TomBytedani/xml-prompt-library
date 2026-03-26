"""Configuration loading and path resolution for the Prompt Library Maintainer."""

from pathlib import Path

import yaml


def _build_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_root() -> Path:
    """Return the Prompt Library root (parent of _build/)."""
    return _build_dir().parent


def load_config() -> dict:
    """Load config.yaml and return the parsed dict."""
    config_path = _build_dir() / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_sections_dir(config: dict | None = None) -> Path:
    if config is None:
        config = load_config()
    return resolve_root() / config["sections_dir"]


def resolve_recipes_dir(config: dict | None = None) -> Path:
    if config is None:
        config = load_config()
    return resolve_root() / config["recipes_dir"]


def resolve_output_path(relative: str, config: dict | None = None) -> Path:
    """Resolve a recipe's output path, with safety check that it stays within root."""
    if config is None:
        config = load_config()
    root = resolve_root()
    output_base = root / config["output_dir"]
    output_path = (output_base / relative).resolve()
    if not str(output_path).startswith(str(root.resolve())):
        raise ValueError(
            f"Output path '{output_path}' is outside the Prompt Library root '{root}'"
        )
    return output_path


def resolve_section(name: str, group: str, config: dict | None = None) -> Path:
    """Resolve a section file by name using group-first-then-shared resolution.

    Resolution order:
    1. _sections/{group}/{name}.md
    2. _sections/shared/{name}.md
    3. Error if not found.
    """
    sections_dir = resolve_sections_dir(config)

    # Try group-specific first
    group_path = sections_dir / group / f"{name}.md"
    if group_path.is_file():
        return group_path

    # Try shared
    shared_path = sections_dir / "shared" / f"{name}.md"
    if shared_path.is_file():
        return shared_path

    raise FileNotFoundError(
        f"Section '{name}' not found. Searched:\n"
        f"  1. {group_path}\n"
        f"  2. {shared_path}"
    )
