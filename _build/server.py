#!/usr/bin/env python3
"""Flask web UI for the Prompt Library Maintainer.

Usage:
    python3 server.py [--port 5111]
"""

import difflib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, render_template, request, redirect, url_for, flash

from config_loader import load_config, resolve_root, resolve_sections_dir, resolve_recipes_dir
from recipe_parser import parse_recipe
from renderer import render as render_recipe
from build import discover_recipes, build_all, build_single, find_recipes_using_section
from version import (
    auto_commit_if_changed, section_history, tag_stable,
    find_last_stable_tag, _find_section_path,
)
import git_ops

app = Flask(__name__)
app.secret_key = "prompt-library-maintainer-dev"


def _config():
    return load_config()


def _root():
    return resolve_root()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    config = _config()
    root = _root()
    sections_dir = resolve_sections_dir(config)
    recipes_dir = resolve_recipes_dir(config)

    # Count sections
    section_count = 0
    groups = set()
    if sections_dir.is_dir():
        for group_dir in sections_dir.iterdir():
            if group_dir.is_dir():
                groups.add(group_dir.name)
                section_count += sum(1 for f in group_dir.glob("*.md"))

    # Count recipes
    recipe_paths = discover_recipes(config)

    # Git state
    has_uncommitted = False
    last_commit = None
    recent_activity = []
    if git_ops.is_git_repo(root):
        has_uncommitted = git_ops.has_changes(root)
        log_entries = git_ops.file_log(root, ".", max_entries=5)
        if log_entries:
            last_commit = log_entries[0]
            recent_activity = log_entries

    return render_template("dashboard.html",
        section_count=section_count,
        recipe_count=len(recipe_paths),
        group_count=len(groups),
        has_uncommitted=has_uncommitted,
        last_commit=last_commit,
        recent_activity=recent_activity,
    )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@app.route("/sections")
def sections_browser():
    config = _config()
    sections_dir = resolve_sections_dir(config)

    groups = {}
    total_count = 0
    if sections_dir.is_dir():
        for group_dir in sorted(sections_dir.iterdir()):
            if group_dir.is_dir():
                sections = []
                for f in sorted(group_dir.glob("*.md")):
                    recipe_count = len(find_recipes_using_section(f.stem, config))
                    sections.append({
                        "name": f.stem,
                        "recipe_count": recipe_count,
                    })
                if sections:
                    groups[group_dir.name] = sections
                    total_count += len(sections)

    return render_template("sections.html",
        groups=groups,
        total_count=total_count,
    )


@app.route("/sections/<group>/<name>")
def section_detail(group, name):
    config = _config()
    root = _root()
    sections_dir = resolve_sections_dir(config)
    section_path = sections_dir / group / f"{name}.md"

    if not section_path.is_file():
        flash("Section not found.", "error")
        return redirect(url_for("sections_browser"))

    content = section_path.read_text(encoding="utf-8")
    recipes_using = find_recipes_using_section(name, config)

    # Git history
    history = []
    if git_ops.is_git_repo(root):
        rel_path = str(section_path.relative_to(root))
        history = git_ops.file_log(root, rel_path)

    return render_template("section_detail.html",
        group=group,
        name=name,
        content=content,
        recipes_using=recipes_using,
        history=history,
    )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

@app.route("/sections/<group>/<name>/rollback/<hash>")
def rollback_confirm(group, name, hash):
    config = _config()
    root = _root()
    sections_dir = resolve_sections_dir(config)
    section_path = sections_dir / group / f"{name}.md"

    if not section_path.is_file():
        flash("Section not found.", "error")
        return redirect(url_for("sections_browser"))

    rel_path = str(section_path.relative_to(root))
    current_content = section_path.read_text(encoding="utf-8")
    old_content = git_ops.file_show(root, rel_path, hash)

    if old_content is None:
        flash(f"Could not retrieve section at commit {hash[:7]}.", "error")
        return redirect(url_for("section_detail", group=group, name=name))

    # Generate HTML diff
    diff_html = ""
    if current_content != old_content:
        differ = difflib.HtmlDiff(wrapcolumn=80)
        diff_html = differ.make_table(
            current_content.splitlines(),
            old_content.splitlines(),
            fromdesc="Current",
            todesc=f"Revert to {hash[:7]}",
        )

    affected_recipes = find_recipes_using_section(name, config)

    return render_template("rollback_confirm.html",
        group=group,
        name=name,
        target_hash=hash,
        short_hash=hash[:7],
        affected_recipes=affected_recipes,
        diff_html=diff_html,
    )


