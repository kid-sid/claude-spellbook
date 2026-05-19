---
name: memory-map
description: Use when installing or configuring memory_map, writing CLAUDE.md session-setup instructions, choosing what to save in memory vs history, managing or pruning history chunks, using cross-project memory, tuning compression, or troubleshooting why Claude isn't loading context at session start.
---

# memory_map

Persistent memory and conversation history MCP server for Claude Code — key-value context store, rolling MongoDB-backed history, and cross-project recall across sessions.

## When to Activate

- Installing memory_map for the first time or on a new machine
- Writing `CLAUDE.md` session-setup instructions (`load_memory`, `suggest_history`)
- Deciding what belongs in memory vs history vs inline code comments
- Pruning stale or sensitive history chunks (`delete_history`)
- Using cross-project or global memory tools
- Configuring history compression or vector search
- Debugging why Claude starts a session without prior context
- Manually checkpointing conversation history with `/mem_save`

## Architecture

```
memory_map_mcp/
├── server.py          — MCP server: 22 tools via FastMCP (stdio transport)
├── history_hook.py    — hook script: saves Q&A pairs on UserPromptSubmit / Stop / PreCompact
└── history_store.py   — storage layer: MongoDB CRUD, BM25, vector search, RRF, MMR

Storage:
├── MongoDB memory_map.history    — conversation chunks (suggest_history, save_history, delete_history)
├── MongoDB memory_map.memory     — key-value memory (save_memory / load_memory)
└── .mcp_memory.json              — per-project fallback when MongoDB not configured
```

MongoDB is **required** for all history features. Key-value memory works without it (falls back to `.mcp_memory.json`), but `suggest_history`, `save_history`, and `delete_history` all return an error if `MEMORY_MAP_MONGO_URI` is unset.

MCP registration makes all tools available globally. Per-project activation is controlled by `CLAUDE.md` — Claude only calls `load_memory` / `suggest_history` automatically if the instructions tell it to.

## Installation

### Step 1 — Install from PyPI

```bash
pip install memory-map-mcp
```

Or install from source for development:

```bash
git clone https://github.com/kid-sid/memory_map.git
cd memory_map
python -m venv venv

# Windows
venv\Scripts\pip install -e .

# Mac/Linux
source venv/bin/activate && pip install -e .
```

### Step 2 — Set MongoDB URI

Add to your environment / shell profile:

```bash
export MEMORY_MAP_MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/"
```

Free-tier MongoDB Atlas works. Without this, history tools are unavailable.

### Step 3 — Register the MCP Server

```bash
# Global — available in every project (recommended)
claude mcp add -s user memory_map memory-map-mcp
```

If installed from source:

```bash
# Windows
claude mcp add -s user memory_map \
  C:/Users/yourname/memory_map/venv/Scripts/python.exe \
  C:/Users/yourname/memory_map/memory_map_mcp/server.py

# Mac/Linux
claude mcp add -s user memory_map \
  python3 /home/yourname/memory_map/memory_map_mcp/server.py
```

Registration scope options:

| Scope flag | Stored in | Available |
|---|---|---|
| `-s user` | `~/.claude/mcp.json` | All projects on this machine |
| `-s project` | `.claude/mcp.json` | This repo only (committed, shared) |
| `-s local` | `.claude/mcp.local.json` | This repo only (gitignored, personal) |

Always use `-s user` for memory_map — it stores files at local paths that differ per machine.

Verify: `claude mcp list` → should show `memory_map`.

### Step 4 — Lifecycle Hooks

Add to `~/.claude/settings.json` so history is captured automatically in every project:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "memory-map-hook",
          "timeout": 10
        }]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "memory-map-hook --force",
          "timeout": 15
        }]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "memory-map-hook --force",
          "timeout": 15,
          "async": true
        }]
      }
    ]
  }
}
```

If installed from source, replace `memory-map-hook` with the full path to `history_hook.py`.

| Hook | When | Flag |
|---|---|---|
| `UserPromptSubmit` | Every message — incremental saves | none |
| `PreCompact` | Before context window compaction | `--force` |
| `Stop` | When Claude finishes a turn | `--force`, `async: true` |

### Step 5 — Enable Per-Project Memory

Add this block to `CLAUDE.md` in the project root:

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `suggest_history` with the current working directory and the user's first message
3. Read both outputs before exploring files or asking questions

Save or update memory entries whenever you learn something worth keeping across sessions.
If something loaded from memory is no longer accurate, update it with `save_memory` using the same key.
Use short, lowercase keys: `stack`, `current_work`, `gotchas`, `key_files`. Keep values concise.
```

