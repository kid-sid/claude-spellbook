---
name: temporal
description: Use when building or debugging the Agentex ADK temporal agent type — structuring workflows and activities, handling signal routing, managing state across replays, or diagnosing workflow failures and retry exhaustion. For standalone Temporal workers outside of Agentex, use general-temporal.
---

# Temporal Workflows (Agentex)

Temporal is the durability layer for async Agentex agents. Every step is recorded as an immutable event; if the worker crashes, Temporal replays history to resume exactly where it left off.

## When to Activate

- Building or editing a Temporal-based agent (`manifest.yaml` has `temporal.enabled: true`)
- Debugging workflow failures, retries, or signal handling
- Adding activities or custom I/O to an existing workflow
- Questions about failure recovery, event replay, or state persistence
- Implementing the state machine pattern inside a workflow

---

## Project File Reading Order

Read in this order to build a complete mental model of any agent:

1. `manifest.yaml` — agent name, workflow name, queue name, env vars
2. `project/models.py` — state shape stored in MongoDB between turns
3. `project/activities.py` — real I/O (HTTP, DB, file); the only place non-deterministic work lives
4. `project/acp.py` — 5-line config wiring ACP → Temporal (no handlers needed here)
5. `project/workflow.py` — `on_task_create` (startup) + `on_task_event_send` (each user turn)
6. `project/run_worker.py` — wires activities + workflow + starts the worker process

---

## Core Concepts

### Event Sourcing / Replay

Temporal records every decision as an immutable event before executing it:

```
Event 1: WorkflowStarted
Event 2: ActivityScheduled  (scrape_url, url1)
Event 3: ActivityCompleted  (scrape_url, url1) → "scraped text"
Event 4: SignalReceived      (RECEIVE_EVENT)
Event 5: ActivityScheduled  (scrape_url, url2)
          ← worker crashes here
```

On restart, Temporal **replays** events 1–4. For completed activities it returns the recorded result (no real I/O). Execution resumes at Event 5 for real.

**Determinism rule:** Workflow code must produce the same decisions on every replay.
- ✅ Call activities for all I/O, random values, current time
- ❌ Never use `random`, `time.time()`, `httpx`, file reads directly in workflow code
- ❌ Never `import` I/O libraries at module level inside workflow files — use `workflow.unsafe.imports_passed_through()` if unavoidable

### Workflow vs Activity

| | Workflow | Activity |
|---|---|---|
| Purpose | Orchestration logic, state decisions | Real I/O (HTTP, DB, LLM calls) |
| I/O allowed | ❌ No — must be deterministic | ✅ Yes |
| Retried by Temporal | Workflow tasks retried on exception | Yes, via `RetryPolicy` |
| Runs in | Worker process (sandboxed) | Worker process (unrestricted) |

---

## ACP Entry Point (`acp.py`)

For Temporal agents, `acp.py` is just configuration. No handlers are registered manually — Temporal routes everything automatically.

```python
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.types.fastacp import TemporalACPConfig

acp = FastACP.create(
    acp_type="async",
    config=TemporalACPConfig(
        type="temporal",
        temporal_address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
    ),
)
```

ACP → Temporal mapping:

| ACP RPC call | Temporal action |
|---|---|
| `task/create` | Starts a new workflow execution |
| `event/send` | Sends `RECEIVE_EVENT` signal to the running workflow |
| `task/cancel` | Cancels the workflow execution directly |

---

## Workflow Structure (`workflow.py`)

All Temporal agents extend `BaseWorkflow`. Two methods to implement:

