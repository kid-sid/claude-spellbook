---
name: claude-code
description: Claude Code setup and customization covering skills, slash commands, agents, hooks (PreToolUse/PostToolUse/SessionStart/Stop), settings.json permissions, MCP server registration, CLAUDE.md project instructions, and IDE integration.
---

# Claude Code Setup

Configuration and customization reference for Claude Code — skills, commands, agents, hooks, permissions, and MCP servers.

## When to Activate

- Setting up skills, slash commands, or agents in a new project or globally
- Writing or debugging hook configurations in `settings.json`
- Configuring tool permissions to reduce approval prompts
- Registering or troubleshooting an MCP server
- Writing `CLAUDE.md` project instructions
- Asking how Claude Code loads context or resolves settings
- Integrating Claude Code with VS Code or JetBrains

## Directory Layout

```
~/.claude/                        # global — applies to all projects
├── settings.json                 # global permissions, hooks, env vars
├── CLAUDE.md                     # global instructions read at every session
├── skills/
│   └── <name>/skill.md           # or <name>.md (flat)
├── agents/
│   └── <name>.md
└── commands/
    └── <name>.md

<project>/
├── CLAUDE.md                     # project instructions (commit this)
└── .claude/
    ├── settings.json             # project permissions + hooks (commit this)
    ├── settings.local.json       # personal overrides (gitignore this)
    ├── skills/                   # project-scoped skills
    ├── agents/                   # project-scoped agents
    └── commands/                 # project-scoped commands
```

Settings are merged: `settings.local.json` overrides `.claude/settings.json` overrides `~/.claude/settings.json`.

## Skills

Skills are markdown files that Claude loads contextually when the task matches.

### File Format

```markdown
---
name: my-skill
description: One keyword-dense sentence used for activation matching.
---

# Title

One-sentence intro.

## When to Activate
- Verb-leading trigger condition
- Another trigger condition

## Content sections…

## Checklist
- [ ] At least one item
```

### Installation

```bash
# Single skill (global)
cp -r skills/my-skill ~/.claude/skills/

# All skills from a library
cp -r skills/* ~/.claude/skills/

# Project-scoped (available only in this project)
cp -r skills/my-skill .claude/skills/
```

### How Skills Load

Claude matches the task description against the `description` frontmatter field and the `## When to Activate` bullet points. No manual invocation needed — skills activate automatically. The `name` field must match the folder name (or file stem for flat layout).

## Slash Commands

Slash commands are prompt templates invoked with `/command-name` in the Claude Code prompt.

### File Format

```markdown
Do the thing the user asked.

## Instructions

1. First step — use `$ARGUMENTS` for any text the user typed after the command name
2. Second step
3. Output format…
```

`$ARGUMENTS` is replaced with everything the user typed after the command name:
```
/my-command foo bar   →   $ARGUMENTS = "foo bar"
/my-command           →   $ARGUMENTS = ""
```

### Examples

```markdown
<!-- .claude/commands/summarize.md -->
Summarize the file at $ARGUMENTS.

Read the file, identify the top 3 key points, and return them as a numbered list.
Each point should be one sentence.
```

```markdown
<!-- .claude/commands/fix-issue.md -->
Fix GitHub issue #$ARGUMENTS in this repository.

1. Run `gh issue view $ARGUMENTS` to read the issue
2. Find the relevant code
3. Implement the fix
4. Write or update tests
5. Summarize what changed
```

### Installation

```bash
# Global (available in all projects)
cp .claude/commands/my-command.md ~/.claude/commands/

# Project-only (stays in this repo)
# Already in .claude/commands/ — no copy needed
```

## Agents

Agents run in an isolated context window with their own tool set and system prompt.

### File Format

```markdown
---
name: my-agent
description: Use this agent when… (triggers auto-delegation)
tools: Read, Grep, Glob, Bash
model: sonnet
color: blue
---

You are a … agent. Your job is to …

## Methodology
Step-by-step approach…

## Output Format
What the agent should return…
```

### Frontmatter Fields

| Field | Values | Notes |
|---|---|---|
| `name` | kebab-case string | Must match filename stem |
| `description` | One sentence | Controls when Claude auto-delegates — write as "Use this agent when…" |
| `tools` | Comma-separated tool names | Omit to inherit all tools; restrict for read-only agents |
| `model` | `sonnet`, `opus`, `haiku`, `inherit` | `inherit` uses the parent session's model |
| `color` | `red` `blue` `green` `yellow` `purple` `orange` | UI accent only |

