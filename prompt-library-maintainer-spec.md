# Prompt Library Maintainer — Functional Analysis

> **Status:** Planning / Pre-implementation  
> **Purpose:** Specification for a build system that assembles reusable prompt sections into complete, copy-ready Obsidian prompt notes, with version control and a visual management interface.  
> **Audience:** Claude Code agent working locally on the vault, and the human iterating on the design.

---

## 1. Problem Statement

The Obsidian vault contains a Prompt Library: a collection of structured prompts formatted as XML inside Markdown code blocks, organized under Markdown headers. The one-click copy on code blocks makes this setup ergonomic for daily use.

The maintenance problem: several prompts (especially bug-scribe prompts targeting different projects) share identical sections. When a shared section is updated, the change must be manually propagated to every prompt that uses it. This is error-prone and doesn't scale.

A secondary problem emerges once shared sections exist: prompt quality can degrade when a section is modified, and without version history there is no way to identify what changed or revert a specific section to a known-good state.

### 1.1 Goals

- **Single source of truth** for every reusable prompt section.
- **One-action rebuild** that regenerates all assembled prompts after any edit.
- **Preserve the current UX**: the output files must remain Markdown notes with XML-in-code-blocks, copyable with one click.
- **Low-friction onboarding of existing prompts**: provide a decomposition tool that takes a complete prompt and generates the section files + template recipe from it.
- **Version control**: automatic git-based history of all section and recipe changes, with per-section rollback capability.
- **Visual management**: a local web UI for browsing section history, tagging stable versions, and performing rollbacks — accessible inside Obsidian via Custom Frames plugin.
- **Extensible**: the architecture should accommodate future enhancements (variable substitution, conditional sections, template/comment handling) without requiring a rewrite.

### 1.2 Version Roadmap

| Version | Scope |
|---|---|
| **v1** | Build script, decompose tool, Shell Commands hotkey, CLI-only workflow |
| **v1.1** | Git integration (auto-commit, per-section rollback CLI), local Flask web UI with Obsidian embed |
| **v2** | Native Obsidian plugin (if the Flask UI proves insufficient), evaluation hooks |

### 1.3 Non-Goals

- Cloud-hosted or multi-user infrastructure.
- Automated quality evaluation of prompt outputs (v2+ territory).
- Live preview or in-editor rendering.

---

## 2. Architecture Overview

```
Prompt Library/
│
├── _build/                        ← Build system (this project)
│   ├── build.py                   ← Main build script
│   ├── decompose.py               ← Import tool: complete prompt → sections + recipe
│   ├── version.py                 ← Git integration layer (v1.1)
│   ├── server.py                  ← Flask web UI server (v1.1)
│   ├── templates/                 ← Jinja2 HTML templates for web UI (v1.1)
│   │   └── ...
│   ├── static/                    ← CSS/JS for web UI (v1.1)
│   │   └── ...
│   └── config.yaml                ← Global config (defaults, paths, server port)
│
├── _sections/                     ← Reusable prompt sections (source of truth)
│   ├── shared/                    ← Sections used across multiple prompt groups
│   │   ├── severity-guidelines.md
│   │   ├── environment-info.md
│   │   └── ...
│   ├── bug-scribe/                ← Sections specific to bug-scribe prompts
│   │   ├── bug-template.md
│   │   ├── reproduction-steps.md
│   │   └── ...
│   └── {other-group}/             ← Future prompt groups get their own subdirectory
│       └── ...
│
├── _recipes/                      ← Assembly recipes (YAML)
│   ├── bug-scribe-crm.yaml
│   ├── bug-scribe-payments.yaml
│   └── ...
│
├── _reference/                    ← Unmanaged reference material (not prompts)
│   ├── excel-format-example.md    ← Example formats, templates, etc.
│   └── ...
│
├── .git/                          ← Local git repo (v1.1, covers _sections/ + _recipes/)
│
├── Bug Report - CRM Project.md          ← OUTPUT (generated, never hand-edited)
├── Bug Report - Payments Project.md     ← OUTPUT (generated)
└── ... (other existing, non-managed notes remain untouched)
```

### 2.1 Naming Conventions & Prefixes

Directories prefixed with `_` (`_build/`, `_sections/`, `_recipes/`) signal "infrastructure, not content." They sort to the top in Obsidian's file explorer and are visually distinct from the actual prompt notes.