Commit `CLAUDE.md` — teammates get session-start loading automatically.

---

## Memory Tools

### `save_memory` / `load_memory` / `delete_memory`

Per-project key-value store backed by MongoDB (or `.mcp_memory.json` without MongoDB).

```
save_memory(project_path, key, value)
load_memory(project_path, query="", top_k=10)   → compressed key-value output
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

Use for: user identity, preferred tools, cross-project conventions. Never store secrets.

---

## History Tools

Conversation history is stored in MongoDB (`memory_map.history` collection), one document per Q&A pair. Tags are extracted by local keyword matching — no LLM calls.

### `suggest_history` — primary session-start tool

```
suggest_history(project_path, user_message, token_budget=2000, diversity=0.3)
```

Hybrid retrieval pipeline:
1. **Concurrent fetch** — vector search + BM25/tag scoring run in parallel
2. **RRF merge** — Reciprocal Rank Fusion combines both ranked lists
3. **MMR re-ranking** — penalises redundant chunks so results cover more distinct topics
4. **Anchor** — most recent chunk always included for session continuity
5. **Token budget** — fills remaining budget with most recent unselected chunks

Call at session start with the user's first message. Returns the most relevant chunks within the token budget.

### `save_history` / `load_history` / `get_history_chunks`

```
save_history(project_path, dialogue, session_id="", tags="")
load_history(project_path, last_n=5)        → tag index (id, timestamp, tags, preview, tokens)
get_history_chunks(project_path, ids)       → full dialogue for comma-separated chunk IDs
```

`save_history` is called automatically by `history_hook.py` — no manual calls needed during normal use. Auto-summarises oldest chunks when total tokens exceed `MCP_HISTORY_MAX_TOKENS` (default 50 000).

`load_history` + `get_history_chunks` are for inspection only — listing what's saved or fetching a specific chunk by ID. Do not use them at session start — use `suggest_history` instead.

### `delete_history` — prune stale or sensitive chunks

```
delete_history(project_path, ids="", older_than_days=0)
```

Remove chunks you no longer need. At least one filter must be provided:

```
# Delete specific chunks by ID (get IDs from load_history or suggest_history output)
delete_history("C:/projects/my-api", ids="6830a1f2e4b0c1234567abcd,6830a1f2e4b0c1234567ef01")
→ "deleted: 2 chunk(s)"

# Remove everything older than 30 days
delete_history("C:/projects/my-api", older_than_days=30)
→ "deleted: 7 chunk(s)"

# Both filters together (union — deletes chunks matching either condition)
delete_history("C:/projects/my-api", ids="6830a1f2e4b0c1234567abcd", older_than_days=30)
```

Deletion is scoped to the given project — other projects are never affected.

### `summarise_history`

```
summarise_history(project_path, n=10)
```

Collapse the n oldest chunks into a single summary chunk. Triggered automatically by `save_history` when the token budget is exceeded; call manually to compact immediately.

### `backfill_history_embeddings` / `backfill_bm25_text`

```
backfill_history_embeddings(project_path="", batch_size=20)
backfill_bm25_text(project_path="", batch_size=100)
```

Run once after enabling vector search or upgrading from an older version. Repeat until `remaining=0`. Pass `project_path=""` to backfill across all projects.

---

## Vector Search (Optional)

Set `MEMORY_MAP_EMBED_PROVIDER` to enable semantic search in `suggest_history`:

| Value | How |
|---|---|
| `openai` | `text-embedding-3-small` (1536-dim); requires `OPENAI_API_KEY` |
| `local` | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU, no API key) |
| `atlas` | Atlas autoEmbed (Voyage-4) via Atlas Vector Search |
| *(unset)* | BM25 + tag scoring only — no vector search |

Without `MEMORY_MAP_EMBED_PROVIDER`, `suggest_history` still works using BM25 and tag matching.

---

## Cross-Project Tools

| Tool | What it does |
|---|---|
| `list_projects` | List all projects that have saved memory under a base path |
| `get_project_summary(project_path)` | One-line summary of a project's memory |
| `load_cross_project_memory(base_path)` | Load memory from sibling projects |
| `search_across_projects(base_path, keyword)` | Full-text search across all project memories |

Use cases:
- Referencing a pattern from a sibling project
- Finding which project owns a shared library
- Onboarding to a new project by comparing to a known one

---

## Utility Tools

| Tool | What it does |
|---|---|
| `get_local_structure(path, max_depth=5)` | Gitignore-aware directory tree |
| `get_github_structure(repo, branch="main", max_depth=5)` | GitHub repo file tree via API |
| `get_git_history(path, count=5)` | Recent commits as `hash \| subject` |

---

## Compression

```
set_compression(project_path, level)
```

| Level | Output | When to use |
|---|---|---|
| `0` | Raw — full fidelity | Debugging, inspecting memory content |
| `1` | Compact (default) | Normal use |
| `2` | Dense — abbreviations | Low context budget, large memories |

Set per-project; persists until changed. Entries not updated in 30+ days get a `[stale: Nd old]` annotation at levels 1 and 2.

---

## CLAUDE.md Session-Start Pattern

Minimal session-setup block for any project:

```markdown
## Session Setup (Required)
At the start of every session, before doing anything else:
1. Call `load_memory` with the current working directory
2. Call `suggest_history` with the current working directory and the user's first message
3. Read both outputs before exploring files or asking questions

