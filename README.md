# Prompt Library Maintainer

A build system for managing large, structured XML-in-Markdown prompts. It breaks prompts into reusable sections, assembles them via recipe files, and tracks changes with Git — all manageable through a web UI or CLI.

Built for use with [Obsidian](https://obsidian.md) vaults but works with any Markdown-based prompt library.

## Problem

Complex prompts (e.g., detailed bug-report templates) often share identical sections across variants. Manually keeping them in sync is error-prone. This tool lets you edit a shared section once and rebuild all prompts that use it.

## How It Works

```
_sections/              Reusable prompt fragments (Markdown files)
  shared/               Sections shared across all prompt groups
  bug-scribe/           Group-specific sections
  ...
_recipes/               YAML files defining how sections assemble
_build/                 The build system (this repo)
```

A **recipe** defines the structure of an output prompt — which sections to include, in what order, with what headings and code fences. The **renderer** reads the recipe, resolves each section reference, and writes the final copy-ready Markdown file.

Section resolution order: `_sections/{group}/{name}.md` → `_sections/shared/{name}.md`.

## Features

- **Build system** — Assemble prompts from shared sections via YAML recipes
- **Decompose tool** — Parse existing prompts into sections + recipe (round-trip verified)
- **Git integration** — Auto-commit on build, section history, rollback, stable tagging
- **Web UI** — Dashboard, section/recipe browsers, visual diffs, one-click rollback and rebuild (Flask, port 5111)
- **CLI** — `build.py`, `decompose.py`, `version.py` for scripting and automation
- **Obsidian integration** — Designed for Shell Commands hotkey (`Ctrl+Shift+B`) and Custom Frames sidebar

## Quick Start

### Requirements

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- Flask (`pip install flask`) — for the web UI only
- Git — for version control features

### Setup

1. Clone this repo into your prompt library directory (or wherever you keep your prompts):
   ```bash
   git clone <repo-url> _build
   ```

2. Create `_build/config.yaml` from the example:
   ```yaml
   sections_dir: "_sections"
   recipes_dir: "_recipes"
   code_fence: "`````````"   # 9 backticks (avoids collision with inner fences)
   default_separator: "\n\n"
   server_port: 5111
   ```

3. Create the directory structure:
   ```bash
   mkdir -p _sections/shared _recipes _reference
   ```

4. Initialize Git (optional but recommended):
   ```bash
   git init
   ```

### Build

```bash
# Rebuild all recipes
python3 _build/build.py

# Rebuild a single recipe
python3 _build/build.py --recipe bug-scribe-gp

# Dry run (preview without writing)
python3 _build/build.py --dry-run

# Check all section references resolve
python3 _build/build.py --check

# Show which recipes use a section
python3 _build/build.py --deps behavioralRules
```

### Decompose an existing prompt

```bash
python3 _build/decompose.py "My Prompt.md" --group my-group
```

This parses the prompt's structure, extracts XML sections into `_sections/`, and generates a recipe YAML in `_recipes/`. Shared sections are deduplicated automatically.

### Web UI

```bash
python3 _build/server.py
# Open http://localhost:5111
```

### Version control

```bash
# View section history
python3 _build/version.py history behavioralRules

# Rollback a section to a previous version
python3 _build/version.py rollback behavioralRules abc1234 --confirm

# Tag a recipe as stable
python3 _build/version.py tag bug-scribe-gp v2-reviewed
```

## Recipe Format

```yaml
group: bug-scribe
output: "000 - GP Bug Report Prompt.md"

frontmatter:
  aliases: ["GP Bug Scribe"]

structure:
  - code_block:
      parts:
        - inline: |
            <custom-instructions>
        - section: behavioralRules
        - section: goal-gp
          separator: "\n"
        - user_input: prompt
        - inline: |
            </custom-instructions>
```

Part types:
- `section: name` — references `_sections/{group}/name.md` or `_sections/shared/name.md`
- `inline: text` — literal text included directly
- `user_input: tag` — empty XML tag for user input (e.g., `<prompt>\n\n</prompt>`)

## License

MIT
