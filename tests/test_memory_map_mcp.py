"""Integration smoke tests for the memory_map MCP server.

These tests spawn the real `memory-map-mcp` process via stdio and call
each tool through the MCP protocol — they verify the server is wired up
correctly end-to-end, not just that the package imports.

Default run uses file-fallback mode (no MongoDB). Tests that need Mongo
are marked with @pytest.mark.mongo and skipped unless MEMORY_MAP_MONGO_URI
is set when pytest is invoked.

Run: pytest tests/ -v
"""
from __future__ import annotations

import json
import re

import pytest

from conftest import extract_text

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------

async def test_initialize_returns_server_info(session):
    """The handshake completed in the fixture; session must be usable."""
    tools = await session.list_tools()
    assert tools.tools, "server exposed zero tools"


async def test_list_tools_includes_documented_surface(session):
    tools = await session.list_tools()
    names = {t.name for t in tools.tools}
    expected = {
        "save_memory", "load_memory", "delete_memory",
        "save_global_memory", "load_global_memory",
        "list_projects", "search_across_projects",
        "get_local_structure", "get_project_summary",
        "save_history", "load_history", "suggest_history",
        "get_history_chunks",
    }
    missing = expected - names
    assert not missing, f"server is missing tools: {sorted(missing)}"


async def test_every_tool_has_a_description(session):
    tools = await session.list_tools()
    undocumented = [t.name for t in tools.tools if not (t.description or "").strip()]
    assert not undocumented, f"tools without descriptions: {undocumented}"


# ---------------------------------------------------------------------------
# Project memory CRUD (file fallback)
# ---------------------------------------------------------------------------

async def test_load_memory_on_empty_project(session, tmp_project):
    result = await session.call_tool("load_memory", {"project_path": tmp_project})
    text = extract_text(result).lower()
    assert "no memory" in text, f"expected empty-state message, got: {text!r}"


async def test_save_then_load_memory_roundtrip(session, tmp_project):
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "stack", "content": "Python + FastAPI",
    })
    text = extract_text(await session.call_tool("load_memory", {"project_path": tmp_project}))
    assert "stack" in text
    assert "Python + FastAPI" in text


async def test_save_memory_overwrites_existing_key(session, tmp_project):
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "stack", "content": "v1-OLD",
    })
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "stack", "content": "v2-NEW",
    })
    text = extract_text(await session.call_tool("load_memory", {"project_path": tmp_project}))
    assert "v2-NEW" in text
    assert "v1-OLD" not in text, "old value still present after overwrite"


async def test_delete_memory_removes_key(session, tmp_project):
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "ephemeral", "content": "delete-me-token",
    })
    await session.call_tool("delete_memory", {
        "project_path": tmp_project, "key": "ephemeral",
    })
    text = extract_text(await session.call_tool("load_memory", {"project_path": tmp_project}))
    assert "delete-me-token" not in text


async def test_load_memory_query_filters_by_relevance(session, tmp_project):
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "stack", "content": "Python FastAPI backend",
    })
    await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "deploy", "content": "Kubernetes Helm chart",
    })
    result = await session.call_tool("load_memory", {
        "project_path": tmp_project, "query": "python", "top_k": 1,
    })
    text = extract_text(result)
    assert "Python" in text or "stack" in text
    assert "Kubernetes" not in text, "top_k=1 should not return the unrelated entry"


async def test_memory_is_isolated_per_project(session, tmp_path):
    proj_a = tmp_path / "a"; proj_a.mkdir()
    proj_b = tmp_path / "b"; proj_b.mkdir()
    await session.call_tool("save_memory", {
        "project_path": str(proj_a), "key": "k", "content": "only-in-A",
    })
    text_b = extract_text(await session.call_tool("load_memory", {
        "project_path": str(proj_b),
    })).lower()
    assert "only-in-a" not in text_b
    assert "no memory" in text_b


async def test_save_memory_rejects_oversized_value(session, tmp_project):
    # MCP_MAX_ENTRY_KB defaults to 10 — push well past it.
    huge = "x" * (50 * 1024)
    result = await session.call_tool("save_memory", {
        "project_path": tmp_project, "key": "blob", "content": huge,
    })
    text = extract_text(result).lower()
    # Either the server refuses or it truncates — both are acceptable defenses.
    # What we don't want is a silent successful write of 50KB.
    if "error" not in text and "too large" not in text and "truncat" not in text:
        # Verify the stored entry isn't actually 50KB
        loaded = extract_text(await session.call_tool("load_memory", {
            "project_path": tmp_project,
        }))
        assert len(loaded) < 30 * 1024, "server accepted oversized payload without truncation"


# ---------------------------------------------------------------------------
# Global memory (cross-project)
# ---------------------------------------------------------------------------

async def test_global_memory_roundtrip(session):
    await session.call_tool("save_global_memory", {
        "key": "shell", "content": "PowerShell on Windows 11",
    })
    text = extract_text(await session.call_tool("load_global_memory", {}))
    assert "shell" in text
    assert "PowerShell" in text


async def test_global_memory_distinct_from_project_memory(session, tmp_project):
    await session.call_tool("save_global_memory", {
        "key": "shell", "content": "global-shell-value",
    })
    project_text = extract_text(await session.call_tool("load_memory", {
        "project_path": tmp_project,
    })).lower()
    assert "global-shell-value" not in project_text, \
        "global memory leaked into project memory"


# ---------------------------------------------------------------------------
# Project discovery + search
# ---------------------------------------------------------------------------

