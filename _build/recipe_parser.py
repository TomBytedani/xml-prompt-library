"""Parse and validate recipe YAML files into structured dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RecipePart:
    kind: str  # "section", "inline", "user_input"
    value: str  # section name, inline text, or tag name
    placeholder: str | None = None  # for user_input
    separator: str | None = None  # override default \n\n


@dataclass
class CodeBlock:
    language: str
    parts: list[RecipePart]


@dataclass
class StructureEntry:
    heading: str | None = None
    level: int | None = None
    code_block: CodeBlock | None = None
    body: str | None = None
    instructions: str | None = None


@dataclass
class Recipe:
    group: str
    output: str
    structure: list[StructureEntry]
    frontmatter: dict | None = None
    source_path: Path = field(default_factory=lambda: Path())


def _parse_part(raw: dict, recipe_path: Path) -> RecipePart:
    """Parse a single part entry from a code_block's parts list."""
    if "section" in raw:
        return RecipePart(
            kind="section",
            value=raw["section"],
            separator=raw.get("separator"),
        )
    elif "inline" in raw:
        return RecipePart(
            kind="inline",
            value=raw["inline"],
            separator=raw.get("separator"),
        )
    elif "user_input" in raw:
        ui = raw["user_input"]
        if isinstance(ui, dict):
            return RecipePart(
                kind="user_input",
                value=ui["tag"],
                placeholder=ui.get("placeholder"),
                separator=raw.get("separator"),
            )
        else:
            raise ValueError(
                f"In {recipe_path}: user_input must be a dict with at least 'tag' key, "
                f"got {type(ui).__name__}"
            )
    else:
        raise ValueError(
            f"In {recipe_path}: unrecognized part type. "
            f"Expected 'section', 'inline', or 'user_input'. Got keys: {list(raw.keys())}"
        )


def _parse_code_block(raw: dict, recipe_path: Path) -> CodeBlock:
    """Parse a code_block entry."""
    language = raw.get("language", "xml")
    raw_parts = raw.get("parts", [])
    parts = [_parse_part(p, recipe_path) for p in raw_parts]
    return CodeBlock(language=language, parts=parts)


def _parse_structure_entry(raw: dict, recipe_path: Path) -> StructureEntry:
    """Parse a single structure entry."""
    entry = StructureEntry()

    if "heading" in raw:
        entry.heading = raw["heading"]
        entry.level = raw.get("level", 2)

    if "code_block" in raw:
        entry.code_block = _parse_code_block(raw["code_block"], recipe_path)

    if "body" in raw:
        entry.body = raw["body"]

    if "instructions" in raw:
        entry.instructions = raw["instructions"]

    return entry


def _strip_yaml_fence(text: str) -> str:
    """Strip a leading ```yaml ... ``` code fence if present (for .md recipe files)."""
    import re
    stripped = text.strip()
    m = re.match(r"^(`{3,})", stripped)
    if not m:
        return text
    fence = m.group(1)
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return text
    body = stripped[first_newline + 1:]
    closing = re.compile(r"\n" + re.escape(fence) + r"`*[ \t]*$")
    body = closing.sub("", body)
    return body


def parse_recipe(recipe_path: Path) -> Recipe:
    """Parse a recipe file (.md with yaml fence, or raw .yaml) into a Recipe dataclass."""
    with open(recipe_path, "r", encoding="utf-8") as f:
        raw = f.read()
    data = yaml.safe_load(_strip_yaml_fence(raw))

    if not isinstance(data, dict):
        raise ValueError(f"In {recipe_path}: expected a YAML mapping at top level")

    # Required fields
    for field_name in ("group", "output", "structure"):
        if field_name not in data:
            raise ValueError(f"In {recipe_path}: missing required field '{field_name}'")

    group = data["group"]
    output = data["output"]

    raw_structure = data["structure"]
    if not isinstance(raw_structure, list):
        raise ValueError(f"In {recipe_path}: 'structure' must be a list")

    structure = [_parse_structure_entry(entry, recipe_path) for entry in raw_structure]

    return Recipe(
        group=group,
        output=output,
        structure=structure,
        frontmatter=data.get("frontmatter"),
        source_path=recipe_path,
    )
