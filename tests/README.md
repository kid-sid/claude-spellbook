# MCP Server Tests

Integration smoke tests for the `memory_map` MCP server. They spawn the real
`memory-map-mcp` process over stdio and call each tool through the MCP
protocol — so a passing run means the server is wired up correctly
end-to-end, not just that the package imports.

## Setup

```powershell
pip install -r tests/requirements-test.txt
# memory-map-mcp itself must already be installed:
pip install "memory-map-mcp[embed-openai]"
```

## Running

```powershell
# Default: file-fallback mode, Mongo tests skipped automatically
pytest tests/ -v

# Include the Mongo-backed history tests
$env:MEMORY_MAP_MONGO_URI = "mongodb://localhost:27017"
pytest tests/ -v

# Just one test
pytest tests/test_memory_map_mcp.py::test_save_then_load_memory_roundtrip -v
```

## What's covered

| Area | Default run | Notes |
|---|---|---|
| Tool discovery (`list_tools`, descriptions) | yes | |
| Project memory CRUD | yes | `.mcp_memory.json` fallback |
| Global memory | yes | Isolated via temp `HOME` / `USERPROFILE` |
| `list_projects`, `search_across_projects` | yes | |
| `get_local_structure` (incl. `max_depth`) | yes | |
| `suggest_history` empty state | yes | |
| `save_history` + `load_history` + `get_history_chunks` | **skipped** | Marked `@pytest.mark.mongo`; needs `MEMORY_MAP_MONGO_URI` |
| Error paths (missing path, idempotent delete) | yes | |

## Isolation guarantees

Every test runs against a fresh `tmp_path` and a redirected `HOME` /
`USERPROFILE`, so:

- Project memory writes land in a throwaway directory.
- Global memory (`~/.mcp_global_memory.json`) writes land in the temp
  home, not your real profile.
- Mongo is not touched unless you opt in via `MEMORY_MAP_MONGO_URI`.

You can run the suite repeatedly without polluting any real saved state.

## Why anyio (not pytest-asyncio)

The MCP Python SDK uses `anyio` task groups internally. `pytest-asyncio`'s
per-test event loop causes cancel-scope mismatches during fixture teardown
(the streams are closed in a different task than they were opened in).
Using anyio's built-in pytest plugin avoids that — tests are marked
`@pytest.mark.anyio` and an `anyio_backend` fixture pins the backend to
asyncio. This is the same approach the MCP SDK uses in its own tests.