async def test_list_projects_finds_saved_project(session, tmp_path):
    proj = tmp_path / "discoverable"
    proj.mkdir()
    await session.call_tool("save_memory", {
        "project_path": str(proj), "key": "k", "content": "v",
    })
    text = extract_text(await session.call_tool("list_projects", {
        "base_path": str(tmp_path), "max_depth": 2,
    }))
    assert "discoverable" in text


async def test_search_across_projects_matches_keyword(session, tmp_path):
    proj_a = tmp_path / "alpha"; proj_a.mkdir()
    proj_b = tmp_path / "bravo"; proj_b.mkdir()
    await session.call_tool("save_memory", {
        "project_path": str(proj_a), "key": "framework", "content": "FastAPI",
    })
    await session.call_tool("save_memory", {
        "project_path": str(proj_b), "key": "framework", "content": "Django",
    })
    text = extract_text(await session.call_tool("search_across_projects", {
        "base_path": str(tmp_path), "keyword": "FastAPI", "max_depth": 2,
    }))
    assert "alpha" in text
    assert "Django" not in text or "bravo" not in text, \
        "search matched a non-matching project"


# ---------------------------------------------------------------------------
# Project structure
# ---------------------------------------------------------------------------

async def test_get_local_structure_lists_files(session, tmp_path):
    proj = tmp_path / "src_proj"
    proj.mkdir()
    (proj / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (proj / "README.md").write_text("# proj\n", encoding="utf-8")
    text = extract_text(await session.call_tool("get_local_structure", {
        "path": str(proj), "max_depth": 2,
    }))
    assert "main.py" in text
    assert "README.md" in text


async def test_get_local_structure_respects_max_depth(session, tmp_path):
    proj = tmp_path / "deep"; proj.mkdir()
    (proj / "level1").mkdir()
    (proj / "level1" / "level2").mkdir()
    (proj / "level1" / "level2" / "buried.txt").write_text("x", encoding="utf-8")
    text = extract_text(await session.call_tool("get_local_structure", {
        "path": str(proj), "max_depth": 1,
    }))
    assert "level1" in text
    assert "buried.txt" not in text, "max_depth=1 should not descend two levels"


# ---------------------------------------------------------------------------
# Suggest history — empty-state behaviour (file-fallback friendly)
# ---------------------------------------------------------------------------

async def test_suggest_history_empty_state(session, tmp_project):
    result = await session.call_tool("suggest_history", {
        "project_path": tmp_project,
        "user_message": "any question",
    })
    text = extract_text(result).lower()
    assert "no history" in text or "no relevant" in text or text.strip() in ("[]", "{}", ""), \
        f"unexpected empty-state response: {text!r}"


# ---------------------------------------------------------------------------
# Mongo-backed history (skipped by default — requires MEMORY_MAP_MONGO_URI)
# ---------------------------------------------------------------------------

@pytest.mark.mongo
async def test_save_and_load_history_roundtrip(mongo_session, tmp_project):
    await mongo_session.call_tool("save_history", {
        "project_path": tmp_project,
        "summary": "User asked how to add a FastAPI route. Assistant explained @app.get.",
        "tags": "fastapi,routes",
    })
    text = extract_text(await mongo_session.call_tool("load_history", {
        "project_path": tmp_project, "last_n": 5,
    }))
    assert "fastapi" in text.lower() or "route" in text.lower()


@pytest.mark.mongo
async def test_suggest_history_returns_relevant_chunk(mongo_session, tmp_project):
    await mongo_session.call_tool("save_history", {
        "project_path": tmp_project,
        "summary": "Added rate limiting to the /search endpoint using slowapi.",
        "tags": "rate-limiting,api",
    })
    await mongo_session.call_tool("save_history", {
        "project_path": tmp_project,
        "summary": "Refactored the user model to use Pydantic v2 ConfigDict.",
        "tags": "refactor,pydantic",
    })
    text = extract_text(await mongo_session.call_tool("suggest_history", {
        "project_path": tmp_project,
        "user_message": "How did we rate limit the search route?",
    })).lower()
    assert "rate" in text or "slowapi" in text


@pytest.mark.mongo
async def test_get_history_chunks_fetches_by_id(mongo_session, tmp_project):
    await mongo_session.call_tool("save_history", {
        "project_path": tmp_project,
        "summary": "Distinctive marker phrase: pelican-orbit-quantum.",
    })
    index_text = extract_text(await mongo_session.call_tool("load_history", {
        "project_path": tmp_project, "last_n": 1,
    }))
    # Pull the chunk ID out of the index response — server emits
    # `[<24-hex-objectid>] <ts> tags:[...] tokens:N preview:"..."`.
    match = re.search(r'\[([a-f0-9]{24})\]', index_text)
    assert match, f"could not find an id in load_history output: {index_text!r}"
    chunk_id = match.group(1)
    full = extract_text(await mongo_session.call_tool("get_history_chunks", {
        "project_path": tmp_project, "ids": chunk_id,
    }))
    assert "pelican-orbit-quantum" in full


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

async def test_load_memory_on_missing_project_does_not_crash(session):
    """Loading from a path that doesn't exist should return empty, not raise."""
    result = await session.call_tool("load_memory", {
        "project_path": "C:/this/path/should/not/exist/anywhere",
    })
    text = extract_text(result).lower()
    # We don't care which message — just that the call returned and didn't raise.
    assert text, "server returned empty response instead of empty-state message"


async def test_delete_memory_on_missing_key_is_idempotent(session, tmp_project):
    """Deleting a key that was never saved should not raise."""
    result = await session.call_tool("delete_memory", {
        "project_path": tmp_project, "key": "never-existed",
    })
    # No assertion on content — just that the call completes.
    assert result is not None
