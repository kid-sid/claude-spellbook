# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with `C:\Users\Sidhartha\claude-spellbook`
2. Call `load_history` with `C:\Users\Sidhartha\claude-spellbook`
3. Read both outputs — they contain saved context and conversation history
4. Do not explore files or ask clarifying questions that memory already answers

Save or update memory entries whenever you learn something worth keeping across sessions.
If something loaded from memory is no longer accurate, update it with `save_memory` using the same key.
Use short, lowercase keys: `stack`, `current_work`, `gotchas`, `key_files`, etc. Keep values concise — one or two sentences max.

---

## Repository Layout

```
skills/<skill-name>/skill.md     — skill reference files (install to ~/.claude/skills/)
.claude/agents/<name>.md         — autonomous subagents (install to ~/.claude/agents/)
.claude/commands/<name>.md       — slash commands (install to ~/.claude/commands/)
tools/<lang>/                    — drop-in linter/formatter configs for 6 languages
templates/                       — scaffold starters
```

---

## Development Commands

```bash
make install      # Install Node + Python linting tools locally (copies from tools/ into root)
make check        # Check which linting tools are available on your PATH
make format       # Run prettier over all skill markdown files
make lint         # Run markdownlint over all skill markdown files
make help         # List all make targets

# Install tool configs into another project
make setup TARGET=/path/to/project LANG=typescript
bash tools/install.sh python --target /path/to/project
```

There are no automated tests — validation is done by the CI workflows in `.github/workflows/ci.yml`. CI checks run on every push and PR to `main`.

---

## CI Validation Rules

Every `skills/*/skill.md` must pass these checks or CI fails:

- First line is `---` (frontmatter open)
- Has `name:` field in frontmatter
- Has `description:` field in frontmatter
- Has a `## When to Activate` section
- Has a `## Checklist` section with at least one `- [ ]` item

`.claude/commands/*.md` files must be non-empty.

---

## Skill File Format

Every skill follows this exact structure — enforced by CI:

```markdown
---
name: <kebab-case matching folder name>
description: Use when <triggering conditions — NOT a summary of topics>
---

# Title

One-sentence intro.

## When to Activate
- Verb-leading trigger condition (6–8 items)

## Content Sections (## and ###)

## Red Flags
- **Anti-pattern name** — why it's wrong and what to do instead (6–10 items)

## Checklist
- [ ] 8–15 items, "before you ship" perspective
```

**Description discipline:** The `description` field must start with `Use when` and list triggering conditions only. Topic summaries cause auto-activation to fail.

**Code examples:**
- Language-agnostic topics: show Python, TypeScript, and Go as siblings
- Tool-specific content (GitHub Actions, Terraform, Dockerfile): native syntax only
- Anti-patterns: `# BAD` / `# GOOD` pairs in the same code block
- Every skill must have at least one decision/comparison table

**Style:** No meta-commentary. No filler prose. Tables for decision matrices. Checklists close every skill.

---

## Agent File Format

```markdown
---
name: kebab-case-name
description: <one sentence — when to delegate to this agent vs. using a slash command>
tools: Read, Grep, Glob, Bash   # minimum required; omit to inherit all
model: sonnet                   # sonnet | opus | haiku | inherit
color: red                      # optional: red | blue | green | yellow | purple | orange
---

System prompt in second person ("You are a…").
```

Agents run in an isolated context window — they do not see the parent session history. Restrict `tools` to the minimum needed (a read-only audit agent must not have `Write` or `Edit`).

---

## Conventions

**Editing skills:** Read `skills/api-design/skill.md` and `skills/claude-api/skill.md` first — they are the canonical format and density reference. Keep skills focused: one domain per file, no overlap with adjacent skills.

**Adding a skill:** Create `skills/<name>/skill.md`, add it to the inventory in both `CLAUDE.md` and `README.md`, open a PR (CI validates format automatically).

**Adding an agent:** Create `.claude/agents/<name>.md`, restrict `tools` to the minimum needed, include a clear output format in the system prompt, add to the Agent Inventory table in both `CLAUDE.md` and `README.md`.

**Skill inventory** is in `README.md`. To see all skills: `Glob skills/*/skill.md`.
