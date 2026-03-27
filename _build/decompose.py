#!/usr/bin/env python3
"""Decompose an existing prompt Markdown file into sections + a draft recipe.

Usage:
    python3 decompose.py <prompt-file> --group <group-name> [--non-interactive]
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Ensure _build/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_config, resolve_root, resolve_sections_dir, resolve_recipes_dir


# ---------------------------------------------------------------------------
# 2.1  Markdown structure parser
# ---------------------------------------------------------------------------

@dataclass
class MarkdownBlock:
    """A block-level element in the prompt Markdown."""
    kind: str  # "instructions", "heading", "code_block", "body"
    content: str = ""
    heading_level: int | None = None
    heading_text: str | None = None
    fence_language: str = "xml"


def parse_prompt_markdown(text: str) -> list[MarkdownBlock]:
    """Parse a prompt Markdown file into structural blocks.

    Handles:
    - 9-backtick code fences (primary)
    - Variable-length fences (fallback)
    - No-heading prompts (bug-scribe pattern)
    - "Prompt:" pseudo-heading (005/006 pattern)
    - Pre-codeblock plain text instructions
    - Auto-generated comment headers (stripped)
    """
    blocks: list[MarkdownBlock] = []
    lines = text.split("\n")
    i = 0
    n = len(lines)

    # Strip YAML frontmatter
    if i < n and lines[i].strip() == "---":
        i += 1
        while i < n and lines[i].strip() != "---":
            i += 1
        if i < n:
            i += 1  # skip closing ---

    # Strip auto-generated HTML comment header lines
    while i < n and lines[i].strip().startswith("<!--"):
        i += 1

    # Skip blank lines after frontmatter/comments
    while i < n and lines[i].strip() == "":
        i += 1

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Skip blank lines between blocks
        if stripped == "":
            i += 1
            continue

        # Check for code fence (3+ backticks)
        fence_match = re.match(r'^(`{3,})(\w*)\s*$', stripped)
        if fence_match:
            fence_str = fence_match.group(1)
            fence_lang = fence_match.group(2) or "xml"
            fence_len = len(fence_str)
            i += 1
            code_lines = []
            # Find matching closing fence (same or greater length)
            while i < n:
                close_match = re.match(r'^(`{3,})\s*$', lines[i].strip())
                if close_match and len(close_match.group(1)) >= fence_len:
                    break
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append(MarkdownBlock(
                kind="code_block",
                content="\n".join(code_lines),
                fence_language=fence_lang,
            ))
            continue

        # Check for heading (## Prompt, etc.)
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text_h = heading_match.group(2).rstrip(":")
            blocks.append(MarkdownBlock(
                kind="heading",
                heading_level=level,
                heading_text=text_h,
            ))
            i += 1
            continue

        # Check for pseudo-heading "Prompt:" (line is exactly "Prompt:" with optional whitespace)
        if re.match(r'^Prompt:\s*$', stripped):
            blocks.append(MarkdownBlock(
                kind="heading",
                heading_level=2,
                heading_text="Prompt",
            ))
            i += 1
            continue

        # Plain text block (instructions or body)
        text_lines = []
        while i < n:
            l = lines[i]
            s = l.strip()
            if s == "":
                # Check if next non-blank line is a fence or heading
                j = i + 1
                while j < n and lines[j].strip() == "":
                    j += 1
                if j < n:
                    next_s = lines[j].strip()
                    if (re.match(r'^`{3,}', next_s) or
                            re.match(r'^#{1,6}\s+', next_s) or
                            re.match(r'^Prompt:\s*$', next_s)):
                        break
                # Part of this text block
                text_lines.append(l)
                i += 1
                continue
            if (re.match(r'^`{3,}', s) or
                    re.match(r'^#{1,6}\s+', s) or
                    re.match(r'^Prompt:\s*$', s)):
                break
            text_lines.append(l)
            i += 1

        text_content = "\n".join(text_lines).strip()
        if text_content:
            # Strip "Instructions for human:" prefix variants
            text_content = _strip_instructions_prefix(text_content)

            # Heuristic: if it appears before a code block, it's instructions
            # Check if next meaningful block is a code_block or heading+code_block
            remaining = "\n".join(lines[i:])
            if re.search(r'`{3,}', remaining):
                blocks.append(MarkdownBlock(kind="instructions", content=text_content))
            else:
                blocks.append(MarkdownBlock(kind="body", content=text_content))

    return blocks


def _strip_instructions_prefix(text: str) -> str:
    """Strip renderer-added prefixes from instructions text."""
    # Built output format: "> **Instructions for human:** ..."
    text = re.sub(r'^>\s*\*\*Instructions for human:\*\*\s*', '', text)
    # Original format: "Instructions for human: ..."
    text = re.sub(r'^Instructions for human:\s*', '', text)
    return text.strip()


# ---------------------------------------------------------------------------
# 2.2  XML section splitter
# ---------------------------------------------------------------------------

@dataclass
class ContentChunk:
    """A chunk of content from inside a code block."""
    kind: str  # "xml_section", "inline", "user_input"
    tag: str = ""       # XML tag name (for xml_section and user_input)
    content: str = ""   # Full content including tags (for xml_section), or text (for inline)
    inner: str = ""     # Content between tags (for xml_section)
    placeholder: str | None = None  # For user_input


def split_code_block_content(content: str) -> list[ContentChunk]:
    """Split code block interior into XML sections, inline text, and user inputs.

    Uses regex-based parsing (NOT xml.etree — content isn't valid XML).
    Applies wrapper heuristic: if single top-level tag covers >80% content, recurse.
    """
    chunks = _split_xml_content(content)

    # Wrapper heuristic: if single XML section covers >80% of content
    if len(chunks) == 1 and chunks[0].kind == "xml_section":
        return [chunks[0]]

    # Wrapper heuristic: if the largest XML section covers >80% of content
    # AND contains child XML tags, treat it as a wrapper (recurse into children).
    xml_sections = [c for c in chunks if c.kind == "xml_section"]
    if xml_sections:
        largest = max(xml_sections, key=lambda c: len(c.content))
        total_len = len(content.strip())
        section_len = len(largest.content.strip())
        has_child_tags = bool(re.search(r'<[a-zA-Z_][\w_.-]*[\s>]', largest.inner))
        if total_len > 0 and section_len / total_len > 0.8 and has_child_tags:
            # This is a wrapper — recurse into its inner content
            wrapper_tag = largest.tag
            inner = largest.inner

            # Find content before the wrapper
            wrapper_start = content.find(f"<{wrapper_tag}")
            pre_content = content[:wrapper_start].strip()

            # Find content after the wrapper
            wrapper_end_tag = f"</{wrapper_tag}>"
            wrapper_end_pos = content.rfind(wrapper_end_tag)
            post_content = content[wrapper_end_pos + len(wrapper_end_tag):].strip()

            result = []
            if pre_content:
                result.append(ContentChunk(kind="inline", content=pre_content))
            # Opening tag as inline
            result.append(ContentChunk(kind="inline", content=f"<{wrapper_tag}>"))
            # Recurse into inner content
            result.extend(_split_xml_content(inner))
            # Closing tag as inline
            result.append(ContentChunk(kind="inline", content=f"</{wrapper_tag}>"))
            if post_content:
                for post_chunk in _split_post_content(post_content):
                    result.append(post_chunk)
            return result

    return chunks


def _split_post_content(text: str) -> list[ContentChunk]:
    """Split post-wrapper content into chunks (handles hash separators + user inputs)."""
    chunks = []
    remaining = text.strip()
    if not remaining:
        return chunks

    # Try to parse as XML tags / inline
    parts = _split_xml_content(remaining)
    return parts


def _split_xml_content(content: str) -> list[ContentChunk]:
    """Core XML splitting logic. Finds top-level XML tags and inter-tag content."""
    chunks: list[ContentChunk] = []
    pos = 0
    text = content

    while pos < len(text):
        # Find next opening tag
        tag_match = re.search(r'<([a-zA-Z_][\w_.-]*?)(?:\s[^>]*)?>',  text[pos:])
        if not tag_match:
            # No more tags — remaining is inline content
            remaining = text[pos:].strip()
            if remaining:
                chunks.append(ContentChunk(kind="inline", content=remaining))
            break

        # Content before this tag is inline
        pre = text[pos:pos + tag_match.start()].strip()
        if pre:
            chunks.append(ContentChunk(kind="inline", content=pre))

        tag_name = tag_match.group(1)
        tag_start_abs = pos + tag_match.start()

        # Find the matching closing tag
        close_tag = f"</{tag_name}>"
        close_pos = _find_closing_tag(text, tag_name, tag_start_abs + len(tag_match.group(0)))

        if close_pos == -1:
            # Self-closing or no closing tag — treat rest as inline
            remaining = text[pos:].strip()
            if remaining:
                chunks.append(ContentChunk(kind="inline", content=remaining))
            break

        # Extract full content and inner content
        tag_open_end = tag_start_abs + len(tag_match.group(0))
        inner_content = text[tag_open_end:close_pos]
        full_content = text[tag_start_abs:close_pos + len(close_tag)]

        # Determine if this is a user_input (empty/near-empty) or xml_section
        inner_stripped = inner_content.strip()
        # Threshold: user_input placeholders are at most ~50 chars and have no child XML tags
        has_child_xml = bool(re.search(r'<[a-zA-Z_][\w_.-]*[\s>]', inner_stripped))
        if len(inner_stripped) <= 50 and not has_child_xml:
            # Check if it's a single-line empty tag like <query></query>
            if not inner_content and "\n" not in full_content:
                # Single-line empty tag → inline
                chunks.append(ContentChunk(
                    kind="inline",
                    content=full_content,
                ))
            else:
                # User input: empty or just a placeholder
                placeholder = inner_stripped if inner_stripped else None
                chunks.append(ContentChunk(
                    kind="user_input",
                    tag=tag_name,
                    content=full_content,
                    placeholder=placeholder,
                ))
        else:
            chunks.append(ContentChunk(
                kind="xml_section",
                tag=tag_name,
                content=full_content,
                inner=inner_content,
            ))

        pos = close_pos + len(close_tag)

    return chunks


def _find_closing_tag(text: str, tag_name: str, start: int) -> int:
    """Find position of the matching closing tag, handling nesting."""
    depth = 1
    pos = start
    open_pattern = re.compile(rf'<{re.escape(tag_name)}(?:\s[^>]*)?>')
    close_pattern = re.compile(rf'</{re.escape(tag_name)}>')

    while pos < len(text) and depth > 0:
        next_open = open_pattern.search(text, pos)
        next_close = close_pattern.search(text, pos)

        if next_close is None:
            return -1

        if next_open and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            if depth == 0:
                return next_close.start()
            pos = next_close.end()

    return -1


# ---------------------------------------------------------------------------
# 2.3  Recipe YAML generator
# ---------------------------------------------------------------------------

def generate_recipe_yaml(
    group: str,
    output_filename: str,
    md_blocks: list[MarkdownBlock],
    chunk_map: dict[int, list[ContentChunk]],
    section_names: dict[str, str],  # chunk_key -> section filename (no .md)
) -> str:
    """Generate a recipe YAML string from parsed structure and content chunks.

    Args:
        group: Recipe group name
        output_filename: Output filename for the prompt
        md_blocks: Parsed markdown blocks
        chunk_map: Map of code_block index -> content chunks
        section_names: Map of "block_idx:chunk_idx" -> section name
    """
    recipe = {
        "group": group,
        "output": output_filename,
        "structure": [],
    }

    code_block_idx = 0
    i = 0
    while i < len(md_blocks):
        block = md_blocks[i]

        if block.kind == "instructions":
            entry: dict = {"instructions": block.content + "\n"}

            # Check if next blocks form a heading + code_block combo
            if i + 1 < len(md_blocks) and md_blocks[i + 1].kind == "heading":
                heading_block = md_blocks[i + 1]
                entry["heading"] = heading_block.heading_text
                if heading_block.heading_level != 2:
                    entry["level"] = heading_block.heading_level

                if (i + 2 < len(md_blocks) and md_blocks[i + 2].kind == "code_block"):
                    cb_block = md_blocks[i + 2]
                    entry["code_block"] = _build_code_block_yaml(
                        cb_block, code_block_idx, chunk_map, section_names
                    )
                    code_block_idx += 1
                    i += 3
                    recipe["structure"].append(entry)
                    continue
                i += 2
                recipe["structure"].append(entry)
                continue

            i += 1
            recipe["structure"].append(entry)
            continue

        if block.kind == "heading":
            entry = {}
            entry["heading"] = block.heading_text
            if block.heading_level != 2:
                entry["level"] = block.heading_level

            # Check if next block is a code_block
            if i + 1 < len(md_blocks) and md_blocks[i + 1].kind == "code_block":
                cb_block = md_blocks[i + 1]
                entry["code_block"] = _build_code_block_yaml(
                    cb_block, code_block_idx, chunk_map, section_names
                )
                code_block_idx += 1
                i += 2
                recipe["structure"].append(entry)
                continue

            i += 1
            recipe["structure"].append(entry)
            continue

        if block.kind == "code_block":
            entry = {}
            entry["code_block"] = _build_code_block_yaml(
                block, code_block_idx, chunk_map, section_names
            )
            code_block_idx += 1
            i += 1
            recipe["structure"].append(entry)
            continue

        if block.kind == "body":
            recipe["structure"].append({"body": block.content})
            i += 1
            continue

        i += 1

    return _dump_recipe_yaml(recipe)


def _build_code_block_yaml(
    block: MarkdownBlock,
    block_idx: int,
    chunk_map: dict[int, list[ContentChunk]],
    section_names: dict[str, str],
) -> dict:
    """Build the code_block dict for recipe YAML."""
    cb: dict = {"language": block.fence_language, "parts": []}

    chunks = chunk_map.get(block_idx, [])
    for ci, chunk in enumerate(chunks):
        key = f"{block_idx}:{ci}"
        part: dict = {}

        if chunk.kind == "xml_section":
            name = section_names.get(key, chunk.tag)
            part["section"] = name
            part["separator"] = "\\n"
        elif chunk.kind == "inline":
            part["inline"] = chunk.content
            part["separator"] = "\\n"
        elif chunk.kind == "user_input":
            ui: dict = {"tag": chunk.tag}
            if chunk.placeholder:
                ui["placeholder"] = chunk.placeholder
            part["user_input"] = ui
            part["separator"] = "\\n"

        if part:
            cb["parts"].append(part)

    return cb


def _dump_recipe_yaml(recipe: dict) -> str:
    """Serialize recipe dict to YAML with proper formatting."""
    lines = []
    lines.append(f"group: {recipe['group']}")
    lines.append(f'output: "{recipe["output"]}"')
    lines.append("")
    lines.append("structure:")

    for entry in recipe["structure"]:
        if "instructions" in entry:
            lines.append("  - instructions: |")
            for il in entry["instructions"].rstrip("\n").split("\n"):
                lines.append(f"      {il}")
            lines.append("")

            if "heading" in entry:
                lines.append(f'    heading: "{entry["heading"]}"')
                if "level" in entry:
                    lines.append(f"    level: {entry['level']}")
            if "code_block" in entry:
                _dump_code_block(entry["code_block"], lines, indent=4)
            continue

        if "heading" in entry and "code_block" in entry:
            lines.append(f'  - heading: "{entry["heading"]}"')
            if "level" in entry:
                lines.append(f"    level: {entry['level']}")
            _dump_code_block(entry["code_block"], lines, indent=4)
            continue

        if "heading" in entry:
            lines.append(f'  - heading: "{entry["heading"]}"')
            if "level" in entry:
                lines.append(f"    level: {entry['level']}")
            continue

        if "code_block" in entry:
            lines.append("  - code_block:")
            _dump_code_block_inner(entry["code_block"], lines, indent=6)
            continue

        if "body" in entry:
            lines.append(f"  - body: |")
            for bl in entry["body"].rstrip("\n").split("\n"):
                lines.append(f"      {bl}")
            continue

    return "\n".join(lines) + "\n"


def _dump_code_block(cb: dict, lines: list[str], indent: int):
    """Dump a code_block entry attached to a heading or instructions."""
    prefix = " " * indent
    lines.append(f"{prefix}code_block:")
    _dump_code_block_inner(cb, lines, indent + 2)


def _dump_code_block_inner(cb: dict, lines: list[str], indent: int):
    """Dump the inner parts of a code_block."""
    prefix = " " * indent
    lines.append(f"{prefix}language: {cb['language']}")
    lines.append(f"{prefix}parts:")
    for part in cb["parts"]:
        if "section" in part:
            lines.append(f"{prefix}  - section: {part['section']}")
            if "separator" in part:
                lines.append(f'{prefix}    separator: "{part["separator"]}"')
        elif "inline" in part:
            # Use double quotes and escape inner quotes
            escaped = part["inline"].replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{prefix}  - inline: "{escaped}"')
            if "separator" in part:
                lines.append(f'{prefix}    separator: "{part["separator"]}"')
        elif "user_input" in part:
            ui = part["user_input"]
            lines.append(f"{prefix}  - user_input:")
            lines.append(f'{prefix}      tag: "{ui["tag"]}"')
            if "placeholder" in ui:
                lines.append(f'{prefix}      placeholder: "{ui["placeholder"]}"')
            if "separator" in part:
                lines.append(f'{prefix}    separator: "{part["separator"]}"')


# ---------------------------------------------------------------------------
# 2.4  Interactive section placement
# ---------------------------------------------------------------------------

def scan_existing_sections(config: dict) -> dict[str, Path]:
    """Scan all existing section files and return a map of content_hash -> path."""
    sections_dir = resolve_sections_dir(config)
    result = {}
    if sections_dir.is_dir():
        for md_file in sections_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8").rstrip("\n")
            result[content] = md_file
    return result


def place_section(
    tag_name: str,
    content: str,
    default_group: str,
    config: dict,
    existing_sections: dict[str, Path],
    non_interactive: bool = False,
) -> tuple[str, Path]:
    """Place a section file, handling deduplication and conflicts.

    Returns (section_name, path) where section_name is the recipe reference name.
    """
    sections_dir = resolve_sections_dir(config)
    content_stripped = content.rstrip("\n")

    # Check for exact content match in existing sections
    if content_stripped in existing_sections:
        existing_path = existing_sections[content_stripped]
        section_name = existing_path.stem
        rel = existing_path.relative_to(sections_dir)
        existing_group = rel.parts[0] if len(rel.parts) > 1 else "shared"

        # Only dedup within the same group or shared
        if existing_group == default_group or existing_group == "shared":
            print(f"  [dedup] '{tag_name}' matches existing section '{section_name}' in {existing_group}/")
            return section_name, existing_path
        else:
            # Cross-group match — offer to move to shared or create in target group
            if not non_interactive:
                print(f"\n  '{tag_name}' matches '{section_name}' in {existing_group}/")
                print(f"  Options: [s]hared (move to shared), [d]uplicate (create in {default_group})")
                choice = input("  Choice: ").strip().lower()
                if choice.startswith("s"):
                    # Move to shared
                    shared_path = sections_dir / "shared" / f"{section_name}.md"
                    shared_path.parent.mkdir(parents=True, exist_ok=True)
                    shared_path.write_text(content_stripped + "\n", encoding="utf-8")
                    existing_sections[content_stripped] = shared_path
                    print(f"  [shared] Moved '{section_name}' to shared/")
                    return section_name, shared_path
            # Non-interactive or chose duplicate: fall through to create in target group
            print(f"  [cross-group] '{tag_name}' matches '{section_name}' in {existing_group}/ — creating in {default_group}/")

    # Determine target group
    if non_interactive:
        target_group = default_group
    else:
        target_group = _ask_group(tag_name, default_group, sections_dir)

    target_dir = sections_dir / target_group
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine filename
    section_name = tag_name
    target_path = target_dir / f"{section_name}.md"

    # Check for conflict
    if target_path.exists():
        existing_content = target_path.read_text(encoding="utf-8").rstrip("\n")
        if existing_content == content_stripped:
            print(f"  [exists] '{section_name}' already exists with identical content")
            existing_sections[content_stripped] = target_path
            return section_name, target_path

        if non_interactive:
            # Auto-suffix with group name
            section_name = f"{tag_name}-{default_group}"
            target_path = target_dir / f"{section_name}.md"
        else:
            action = _ask_conflict(tag_name, target_path, existing_content, content_stripped)
            if action == "overwrite":
                pass  # Will write below
            elif action == "keep":
                print(f"  [kept] Keeping existing '{section_name}', skipping new content")
                return section_name, target_path
            elif action.startswith("rename:"):
                section_name = action.split(":", 1)[1]
                target_path = target_dir / f"{section_name}.md"

    # Write section file
    target_path.write_text(content_stripped + "\n", encoding="utf-8")
    existing_sections[content_stripped] = target_path
    print(f"  [created] {target_path.relative_to(resolve_root())}")
    return section_name, target_path


def _ask_group(tag_name: str, default_group: str, sections_dir: Path) -> str:
    """Ask user which group to place a section in."""
    # List available groups
    groups = []
    if sections_dir.is_dir():
        groups = sorted([d.name for d in sections_dir.iterdir() if d.is_dir()])

    print(f"\n  Section '{tag_name}' — place in which group?")
    print(f"  Available: {', '.join(groups) if groups else '(none yet)'}")
    print(f"  Default: [{default_group}]")

    choice = input("  Group: ").strip()
    return choice if choice else default_group


def _ask_conflict(tag_name: str, path: Path, old: str, new: str) -> str:
    """Ask user how to resolve a file conflict."""
    print(f"\n  CONFLICT: '{tag_name}' already exists at {path} with different content.")
    print(f"  Existing: {len(old)} chars | New: {len(new)} chars")
    print("  Options: [o]verwrite, [k]eep existing, [r]ename new")

    choice = input("  Choice: ").strip().lower()
    if choice.startswith("o"):
        return "overwrite"
    elif choice.startswith("k"):
        return "keep"
    elif choice.startswith("r"):
        new_name = input("  New section name: ").strip()
        return f"rename:{new_name}"
    return "keep"


# ---------------------------------------------------------------------------
# 2.5  CLI: Full decompose pipeline
# ---------------------------------------------------------------------------

def decompose(
    prompt_path: Path,
    group: str,
    config: dict | None = None,
    non_interactive: bool = False,
    dry_run: bool = False,
) -> dict:
    """Decompose a prompt file into sections + recipe.

    Returns dict with 'recipe_path', 'sections_created', 'sections_deduped'.
    """
    if config is None:
        config = load_config()

    print(f"Decomposing: {prompt_path.name}")
    print(f"Group: {group}")

    # Read prompt
    content = prompt_path.read_text(encoding="utf-8")
    output_filename = prompt_path.name

    # Step 1: Parse markdown structure
    md_blocks = parse_prompt_markdown(content)
    print(f"  Parsed {len(md_blocks)} markdown block(s)")

    # Step 2: Split code blocks into chunks
    chunk_map: dict[int, list[ContentChunk]] = {}
    code_block_idx = 0
    for block in md_blocks:
        if block.kind == "code_block":
            chunks = split_code_block_content(block.content)
            chunk_map[code_block_idx] = chunks
            print(f"  Code block {code_block_idx}: {len(chunks)} chunk(s)")
            code_block_idx += 1

    # Step 3: Place sections
    existing_sections = scan_existing_sections(config)
    section_names: dict[str, str] = {}
    sections_created = 0
    sections_deduped = 0

    if not dry_run:
        for bi, chunks in chunk_map.items():
            for ci, chunk in enumerate(chunks):
                key = f"{bi}:{ci}"
                if chunk.kind == "xml_section":
                    # Use the inner content (between tags) as the section content
                    section_content = chunk.content  # full with tags
                    name, path = place_section(
                        chunk.tag, section_content, group, config,
                        existing_sections, non_interactive,
                    )
                    section_names[key] = name

                    # Track stats
                    if path.read_text(encoding="utf-8").rstrip("\n") == section_content.rstrip("\n"):
                        # Was it a dedup or new?
                        pass
    else:
        # Dry run: just assign names
        for bi, chunks in chunk_map.items():
            for ci, chunk in enumerate(chunks):
                key = f"{bi}:{ci}"
                if chunk.kind == "xml_section":
                    section_names[key] = chunk.tag

    # Step 4: Generate recipe YAML
    recipe_yaml = generate_recipe_yaml(
        group, output_filename, md_blocks, chunk_map, section_names
    )

    # Step 5: Write recipe
    recipe_stem = _make_recipe_stem(prompt_path.name, group)
    recipes_dir = resolve_recipes_dir(config)
    recipe_path = recipes_dir / f"{recipe_stem}.md"
    recipe_md = f"```yaml\n{recipe_yaml}```\n"

    if dry_run:
        print(f"\n--- Draft recipe ({recipe_stem}.md) ---")
        print(recipe_md)
        print("--- End draft ---")
    else:
        recipes_dir.mkdir(parents=True, exist_ok=True)
        recipe_path.write_text(recipe_md, encoding="utf-8")
        print(f"\n  [recipe] {recipe_path.relative_to(resolve_root())}")

    return {
        "recipe_path": recipe_path,
        "recipe_yaml": recipe_yaml,
        "section_names": section_names,
        "md_blocks": md_blocks,
        "chunk_map": chunk_map,
    }


def _make_recipe_stem(filename: str, group: str) -> str:
    """Generate a recipe filename stem from the prompt filename."""
    # Remove number prefix and extension
    name = Path(filename).stem
    # Remove leading number + separator (e.g., "005 - ")
    name = re.sub(r'^\d+\s*-\s*', '', name)
    # Slugify
    name = name.lower().replace(" ", "-")
    name = re.sub(r'[^a-z0-9-]', '', name)
    name = re.sub(r'-+', '-', name).strip('-')
    return f"{group}-{name}" if group not in name else name


def main():
    parser = argparse.ArgumentParser(
        description="Decompose a prompt Markdown file into sections + recipe."
    )
    parser.add_argument("prompt_file", help="Path to the prompt Markdown file")
    parser.add_argument("--group", required=True, help="Group name for sections")
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="Skip interactive prompts; use defaults"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show draft recipe without writing files"
    )

    args = parser.parse_args()
    prompt_path = Path(args.prompt_file)

    if not prompt_path.is_file():
        print(f"Error: file not found: {prompt_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    decompose(prompt_path, args.group, config,
              non_interactive=args.non_interactive, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
