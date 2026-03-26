"""Render a parsed recipe + sections into a complete output Markdown file."""

from pathlib import Path

import yaml

from config_loader import load_config, resolve_root, resolve_section
from recipe_parser import Recipe, StructureEntry, RecipePart


def _render_frontmatter(frontmatter: dict) -> str:
    """Render YAML frontmatter block."""
    # Use yaml.dump with default_flow_style for lists to match Obsidian conventions
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            # Render lists in flow style: tags: ["QA", "bug-report"]
            lines.append(f"{key}: {yaml.dump(value, default_flow_style=True).strip()}")
        else:
            lines.append(f"{key}: {yaml.dump(value, default_flow_style=True).strip()}")
    lines.append("---")
    return "\n".join(lines)


def _render_comment_header(recipe: Recipe) -> str:
    """Render the auto-generated comment header."""
    config = load_config()
    recipe_rel = recipe.source_path.name
    return (
        f"<!-- {config['auto_comment']} -->\n"
        f"<!-- Source recipe: _recipes/{recipe_rel} -->\n"
        f"<!-- Rebuild: Ctrl+Shift+B or run python3 _build/build.py -->"
    )


def _render_instructions(text: str) -> str:
    """Render instructions as a blockquote."""
    lines = text.rstrip("\n").split("\n")
    result = []
    for i, line in enumerate(lines):
        if i == 0:
            result.append(f"> **Instructions for human:** {line}")
        else:
            result.append(f"> {line}")
    return "\n".join(result)


def _render_user_input(part: RecipePart) -> str:
    """Render a user_input part as an XML tag."""
    tag = part.value
    if part.placeholder:
        return f"<{tag}>\n{part.placeholder}\n</{tag}>"
    else:
        return f"<{tag}>\n\n</{tag}>"


def _render_code_block(code_block, recipe: Recipe, config: dict) -> str:
    """Render a code block with all its parts assembled."""
    fence = config["code_fence"]
    default_sep = config["default_separator"].encode().decode("unicode_escape")

    # Render each part
    rendered_parts = []
    separators = []
    for part in code_block.parts:
        if part.kind == "section":
            section_path = resolve_section(part.value, recipe.group, config)
            content = section_path.read_text(encoding="utf-8").rstrip("\n")
            rendered_parts.append(content)
        elif part.kind == "inline":
            rendered_parts.append(part.value.rstrip("\n"))
        elif part.kind == "user_input":
            rendered_parts.append(_render_user_input(part))

        # Store the separator for the gap AFTER this part
        if part.separator is not None:
            separators.append(part.separator.encode().decode("unicode_escape"))
        else:
            separators.append(default_sep)

    # Join parts with separators (separator[i] goes between part[i] and part[i+1])
    if not rendered_parts:
        inner = ""
    else:
        inner = rendered_parts[0]
        for i in range(1, len(rendered_parts)):
            inner += separators[i - 1] + rendered_parts[i]

    return f"{fence}{code_block.language}\n{inner}\n{fence}"


def render(recipe: Recipe, config: dict | None = None) -> str:
    """Render a complete output file from a recipe."""
    if config is None:
        config = load_config()

    blocks = []

    # 1. Frontmatter
    if recipe.frontmatter:
        blocks.append(_render_frontmatter(recipe.frontmatter))

    # 2. Comment header
    blocks.append(_render_comment_header(recipe))

    # 3. Structure entries
    for entry in recipe.structure:
        if entry.instructions:
            blocks.append(_render_instructions(entry.instructions))

        if entry.heading:
            prefix = "#" * entry.level
            blocks.append(f"{prefix} {entry.heading}")

        if entry.code_block:
            blocks.append(_render_code_block(entry.code_block, recipe, config))

        if entry.body:
            blocks.append(entry.body.rstrip("\n"))

    return "\n\n".join(blocks) + "\n"
