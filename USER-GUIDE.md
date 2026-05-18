# User Guide

## Typical Workflows

### Build or validate the library

**Normal build:**

```bash
python3 _build/build.py
```

This validates all recipes, rebuilds every generated prompt whose content changed, and auto-commits changes when auto-commit is available.

**Validate without writing:**

```bash
python3 _build/build.py --check
```

Use this after editing recipes or sections. It checks recipe YAML syntax, recipe structure, common literal-block indentation mistakes, and section references.

**Preview build results without writing:**

```bash
python3 _build/build.py --dry-run
```

Dry runs still validate recipes first, then report which output files would change.

### Edit a shared section

1. Edit the section file in `_sections/shared/` or the relevant `_sections/{group}/` directory.
2. Optional: validate with `python3 _build/build.py --check`.
3. Rebuild with `python3 _build/build.py`, or use the Obsidian `Ctrl+Shift+B` command if configured.
4. All prompts using that section are updated and auto-committed.

### Add a new prompt

**From scratch:**

1. Create section files in `_sections/{group}/` or `_sections/shared/`.
2. Create a recipe file in `_recipes/`. Prefer `_recipes/your-recipe.md` with a fenced YAML block; `.yaml` is still supported as a fallback.
3. Validate with `python3 _build/build.py --check`.
4. Build with `python3 _build/build.py --recipe your-recipe`.

**From an existing prompt:**

1. Run `python3 _build/decompose.py "Your Prompt.md" --group your-group`.
2. Review the generated sections and recipe.
3. Validate with `python3 _build/build.py --check`.
4. Rebuild to verify with `python3 _build/build.py --recipe your-recipe`.

### Create a variant of an existing prompt

1. Copy the recipe file, for example `cp _recipes/original.md _recipes/variant.md`.
2. Edit the new recipe: change `output`, swap sections, or add overrides.
3. Create any new group-specific sections in `_sections/{group}/`.
4. Validate with `python3 _build/build.py --check`.
5. Build with `python3 _build/build.py --recipe variant`.

### Rollback a bad edit

**Via CLI:**

```bash
python3 _build/version.py history sectionName
python3 _build/version.py rollback sectionName abc1234 --confirm
```

**Via Web UI:**

1. Open `http://localhost:5111`, then go to Sections and select the section.
2. In the History table, click "Revert" next to the desired version.
3. Review the diff and affected recipes, then confirm.

### Tag a stable version

```bash
python3 _build/version.py tag bug-scribe-gp v2-reviewed
```

This creates a Git tag such as `stable/bug-scribe-gp/v2-reviewed` so you can return to that known-good state.

---

## Recipe YAML Reference

Recipes are usually stored as Markdown files in `_recipes/` with YAML wrapped in a code fence for easier Obsidian editing:

````markdown
```yaml
group: bug-scribe
output: "000 - Prompt.md"

structure:
  - code_block:
      language: xml
      parts:
        - section: intro
```
````

Raw `.yaml` recipes are also supported if there are no `.md` recipes in `_recipes/`.

```yaml
group: bug-scribe          # Section resolution group
output: "000 - Prompt.md"  # Output filename, relative to the library root

frontmatter:               # Optional YAML frontmatter for the output file
  aliases: ["My Prompt"]

structure:                 # Ordered list of content blocks
  - heading: "Prompt"      # Markdown heading, level 2 by default
    level: 2

  - instructions: |        # Blockquote instructions block
      Paste this into the AI chat.

  - code_block:            # Fenced code block using the global code_fence setting
      language: xml
      parts:
        - section: behavioralRules         # Load from _sections/
        - section: goal-gp
          separator: "\n"                  # Override default separator
        - inline: "<custom-instructions>"  # Literal text
          separator: "\n"
        - user_input:                      # Renders <prompt>...</prompt>
            tag: "prompt"
            placeholder: "Enter bug here"  # Optional placeholder text

  - body: |                # Plain text outside code blocks
      Additional notes here.
```

**Section resolution:** `_sections/{group}/{name}.md` is checked first, then `_sections/shared/{name}.md`.

**Literal block indentation:** after `body: |`, `instructions: |`, or other YAML literal blocks, keep content lines indented consistently:

```yaml
  - body: |
      SIS BOAD user:
      ```
      tommasogiuseppe.brindani@external.ivecogroup.com
      ```
```

If a line is under-indented, `build.py --check` reports the recipe path, line, column, and nearby source lines before a build writes anything.

---

## Validation and Error Handling

Regular build usage does not change when recipes are valid. The meaningful change is failure behavior: builds now validate first and abort before writing output files if a recipe is invalid.

Validation checks:

- recipe YAML syntax, including fenced `_recipes/*.md` files
- required recipe fields: `group`, `output`, and `structure`
- basic recipe structure, such as `structure` and `code_block.parts` being lists
- common literal-block indentation mistakes in `body: |` and `instructions: |`
- referenced sections in `_sections/{group}/` or `_sections/shared/`

Example validation output:

```text
Checking 9 recipe(s)...
  [ok] bug-scribe-crm
  [error] bug-scribe-af

1 error(s) found:

Recipe 'bug-scribe-af':
  _recipes/bug-scribe-af.md:13:5: error: possible under-indented literal block line; expected at least 6 leading spaces
  Nearby recipe lines:
      10:       ```
      11:       SIS BOAD user:
      12:       ```
  >   13:     tommasogiuseppe.brindani@external.ivecogroup.com
      14:       ```
```

---

## Web UI Pages

| Page | URL | Purpose |
|------|-----|---------|
| Dashboard | `/` | Overview stats, recent activity, rebuild button |
| Sections | `/sections` | Browse all sections by group |
| Section Detail | `/sections/{group}/{name}` | Content preview, history, impact analysis, revert |
| Recipes | `/recipes` | Browse all recipes |
| Recipe Detail | `/recipes/{name}` | Sections list, stable tags, assembled preview |
| Build | `/build` | Rebuild all or single recipe, view build log |

---

## Obsidian Integration

### Shell Commands plugin rebuild hotkey

1. Install the Shell Commands plugin.
2. Add a new command: `python3 <full-path-to>/_build/build.py`.
3. Bind it to `Ctrl+Shift+B`.

### Custom Frames plugin embedded web UI

1. Install the Custom Frames plugin.
2. Add a frame with URL `http://localhost:5111` and display it in the sidebar.
3. Start the server with `python3 _build/server.py`.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `python3 _build/build.py` | Validate and rebuild all recipes |
| `python3 _build/build.py --recipe NAME` | Validate and rebuild a single recipe by filename stem, without `.md` or `.yaml` |
| `python3 _build/build.py --dry-run` | Validate and preview changes without writing |
| `python3 _build/build.py --check` | Validate recipe syntax, structure, indentation, and section references |
| `python3 _build/build.py --deps SECTION` | List recipes using a section |
| `python3 _build/decompose.py FILE --group GROUP` | Parse a prompt into sections and a recipe |
| `python3 _build/decompose.py FILE --group GROUP --dry-run` | Preview decompose without writing |
| `python3 _build/version.py history SECTION` | Show Git history for a section |
| `python3 _build/version.py rollback SECTION HASH --confirm` | Revert a section to a previous version |
| `python3 _build/version.py tag RECIPE [LABEL]` | Tag a recipe as stable |
| `python3 _build/version.py tags` | List all stable tags |
| `python3 _build/version.py diff SECTION [HASH]` | Show diff for a section |
| `python3 _build/server.py [--port PORT]` | Start the web UI |