> **AGENT NOTE — Discovery step:**  
> Before implementing, inspect the actual vault structure. Identify:
> - Where the Prompt Library currently lives (root? subfolder?).
> - How existing prompts are structured (header hierarchy, code block language tags, number of code blocks per file).
> - Which sections are already shared across prompts (diff them).
> - Whether the vault already has a `.git/` directory (if so, the versioning layer should use it rather than creating a separate repo; see §6 for details).
> - Adapt all paths in this spec to match the real layout.

### 2.2 Section Grouping Strategy

Sections are organized in subdirectories under `_sections/`:

| Directory | Contains | Example |
|---|---|---|
| `shared/` | Sections referenced by 2+ prompt groups | `severity-guidelines.md`, `environment-info.md` |
| `bug-scribe/` | Sections used only within bug-scribe prompts | `bug-template.md`, `project-context-crm.md` |
| `{group}/` | Sections for any future prompt group | `code-review/checklist.md` |

**Rules:**
- A section starts in its group directory.
- When a second prompt group needs it, promote it to `shared/`.
- The build script resolves section references by searching: first the group directory matching the recipe, then `shared/`. This means recipes don't need to specify the subdirectory — just the section filename.

**Resolution order for a recipe in group `bug-scribe`:**
1. `_sections/bug-scribe/{name}.md`
2. `_sections/shared/{name}.md`
3. Error if not found.

---

## 3. File Formats

### 3.1 Section Files (`_sections/**/*.md`)

Plain text/XML content. No Markdown wrappers, no code fences — just the raw content that will be injected.

```xml
<!-- _sections/shared/severity-guidelines.md -->
<severity_guidelines>
- Critical: Production down, data loss, security breach
- High: Core functionality broken, no workaround
- Medium: Feature degraded, workaround exists
- Low: Cosmetic, minor UX issues
</severity_guidelines>
```

If a section contains the entire XML-tagged block (opening + closing tags), it is self-contained.  
If it's a fragment meant to be wrapped by the recipe's inline content, that's fine too — the build script performs simple text concatenation.

### 3.2 Recipe Files (`_recipes/*.yaml`)

Each recipe describes one output prompt.

```yaml
# _recipes/create-excel-column-from-ac.yaml

# Metadata
group: test-cases              # Used for section resolution order
output: "005 - Create excel column from AC example.md"  # Path relative to Prompt Library root

# Obsidian frontmatter (optional) — injected as YAML frontmatter in the output file
frontmatter:
  tags: ["QA", "Excel", "acceptance-criteria"]
  aliases: ["AC to Excel column"]
  # Any key-value pairs here are passed through to the output's YAML frontmatter

# Markdown structure of the output file
# Each entry becomes a section in the final Markdown note
structure:
  - instructions: |
      First, copy the Acceptance Criteria table into an empty Excel, clean it up
      and line up the Criteria with the filled cells/rows. And then paste it as
      CSV file in this prompt.

  - heading: "Prompt"
    level: 2                   # H2
    code_block:                # This heading gets a code block under it
      language: "xml"          # Code fence language tag
      parts:
        # Ordered list of content pieces to concatenate inside the code block
        - section: csv-input-placeholder       # resolved via group → shared
        - section: ac-to-checklist-task        # resolved via test-cases/
        - section: ac-checklist-example-output # resolved via test-cases/
        - user_input:                          # Empty tag for user to fill in
            tag: "csv_file"                    # Renders as <csv_file>\npaste here\n</csv_file>
            placeholder: "paste here"          # Optional hint text inside the tag
```

```yaml
# _recipes/bug-scribe-crm.yaml

# Metadata
group: bug-scribe              # Used for section resolution order
output: "Bug Report - CRM Project.md"  # Path relative to Prompt Library root

# Obsidian frontmatter (optional)
frontmatter:
  tags: ["QA", "bug-report", "CRM"]
  aliases: ["CRM Bug Scribe"]

# Markdown structure of the output file
structure:
  - heading: "Bug Scribe - CRM Project"
    level: 1                   # H1

  - heading: "Prompt"
    level: 2                   # H2
    code_block:                # This heading gets a code block under it
      language: "xml"          # Code fence language tag
      parts:
        # Ordered list of content pieces to concatenate inside the code block
        - section: severity-guidelines       # resolved via group → shared
        - section: environment-info          # resolved via group → shared
        - section: reproduction-steps        # resolved via group → shared
        - section: bug-template              # resolved via bug-scribe/
        - inline: |
            <project_context>
              <project>CRM Integration</project>
              <team>Backend Squad</team>
              <default_user_type>External Consultant</default_user_type>
              <jira_prefix>CRM</jira_prefix>
            </project_context>
        - inline: "#######"                  # Visual separator (rendered as-is inside code block)
        - user_input:
            tag: "prompt"                    # Renders as <prompt>\n\n</prompt>

  - heading: "Notes"
    level: 2
    body: |
      Remember to include screenshots when applicable.
      Attach relevant logs from the CRM middleware.
```

