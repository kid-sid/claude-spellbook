---
name: memory-map
description: Use when installing or configuring memory_map, writing CLAUDE.md session-setup instructions, choosing what to save in memory vs history, managing cross-project memory, tuning compression, or troubleshooting why Claude isn't loading context at session start.
---

# memory_map

Persistent memory and conversation history MCP server for Claude Code — key-value context store, rolling history, and cross-project recall across sessions.

## When to Activate

- Installing memory_map for the first time or on a new machine
- Writing `CLAUDE.md` session-setup instructions (`load_memory`, `load_history`)
- Deciding what belongs in memory vs history vs inline code comments
- Using cross-project or global memory tools
- Configuring history compression or external summarization
- Debugging why Claude starts a session without prior context
- Manually checkpointing conversation history with `/mem_save`

## Architecture

```
memory_map/
├── server.py          — MCP server (stdio transport)
├── history_hook.py    — hook script: saves history on UserPromptSubmit / Stop / PreCompact
├── CLAUDE.md          — copy into any project to enable session-start loading
└── venv/              — Python virtualenv

Per-project files (written to the project root automatically):
├── .mcp_memory.json   — key-value store (load_memory / save_memory)
└── .mcp_history.json  — rolling conversation history (20 chunks)
```

MCP registration makes all tools available globally. Per-project activation is controlled by `CLAUDE.md` — Claude only calls `load_memory` / `load_history` automatically if the instructions tell it to.

## Installation

### Step 1 — Clone and Install

```bash
git clone https://github.com/kid-sid/memory_map.git
cd memory_map

# Windows
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# Mac/Linux
python3 -m venv venv
source venv/bin/activate && pip install -r requirements.txt
```

### Step 2 — Register the MCP Server

```bash
# Global — available in every project (recommended)
# Windows
claude mcp add -s user memory_map \
  C:/Users/yourname/memory_map/venv/Scripts/python.exe \
  C:/Users/yourname/memory_map/server.py

# Mac/Linux
claude mcp add -s user memory_map \
  python3 /home/yourname/memory_map/server.py
```

Registration scope options:

| Scope flag | Stored in | Available |
|---|---|---|
| `-s user` | `~/.claude/mcp.json` | All projects on this machine |
| `-s project` | `.claude/mcp.json` | This repo only (committed, shared) |
| `-s local` | `.claude/mcp.local.json` | This repo only (gitignored, personal) |

Always use `-s user` for memory_map — it stores files with local paths that differ per machine.

Verify: `claude mcp list` → should show `memory_map`.

### Step 3 — Lifecycle Hooks

Add to `~/.claude/settings.json` so history is captured automatically in every project:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "python C:/Users/yourname/memory_map/history_hook.py",
          "timeout": 10
        }]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "python C:/Users/yourname/memory_map/history_hook.py --force",
          "timeout": 15
        }]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "python C:/Users/yourname/memory_map/history_hook.py --force",
          "timeout": 15,
          "async": true
        }]
      }
    ]
  }
}
```

Mac/Linux: use `python3` and POSIX paths.

| Hook | When | Flag |
|---|---|---|
| `UserPromptSubmit` | Every message — incremental saves | none |
| `PreCompact` | Before context window compaction | `--force` |
| `Stop` | When Claude finishes a turn | `--force`, `async: true` |

### Step 4 — Enable Per-Project Memory

Copy `CLAUDE.md` from the memory_map repo into the project root:

```bash
# Windows
copy C:\Users\yourname\memory_map\CLAUDE.md CLAUDE.md

# Mac/Linux
cp ~/memory_map/CLAUDE.md ~/your-project/CLAUDE.md
```

Commit `CLAUDE.md` — teammates get session-start loading automatically. The file content Claude needs:

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `load_history` with the current working directory
3. Read both outputs before exploring files or asking questions
```

---

## Memory Tools

### `save_memory` / `load_memory` / `delete_memory`

Per-project key-value store. Values persist in `.mcp_memory.json`.

```
save_memory(project_path, key, value)
load_memory(project_path)         → returns all key-value pairs
delete_memory(project_path, key)
```

**Key conventions:**

| Key | What to store |
|---|---|
| `stack` | Language, framework, runtime versions |
| `current_work` | Active feature, bug, or initiative |
| `gotchas` | Non-obvious constraints, known failures, env quirks |
| `key_files` | Entry points, config files, critical paths |
| `conventions` | Non-obvious team decisions not in the code |
| `blockers` | Current blockers or dependencies on others |

Rules:
- Short, lowercase, underscore-separated keys
- Values: one or two sentences max — dense, not verbose
- Overwrite stale values with the same key; don't accumulate duplicates
- Convert relative dates to absolute: "Thursday" → "2026-05-15"

**What NOT to save in memory:**
- Code patterns and architecture (read the code)
- Git history / who changed what (`git log` / `git blame`)
- Fix recipes (the fix is in the code; commit message has context)
- Ephemeral task state (in-progress work, current conversation)
- Anything already in `CLAUDE.md`

### Global Memory

Shared across all projects on the machine:

```
save_global_memory(key, value)
load_global_memory()
```

Use for: user identity, preferred tools, cross-project conventions, API key locations (not values). Never store secrets.

---

## History Tools

### `load_history` / `save_history`

Rolling conversation history stored in `.mcp_history.json` (20 chunks max). `history_hook.py` calls `save_history` automatically via hooks — no manual calls needed during normal use.

```
load_history(project_path, last_n=5)   → returns N most recent chunks
save_history(project_path, content)
```

### Manual Checkpoint: `/mem_save`

