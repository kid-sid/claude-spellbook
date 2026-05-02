---
name: agentex
description: Agentex platform patterns — agent types (sync/async/temporal), ACP protocol, local development on Windows, architecture, and common gotchas.
---

# Agentex Platform

Agentex is a platform for building and deploying intelligent agents. The repo has two main parts:
- `agentex/` — FastAPI backend + Temporal workflows (runs in Docker)
- `agentex-ui/` — Next.js frontend (runs locally)

Agents are built with the `agentex-sdk` CLI and run as separate processes that register with the backend.

---

## Agent Types

### Sync ACP
One message in, one response out. Stateless.

```python
acp = FastACP.create(acp_type="sync")

@acp.on_message_send
async def handle(params: SendMessageParams) -> TaskMessageContent:
    return TextContent(author="agent", content="reply")
```

**Use when:** FAQ bots, translation, data lookups, single-turn interactions.

### Async ACP (base)
Task lifecycle with persistent state across multiple turns.

```python
acp = FastACP.create(acp_type="async", config=AsyncACPConfig(type="base"))

@acp.on_task_create   # called once — initialize state
@acp.on_task_event_send  # called per message — respond via adk.messages.create
@acp.on_task_cancel   # called on cancel — cleanup
```

Key difference from sync: responses are **pushed** via `adk.messages.create`, not returned.
State is persisted via `adk.state.create / get_by_task_and_agent / update`.

**Use when:** multi-turn conversations, stateful workflows, streaming LLM responses.
**Warning:** race conditions if parallel events arrive — use Temporal for production.

### Async ACP + Temporal
Same as Async but every step is a durable Temporal workflow. Survives crashes and restarts.

```yaml
# manifest.yaml
agent:
  acp_type: async
  temporal:
    enabled: true
```

**Use when:** production agents, long-running tasks, human-in-the-loop, complex multi-step tool chains.

---

## ACP State Pattern (Async)

```python
class MyState(BaseModel):
    turn: int
    messages: List[Message]

# Create on task init
await adk.state.create(task_id=..., agent_id=..., state=MyState(...))

# Read on each event
task_state = await adk.state.get_by_task_and_agent(task_id=..., agent_id=...)
state = MyState.model_validate(task_state.state)

# Write back after mutating
await adk.state.update(state_id=task_state.id, task_id=..., agent_id=..., state=state)
```

---

## Sending Messages (Async)

```python
# Echo user message back (so it shows in UI)
await adk.messages.create(task_id=params.task.id, content=params.event.content)

# Send agent reply
await adk.messages.create(
    task_id=params.task.id,
    content=TextContent(author="agent", content="response text"),
)

# Streaming LLM (auto-sends chunks to UI)
await adk.providers.litellm.chat_completion_stream_auto_send(
    task_id=params.task.id,
    llm_config=LLMConfig(model="gpt-4o-mini", messages=state.messages, stream=True),
)
```

---

## manifest.yaml Structure

```yaml
local_development:
  agent:
    port: 8000          # must be unique per agent (8000, 8001, 8002...)
    host_address: host.docker.internal
  paths:
    acp: project/acp.py

agent:
  name: my-agent        # unique name, shown in UI
  acp_type: sync        # or async
  temporal:
    enabled: false
  credentials: []
  env: {}
```

---

## Backend Architecture

```
src/
├── api/routes/         # FastAPI endpoints
├── domain/entities/    # Pure Pydantic models
├── domain/use_cases/   # Business logic
├── adapters/crud_store/ # DB adapters (Postgres + MongoDB)
├── adapters/streams/   # Redis SSE streams
└── config/dependencies.py  # Singleton GlobalDependencies
```

**Layer rules:**
- Domain layer has zero framework imports
- API layer → use cases → domain ← adapters
- ORM ↔ domain conversion via explicit converter functions — never skip layers

**Exceptions:**
- `ClientError` → 400, `ServiceError` → 500, `ItemDoesNotExist` → 404

---

## Windows-Specific Gotchas

| Problem | Fix |
|---|---|
| `uv sync` fails: platform not compatible | Add `"sys_platform == 'win32'"` to `environments` in root `pyproject.toml`, then `uv lock` |
| `load_dotenv(override=True)` clobbers Docker env vars | Change to `override=False` in `environment_variables.py` |
| Local PostgreSQL on port 5432 blocks Docker | Change Docker postgres port to `5434:5432` in `docker-compose.yml` |
| `agentex init` Unicode error | Set `$env:PYTHONUTF8 = "1"` before running |
| `agentex init` path has `\n` in it | Type short relative name (`my-agent`), not a full path |
| `source .venv/bin/activate` fails | Use `.venv\Scripts\Activate.ps1` on Windows |
| Temporal worker connects to `localhost` inside Docker | Caused by `.env` overriding Docker network hostnames — needs `override=False` |

---

## Ports

| Port | Service |
|---|---|
| 3000 | Frontend UI |
| 5003 | FastAPI backend (Swagger at /swagger) |
| 5432 | Local PostgreSQL (if installed) |
| 5434 | Docker agentex-postgres (remapped to avoid conflict) |
| 5433 | Docker Temporal PostgreSQL |
| 6379 | Redis |
| 7233 | Temporal server |
| 8080 | Temporal UI |
| 8000+ | Agent ACP servers (one port per agent) |
| 27017 | MongoDB |

---

## Key Environment Variables (agentex/.env)

```env
ENVIRONMENT=development
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5434/agentex
TEMPORAL_ADDRESS=localhost:7233
REDIS_URL=redis://localhost:6379
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE_NAME=agentex
AGENTEX_SERVER_TASK_QUEUE=agentex-server
ALLOWED_ORIGINS=http://localhost:3000
ENABLE_HEALTH_CHECK_WORKFLOW=true
```

---

## Running Tests

```powershell
cd agentex
# Unit tests (no Docker needed)
.\build.ps1 test-unit

# Integration tests (needs Docker infra running)
.\build.ps1 test-integration

# Specific file
.\build.ps1 test -File tests/unit/test_foo.py
```
