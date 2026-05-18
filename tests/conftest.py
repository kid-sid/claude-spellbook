"""Pytest fixtures for memory_map MCP integration tests.

Spawns the pip-installed `memory-map-mcp` binary over stdio and connects a
real MCP ClientSession. Each test gets an isolated HOME so file-backed
memory does not leak between tests or pollute the user's real state.

History tests require MongoDB and are skipped unless `MEMORY_MAP_MONGO_URI`
is set in the environment when pytest is invoked.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.fixture
def anyio_backend():
    """Pin anyio to asyncio so tests don't try to run on trio too."""
    return "asyncio"


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.mongo tests unless MEMORY_MAP_MONGO_URI is set."""
    if os.environ.get("MEMORY_MAP_MONGO_URI"):
        return
    skip_mongo = pytest.mark.skip(reason="MEMORY_MAP_MONGO_URI not set — Mongo-only path")
    for item in items:
        if "mongo" in item.keywords:
            item.add_marker(skip_mongo)


@pytest.fixture(scope="session", autouse=True)
def _require_binary():
    if shutil.which("memory-map-mcp") is None:
        pytest.skip(
            "memory-map-mcp not on PATH — run `pip install memory-map-mcp` first",
            allow_module_level=True,
        )


@pytest.fixture
def isolated_home(tmp_path):
    """A scratch HOME the spawned server will treat as the user profile.

    Used for global memory + any path that resolves via pathlib.Path.home().
    """
    return tmp_path / "home"


@pytest.fixture
def tmp_project(tmp_path):
    """A scratch project_path that won't conflict with real saved memory."""
    p = tmp_path / "proj"
    p.mkdir()
    return str(p)


@pytest.fixture
def server_env(isolated_home):
    """Environment for the MCP subprocess — file-fallback mode, isolated HOME."""
    isolated_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    # Force file-fallback for memory by clearing Mongo URI from inherited env.
    # (Tests that need Mongo override this via the `mongo_server_env` fixture.)
    env.pop("MEMORY_MAP_MONGO_URI", None)
    # Redirect home so global memory writes to tmp_path, not the real profile.
    env["HOME"] = str(isolated_home)
    env["USERPROFILE"] = str(isolated_home)
    # Disable optional embedding so suggest_history stays on the BM25 path.
    env.pop("MEMORY_MAP_EMBED_PROVIDER", None)
    env.pop("EMBED_PROVIDER", None)
    return env


@pytest.fixture
async def session(server_env):
    """A live MCP ClientSession connected to memory-map-mcp over stdio.

    Uses anyio's pytest plugin (not pytest-asyncio) — the MCP SDK relies on
    anyio task groups, and pytest-asyncio's per-test event loop breaks the
    cancel-scope contract during fixture teardown.
    """
    params = StdioServerParameters(
        command="memory-map-mcp",
        args=[],
        env=server_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


@pytest.fixture
async def mongo_session(server_env):
    """Mongo-backed session — only spawns when MEMORY_MAP_MONGO_URI is set."""
    uri = os.environ.get("MEMORY_MAP_MONGO_URI")
    if not uri:
        pytest.skip("MEMORY_MAP_MONGO_URI not set")
    env = dict(server_env)
    env["MEMORY_MAP_MONGO_URI"] = uri
    params = StdioServerParameters(command="memory-map-mcp", args=[], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            yield s


def extract_text(result) -> str:
    """Concatenate text content blocks from a tools/call result."""
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)