```python
from typing import override
from temporalio import workflow
from agentex.lib.core.temporal.types.workflow import SignalName
from agentex.lib.core.temporal.workflows.workflow import BaseWorkflow
from agentex.lib.environment_variables import EnvironmentVariables
from agentex.lib.types.acp import CreateTaskParams, SendEventParams

environment_variables = EnvironmentVariables.refresh()

@workflow.defn(name=environment_variables.WORKFLOW_NAME)
class MyWorkflow(BaseWorkflow):

    def __init__(self):
        super().__init__(display_name="My Agent")
        self._done = False  # set True to exit; usually stays False (cancelled externally)

    @workflow.run
    @override
    async def on_task_create(self, params: CreateTaskParams) -> None:
        # Called ONCE when the task is created.
        # Initialize state, send opening message, then block.
        await adk.state.create(task_id=params.task.id, agent_id=params.agent.id, state=MyState.initial())
        await adk.messages.create(task_id=params.task.id, content=TextContent(author="agent", content="Ready!"))
        await workflow.wait_condition(lambda: self._done)  # keeps workflow alive

    @workflow.signal(name=SignalName.RECEIVE_EVENT)
    @override
    async def on_task_event_send(self, params: SendEventParams) -> None:
        # Called on EVERY user message. Runs as a Temporal signal handler.
        # All logic for responding to user input lives here.
        ...
```

**`wait_condition` is mandatory** in `on_task_create`. Without it the workflow exits immediately after startup and can no longer receive signals.

---

## Activities (`activities.py`)

Activities are the only place with real I/O. Group them in a class, register the bound instance in `run_worker.py`.

```python
import httpx
from pydantic import BaseModel
from temporalio import activity

SCRAPE_URL_ACTIVITY = "scrape_url"  # string name must match workflow.execute_activity() call

class ScrapeURLParams(BaseModel):
    url: str  # serialized to JSON by Temporal when dispatching to the worker

class ScraperActivities:
    @activity.defn(name=SCRAPE_URL_ACTIVITY)
    async def scrape_url(self, params: ScrapeURLParams) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(params.url)
            response.raise_for_status()  # non-2xx → exception → Temporal retries
        return response.text[:8000]
```

**Calling an activity from the workflow:**

```python
from datetime import timedelta
from temporalio.common import RetryPolicy

result: str = await workflow.execute_activity(
    SCRAPE_URL_ACTIVITY,
    ScrapeURLParams(url=url),
    start_to_close_timeout=timedelta(minutes=2),  # must finish within this window
    retry_policy=RetryPolicy(maximum_attempts=2),  # 2 total attempts before raising
)
```

---

## State Management

State is a Pydantic model stored in MongoDB, keyed by `(task_id, agent_id)`. Load → mutate in-memory → save.

```python
# models.py
from agentex.lib.utils.model_utils import BaseModel

class MyState(BaseModel):
    turn: int = 0
    pending_urls: list[str] = []

    @classmethod
    def initial(cls) -> "MyState":
        return cls()
```

```python
# Inside on_task_create
await adk.state.create(task_id=task_id, agent_id=agent_id, state=MyState.initial())

# Inside on_task_event_send
task_state = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)
state = MyState.model_validate(task_state.state)   # deserialize

state.turn += 1                                     # mutate in-memory

await adk.state.update(                             # persist
    state_id=task_state.id,
    task_id=task_id,
    agent_id=agent_id,
    state=state,
)
```

**Important:** `adk.state.update` inside a workflow executes as a Temporal activity. If the worker crashes before it runs, MongoDB retains the old state and the replay re-runs the handler from scratch using the old state — no corruption occurs.

---

## Worker Entry Point (`run_worker.py`)

```python
import asyncio
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from agentex.lib.core.temporal.activities import get_all_activities
from agentex.lib.core.temporal.workers.worker import AgentexWorker
from agentex.lib.environment_variables import EnvironmentVariables

from project.activities import ScraperActivities
from project.workflow import MyWorkflow

env = EnvironmentVariables.refresh()

async def main():
    scraper = ScraperActivities()
    worker = AgentexWorker(task_queue=env.WORKFLOW_TASK_QUEUE, health_check_port=8084)
    await worker.run(
        activities=[*get_all_activities(), scraper.scrape_url],
        workflow=MyWorkflow,
    )

if __name__ == "__main__":
    asyncio.run(main())
```

- `get_all_activities()` — built-in ADK activities (messages, state, tracing). Must always be included.
- `ScraperActivities()` — instantiated here so `scraper.scrape_url` is a bound method.
- `WORKFLOW_TASK_QUEUE` — injected by `agentex agents run` from `manifest.yaml` (`agent.temporal.workflows[0].queue_name`).

---

## Environment Variables

Never set manually for normal runs — `agentex agents run --manifest manifest.yaml` injects them from `manifest.yaml`:

