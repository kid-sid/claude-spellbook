Save a curated session-level summary to history. Use this at meaningful milestones — end of session, before a long break, after wrapping a chunk of work — not after every turn. The auto-hooks (`UserPromptSubmit`, `Stop`, `PreCompact`) already capture turns; this command is for the higher-signal arc that those per-turn saves can't see.

Execute these in order in one response:

1. Call `ToolSearch` with `query: "select:mcp__memory_map__save_history"` to load the schema.

2. Distill the session arc into 4–8 lines covering:
   - **What we worked on** — the actual task(s), not a turn-by-turn log
   - **Key decisions** — non-obvious choices and the reasoning behind them
   - **Artifacts** — files touched, commits, issues opened/closed, PRs (with refs)
   - **Open threads** — anything started but not finished, or follow-ups identified
   - Skip: routine acks, exploration deadends, and anything trivially recoverable from `git log`

3. Pick 2–5 lowercase tags from the session content (comma-separated, no spaces): topic tags like `auth`, `mcp`, `refactor`, `bug-fix`, `migration`, `docs`. These drive future `suggest_history` recall — pick the words you'd grep for next month.

4. Call `mcp__memory_map__save_history` with:
   - `project_path`: the current working directory
   - `dialogue`: the distilled summary from step 2 (target 600–1500 chars)
   - `session_id`: ""
   - `tags`: the comma-separated tag string from step 3

5. Reply with just the returned chunk ID on one line. No recap, no explanation.

This is curation, not capture. The point is to leave a high-signal breadcrumb a future session can retrieve — not to duplicate what the per-turn hooks already store.