Save or update memory entries whenever you learn something worth keeping across sessions.
If something loaded from memory is no longer accurate, update it with `save_memory` using the same key.
Do not call `load_history` + `get_history_chunks` manually at session start — those are for inspection only.
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Claude starts sessions cold with no memory | `CLAUDE.md` missing or not instructing `load_memory` | Add session-setup block to `CLAUDE.md` |
| `load_memory` returns "no memory saved yet" | First session, or memory was deleted | Normal — save entries as context is established |
| History tools return "MongoDB unavailable" | `MEMORY_MAP_MONGO_URI` not set | Export the env var; verify with `echo $MEMORY_MAP_MONGO_URI` |
| `suggest_history` returns "no history yet" | Hooks not configured, or first session | Check hooks in `settings.json`; run `memory-map-hook --force` manually |
| MCP server not found | Not registered, or wrong path | Re-run `claude mcp add`; verify with `claude mcp list` |
| Hook hangs the session | No `timeout` on hook | Ensure `"timeout": 10` is set on every hook |
| Stale chunks surfacing in suggestions | Old history never pruned | Run `delete_history(project_path, older_than_days=N)` |

---

## Red Flags

- **Putting API keys or passwords in `save_memory`** — memory may be committed or shared; store only key names and env var references, never values
- **No `CLAUDE.md` after registering the MCP server** — registration makes tools available but Claude only auto-loads memory if the session-setup instructions tell it to
- **Using `-s project` for memory_map registration** — memory_map stores files at local absolute paths that differ per machine; use `-s user` always
- **Saving entire file contents or code blocks in memory** — values should be one to two sentences; large values bloat the store and crowd out useful keys
- **Hooks without `timeout`** — a stalled hook blocks Claude Code indefinitely; always set `"timeout": N`
- **Calling `load_history` + `get_history_chunks` at session start** — use `suggest_history` instead; it runs hybrid retrieval and returns the most relevant chunks within a token budget
- **Never running `delete_history`** — history grows unbounded; prune stale projects periodically with `older_than_days`

---

## Checklist

- [ ] `pip install memory-map-mcp` succeeded; `memory-map-mcp` command is on PATH
- [ ] `MEMORY_MAP_MONGO_URI` is set in the environment
- [ ] `claude mcp list` shows `memory_map` with correct entry point
- [ ] Registration used `-s user` (not `-s project` or `-s local`)
- [ ] Three lifecycle hooks in `~/.claude/settings.json`: `UserPromptSubmit`, `PreCompact`, `Stop`
- [ ] Every hook has a `"timeout"` value; `Stop` hook has `"async": true`
- [ ] `CLAUDE.md` added to the project root and committed
- [ ] `CLAUDE.md` instructs `load_memory` and `suggest_history` at session start (not `load_history`)
- [ ] No secrets stored in `save_memory` — only descriptive values and env var names
- [ ] Memory keys are short, lowercase, and overwrite stale values (no duplicates)
- [ ] `backfill_history_embeddings` run if `MEMORY_MAP_EMBED_PROVIDER` was set after initial use
- [ ] `/mem_save` used before context compaction or ending a long session mid-task