| Env var | Source in manifest |
|---|---|
| `WORKFLOW_NAME` | `agent.temporal.workflows[0].name` |
| `WORKFLOW_TASK_QUEUE` | `agent.temporal.workflows[0].queue_name` |
| `AGENT_NAME` | `agent.name` |
| `OPENAI_API_KEY` etc. | `agent.env.*` |

A `project/.env` file is only needed when running `acp.py` or `run_worker.py` **directly** without the CLI.

---

## Failure Handling

### What Temporal handles automatically

| Failure | Temporal behaviour |
|---|---|
| Worker process crash | Replays event history on next available worker; resumes from last checkpoint |
| Activity timeout | Retries per `RetryPolicy`; raises `ActivityError` into workflow after max attempts |
| Workflow task exception | Retries the workflow task; workflow moves to FAILED after repeated failures |

### What the code must handle explicitly

**Activity failure (after all retries):** wrap `workflow.execute_activity` in `try/except`:

```python
try:
    page_text = await workflow.execute_activity(
        SCRAPE_URL_ACTIVITY, ScrapeURLParams(url=u),
        start_to_close_timeout=timedelta(minutes=2),
        retry_policy=RetryPolicy(maximum_attempts=2),
    )
    scraped_pages.append((u, page_text))
except Exception as e:
    await adk.messages.create(task_id=task_id,
        content=TextContent(author="agent", content=f"Failed to scrape `{u}`: {e}"))
    # continue loop — one bad URL doesn't abort the batch
```

**State load failure** (MongoDB down): unhandled → workflow FAILED:

```python
try:
    task_state = await adk.state.get_by_task_and_agent(task_id=task_id, agent_id=agent_id)
    state = MyState.model_validate(task_state.state)
except Exception as e:
    await adk.messages.create(task_id=task_id,
        content=TextContent(author="agent", content=f"Failed to load state: {e}. Try again."))
    return
```

**LLM call failure** (OpenAI/litellm down): unhandled → workflow FAILED:

```python
try:
    chat_completion = await adk.providers.litellm.chat_completion(llm_config=..., trace_id=task_id)
except Exception as e:
    await adk.messages.create(task_id=task_id,
        content=TextContent(author="agent", content=f"Summarization failed: {e}. Please resend URLs."))
    await adk.state.update(state_id=task_state.id, task_id=task_id, agent_id=agent_id, state=state)
    return
```

**Failure handling pattern:**

- Wrap `workflow.execute_activity` in `try/except` — continue or message user on failure
- Wrap `adk.state.get_by_task_and_agent` — return early and message user on failure
- Wrap `adk.providers.litellm.chat_completion` — save state before returning on failure
- Save state before every `return` so the next signal loads clean data

---

## State Machine Pattern

For workflows with multiple distinct phases, use `agentex.lib.sdk.state_machine`:

```python
from agentex.lib.sdk.state_machine.state import State

self.state_machine = MyStateMachine(
    initial_state=MyPhase.WAITING,
    states=[
        State(name=MyPhase.WAITING,    workflow=WaitingWorkflow()),
        State(name=MyPhase.PROCESSING, workflow=ProcessingWorkflow()),
        State(name=MyPhase.DONE,       workflow=DoneWorkflow()),
    ],
    state_machine_data=MyData(),
    trace_transitions=True,
)

# In on_task_create:
await self.state_machine.run()

# In on_task_event_send — trigger transitions:
await self.state_machine.transition(MyPhase.PROCESSING)
```

See `state_machine/project/` in the repo for a full deep-research example.

---

## ADK Providers

```python
from agentex.lib import adk
from agentex.lib.types.llm_messages import LLMConfig, SystemMessage, UserMessage

# Non-streaming LLM call (litellm)
result = await adk.providers.litellm.chat_completion(
    llm_config=LLMConfig(
        model="gpt-4o-mini",
        messages=[SystemMessage(content="You are helpful."), UserMessage(content="Summarize this.")],
    ),
    trace_id=task_id,
)
summary = result.choices[0].message.content or ""

# Streaming LLM — auto-sends chunks to the UI
await adk.providers.litellm.chat_completion_stream_auto_send(
    task_id=task_id,
    llm_config=LLMConfig(model="gpt-4o-mini", messages=messages, stream=True),
    trace_id=task_id,
)

# OpenAI Agents SDK (with tools + MCP)
run_result = await adk.providers.openai.run_agent_streamed_auto_send(
    task_id=task_id,
    trace_id=task_id,
    input_list=conversation_history,
    tools=[MY_FUNCTION_TOOL],
    agent_name="Assistant",
    agent_instructions="You are helpful.",
    model="gpt-4o-mini",
)
final_history = run_result.final_input_list  # updated conversation for next turn
```

