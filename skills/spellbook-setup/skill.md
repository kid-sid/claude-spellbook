---
name: spellbook-setup
description: Use when installing claude-spellbook for the first time, setting up skills/agents/commands globally or into a specific project, registering the memory_map MCP server, enabling lifecycle hooks, or migrating an existing install to a new machine.
---

# Claude Spellbook Setup

Install and configure claude-spellbook — globally (all projects) or scoped to one project.

## When to Activate

- Installing claude-spellbook on a new machine or for a new user
- Deciding between global and project-level skill/agent install
- Setting up the memory_map MCP server for persistent memory
- Enabling auto-format, safety, and history hooks in `settings.json`
- Adding spellbook skills/commands to a single project without touching global config
- Verifying or repairing an existing spellbook install

## Prerequisites

| Requirement | Check |
|---|---|
| Claude Code CLI | `claude --version` |
| Git | `git --version` |
| Python 3.9+ (for memory_map) | `python --version` or `python3 --version` |

## Clone the Repo

```bash
git clone https://github.com/kid-sid/claude-spellbook.git
cd claude-spellbook
```

## Global Install (Recommended)

Global install puts skills, agents, and commands into `~/.claude/` so they are available in **every project** without any per-project steps.

### Step 1 — Skills

```bash
# All skills (recommended — they activate on-demand, no overhead)
cp -r skills/* ~/.claude/skills/

# Single skill
cp -r skills/security ~/.claude/skills/
```

### Step 2 — Agents

```bash
cp -r .claude/agents/* ~/.claude/agents/
```

### Step 3 — Slash Commands

```bash
cp -r .claude/commands/* ~/.claude/commands/
```

### Step 4 — memory_map MCP Server

```bash
# Install from PyPI — bundles the OpenAI client for semantic history search
pip install "memory-map-mcp[embed-openai]"

# Base install — works fine if you stick with local embeddings or BM25 only
# pip install memory-map-mcp
```

Set the MongoDB URI (required for history; key-value memory falls back to a local file):

```bash
# Mac/Linux — add to ~/.zshrc or ~/.bashrc
export MEMORY_MAP_MONGO_URI="mongodb+srv://<user>:<password>@<cluster>.mongodb.net"

# Windows PowerShell — add to $PROFILE
$env:MEMORY_MAP_MONGO_URI = "mongodb+srv://<user>:<password>@<cluster>.mongodb.net"
```

Register globally:

```bash
claude mcp add -s user memory_map -- memory-map-mcp
```

Verify registration:

```bash
claude mcp list
```

See `skills/memory-map/skill.md` for full setup (vector search, env vars, troubleshooting).

### Step 5 — Lifecycle Hooks

Add to `~/.claude/settings.json` (create if absent). The `memory-map-hook` entry point is installed by the pip package — no need for absolute paths.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "matcher": "", "hooks": [{ "type": "command", "command": "memory-map-hook", "timeout": 10 }] }
    ],
    "PreCompact": [
      { "matcher": "", "hooks": [{ "type": "command", "command": "memory-map-hook --force", "timeout": 15 }] }
    ],
    "Stop": [
      { "matcher": "", "hooks": [{ "type": "command", "command": "memory-map-hook --force", "timeout": 15, "async": true }] }
    ]
  }
}
```

### Step 6 — Global CLAUDE.md (Optional)

Append to `~/.claude/CLAUDE.md` to load memory in every project:

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `suggest_history` with the current working directory and the user's first message
3. Read both outputs before exploring files or asking questions
```

---

## Project-Level Install

Project-level keeps spellbook assets inside one repo. Use this when: the team shares a specific subset of skills, you want version-controlled agents per repo, or you can't modify global config.

### Skills (project-scoped)

```bash
# All skills
cp -r /path/to/claude-spellbook/skills/* .claude/skills/

# Selected skills only
mkdir -p .claude/skills
cp -r /path/to/claude-spellbook/skills/security .claude/skills/
cp -r /path/to/claude-spellbook/skills/api-design .claude/skills/
```

### Agents and Commands

```bash
mkdir -p .claude/agents .claude/commands
cp /path/to/claude-spellbook/.claude/agents/* .claude/agents/
cp /path/to/claude-spellbook/.claude/commands/* .claude/commands/
```

### Project Hooks

```bash
# Copy spellbook's hooks config into the project (review before committing)
cp /path/to/claude-spellbook/.claude/settings.local.json .claude/settings.local.json
```

`settings.local.json` enables auto-format on write/edit, bash command logging, and safety guards. Add to `.gitignore` if the hooks reference local paths; commit if they are path-agnostic.

### Tool Configs