@app.route("/sections/<group>/<name>/rollback/<hash>", methods=["POST"])
def do_rollback(group, name, hash):
    config = _config()
    root = _root()
    sections_dir = resolve_sections_dir(config)
    section_path = sections_dir / group / f"{name}.md"

    if not section_path.is_file():
        flash("Section not found.", "error")
        return redirect(url_for("sections_browser"))

    rel_path = str(section_path.relative_to(root))

    try:
        git_ops.checkout_file(root, rel_path, hash)
        # Rebuild all
        build_all(config)
        # Auto-commit
        git_ops.stage_files(root, [config["sections_dir"], config["recipes_dir"], "."])
        git_ops.commit(root, f"Rollback: {name} reverted to {hash[:7]}")
        flash(f"Successfully reverted '{name}' to {hash[:7]} and rebuilt.", "success")
    except Exception as e:
        flash(f"Rollback failed: {e}", "error")

    return redirect(url_for("section_detail", group=group, name=name))


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

@app.route("/recipes")
def recipes_browser():
    config = _config()
    recipe_paths = discover_recipes(config)

    recipes = []
    for rp in recipe_paths:
        recipe = parse_recipe(rp)
        section_count = 0
        if recipe.structure:
            for entry in recipe.structure:
                if entry.code_block:
                    section_count += sum(
                        1 for p in entry.code_block.parts if p.kind == "section"
                    )
        recipes.append({
            "name": rp.stem,
            "output": recipe.output,
            "group": recipe.group,
            "section_count": section_count,
        })

    return render_template("recipes.html", recipes=recipes)


@app.route("/recipes/<name>")
def recipe_detail(name):
    config = _config()
    root = _root()
    recipes_dir = resolve_recipes_dir(config)
    recipe_path = recipes_dir / f"{name}.md"
    if not recipe_path.is_file():
        recipe_path = recipes_dir / f"{name}.yaml"

    if not recipe_path.is_file():
        flash("Recipe not found.", "error")
        return redirect(url_for("recipes_browser"))

    recipe = parse_recipe(recipe_path)

    # Collect sections info
    sections = []
    for entry in recipe.structure:
        if entry.code_block:
            for part in entry.code_block.parts:
                if part.kind == "section":
                    section_path = _find_section_path(part.value, config)
                    if section_path:
                        sections_dir = resolve_sections_dir(config)
                        rel = section_path.relative_to(sections_dir)
                        group = rel.parts[0] if len(rel.parts) > 1 else "shared"
                        sections.append({"name": part.value, "group": group, "kind": "section"})
                    else:
                        sections.append({"name": part.value, "group": None, "kind": "section (missing)"})
                elif part.kind == "inline":
                    display = part.value[:50] + "..." if len(part.value) > 50 else part.value
                    sections.append({"name": display, "group": None, "kind": "inline"})
                elif part.kind == "user_input":
                    sections.append({"name": f"<{part.value}>", "group": None, "kind": "user_input"})

    # Stable tags
    tags = []
    if git_ops.is_git_repo(root):
        tags = git_ops.list_tags(root, f"stable/{name}/*")

    # Preview
    try:
        preview = render_recipe(recipe, config)
    except Exception as e:
        preview = f"Error rendering: {e}"

    return render_template("recipe_detail.html",
        name=name,
        recipe=recipe,
        sections=sections,
        tags=tags,
        preview=preview,
    )


@app.route("/recipes/<name>/tag", methods=["POST"])
def do_tag(name):
    label = request.form.get("label", "").strip() or None
    try:
        tag_name = tag_stable(name, label)
        flash(f"Tagged as '{tag_name}'.", "success")
    except Exception as e:
        flash(f"Tagging failed: {e}", "error")
    return redirect(url_for("recipe_detail", name=name))


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

@app.route("/build")
def build_view():
    return render_template("build.html", results=None, build_log=None)


@app.route("/build", methods=["POST"])
def do_build():
    config = _config()
    recipe_name = request.form.get("recipe", "").strip()

    # Capture print output
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        if recipe_name:
            recipes_dir = resolve_recipes_dir(config)
            recipe_path = recipes_dir / f"{recipe_name}.md"
            if not recipe_path.is_file():
                recipe_path = recipes_dir / f"{recipe_name}.yaml"
            if not recipe_path.is_file():
                flash(f"Recipe '{recipe_name}' not found.", "error")
                sys.stdout = old_stdout
                return redirect(url_for("build_view"))
            result = build_single(recipe_path, config)
            results = [result]
        else:
            results = build_all(config)

        # Auto-commit
        auto_commit_if_changed(config)
    except Exception as e:
        flash(f"Build failed: {e}", "error")
        results = []
    finally:
        build_log = buffer.getvalue()
        sys.stdout = old_stdout

    changed = sum(1 for r in results if r["changed"])
    if changed > 0:
        flash(f"Build complete: {changed} file(s) updated.", "success")
    else:
        flash("Build complete: no changes.", "success")

    return render_template("build.html", results=results, build_log=build_log)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Prompt Library web UI")
    parser.add_argument("--port", type=int, default=None, help="Port (default: from config)")
    parser.add_argument("--host", default="127.0.0.1", help="Host")
    args = parser.parse_args()

    config = _config()
    port = args.port or config.get("server_port", 5111)

    print(f"Starting Prompt Library UI at http://{args.host}:{port}")
    app.run(host=args.host, port=port, debug=True)


if __name__ == "__main__":
    main()