**Key design decisions in this format:**

- `structure` is an ordered list — it defines the Markdown output top-to-bottom.
- `parts` within a `code_block` are concatenated in order with a blank line (`\n\n`) as the default separator. Individual parts can override this with an optional `separator:` field (e.g., `separator: "\n"` for no blank line between this part and the next, or `separator: "\n\n\n"` for extra spacing). This is needed because existing prompts have inconsistent spacing between sections.
- `section:` references are resolved by name (without path or extension).
- `inline:` allows recipe-specific content without creating a dedicated section file. This includes non-XML content like hash separators (`#######`) that appear between sections in existing prompts. **Implementation note on YAML indentation:** YAML's `|` (literal block scalar) automatically strips leading indentation based on the first content line. For example, `inline: |` followed by 4-space-indented XML will produce content with 0 leading spaces. The decomposer must generate `inline:` blocks that account for this (indent content to the YAML nesting level, knowing YAML will strip it back). This is the expected YAML behavior, not a bug — but is a common source of "output doesn't match" issues during migration.
- `body:` under a heading places plain Markdown text (not in a code block).
- `instructions:` places human-facing preparation steps *before* the code block, rendered as a blockquote/callout (e.g., `> **Instructions for human:** ...`). These are workflow steps for the user, not content for the AI.
- `user_input:` marks an intentionally empty XML tag where the user pastes their input before copying the prompt. The `tag` field specifies the XML tag name; the optional `placeholder` field provides hint text inside it. If no placeholder is given, the tag renders with an empty line inside (e.g., `<prompt>\n\n</prompt>`).
- `frontmatter:` (optional, recipe-level) specifies Obsidian YAML frontmatter key-value pairs to inject at the top of the output file. This enables Obsidian-native features like search by tag, graph view clustering, Dataview queries, and alias-based linking. Common fields: `tags`, `aliases`, `cssclasses`.
- Multiple code blocks per file are supported by having multiple `code_block` entries under different headings. However, v1 targets a single code block per output file to match current prompt conventions.

### 3.3 Output Files

Generated Markdown files. The build script produces output with the following structure:

1. **Obsidian YAML frontmatter** (if `frontmatter:` is specified in the recipe).
2. **Auto-generated HTML comment** identifying the file as managed.
3. **Human instructions** (if `instructions:` is specified), rendered as a blockquote.
4. **Headings, code blocks, and body text** as defined by the recipe's `structure`.

