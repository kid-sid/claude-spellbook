Review recent conversation history and either explain what was just done or rewrite/refine the last output.

**Usage:**
- `/reprompt` — auto-detects mode from context: explains if recent work was complex, rewrites if recent output can be improved
- `/reprompt explain` — summarise what happened in the last few turns
- `/reprompt rewrite` — rewrite the last substantial output (code, document, plan) to improve it
- `/reprompt rewrite <guidance>` — rewrite with a specific direction, e.g. `/reprompt rewrite make it shorter and add Go examples`

## Instructions

### 1. Read recent history

Look back at the last **5–10 conversation turns** (user messages + assistant responses). Identify:

- What was the most recent **substantial output**? (code block, document, plan, explanation, command, etc.)
- What was the user asking for at the time?
- Were there any corrections, clarifications, or follow-up requests that weren't fully addressed?

If the project uses `.mcp_history.json`, optionally load it with `mcp__memory_map__load_history` for turns that may have been compacted out of context.

### 2. Determine mode

Parse `$ARGUMENTS`:

| Argument starts with | Mode |
|---|---|
| `explain` or empty and last output was complex | **Explain** |
| `rewrite` or `refine` or `improve` | **Rewrite** |
| Empty and last output was short/clear | **Explain** (default) |

Everything after `explain` / `rewrite` / `refine` is treated as **optional guidance** for that mode.

---

### Mode: Explain

Produce a plain-language summary of what happened in the recent turns:

```
## What just happened

### Summary
<2–3 sentence plain-language recap of the last task>

### What was changed / created
- `<file or artifact>` — <what it does and why>
- `<file or artifact>` — <what it does and why>

### Key decisions made
- <decision 1> — <why this approach was chosen>
- <decision 2> — <why this approach was chosen>

### What was NOT done (if relevant)
- <scope that was explicitly excluded or deferred>

### What comes next (if any next step was identified)
- <next step>
```

Keep it factual — only what actually happened, nothing speculative.

---

### Mode: Rewrite

Take the last substantial output and improve it. Apply the optional guidance first; if no guidance was given, apply these defaults:

**For code:**
- Remove unnecessary comments and dead code
- Simplify complex expressions without losing clarity
- Ensure naming is consistent with the file's conventions
- Check for off-by-one errors, missed edge cases, or hardcoded values

**For prose / documents / skills:**
- Cut filler sentences
- Replace passive voice with active
- Ensure examples match what was described
- Fix any internal inconsistencies

**For plans / checklists:**
- Remove redundant steps
- Make each item actionable (verb-led)
- Reorder if a dependency order would be clearer

Output the full rewritten version — not a diff, not a description of changes. Then add a short footer:

```
---
**Changes from original:** <bullet list of what was changed and why>
```

---

### 3. Check for unresolved follow-ups

After either mode, scan recent turns for anything the user flagged but wasn't addressed:
- Questions that were answered incompletely
- "TODO" or "later" items that are now relevant
- Corrections that were acknowledged but not applied

If any exist, append:

```
### Unresolved from recent context
- <item> — <what still needs to happen>
```

Only include this section if there are actual unresolved items.