### Available Tools

```
Read, Write, Edit, Bash, Glob, Grep,
WebFetch, WebSearch,
Agent, TaskCreate, TaskUpdate, TaskList,
NotebookEdit
```

Principle of least privilege: a read-only audit agent should declare `tools: Read, Grep, Glob, Bash` — no `Write` or `Edit`.

### Installation

```bash
# Global
cp .claude/agents/my-agent.md ~/.claude/agents/

# Project-only
# Already in .claude/agents/ — committed with the repo
```

## Hooks

Hooks run shell commands automatically in response to Claude Code events.

### Settings Structure

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolName",
        "hooks": [
          {
            "type": "command",
            "command": "shell command here",
            "timeout": 10,
            "async": false
          }
        ]
      }
    ]
  }
}
```

### Hook Events

| Event | When it fires | Matcher targets |
|---|---|---|
| `SessionStart` | Once at session open | Empty string `""` |
| `UserPromptSubmit` | Every time user submits a message | Message content substring |
| `PreToolUse` | Before a tool call executes | Tool name |
| `PostToolUse` | After a tool call completes | Tool name |
| `PreCompact` | Before context window compaction | Empty string `""` |
| `Stop` | When Claude finishes a turn | Empty string `""` |

### Hook Environment Variables

| Variable | Available in | Value |
|---|---|---|
| `$CLAUDE_FILE_PATH` | `Write`, `Edit` hooks | Absolute path of the file |
| `$CLAUDE_TOOL_NAME` | All tool hooks | Name of the tool being called |
| `$CLAUDE_TOOL_INPUT` | All tool hooks | JSON-encoded tool input |
| `$CLAUDE_TOOL_OUTPUT` | `PostToolUse` only | JSON-encoded tool output |

### Common Hook Patterns

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "prettier --write $CLAUDE_FILE_PATH",
            "if": "Write(**/*.ts)"
          },
          {
            "type": "command",
            "command": "black $CLAUDE_FILE_PATH",
            "if": "Write(**/*.py)"
          }
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "eslint --fix $CLAUDE_FILE_PATH",
            "if": "Edit(**/*.ts)"
          },
          {
            "type": "command",
            "command": "ruff check --fix $CLAUDE_FILE_PATH",
            "if": "Edit(**/*.py)"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"[$(date)] $CLAUDE_TOOL_INPUT\" >> .claude/command.log",
            "async": true
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{ "type": "command", "command": "git status" }]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python ~/tools/notify.py 'Claude finished'",
            "async": true
          }
        ]
      }
    ]
  }
}
```

The `if` field inside a hook entry is a secondary glob filter on top of the `matcher`. Use it to handle multiple file types under one `matcher` block.

`async: true` — hook runs in background; Claude doesn't wait for it. Use for logging, notifications.  
`async: false` (default) — Claude waits for the hook to complete before continuing. Use for formatters, validators.

### PreToolUse Blocking

A `PreToolUse` hook with exit code `2` blocks the tool call and surfaces the hook's stdout as an error message to Claude.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'echo $CLAUDE_TOOL_INPUT | grep -q \"rm -rf\" && { echo \"rm -rf blocked\"; exit 2; } || exit 0'"
          }
        ]
      }
    ]
  }
}
```

## Settings and Permissions

### Settings Files

```
~/.claude/settings.json           # global defaults
<project>/.claude/settings.json   # project (commit — shared with team)
<project>/.claude/settings.local.json  # personal overrides (gitignore)
```

### Permissions

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run *)",
      "Bash(git *)",
      "Write(**/*.ts)",
      "Write(**/*.py)",
      "Bash(docker compose up *)"
    ],
    "deny": [
      "Bash(git push --force *)",
      "Bash(rm -rf *)"
    ]
  }
}
```

Permission string syntax:
```
"Bash(command prefix *)"   — allow bash commands matching the prefix
"Write(**/*.ext)"          — allow writing files matching the glob
"Read(**/*)"               — allow reading any file
"*"                        — allow everything (use in dev only)
```

Deny rules take precedence over allow rules.

### Environment Variables

```json
{
  "env": {
    "NODE_ENV": "development",
    "PYTHONPATH": "/app/src",
    "LOG_LEVEL": "debug"
  }
}
```