**Code fence length:** All output code blocks use **9 backticks** (`` ````````` ``) as the fence delimiter. This is required because prompt content may contain inner code fences (e.g., double-fenced codeblock examples, markdown templates). Using 9 backticks guarantees no collision with any inner fence.

Example output:

```
---
tags: ["QA", "bug-report", "CRM"]
aliases: ["CRM Bug Scribe"]
---

<!-- AUTO-GENERATED by Prompt Library Maintainer. Do not edit manually. -->
<!-- Source recipe: _recipes/bug-scribe-crm.yaml -->
<!-- Rebuild: Ctrl+Shift+B or run python3 _build/build.py -->

# Bug Scribe - CRM Project

## Prompt

`````````xml
<severity_guidelines>
...
</severity_guidelines>

<environment_info>
...
</environment_info>

<project_context>
  ...
</project_context>
#######
<prompt>

</prompt>
`````````

## Notes

Remember to include screenshots when applicable.
Attach relevant logs from the CRM middleware.
```

Example output with human instructions (prompt 005 pattern):

```
---
tags: ["QA", "Excel", "acceptance-criteria"]
---

<!-- AUTO-GENERATED by Prompt Library Maintainer. Do not edit manually. -->
<!-- Source recipe: _recipes/create-excel-column-from-ac.yaml -->

> **Instructions for human:** First, copy the Acceptance Criteria table into
> an empty Excel, clean it up and line up the Criteria with the filled
> cells/rows. And then paste it as CSV file in this prompt.

`````````xml
<csv_file>
paste here
</csv_file>

<task>
...
</task>
`````````
```

---

## 4. Build Script (`build.py`)

### 4.1 Core Logic

```
For each .yaml recipe in _recipes/:
  1. Parse the YAML.
  2. Determine the group (for section resolution).
  3. If `frontmatter` is present: write YAML frontmatter block (--- delimited).
  4. Write the auto-generated comment header.
  5. For each entry in `structure`:
     a. If `instructions` is present: render as blockquote
        (prefix each line with `> `, prepend `> **Instructions for human:** `).
     b. If `heading` is present: write the Markdown heading.
     c. If `code_block` is present:
        - Open a fenced code block using 9 backticks with the specified language.
        - For each part:
          - If `section`: resolve and read the file, append content.
          - If `inline`: append the literal text.
          - If `user_input`: render as an XML tag with the specified `tag` name,
            containing the `placeholder` text or a blank line if no placeholder.
        - Close the fenced code block with 9 backticks.
     d. If `body` is present: write it as plain Markdown.
  6. Write the assembled content to the output path.
  7. Report what was generated.
  8. (v1.1) If any source files changed, auto-commit via version.py.
```

### 4.2 CLI Interface

```
python3 _build/build.py                    # Rebuild all recipes
python3 _build/build.py --recipe <name>    # Rebuild a single recipe
python3 _build/build.py --dry-run          # Show what would be generated without writing
python3 _build/build.py --check            # Verify all section references resolve (CI-friendly)
python3 _build/build.py --deps <section>   # Show which recipes use a given section
```

### 4.3 Error Handling

- **Missing section:** Fail loudly with the recipe name, the section name, and the directories searched.
- **Duplicate section names** across group and shared: warn, prefer group-specific (this is intentional — it allows overriding a shared section for a specific group).
- **Output file outside Prompt Library directory:** Refuse to write (safety check).

### 4.4 Integration with Obsidian

Trigger mechanism: **Shell Commands plugin** (community plugin, already available).

- Register command: `python3 /path/to/vault/Prompt Library/_build/build.py`
- Bind to hotkey: `Ctrl+Shift+B` (or whatever is comfortable).
- Obsidian auto-detects file changes on disk, so output files update immediately in the sidebar and editor.

---

## 5. Decompose Script (`decompose.py`)

### 5.1 Purpose

Bootstrap the system from existing complete prompts. Takes a finished prompt Markdown file and produces:
- A set of candidate section files in `_sections/{group}/`.
- A draft recipe in `_recipes/`.

### 5.2 Approach

Since prompts are already structured with Markdown headings and XML-in-code-blocks, the decomposition can be largely structural:

```
1. Parse the Markdown:
   - Identify text before the code block. If present, treat it as `instructions:`
     content (human-facing preparation steps).
   - Identify headings (levels, text).
   - Identify fenced code blocks (language tag, content). Note: existing prompts
     use 9-backtick fences — the parser must handle variable fence lengths.
   - Identify non-code body text.

2. Within each code block, identify top-level XML sections:
   - Split on top-level XML tags (e.g., <severity_guidelines>...</severity_guidelines>).
   - Each top-level tag block becomes a candidate section file.
   - Name the file after the tag name (e.g., severity-guidelines.md).

   IMPORTANT — Non-XML content handling:
   - Not all content inside code blocks is XML. Prompts may contain:
     - Hash separators (e.g., `#######`) used as visual dividers.
     - Plain text between XML sections (e.g., "TEMPLATE (use this exact structure...)").
     - Empty XML tags intended as user input areas (e.g., <prompt>\n\n</prompt>).
   - Hash separators and plain text → emit as `inline:` parts in the recipe.
   - Empty/near-empty XML tags (e.g., <prompt></prompt>, <csv_file>paste here</csv_file>,
     <excel_input>\n\n</excel_input>) → emit as `user_input:` parts in the recipe
     with the tag name and any placeholder text extracted.
   - The decomposer must NOT silently drop non-XML content. Any content that
     doesn't parse as a top-level XML block should be preserved as `inline:`.

3. Generate the recipe YAML:
   - Map the heading structure.
   - Reference each extracted section by name.
   - Map `instructions:` text if found before the code block.
   - Map `user_input:` entries for empty input tags.
   - Leave inline content for anything that doesn't cleanly split into a tag block.

4. Interactive section placement:
   For each candidate section, prompt the user to specify the target group folder
   (e.g., `shared`, `bug-scribe`, `test-cases`). Then:
   a. If the group folder doesn't exist → create it under `_sections/`.
   b. If the group folder exists but no file with this name exists → write the
      section file into the group folder.
   c. If a file with this name already exists in the target folder → compare
      content:
      - If identical: reuse the existing section reference in the recipe.
      - If different: show a diff and ask the user whether to:
        (i) overwrite the existing file,
        (ii) keep the existing file and point the recipe at it, or
        (iii) save under an alternative name (prompted).
   d. If the section already exists in `shared/` and the user chooses a
      group-specific folder, note that the group-specific version will
      override shared (per §2.2 resolution order). Confirm this is intentional.
```

### 5.3 CLI Interface

```
python3 _build/decompose.py "Bug Report - CRM Project.md" --group bug-scribe
```

The `--group` flag sets the default group folder for sections. During interactive placement, the user can override this per-section (e.g., directing shared sections to `shared/` instead).

### 5.4 Deduplication Across Imports

When importing a second prompt from the same group:
- Compare each candidate section against existing files in `_sections/` (all group folders + shared).
- If content matches an existing section: reuse the reference, don't create a duplicate.
- If content is different: the interactive placement flow (§5.2 step 4c) handles the conflict.

---

## 6. Git Version Control (`version.py`) — v1.1

### 6.1 Scope and Repository Strategy

The git layer versions the **source files only**: `_sections/` and `_recipes/`. Output files are regenerated from source and do not need independent versioning.

**Repository decision (agent must resolve during discovery):**
- If the Obsidian vault already has a `.git/` repo, use it — the Prompt Library files are just part of the vault's history. Configure a `.gitignore` to exclude output files if desired.
- If the vault has no git history, initialize a repo scoped to the Prompt Library directory only.

### 6.2 Auto-Commit on Build

Every successful `build.py` run that detects changes in `_sections/` or `_recipes/` since the last commit should:

1. Run `git diff --stat` and capture the summary.
2. Stage all changed files in `_sections/` and `_recipes/`.
3. Commit with an auto-generated message:

```
[prompt-library] Rebuild: 2 sections changed

Modified:
  _sections/shared/severity-guidelines.md
  _recipes/bug-scribe-crm.yaml
```

4. Print the diff summary to the console so the user knows what was versioned.

If there are no changes since the last commit, skip silently.

### 6.3 Per-Section History

The version module exposes a function to retrieve the change history of a single section file:

```python
def section_history(section_path: str, max_entries: int = 20) -> list[dict]:
    """
    Returns a list of dicts, each containing:
      - commit_hash: short hash
      - date: human-readable date
      - message: commit message
      - diff_preview: first N lines of the diff for this file in that commit
      - tags: any git tags on this commit relevant to the section's recipes
    """
```

This powers both the CLI and the web UI. Under the hood it's `git log --follow -- <path>` with `git diff <hash>~1 <hash> -- <path>` for the diff preview.

### 6.4 Per-Section Rollback

Rolling back a section means restoring a single file to an earlier version, then rebuilding.

```python
def rollback_section(section_path: str, target_hash: str) -> dict:
    """
    1. Identify which recipes reference this section (impact analysis).
    2. git checkout <target_hash> -- <section_path>
    3. Run build.py to regenerate affected outputs.
    4. Auto-commit with message: "[prompt-library] Rollback: severity-guidelines.md → <short_hash>"
    5. Return a summary of what was rolled back and which outputs changed.
    """
```

**Impact analysis is critical.** Before executing the rollback, the system must show the user which recipes (and therefore which output prompts) will be affected. The web UI presents this as a confirmation step; the CLI prints it and requires a `--confirm` flag.

### 6.5 Stable Version Tagging

Tags mark "known-good" states. When a user has verified that a prompt produces quality output, they can tag the current state:

```python
def tag_stable(recipe_name: str, label: str = None) -> str:
    """
    Creates a git tag on the current commit.
    Format: stable/{recipe_name}/{label_or_timestamp}
    Example: stable/bug-scribe-crm/2026-03-25
    """
```

Tags serve two purposes:
- **Quick rollback target**: "revert to last stable" becomes a single action — find the most recent `stable/{recipe}/*` tag and rollback to that commit.
- **Safety net**: before making risky edits to a shared section, tag all affected recipes as stable first.

### 6.6 CLI Interface (v1.1)

```
python3 _build/version.py history <section-name>              # Show version history
python3 _build/version.py rollback <section-name> <hash>      # Rollback (requires --confirm)
python3 _build/version.py rollback <section-name> --to-stable  # Rollback to last stable tag
python3 _build/version.py tag <recipe-name> [label]           # Tag current state as stable
python3 _build/version.py tags                                 # List all stable tags
python3 _build/version.py diff <section-name> [hash]          # Show diff vs current
```

These commands are the fallback interface. The primary interface for non-git-savvy users is the web UI described in §7.

---

## 7. Web UI (`server.py`) — v1.1

### 7.1 Purpose

A local-only Flask web interface that provides visual management of the Prompt Library without requiring any git knowledge. The user interacts with buttons, dropdowns, and diffs rendered as HTML — never with git commands.

### 7.2 Technical Stack

- **Backend:** Flask (Python, same environment as build.py — no additional runtime).
- **Frontend:** Server-rendered HTML via Jinja2 templates. Minimal JavaScript for interactive elements (diff toggle, confirmation modals). No frontend build step, no npm.
- **Runs at:** `localhost:5111` (configurable in `config.yaml`).
- **Lifecycle:** Started manually via `python3 _build/server.py` or via a Shell Commands hotkey in Obsidian. Lightweight enough to leave running in the background.

### 7.3 Obsidian Integration via Custom Frames

The **Custom Frames** community plugin allows embedding arbitrary web pages as Obsidian panes. Configuration:

```yaml
# Custom Frames plugin settings
- name: "Prompt Library Manager"
  url: "http://localhost:5111"
  addRibbonIcon: true
  openInCenter: false          # Opens as a sidebar pane
  displayName: "Prompt Mgr"
```

This gives the user a sidebar panel inside Obsidian that shows the full web UI. It's not native, but it's visually integrated and doesn't require switching windows.

### 7.4 UI Pages and Features

#### 7.4.1 Dashboard (`/`)

Overview of the Prompt Library state:

- **Section count** and **recipe count**.
- **Last build timestamp**.
- **Uncommitted changes**: list of sections/recipes modified since last build (shows a "Rebuild Now" button if any exist).
- **Recent activity**: last 10 commits with their messages.
- Quick-action buttons: "Rebuild All", "Tag All as Stable".

#### 7.4.2 Sections Browser (`/sections`)

List of all sections, grouped by directory (`shared/`, `bug-scribe/`, etc.):

- Each section shows: filename, last modified date, number of recipes that use it.
- Click a section → Section Detail page.
- Visual indicator if a section has uncommitted changes.

#### 7.4.3 Section Detail (`/sections/<group>/<name>`)

Single-section management view:

- **Current content**: rendered in a read-only code viewer with syntax highlighting.
- **Version history**: list of past versions (date, commit message, diff preview). Each entry has:
  - "View Full Diff" button → expands inline diff.
  - "Rollback to This Version" button → triggers confirmation flow.
- **Impact panel**: which recipes use this section (always visible, so the user understands rollback scope).
- **Stable tags**: if any commits are tagged stable for recipes using this section, they're highlighted in the history.

#### 7.4.4 Rollback Confirmation (`/sections/<group>/<name>/rollback/<hash>`)

Before executing a rollback, this page shows:

- Side-by-side diff: current version vs. the version being rolled back to.
- List of affected recipes and their output filenames.
- A prominent "Confirm Rollback" button and a "Cancel" link.
- After confirmation: execute the rollback, rebuild, auto-commit, and redirect to the Section Detail page with a success banner.

#### 7.4.5 Recipes Browser (`/recipes`)

List of all recipes:

- Recipe name, output filename, section count, last build date.
- Click → Recipe Detail page.

#### 7.4.6 Recipe Detail (`/recipes/<name>`)

- **Sections used**: ordered list with links to each section's detail page.
- **Stable tags**: list of tagged stable versions for this recipe, with "Rollback to This Stable Version" buttons.
- **"Tag as Stable" button**: tags the current commit for this recipe.
- **Preview**: show the fully assembled output prompt (read-only).

#### 7.4.7 Build & Diff View (`/build`)

- "Rebuild All" and "Rebuild Single Recipe" (dropdown) buttons.
- **Pre-build diff**: before rebuilding, show what changed since the last build (equivalent to `git diff --stat` but human-readable).
- **Build log**: after rebuilding, show which output files were regenerated and the auto-commit message.

### 7.5 UI Design Principles

- **No git terminology exposed.** The UI says "versions," "history," "revert," and "mark as stable" — never "commit," "checkout," "tag," or "hash." Commit hashes are used internally but displayed as dates or short labels.
- **Confirmation before destructive actions.** Rollbacks always show a diff and affected recipes before executing.
- **Minimal dependencies.** The UI should work with Flask + Jinja2 + a classless CSS framework (e.g., Simple.css or Pico.css). No React, no build tools.
- **Responsive enough for a sidebar pane.** Since it may be rendered in a narrow Obsidian sidebar via Custom Frames, the layout should be functional at ~350px width.

---

## 8. Design Considerations for Future Versions

### 8.1 Template Sections and Natural-Language Comments

Some existing prompts include a `<template>` section that mixes verbatim text (to be output as-is by the consuming Assistant) with natural-language comments in `/* ... */` notation. These comments are instructions to the Assistant about what *not* to include verbatim.

**Current status:** This pattern is handled entirely within the section content — the build system treats it as opaque text and passes it through unchanged. No special processing needed in v1.

**Future potential:** The recipe format could be extended to support parameterized templates:

```yaml
parts:
  - section: bug-template
    template_vars:
      field_to_fill: "Description of what goes here"
      optional_note: "/* Only include if the bug involves API calls */"
```

This would allow a single `bug-template.md` section to serve multiple projects with different placeholder guidance. The mechanism is analogous to how `inline:` works but applied *within* a section file using markers (e.g., `{{field_to_fill}}`).

**Decision:** Capture this as a documented extension point. Do not implement in v1, but ensure the recipe format doesn't preclude it (i.e., `parts` entries should be dicts, not plain strings, so additional keys can be added).

### 8.2 Conditional Sections

Some prompts may need sections included or excluded based on context:

```yaml
parts:
  - section: api-specific-info
    condition: "project_type == 'api'"
```

Not needed now, but the `parts` list structure supports adding this without breaking changes.

### 8.3 File-Watcher Auto-Rebuild

Via Shell Commands plugin event triggers or an external file-watcher (e.g., `watchdog` Python package), the build could be triggered automatically on save of any file in `_sections/` or `_recipes/`. Low priority — the hotkey is sufficient.

### 8.4 Quality Evaluation Hooks (v2)

Once versioning is in place, the infrastructure exists to add automated quality checks:

- After rebuilding, optionally submit the assembled prompt to an LLM with a known test input.
- Compare the output against a saved reference response.
- Flag regressions before tagging as stable.

This is a significant scope increase and depends on API access. Documented here as a future direction, not a near-term commitment.

### 8.5 Non-XML Prompt Language Support

The current system exclusively handles XML-based structured prompts. Some future prompt styles may use JSON, YAML, or other structured formats inside code blocks. The architecture accommodates this:

- The `language` field in `code_block` already supports arbitrary values.
- Section files are language-agnostic (plain text).
- The decomposer's XML-tag splitting logic (§5.2) would need a parser per language.

**Priority:** Low. Not expected to be needed. Documented here so the architecture doesn't accidentally preclude it.

### 8.6 Native Obsidian Plugin (v2)

If the Flask + Custom Frames approach proves insufficient (e.g., the sidebar embedding is too limiting, or the extra running process is annoying), a native Obsidian plugin could replace the web UI entirely. The plugin would call the same Python scripts via child processes, so the backend logic remains unchanged — only the frontend moves from HTML to Obsidian's UI framework (TypeScript + Obsidian API).

Estimated effort: 30–50 hours. Only pursue if v1.1 reveals clear UX gaps that can't be solved within the web UI.

---

## 9. Agent Instructions — Implementation Plan

### Phase 0: Discovery

1. Explore the vault's Prompt Library directory. Catalog:
   - All existing prompt files (names, paths).
   - The Markdown structure of each (heading levels, code block count and language).
   - Within code blocks: the top-level XML tags used.
2. Diff the bug-scribe prompts against each other. Identify:
   - Identical sections (candidates for `shared/` or `bug-scribe/`).
   - Sections that differ only in project-specific values (candidates for `inline:` or future template vars).
   - Sections unique to a single prompt.
3. Check for existing `.git/` in the vault. Note current git state if present.
4. Document findings before writing any code.

### Phase 1: Core Build System (v1)

1. Create the directory structure (`_build/`, `_sections/`, `_recipes/`, `_reference/`).
2. Implement `build.py` with the core logic described in §4.
3. Manually create one recipe + its sections from an existing prompt.
4. Verify the output against the original prompt using a two-tier approach:
   - **Code block content:** must match exactly (byte-level diff of everything inside the 9-backtick fences). This is the prompt payload — any discrepancy means the build is wrong.
   - **Surrounding Markdown structure:** verify structural correctness (headings, frontmatter, instructions blockquote) but accept intentional format differences from the original. The migration adds frontmatter, reformats human instructions as blockquotes, and standardizes fence length — these are deliberate changes, not errors.

### Phase 2: Decompose Tool (v1)

1. Implement `decompose.py` as described in §5.
2. Run it on one existing prompt; compare its output recipe+sections against the manually created ones from Phase 1.
3. Run it on remaining prompts; review deduplication behavior.

### Phase 3: Full Migration (v1)

1. Decompose all existing managed prompts.
2. Review and organize sections (move shared ones to `shared/`, group-specific to their group directory).
3. Rebuild all and verify code block content matches originals exactly (same two-tier verification as Phase 1 step 4).
4. Move reference material (e.g., format examples, non-prompt files) to `_reference/`.
5. Set up the Shell Commands hotkey.

### Phase 4: Git Integration (v1.1)

1. Implement `version.py` with the functions described in §6.
2. Initialize git repo (or configure existing one) with appropriate `.gitignore`.
3. Hook auto-commit into `build.py`.
4. Create an initial commit capturing all current sections and recipes as the baseline.
5. Test the full cycle: edit a section → rebuild → verify auto-commit → rollback via CLI → verify rebuild.

### Phase 5: Web UI (v1.1)

1. Implement `server.py` with Flask, starting with the dashboard and sections browser.
2. Add section detail page with version history and diff rendering.
3. Add rollback confirmation flow.
4. Add recipe browser and detail pages.
5. Add build trigger and diff view.
6. Configure Custom Frames plugin in Obsidian to embed the UI.
7. End-to-end test: edit a section in Obsidian → rebuild via web UI → review history → tag as stable → make a bad edit → rollback via web UI → verify restoration.

### Phase 6: Iteration

1. Address edge cases found during real usage.
2. Evaluate extension points from §8 based on actual needs.

---

## 10. Open Questions

> These should be resolved during Phase 0 discovery or through discussion before implementation.

- [ ] **Vault path:** Where exactly does the Prompt Library live within the Obsidian vault? Is it a top-level folder or nested? *(Placeholder — to be filled by user.)*

### 10.1 Resolved Questions

The following questions from the original spec have been resolved through discussion:

- [x] **Code block language tags:** All prompts use `xml`. The system targets XML-based structured prompts only. Other structured language styles (e.g., JSON, YAML prompts) are a low-priority future consideration — the architecture should not preclude them but v1 does not implement support.
- [x] **Multiple code blocks per prompt:** v1 targets a single 9-backtick code block per output file, matching current conventions. The `instructions:` field handles pre-code-block text.
- [x] **Non-managed prompts:** All prompts go through the recipe system, even trivial ones (ensures future extensibility). Reference material (non-prompt files like format examples) lives in `_reference/` and is not managed by the build system.
- [x] **Section naming conflicts:** Handled interactively during decomposition (§5.2 step 4). During build, the resolution order (group-specific first, then shared) handles runtime conflicts — the build script should warn when a group-specific section shadows a shared one with the same name.
- [x] **Obsidian metadata:** Output files support optional YAML frontmatter via the recipe's `frontmatter:` field (§3.2). This enables tags, aliases, cssclasses, and other Obsidian-native features.
- [x] **Existing git state:** No existing `.git/` repo. Will be initialized during build system setup.
- [x] **Custom Frames plugin:** User will install it — no blockers.
- [x] **Flask server lifecycle:** Manual start is acceptable for v1.1.
