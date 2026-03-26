#!/usr/bin/env python3
"""Round-trip test: decompose originals → rebuild → verify byte-identical code blocks.

Usage:
    python3 test_roundtrip.py [--prompts 004,005,006,008,009] [--clean]
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import load_config, resolve_root, resolve_sections_dir, resolve_recipes_dir
from recipe_parser import parse_recipe
from renderer import render
from decompose import decompose


EXAMPLE_DIR = "06 - Prompt Library Example/3-output"

# Map of prompt number → group name
PROMPT_GROUPS = {
    "000": "bug-scribe",
    "001": "bug-scribe",
    "002": "bug-scribe",
    "004": "follow-up",
    "005": "test-cases",
    "006": "test-cases",
    "008": "rovo",
    "009": "frontend",
}


def extract_code_blocks(text: str) -> list[str]:
    """Extract all 9-backtick code block interiors from text."""
    pattern = re.compile(r'`{9}\w*\n(.*?)\n`{9}', re.DOTALL)
    return pattern.findall(text)


def extract_code_blocks_any(text: str) -> list[str]:
    """Extract code block interiors using the largest fence in the text."""
    # Find all fence openings and determine the longest one
    fences = re.findall(r'^(`{3,})\w*\s*$', text, re.MULTILINE)
    if not fences:
        return []
    max_len = max(len(f) for f in fences)
    pattern = re.compile(rf'`{{{max_len}}}\w*\n(.*?)\n`{{{max_len}}}', re.DOTALL)
    return pattern.findall(text)


def run_roundtrip(prompt_numbers: list[str], clean: bool = False):
    """Run round-trip test for specified prompts."""
    root = resolve_root()
    config = load_config()
    example_dir = root / EXAMPLE_DIR

    # Test working directory: use a temporary area
    test_sections_dir = root / "_test_sections"
    test_recipes_dir = root / "_test_recipes"

    if clean:
        if test_sections_dir.exists():
            shutil.rmtree(test_sections_dir)
        if test_recipes_dir.exists():
            shutil.rmtree(test_recipes_dir)

    # Override config for test
    test_config = dict(config)
    test_config["sections_dir"] = "_test_sections"
    test_config["recipes_dir"] = "_test_recipes"

    test_sections_dir.mkdir(parents=True, exist_ok=True)
    test_recipes_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for num in prompt_numbers:
        group = PROMPT_GROUPS.get(num)
        if not group:
            print(f"SKIP {num}: no group mapping")
            continue

        # Find the prompt file
        matches = list(example_dir.glob(f"{num} - *.md"))
        if not matches:
            print(f"SKIP {num}: file not found")
            continue

        prompt_path = matches[0]
        print(f"\n{'='*60}")
        print(f"Testing: {prompt_path.name}")
        print(f"{'='*60}")

        # Read original
        original = prompt_path.read_text(encoding="utf-8")
        original_blocks = extract_code_blocks_any(original)
        if not original_blocks:
            print(f"  WARN: no code blocks found in original")
            results.append((num, "NO_BLOCKS", prompt_path.name))
            continue

        # Decompose
        result = decompose(
            prompt_path, group, test_config,
            non_interactive=True, dry_run=False,
        )

        # Build from generated recipe
        recipe_path = result["recipe_path"]
        if not recipe_path.exists():
            print(f"  FAIL: recipe not created at {recipe_path}")
            results.append((num, "NO_RECIPE", prompt_path.name))
            continue

        try:
            recipe = parse_recipe(recipe_path)
            built_output = render(recipe, test_config)
        except Exception as e:
            print(f"  FAIL: build error: {e}")
            results.append((num, "BUILD_ERROR", str(e)))
            continue

        # Extract code blocks from built output
        built_blocks = extract_code_blocks(built_output)
        if not built_blocks:
            built_blocks = extract_code_blocks_any(built_output)

        # Compare
        if len(original_blocks) != len(built_blocks):
            print(f"  FAIL: code block count mismatch: {len(original_blocks)} vs {len(built_blocks)}")
            results.append((num, "COUNT_MISMATCH", f"{len(original_blocks)} vs {len(built_blocks)}"))
            continue

        all_match = True
        for j, (orig, built) in enumerate(zip(original_blocks, built_blocks)):
            if orig == built:
                print(f"  Block {j}: MATCH ({len(orig)} chars)")
            else:
                print(f"  Block {j}: DIFF!")
                # Find first difference
                for k, (a, b) in enumerate(zip(orig, built)):
                    if a != b:
                        ctx = 40
                        print(f"    First diff at char {k}:")
                        print(f"    Original: ...{repr(orig[max(0,k-ctx):k+ctx])}...")
                        print(f"    Built:    ...{repr(built[max(0,k-ctx):k+ctx])}...")
                        break
                else:
                    shorter = min(len(orig), len(built))
                    print(f"    Length diff: {len(orig)} vs {len(built)}")
                    print(f"    Original tail: {repr(orig[shorter:shorter+80])}")
                    print(f"    Built tail:    {repr(built[shorter:shorter+80])}")
                all_match = False

        status = "PASS" if all_match else "FAIL"
        results.append((num, status, prompt_path.name))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for num, status, name in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {num}: {status} — {name}")

    # Cleanup test dirs
    if clean or all(r[1] == "PASS" for r in results):
        if test_sections_dir.exists():
            shutil.rmtree(test_sections_dir)
        if test_recipes_dir.exists():
            shutil.rmtree(test_recipes_dir)
        print("\nCleaned up test directories.")

    passed = sum(1 for r in results if r[1] == "PASS")
    total = len(results)
    print(f"\n{passed}/{total} passed")
    return all(r[1] == "PASS" for r in results)


def main():
    parser = argparse.ArgumentParser(description="Round-trip decompose → build test")
    parser.add_argument(
        "--prompts", default="004,005,006,008,009",
        help="Comma-separated prompt numbers to test"
    )
    parser.add_argument("--clean", action="store_true", help="Clean test dirs before run")

    args = parser.parse_args()
    numbers = [n.strip() for n in args.prompts.split(",")]

    success = run_roundtrip(numbers, clean=args.clean)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