```bash
# Install formatter/linter configs for one language
bash /path/to/claude-spellbook/tools/install.sh python --target .
bash /path/to/claude-spellbook/tools/install.sh typescript --target .

# All languages
bash /path/to/claude-spellbook/tools/install.sh all --target .
```

Or via Makefile:

```bash
make setup TARGET=. LANG=python
```

### Per-Project Memory (CLAUDE.md)

Add this block to `CLAUDE.md` at the project root (create the file if absent):

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `suggest_history` with the current working directory and the user's first message
3. Read both outputs before exploring files or asking questions
```

Commit `CLAUDE.md` so all teammates get session-start memory loading.

---

## Scope Decision Matrix

| Goal | Global | Project |
|---|---|---|
| Use skills in all your projects | ✓ | — |
| Share agents with the whole team | — | ✓ (commit `.claude/agents/`) |
| Keep skills out of the repo | ✓ | — |
| Audit/pin agent versions per project | — | ✓ |
| Memory + history in every project | ✓ (hooks + global MCP) | — |
| One-off test of a new skill | — | ✓ |
| Personal MCP server (private API keys) | ✓ (`-s user`) | — |
| Shared MCP server (team tooling) | — | ✓ (`-s project`) |

---

## Verify the Install

```bash
# Skills are visible
ls ~/.claude/skills/         # global
ls .claude/skills/           # project

# Agents are visible
ls ~/.claude/agents/         # global
ls .claude/agents/           # project

# Commands are visible
ls ~/.claude/commands/       # global
ls .claude/commands/         # project

# MCP server is registered
claude mcp list

# Hooks are present
cat ~/.claude/settings.json  # look for "hooks" key
```

Open a new Claude Code session and describe a task — the relevant skill should activate automatically (no manual invocation needed).

---

## Updating

```bash
cd claude-spellbook
git pull

# Re-copy to overwrite outdated files
cp -r skills/* ~/.claude/skills/
cp -r .claude/agents/* ~/.claude/agents/
cp -r .claude/commands/* ~/.claude/commands/
```

Skills and agents are plain markdown — no restart required after updating.

---

## Red Flags

- **Registering memory_map with `-s project` instead of `-s user`** — project-scoped MCP servers are stored in `.claude/mcp.json` and apply to everyone who clones the repo; memory_map uses local paths that differ per machine; always register with `-s user`
- **Copying `settings.local.json` into a shared repo without reviewing paths** — hooks may reference absolute paths to local formatters or scripts; paths that exist on your machine may not exist on a teammate's; audit every `command` value before committing
- **Installing all 50+ skills globally then wondering why context is slow** — skills are loaded on-demand by description matching, not all at once; installing everything globally has no performance cost; if load times feel slow, the issue is elsewhere (large CLAUDE.md, slow MCP server)
- **Omitting CLAUDE.md in a project after setting up memory_map** — without CLAUDE.md, Claude won't call `load_memory` at session start even if the MCP server is registered; the file is what triggers the session setup routine
- **Using hardcoded Windows paths in hooks for a cross-platform team** — `C:/Users/yourname/...` hooks break on Mac/Linux; either use relative paths, an env var (`$HOME`), or keep lifecycle hooks in `~/.claude/settings.json` (personal) rather than `.claude/settings.json` (shared)
- **Not gitignoring `.claude/settings.local.json`** — this file is for personal overrides and local tool paths; committing it forces your local paths onto teammates; add it to `.gitignore`
- **Forgetting to add a `timeout` to hooks** — a hook that hangs (e.g., slow Python startup, network call) blocks Claude Code indefinitely; every hook command must have `"timeout": N`

---

## Checklist

- [ ] `claude --version` confirms Claude Code is installed
- [ ] Repo cloned: `git clone https://github.com/kid-sid/claude-spellbook.git`
- [ ] Skills copied to `~/.claude/skills/` (global) or `.claude/skills/` (project)
- [ ] Agents copied to `~/.claude/agents/` or `.claude/agents/`
- [ ] Slash commands copied to `~/.claude/commands/` or `.claude/commands/`
- [ ] `pip install memory-map-mcp` succeeded; `memory-map-mcp` is on PATH
- [ ] `MEMORY_MAP_MONGO_URI` exported in shell profile
- [ ] memory_map registered: `claude mcp list` shows `memory_map`
- [ ] Lifecycle hooks added to `~/.claude/settings.json` with `timeout` values
- [ ] `CLAUDE.md` present at project root with the session-setup block
- [ ] `.claude/settings.local.json` added to `.gitignore` if hooks use local paths
- [ ] Tool configs installed for the project's language stack
- [ ] New Claude Code session opened — a relevant skill activates automatically on first task
