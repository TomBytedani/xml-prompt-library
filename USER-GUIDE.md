# User Guide

## Typical Workflows

### Edit a shared section

1. Edit the section file in `_sections/shared/` (e.g., `behavioralRules.md`)
2. Rebuild: `python3 _build/build.py` (or `Ctrl+Shift+B` in Obsidian)
3. All prompts using that section are updated and auto-committed

### Add a new prompt

**From scratch:**
1. Create section files in `_sections/{group}/` or `_sections/shared/`
2. Create a recipe YAML in `_recipes/` (see format below)
3. Build: `python3 _build/build.py --recipe your-recipe`

**From an existing prompt:**
1. Run: `python3 _build/decompose.py "Your Prompt.md" --group your-group`
2. Review the generated sections and recipe
3. Rebuild to verify: `python3 _build/build.py --recipe your-recipe`

### Create a variant of an existing prompt

1. Copy the recipe YAML: `cp _recipes/original.yaml _recipes/variant.yaml`
2. Edit the new recipe — change `output`, swap sections, add overrides
3. Create any new group-specific sections in `_sections/{group}/`
4. Build: `python3 _build/build.py --recipe variant`

### Rollback a bad edit

**Via CLI:**
```bash
python3 _build/version.py history sectionName        # find the commit hash
python3 _build/version.py rollback sectionName abc1234 --confirm
```

**Via Web UI:**
1. Open http://localhost:5111 → Sections → select the section
2. In the History table, click "Revert" next to the desired version
3. Review the diff and affected recipes → Confirm

### Tag a stable version

```bash
python3 _build/version.py tag bug-scribe-gp v2-reviewed
```

This creates a Git tag `stable/bug-scribe-gp/v2-reviewed` so you can always return to this known-good state.

---

## Recipe YAML Reference

```yaml
group: bug-scribe          # Section resolution group
output: "000 - Prompt.md"  # Output filename (relative to library root)

frontmatter:               # Optional YAML frontmatter for the output file
  aliases: ["My Prompt"]

structure:                  # Ordered list of content blocks
  - heading: "Prompt"      # Markdown heading (## level)

  - instructions: |        # Blockquote instructions block
      Paste this into the AI chat.

  - code_block:            # 9-backtick fenced code block
      parts:
        - section: behavioralRules         # Load from _sections/
        - section: goal-gp
          separator: "\n"                  # Override default \n\n separator
        - inline: |                        # Literal text
            <custom-instructions>
        - user_input: prompt               # Empty tag: <prompt>\n\n</prompt>
          placeholder: "Enter bug here"    # Optional placeholder text

  - body: |                # Plain text (outside code blocks)
      Additional notes here.
```

**Section resolution:** `_sections/{group}/{name}.md` is checked first, then `_sections/shared/{name}.md`.

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

### Shell Commands plugin (rebuild hotkey)

1. Install the Shell Commands plugin
2. Add a new command: `python3 <full-path-to>/_build/build.py`
3. Bind to `Ctrl+Shift+B`

### Custom Frames plugin (embedded web UI)

1. Install the Custom Frames plugin
2. Add a frame: URL `http://localhost:5111`, display in sidebar
3. Start the server: `python3 _build/server.py`

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `build.py` | Rebuild all recipes |
| `build.py --recipe NAME` | Rebuild a single recipe |
| `build.py --dry-run` | Preview changes without writing |
| `build.py --check` | Verify all section references resolve |
| `build.py --deps SECTION` | List recipes using a section |
| `decompose.py FILE --group GROUP` | Parse a prompt into sections + recipe |
| `decompose.py FILE --group GROUP --dry-run` | Preview decompose without writing |
| `version.py history SECTION` | Show Git history for a section |
| `version.py rollback SECTION HASH --confirm` | Revert a section to a previous version |
| `version.py tag RECIPE [LABEL]` | Tag a recipe as stable |
| `version.py tags` | List all stable tags |
| `version.py diff SECTION [HASH]` | Show diff for a section |
| `server.py [--port PORT]` | Start the web UI |