Run `/mem_save` at any time to force-save the current conversation as a history chunk. Use before long operations, context compaction, or ending a session mid-task.

---

## Cross-Project Tools

| Tool | What it does |
|---|---|
| `list_projects` | List all projects that have saved memory |
| `get_project_summary(project_path)` | One-line summary of a project's memory |
| `load_cross_project_memory(project_path)` | Load memory from a different project |
| `search_across_projects(query)` | Full-text search across all project memories |

Use cases:
- Referencing a pattern from a sibling project
- Finding which project owns a shared library
- Onboarding to a new project by comparing to a known one

---

## Utility Tools

| Tool | What it does |
|---|---|
| `get_local_structure(project_path)` | Gitignore-aware directory tree |
| `get_github_structure(owner, repo, branch?)` | GitHub repo file tree via API |
| `get_git_history(project_path, limit?)` | Recent commits |

These are read-only exploration tools — call them at session start to orient quickly without reading every file.

---

## Compression

```
set_compression(project_path, level)
```

| Level | Output | When to use |
|---|---|---|
| `0` | Raw — full fidelity | Debugging, inspecting history content |
| `1` | Compact — whitespace stripped | Normal use |
| `2` | Dense — abbreviations, no filler | Low context budget, large histories |

Set per-project; persists until changed. Default is compact (1).

---

## Privacy and External Summarization

History is stored **locally** by default using simple truncation — no data leaves the machine.

To enable OpenAI-backed summarization (richer history compression):

```bash
# Add to your environment / shell profile
export OPENAI_API_KEY="sk-..."
export MCP_HISTORY_EXTERNAL_SUMMARIZE=1
```

When both are set, `history_hook.py` sends up to 4 000 characters of recent conversation to `gpt-4o-mini` before storing the summary locally.

**What gets sent:** recent dialogue including source code, file contents, and environment details. Only enable if you're comfortable with that leaving your machine. Do not enable on machines with proprietary codebases unless your org has approved the OpenAI data-processing agreement.

---

## CLAUDE.md Session-Start Pattern

Minimal session-setup block for any project:

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `load_history` with the current working directory
3. Read both outputs before exploring files or asking questions

Save or update memory entries whenever you learn something worth keeping across sessions.
If something loaded from memory is no longer accurate, update it with `save_memory` using the same key.
Use short, lowercase keys: `stack`, `current_work`, `gotchas`, `key_files`. Keep values concise.
```

Extend this block with project-specific keys or additional tool calls (`get_local_structure`, etc.) when the project benefits from them.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Claude starts sessions cold with no memory | `CLAUDE.md` missing or not instructing `load_memory` | Copy `CLAUDE.md` from memory_map repo into project root |
| `load_memory` returns "no memory saved yet" | First session, or memory was deleted | Normal — save entries as context is established |
| History not saving between sessions | Hooks missing or wrong path in `settings.json` | Verify `history_hook.py` path; run it manually: `python memory_map/history_hook.py --force` |
| MCP server not found | Not registered, or wrong Python path | Re-run `claude mcp add`; verify with `claude mcp list` |
| `history_hook.py` hangs the session | No `timeout` on hook or slow Python startup | Ensure `"timeout": 10` is set; use virtualenv Python, not system Python |
| Memory values growing stale | Not updating keys after project shifts | Always overwrite with the same key rather than adding new ones |

---

## Red Flags

- **Putting API keys or passwords in `save_memory`** — memory is stored in `.mcp_memory.json` in the project root, which may be committed or shared; store only key names and env var references, never values
- **No `CLAUDE.md` after registering the MCP server** — registration makes tools available but doesn't call them; Claude only auto-loads memory if the session-setup instructions tell it to
- **Using `-s project` for memory_map registration** — project-scoped MCP servers are committed and affect all teammates, but memory_map stores files at local absolute paths that differ per machine; use `-s user` always
- **Saving entire file contents or code blocks in memory** — memory values should be one to two sentences; large values bloat `.mcp_memory.json`, slow load times, and crowd out useful keys
- **Setting `MCP_HISTORY_EXTERNAL_SUMMARIZE=1` on a machine with proprietary code** — history includes file contents; check your org's data policy before enabling OpenAI-backed summarization
- **Hooks without `timeout`** — a stalled `history_hook.py` (e.g., network timeout during OpenAI summarization) blocks Claude Code indefinitely; always set `"timeout": N`
- **Calling `load_history` + `get_history_chunks` manually at session start** — these are for inspection and the `/mem_save` flow only; use `load_history(last_n=5)` for session continuity, not the raw chunk API

---

## Checklist

- [ ] memory_map cloned; virtualenv created; `pip install -r requirements.txt` succeeded
- [ ] `claude mcp list` shows `memory_map` with correct Python path
- [ ] Registration used `-s user` (not `-s project` or `-s local`)
- [ ] Three lifecycle hooks present in `~/.claude/settings.json`: `UserPromptSubmit`, `PreCompact`, `Stop`
- [ ] Every hook has a `"timeout"` value; `Stop` hook has `"async": true`
- [ ] `CLAUDE.md` copied into the project root and committed
- [ ] `CLAUDE.md` instructs `load_memory` and `load_history` at session start
- [ ] No secrets stored in `save_memory` — only descriptive values and env var names
- [ ] Memory keys are short, lowercase, and overwrite stale values (no duplicates)
- [ ] Compression level set appropriately for the project's history volume
- [ ] External summarization (`MCP_HISTORY_EXTERNAL_SUMMARIZE=1`) only enabled after data-policy check
- [ ] `/mem_save` used before context compaction or ending a long session mid-task
