Manually save a conversation history checkpoint to .mcp_history.json.

Steps:
1. Look at the recent conversation turns that haven't been checkpointed yet (since the last history save, if any).
2. Write a dense, compressed summary of what was discussed or built — decisions made, code changed, problems solved. Use abbreviations (py, js, db, srv, impl, config, etc). Max 200 chars. No filler words.
3. Call the `save_history` MCP tool with:
   - `project_path`: the current working directory (use `$CWD` or ask if unclear)
   - `summary`: the summary you wrote
   - `session_id`: leave empty string if unknown

After saving, confirm with the chunk ID that was returned.