---

## Tracing

```python
# Span as context manager (auto-closes)
async with adk.tracing.span(trace_id=task_id, name="Turn 1", input=state) as span:
    await adk.messages.create(..., trace_id=task_id, parent_span_id=span.id)
    result = await adk.providers.litellm.chat_completion(..., trace_id=task_id)
    span.output = result

# Manual span (must call end() yourself)
span = await adk.tracing.start_span(trace_id=task_id, name="Turn 1", input={...})
# ... work ...
await adk.tracing.end_span(span_id=span.id, output={...})
```

---

## Running Locally

```bash
# From the agent directory (e.g. url-summarizer-temporal/)
export ENVIRONMENT=development
agentex agents run --manifest manifest.yaml

# Debug mode — attach VS Code debugger on port 5679
agentex agents run --manifest manifest.yaml --debug-worker --debug-port 5679
```

Temporal UI (inspect workflow history, signals, failures): <http://localhost:8080>

---

## Red Flags

- **I/O directly in workflow code** — `httpx`, database queries, or LLM calls in a workflow function break determinism; on replay Temporal returns the recorded result instead of re-executing, so the actual network call never happens and the code path diverges; all I/O must be in activities
- **`random`, `time.time()`, or `datetime.now()` in a workflow** — these return different values on every replay, causing divergence; use `workflow.now()` for timestamps and pass randomness through activity return values
- **`on_task_create` without `await workflow.wait_condition(lambda: self._done)`** — without this the workflow function returns immediately after startup, the workflow execution completes, and all subsequent `RECEIVE_EVENT` signals are dropped because there is no running workflow to receive them
- **`workflow.execute_activity` without `try/except`** — when an activity exhausts its retry policy Temporal raises `ActivityError` into the workflow; unhandled, this puts the workflow into FAILED state and the user never receives an error message; always catch and notify
- **Not saving state before `return` in a signal handler** — returning from `on_task_event_send` without calling `adk.state.update` leaves MongoDB with the state from the previous turn; the next signal handler loads stale data and the agent loses its context
- **Not including `get_all_activities()` in `run_worker.py`** — ADK built-in activities handle `adk.messages`, `adk.state`, and tracing; omitting them causes every `adk.*` call to fail at runtime with "activity not registered on this worker"
- **Importing I/O libraries at module level in workflow files** — Temporal's sandbox isolates workflow execution; `import httpx` at the top of a workflow file either fails in sandboxed mode or subtly breaks determinism; use `workflow.unsafe.imports_passed_through()` if you must import, or move the import into the activity file

## Checklist

- [ ] Workflow code has zero I/O — all HTTP, DB, and LLM calls are in activities
- [ ] No `random`, `time.time()`, or I/O imports at module level in workflow files
- [ ] `on_task_create` ends with `await workflow.wait_condition(lambda: self._done)`
- [ ] Activities use `@activity.defn(name=CONSTANT)` with string constant matching `execute_activity()` call
- [ ] `start_to_close_timeout` and `retry_policy` set on every `execute_activity` call
- [ ] `workflow.execute_activity` wrapped in `try/except` to handle exhausted retries
- [ ] `adk.state.get_by_task_and_agent` wrapped — unhandled exception → workflow FAILED
- [ ] `adk.providers.litellm.chat_completion` wrapped — state saved before returning on failure
- [ ] State saved before every `return` inside signal handlers so next signal loads clean data
- [ ] `get_all_activities()` included alongside custom activities in `run_worker.py`
- [ ] `WORKFLOW_NAME` and `WORKFLOW_TASK_QUEUE` are injected by the CLI — not set manually
