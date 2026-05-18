"""Parse and validate recipe YAML files into structured dataclasses."""

from dataclasses import dataclass, field
from pathlib import Path
import re

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


@dataclass
class RecipeDiagnostic:
    severity: str
    message: str
    line: int | None = None
    column: int | None = None
    context: str | None = None

    def format(self, recipe_path: Path) -> str:
        location = str(recipe_path)
        if self.line is not None:
            location += f":{self.line}"
            if self.column is not None:
                location += f":{self.column}"

        text = f"{location}: {self.severity}: {self.message}"
        if self.context:
            text += f"\n{self.context}"
        return text


class RecipeParseError(ValueError):
    """Raised when a recipe file cannot be parsed as valid recipe YAML."""

    def __init__(
        self,
        recipe_path: Path,
        message: str,
        line: int | None = None,
        column: int | None = None,
        context: str | None = None,
    ):
        self.diagnostic = RecipeDiagnostic(
            severity="error",
            message=message,
            line=line,
            column=column,
            context=context,
        )
        super().__init__(self.diagnostic.format(recipe_path))


def _line_context(lines: list[str], line_number: int | None, radius: int = 3) -> str | None:
    """Return a small numbered source excerpt around a 1-based line number."""
    if line_number is None or line_number < 1 or line_number > len(lines):
        return None

    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    width = len(str(end))
    result = ["Nearby recipe lines:"]
    for n in range(start, end + 1):
        marker = ">" if n == line_number else " "
        result.append(f"{marker} {n:>{width}}: {lines[n - 1]}")
    return "\n".join(result)


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_yaml_fence_with_offset(text: str) -> tuple[str, int]:
    """Strip a leading ```yaml ... ``` fence and return (body, source_line_offset)."""
    lines = text.splitlines()
    first_content = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first_content is None:
        return text, 0

    opening = lines[first_content].strip()
    m = re.match(r"^(`{3,})", opening)
    if not m:
        return text, 0

    fence = m.group(1)
    body_lines = lines[first_content + 1:]
    last_content = next((i for i in range(len(body_lines) - 1, -1, -1) if body_lines[i].strip()), None)
    if last_content is not None:
        closing = body_lines[last_content].strip()
        if re.fullmatch(re.escape(fence) + r"`*", closing):
            body_lines = body_lines[:last_content]

    return "\n".join(body_lines), first_content + 1


def lint_recipe_file(recipe_path: Path) -> list[RecipeDiagnostic]:
    """Find common recipe formatting mistakes that produce confusing YAML errors."""
    raw = recipe_path.read_text(encoding="utf-8")
    return lint_recipe_text(raw)


def lint_recipe_text(text: str) -> list[RecipeDiagnostic]:
    """Lint recipe source text without requiring it to be valid YAML."""
    diagnostics: list[RecipeDiagnostic] = []
    lines = text.splitlines()

    block_re = re.compile(r"^(\s*)(?:-\s+)?(?:body|instructions):\s*[|>]")
    for i, line in enumerate(lines):
        if not block_re.match(line):
            continue

        block_indent = _leading_spaces(line)
        expected_indent = None
        for j in range(i + 1, len(lines)):
            content = lines[j]
            stripped = content.strip()
            if not stripped:
                continue

            indent = _leading_spaces(content)
            if indent <= block_indent:
                break

            if expected_indent is None:
                expected_indent = indent
                continue

            if block_indent < indent < expected_indent:
                diagnostics.append(RecipeDiagnostic(
                    severity="error",
                    message=(
                        "possible under-indented literal block line; "
                        f"expected at least {expected_indent} leading spaces"
                    ),
                    line=j + 1,
                    column=indent + 1,
                    context=_line_context(lines, j + 1),
                ))

    return diagnostics


def _parse_part(raw: dict, recipe_path: Path) -> RecipePart:
    """Parse a single part entry from a code_block's parts list."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"In {recipe_path}: code_block parts must be mappings, got {type(raw).__name__}"
        )

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
    if not isinstance(raw, dict):
        raise ValueError(f"In {recipe_path}: code_block must be a mapping")

    language = raw.get("language", "xml")
    raw_parts = raw.get("parts", [])
    if not isinstance(raw_parts, list):
        raise ValueError(f"In {recipe_path}: code_block.parts must be a list")

    parts = [_parse_part(p, recipe_path) for p in raw_parts]
    return CodeBlock(language=language, parts=parts)


def _parse_structure_entry(raw: dict, recipe_path: Path) -> StructureEntry:
    """Parse a single structure entry."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"In {recipe_path}: structure entries must be mappings, got {type(raw).__name__}"
        )

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
    body, _ = _strip_yaml_fence_with_offset(text)
    return body


def parse_recipe(recipe_path: Path) -> Recipe:
    """Parse a recipe file (.md with yaml fence, or raw .yaml) into a Recipe dataclass."""
    with open(recipe_path, "r", encoding="utf-8") as f:
        raw = f.read()
    yaml_text, line_offset = _strip_yaml_fence_with_offset(raw)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        source_line = mark.line + 1 + line_offset if mark else None
        source_column = mark.column + 1 if mark else None
        problem = getattr(e, "problem", None) or str(e)
        raise RecipeParseError(
            recipe_path,
            f"YAML parse error: {problem}",
            line=source_line,
            column=source_column,
            context=_line_context(raw.splitlines(), source_line),
        ) from e

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
