#!/usr/bin/env python3
"""Build script for the Prompt Library Maintainer.

Assembles reusable prompt sections into complete Obsidian prompt notes.
"""

import argparse
import sys
from pathlib import Path

# Ensure _build/ is on the path so imports work when invoked from any directory
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_config, resolve_recipes_dir, resolve_output_path, resolve_section
from recipe_parser import parse_recipe
from renderer import render

try:
    from version import auto_commit_if_changed
except ImportError:
    auto_commit_if_changed = None


def discover_recipes(config: dict) -> list[Path]:
    """Find all recipe files (.md preferred, .yaml as fallback)."""
    recipes_dir = resolve_recipes_dir(config)
    if not recipes_dir.is_dir():
        return []
    md_recipes = sorted(recipes_dir.glob("*.md"))
    if md_recipes:
        return md_recipes
    return sorted(recipes_dir.glob("*.yaml"))


def find_recipes_using_section(section_name: str, config: dict) -> list[str]:
    """Find all recipes that reference a given section name."""
    results = []
    for recipe_path in discover_recipes(config):
        recipe = parse_recipe(recipe_path)
        for entry in recipe.structure:
            if entry.code_block:
                for part in entry.code_block.parts:
                    if part.kind == "section" and part.value == section_name:
                        results.append(recipe_path.stem)
                        break
                else:
                    continue
                break
    return results


def build_single(recipe_path: Path, config: dict, dry_run: bool = False) -> dict:
    """Build a single recipe. Returns a result dict."""
    recipe = parse_recipe(recipe_path)
    output_path = resolve_output_path(recipe.output, config)
    output_content = render(recipe, config)

    # Check if content changed
    changed = True
    if output_path.is_file():
        existing = output_path.read_text(encoding="utf-8")
        if existing == output_content:
            changed = False

    if dry_run:
        status = "would change" if changed else "unchanged"
        print(f"  [{status}] {recipe.output}")
    else:
        if changed:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_content, encoding="utf-8")
            print(f"  [written] {recipe.output}")
        else:
            print(f"  [unchanged] {recipe.output}")

    return {
        "recipe": recipe_path.stem,
        "output": recipe.output,
        "changed": changed,
    }


def build_all(config: dict, dry_run: bool = False) -> list[dict]:
    """Build all recipes."""
    recipe_paths = discover_recipes(config)
    if not recipe_paths:
        print("No recipes found.")
        return []

    print(f"Building {len(recipe_paths)} recipe(s)...")
    results = []
    for recipe_path in recipe_paths:
        results.append(build_single(recipe_path, config, dry_run))

    changed_count = sum(1 for r in results if r["changed"])
    print(f"\nDone: {changed_count} changed, {len(results) - changed_count} unchanged.")
    return results


def check_all(config: dict) -> list[dict]:
    """Verify all section references resolve without writing."""
    recipe_paths = discover_recipes(config)
    if not recipe_paths:
        print("No recipes found.")
        return []

    errors = []
    print(f"Checking {len(recipe_paths)} recipe(s)...")
    for recipe_path in recipe_paths:
        recipe = parse_recipe(recipe_path)
        for entry in recipe.structure:
            if entry.code_block:
                for part in entry.code_block.parts:
                    if part.kind == "section":
                        try:
                            resolve_section(part.value, recipe.group, config)
                        except FileNotFoundError as e:
                            errors.append({
                                "recipe": recipe_path.stem,
                                "section": part.value,
                                "error": str(e),
                            })

    if errors:
        print(f"\n{len(errors)} error(s) found:")
        for err in errors:
            print(f"  Recipe '{err['recipe']}': {err['error']}")
        return errors
    else:
        print("All section references resolved successfully.")
        return []


def show_deps(section_name: str, config: dict):
    """Show which recipes depend on a given section."""
    recipes = find_recipes_using_section(section_name, config)
    if recipes:
        print(f"Section '{section_name}' is used by:")
        for r in recipes:
            print(f"  - {r}")
    else:
        print(f"Section '{section_name}' is not referenced by any recipe.")


def main():
    parser = argparse.ArgumentParser(
        description="Build Prompt Library output files from recipes and sections."
    )
    parser.add_argument("--recipe", help="Build a single recipe by name (without extension)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing")
    parser.add_argument("--check", action="store_true", help="Verify all section references resolve")
    parser.add_argument("--deps", metavar="SECTION", help="Show which recipes use a given section")

    args = parser.parse_args()
    config = load_config()

    if args.check:
        errors = check_all(config)
        sys.exit(1 if errors else 0)

    if args.deps:
        show_deps(args.deps, config)
        return

    if args.recipe:
        recipes_dir = resolve_recipes_dir(config)
        recipe_path = recipes_dir / f"{args.recipe}.md"
        if not recipe_path.is_file():
            recipe_path = recipes_dir / f"{args.recipe}.yaml"
        if not recipe_path.is_file():
            print(f"Error: recipe '{args.recipe}' not found in {recipes_dir}", file=sys.stderr)
            sys.exit(1)
        build_single(recipe_path, config, dry_run=args.dry_run)
    else:
        build_all(config, dry_run=args.dry_run)

    # Auto-commit if not in dry-run/check mode
    if not args.dry_run and not args.check and auto_commit_if_changed:
        auto_commit_if_changed(config)


if __name__ == "__main__":
    main()