### Model Override

```json
{
  "model": "claude-opus-4-7"
}
```

## MCP Servers

MCP (Model Context Protocol) servers expose tools and resources to Claude Code.

### Registration

```bash
# Register globally (available in all projects)
claude mcp add -s user <name> <command> [args...]

# Register for current project only (stored in .claude/mcp.json)
claude mcp add -s project <name> <command> [args...]

# Register locally (personal, stored in .claude/mcp.local.json — gitignored)
claude mcp add -s local <name> <command> [args...]
```

### Examples

```bash
# Python MCP server
claude mcp add -s user memory_map \
  /home/user/memory_map/venv/bin/python \
  /home/user/memory_map/server.py

# Node MCP server
claude mcp add -s user filesystem \
  npx @modelcontextprotocol/server-filesystem /tmp

# With environment variables
claude mcp add -s project my-server \
  --env API_KEY=abc123 \
  node server.js
```

### Management

```bash
claude mcp list                  # list all registered servers
claude mcp remove <name>         # unregister a server
claude mcp get <name>            # show config for one server
```

MCP config is stored as JSON:
```json
{
  "mcpServers": {
    "memory_map": {
      "command": "/home/user/memory_map/venv/bin/python",
      "args": ["/home/user/memory_map/server.py"]
    }
  }
}
```

## CLAUDE.md

`CLAUDE.md` files inject persistent instructions into every session.

### Load Order

```
~/.claude/CLAUDE.md              # always loaded (global)
<project>/CLAUDE.md              # loaded when in that project
<project>/src/CLAUDE.md          # loaded when working in src/ (scoped)
```

All matching files are concatenated — lower-level files extend rather than replace.

### What to Put in CLAUDE.md

```markdown
## Session Setup
<!-- Steps Claude must run at session start -->
1. Run `load_memory` with the current working directory
2. Run `load_history` with the current working directory

## Project Context
<!-- What the project is and how it's structured -->
This is a FastAPI service that handles payment processing.
Main entry point: src/main.py. Tests: tests/.

## Conventions
<!-- Non-obvious decisions that Claude should follow -->
- Use `snake_case` for all Python identifiers
- Never commit directly to main — always branch
- Database migrations live in alembic/versions/

## Commands
<!-- Common tasks Claude should know how to run -->
- Run tests: `pytest tests/ -x`
- Start dev server: `uvicorn src.main:app --reload`
- Lint: `ruff check src/`
```

Avoid documenting things derivable from reading the code. Focus on: session setup, non-obvious conventions, workflow automation steps, and external context Claude can't infer.

## IDE Integration

### VS Code

Install the **Claude Code** extension from the VS Code marketplace. After installing:

```
Ctrl+Shift+P → "Claude Code: Open"   — open Claude Code panel
Ctrl+Shift+P → "Claude Code: Focus"  — focus without opening a new window
```

The extension reads `.claude/settings.json` from the workspace root automatically.

### JetBrains (IntelliJ, PyCharm, WebStorm, etc.)

Install the **Claude Code** plugin from the JetBrains Marketplace. After installing:

```
Tools → Claude Code → Open Session
```

Both IDEs support inline diff review, file context injection, and running Claude Code commands from within the editor.

## Checklist

- [ ] Skills installed to `~/.claude/skills/` (global) or `.claude/skills/` (project-scoped)
- [ ] Each skill has `name`, `description` frontmatter and a `## When to Activate` section
- [ ] Slash commands installed to `~/.claude/commands/` or `.claude/commands/`; use `$ARGUMENTS` for user input
- [ ] Agents declare minimum required `tools` — read-only agents exclude `Write` and `Edit`
- [ ] Agent `description` written as "Use this agent when…" for correct auto-delegation
- [ ] `settings.json` committed to `.claude/` for shared project permissions; personal overrides in `settings.local.json` (gitignored)
- [ ] Formatter/linter hooks use `async: false` so files are fixed before Claude continues
- [ ] Logging/notification hooks use `async: true` so they don't block Claude
- [ ] `PreToolUse` safety hooks exit `2` to block, `0` to allow
- [ ] MCP servers registered with correct scope: `user` for personal tools, `project` for shared
- [ ] `CLAUDE.md` covers session setup steps, non-obvious conventions, and key commands — not things readable from the code
- [ ] Global `~/.claude/CLAUDE.md` contains only instructions that apply across all projects
