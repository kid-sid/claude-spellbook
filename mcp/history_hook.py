#!/usr/bin/env python3
"""
Claude Code hook: conversation history persistence.

Fires on UserPromptSubmit (every message) and PreCompact (before compaction).
Every 10 user messages (or on --force), reads the transcript, summarizes via
GPT-4o-mini, and appends a chunk to .mcp_history.json in the project directory.

Usage (configured in .claude/settings.local.json):
    echo '{"session_id":"...","transcript_path":"...","cwd":"..."}' | python history_hook.py
    echo '{"session_id":"...","transcript_path":"...","cwd":"..."}' | python history_hook.py --force
"""

import sys
import json
import os
import pathlib
import tempfile
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(pathlib.Path(__file__).parent / ".env")

HISTORY_FILE = ".mcp_history.json"
MAX_CHUNKS = 20
SAVE_INTERVAL = 10


# --- Counter ---

def _counter_path(session_id: str) -> pathlib.Path:
    return pathlib.Path(tempfile.gettempdir()) / f"claude_hist_{session_id[:8]}.txt"


def _watermark_path(session_id: str) -> pathlib.Path:
    return pathlib.Path(tempfile.gettempdir()) / f"claude_hist_wm_{session_id[:8]}.txt"


def increment_counter(session_id: str) -> int:
    p = _counter_path(session_id)
    count = 0
    if p.exists():
        try:
            count = int(p.read_text().strip())
        except (ValueError, OSError):
            count = 0
    count += 1
    p.write_text(str(count))
    return count


def read_watermark(session_id: str) -> int:
    p = _watermark_path(session_id)
    if p.exists():
        try:
            return int(p.read_text().strip())
        except (ValueError, OSError):
            return 0
    return 0


def write_watermark(session_id: str, line_num: int):
    _watermark_path(session_id).write_text(str(line_num))


# --- Transcript parsing ---

def extract_recent_dialogue(transcript_path: str, watermark: int) -> tuple[list[dict], int]:
    """Read transcript from watermark line onwards, extract user/assistant text.

    Returns (exchanges, new_watermark) where exchanges is a list of
    {"role": "user"|"assistant", "content": str} dicts.
    """
    exchanges = []
    total_lines = 0

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i < watermark:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                msg = entry.get("message", {})
                role = msg.get("role", "")
                content = msg.get("content", "")

                if entry_type not in ("user", "assistant") or role not in ("user", "assistant"):
                    continue

                # Extract text content
                text = ""
                if isinstance(content, str):
                    # Skip meta/command messages
                    if content.startswith("<local-command") or content.startswith("<command-name>"):
                        continue
                    text = content.strip()
                elif isinstance(content, list):
                    # Extract text blocks only (skip thinking, tool_use, tool_result)
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    text = " ".join(parts).strip()

                if text and len(text) > 5:
                    exchanges.append({"role": role, "content": text[:500]})
    except (OSError, IOError):
        return [], watermark

    return exchanges, total_lines


# --- GPT summarization ---

def summarize_with_gpt(dialogue: str) -> str:
    """Call OpenAI GPT-4o-mini to summarize conversation dialogue."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Fallback: truncated raw text
        return dialogue[:300]

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Summarize this conversation into a dense, compressed format. "
                            "Focus on: decisions made, code changes, topics discussed, "
                            "problems solved. Use abbreviations (py, js, db, srv, auth, "
                            "fe, be, config, env, etc). Max 200 chars. No filler words. "
                            "Output only the summary, nothing else."
                        ),
                    },
                    {"role": "user", "content": dialogue},
                ],
                "max_tokens": 150,
                "temperature": 0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        # On any API error, fall back to truncated text
        return dialogue[:300]


# --- History storage ---

def _history_path(cwd: str) -> pathlib.Path:
    return pathlib.Path(cwd) / HISTORY_FILE


def read_history(cwd: str) -> dict:
    p = _history_path(cwd)
    if not p.exists():
        return {"_meta": {"max_chunks": MAX_CHUNKS, "watermark": 0}, "chunks": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"_meta": {"max_chunks": MAX_CHUNKS, "watermark": 0}, "chunks": []}


def save_chunk(cwd: str, session_id: str, summary: str, watermark: int):
    data = read_history(cwd)
    chunks = data.get("chunks", [])

    next_id = (chunks[-1]["id"] + 1) if chunks else 1
    chunks.append({
        "id": next_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "session": session_id[:8],
        "summary": summary,
    })

    # Enforce rolling window
    if len(chunks) > MAX_CHUNKS:
        chunks = chunks[-MAX_CHUNKS:]

    data["chunks"] = chunks
    data["_meta"]["watermark"] = watermark
    data["_meta"]["last_session"] = session_id[:8]
    data["_meta"]["last_save"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    p = _history_path(cwd)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --- Main ---

def main():
    force = "--force" in sys.argv

    # Read stdin JSON from Claude Code
    try:
        stdin_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print("{}")
        return

    session_id = stdin_data.get("session_id", "unknown")
    transcript_path = stdin_data.get("transcript_path", "")
    cwd = stdin_data.get("cwd", "")

    if not cwd:
        print("{}")
        return

    # Increment counter
    count = increment_counter(session_id)

    # Check if we should save
    if not force and (count % SAVE_INTERVAL != 0):
        print("{}")
        return

    # No transcript path → can't extract
    if not transcript_path or not os.path.exists(transcript_path):
        print("{}")
        return

    # Read watermark
    watermark = read_watermark(session_id)

    # Extract recent dialogue
    exchanges, new_watermark = extract_recent_dialogue(transcript_path, watermark)

    if not exchanges:
        print("{}")
        return

    # Build dialogue text for summarization
    dialogue = "\n".join(f"{e['role']}: {e['content']}" for e in exchanges)

    # Truncate dialogue input to ~4000 chars to keep API call small
    if len(dialogue) > 4000:
        dialogue = dialogue[:4000]

    # Summarize
    summary = summarize_with_gpt(dialogue)

    # Save chunk
    save_chunk(cwd, session_id, summary, new_watermark)

    # Update watermark
    write_watermark(session_id, new_watermark)

    # Output systemMessage
    chunk_count = len(read_history(cwd).get("chunks", []))
    output = {
        "systemMessage": f"[history] Conversation checkpoint saved (chunk {chunk_count}/{MAX_CHUNKS})"
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
