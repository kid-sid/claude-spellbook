---
name: general-temporal
description: Use when building or debugging Temporal workflows in Python — structuring workflows and activities, enforcing determinism, handling retries and timeouts, managing state across replays, or diagnosing workflow failures.
---

# Temporal Workflows — Python Patterns

Temporal is a durable execution engine. Every workflow step is recorded as an immutable event; if the worker crashes, Temporal replays history to resume exactly where it left off.

## When to Activate

- Structuring a new Temporal workflow and its activities
- Debugging non-determinism errors, replay failures, or signal issues
- Adding retries, timeouts, or error handling to activities
- Managing state across workflow turns without losing it on crash
- Implementing human-in-the-loop or long-running multi-step pipelines
- Writing or wiring a Temporal worker

---

## Core Concepts

### Event Sourcing / Replay

Temporal records every decision as an immutable event before executing it:

```
Event 1: WorkflowStarted
Event 2: ActivityScheduled  (fetch_data, url)
Event 3: ActivityCompleted  (fetch_data, url) → "result"
Event 4: SignalReceived      (approve)
Event 5: ActivityScheduled  (process_data, ...)
          ← worker crashes here
```

On restart, Temporal **replays** events 1–4. For completed activities it returns the recorded result — no real I/O. Execution resumes at Event 5 for real.

**Determinism rule:** Workflow code must produce the same decisions on every replay.
- ✅ Call activities for all I/O, random values, current time
- ❌ Never use `random`, `time.time()`, `datetime.now()`, `httpx`, or file reads in workflow code
- ❌ Never import I/O libraries at module level in workflow files

### Workflow vs Activity

| | Workflow | Activity |
|---|---|---|
| Purpose | Orchestration, decisions, state | Real I/O — HTTP, DB, LLM, file |
| I/O allowed | ❌ Must be deterministic | ✅ Unrestricted |
| Retried by Temporal | Workflow tasks retry on exception | Yes, via `RetryPolicy` |
| Current time | `workflow.now()` only | `datetime.now()` fine |

---

## Minimal Workflow

```python
# workflow.py
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from activities import fetch_data, process_data  # imported for type reference only


@workflow.defn
class MyWorkflow:

    @workflow.run
    async def run(self, url: str) -> str:
        # All I/O goes through execute_activity — never call directly
        raw = await workflow.execute_activity(
            fetch_data,
            url,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        result = await workflow.execute_activity(
            process_data,
            raw,
            start_to_close_timeout=timedelta(minutes=5),
        )

        return result
```

---

## Activities

Activities are the only place with real I/O. Keep them focused — one network call or DB operation per activity.

```python
# activities.py
import httpx
from temporalio import activity


@activity.defn
async def fetch_data(url: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()   # non-2xx → exception → Temporal retries
    return response.text


@activity.defn
async def process_data(raw: str) -> str:
    # CPU-bound or DB work here
    return raw.strip().upper()
```

**Activity design rules:**
- Accept and return JSON-serializable types (str, int, dict, list, Pydantic models)
- Raise exceptions freely — Temporal catches and retries per `RetryPolicy`
- Make activities **idempotent** — they may run more than once on retry
- Keep activities short — long-running ones need heartbeats

---

## Worker

```python
# run_worker.py
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from workflow import MyWorkflow
from activities import fetch_data, process_data


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="my-task-queue",
        workflows=[MyWorkflow],
        activities=[fetch_data, process_data],
    )

    print("Worker started")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Starting a Workflow

```python
# client.py
import asyncio
from temporalio.client import Client
from workflow import MyWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    # Start and wait for result
    result = await client.execute_workflow(
        MyWorkflow.run,
        "https://example.com/data",
        id="my-workflow-id-001",      # unique per workflow instance
        task_queue="my-task-queue",
    )
    print(result)

    # Start without waiting (fire and forget)
    handle = await client.start_workflow(
        MyWorkflow.run,
        "https://example.com/data",
        id="my-workflow-id-002",
        task_queue="my-task-queue",
    )
    # Later: result = await handle.result()


asyncio.run(main())
```

---

## Retries and Timeouts

```python
from datetime import timedelta
from temporalio.common import RetryPolicy

# Full retry config
result = await workflow.execute_activity(
    fetch_data,
    url,
    # How long one attempt can run
    start_to_close_timeout=timedelta(minutes=2),

    # How long all attempts combined can run
    schedule_to_close_timeout=timedelta(minutes=10),

    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),   # first retry after 1s
        backoff_coefficient=2.0,                  # doubles each retry
        maximum_interval=timedelta(seconds=30),   # cap at 30s
        maximum_attempts=5,                       # 5 total attempts, then raise
        non_retryable_error_types=["ValueError"], # don't retry these
    ),
)
```

| Timeout | Scope | Use for |
|---|---|---|
| `start_to_close_timeout` | Single attempt | Normal activity duration limit |
| `schedule_to_close_timeout` | All attempts | Hard deadline across all retries |
| `schedule_to_start_timeout` | Queue wait time | Detect stuck workers |

---

## Signals and Queries

```python
@workflow.defn
class ApprovalWorkflow:

    def __init__(self):
        self._approved = False
        self._status = "pending"

    @workflow.run
    async def run(self, item_id: str) -> str:
        # Block until approved (or timeout)
        await workflow.wait_condition(
            lambda: self._approved,
            timeout=timedelta(hours=24),   # give up after 24h
        )
        return await workflow.execute_activity(
            process_item, item_id,
            start_to_close_timeout=timedelta(minutes=5),
        )

    @workflow.signal
    async def approve(self) -> None:
        self._approved = True
        self._status = "approved"

    @workflow.signal
    async def reject(self, reason: str) -> None:
        self._status = f"rejected: {reason}"
        raise Exception(f"Rejected: {reason}")

    @workflow.query
    def status(self) -> str:
        return self._status


# Send a signal from a client
handle = client.get_workflow_handle("approval-workflow-id")
await handle.signal(ApprovalWorkflow.approve)

# Query current state without interrupting
status = await handle.query(ApprovalWorkflow.status)
```

---

## State Management

Workflows are stateful by design — instance variables persist across signals and replay.

```python
@workflow.defn
class BatchWorkflow:

    def __init__(self):
        self._results: list[str] = []
        self._errors: list[str] = []

    @workflow.run
    async def run(self, urls: list[str]) -> dict:
        for url in urls:
            try:
                result = await workflow.execute_activity(
                    fetch_data, url,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                self._results.append(result)
            except Exception as e:
                self._errors.append(f"{url}: {e}")

        return {"results": self._results, "errors": self._errors}
```

**For state that must survive worker replacement** (long-running workflows across deployments), persist it in an external store (Postgres, Redis) via an activity and reload it on startup.

```python
@workflow.run
async def run(self, workflow_id: str) -> str:
    # Load persisted state at the start of each run
    state = await workflow.execute_activity(
        load_state, workflow_id,
        start_to_close_timeout=timedelta(seconds=10),
    )
    # ... do work, update state via save_state activity ...
```

---

## Long-Running Activities (Heartbeats)

Activities that take longer than `start_to_close_timeout` must send heartbeats — otherwise Temporal assumes the worker is dead and retries.

```python
@activity.defn
async def process_large_file(file_path: str) -> str:
    lines = open(file_path).readlines()
    results = []

    for i, line in enumerate(lines):
        result = expensive_operation(line)
        results.append(result)

        # Heartbeat every 100 lines — keeps the activity alive
        if i % 100 == 0:
            activity.heartbeat(f"processed {i}/{len(lines)} lines")

    return "\n".join(results)


# In workflow — set heartbeat_timeout shorter than start_to_close_timeout
await workflow.execute_activity(
    process_large_file,
    file_path,
    start_to_close_timeout=timedelta(hours=1),
    heartbeat_timeout=timedelta(seconds=30),   # fail if no heartbeat in 30s
)
```

---

## Child Workflows

```python
from temporalio.workflow import ChildWorkflowHandle

@workflow.defn
class ParentWorkflow:

    @workflow.run
    async def run(self, items: list[str]) -> list[str]:
        # Launch child workflows concurrently
        handles: list[ChildWorkflowHandle] = []
        for item in items:
            handle = await workflow.start_child_workflow(
                ChildWorkflow.run,
                item,
                id=f"child-{item}",
                task_queue="my-task-queue",
            )
            handles.append(handle)

        # Wait for all to complete
        return list(await asyncio.gather(*[h.result() for h in handles]))
```

---

## Testing

```python
# test_workflow.py
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflow import MyWorkflow
from activities import fetch_data, process_data


@pytest.mark.asyncio
async def test_my_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MyWorkflow],
            activities=[fetch_data, process_data],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                "https://example.com",
                id="test-workflow-1",
                task_queue="test-queue",
            )
            assert result == "EXPECTED OUTPUT"


# Mock activities for unit testing the workflow logic
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_workflow_with_mocked_activities():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        mock_fetch = AsyncMock(return_value="raw data")
        mock_process = AsyncMock(return_value="processed")

        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MyWorkflow],
            activities=[mock_fetch, mock_process],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run, "https://example.com",
                id="test-2", task_queue="test-queue",
            )
            assert result == "processed"
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `workflow.NondeterminismError` | Workflow code changed after workflows started | Never change the order/type of `execute_activity` calls; version with `workflow.patched()` |
| `ActivityError` / `ApplicationError` | Activity raised after exhausting retries | Catch in workflow, notify user, continue or abort |
| Signal dropped | Workflow already completed when signal arrived | Send signals before the workflow finishes, or use `update` instead of `signal` |
| `schedule_to_start_timeout` exceeded | No workers polling the task queue | Start a worker on the same task queue |
| Activity runs twice | Worker crashed after activity completed but before Temporal recorded it | Make activities idempotent |

---

## Versioning (Safe Code Changes)

```python
# Use workflow.patched() to change workflow logic without breaking running workflows
@workflow.run
async def run(self, url: str) -> str:
    if workflow.patched("use-v2-processor"):
        # New code path — for workflows started after this deploy
        result = await workflow.execute_activity(
            process_data_v2, url,
            start_to_close_timeout=timedelta(minutes=5),
        )
    else:
        # Old code path — for workflows already in flight
        result = await workflow.execute_activity(
            process_data, url,
            start_to_close_timeout=timedelta(minutes=5),
        )
    return result
```

Once all pre-patch workflows complete, remove the `else` branch and the `patched()` call.

---

## Red Flags

- **I/O directly in workflow code** — `httpx`, database queries, or `open()` calls in a workflow function break determinism; on replay the call fires again and may return a different result, causing `NondeterminismError`; all I/O must live in activities
- **`random`, `time.time()`, or `datetime.now()` in a workflow** — these return different values on every replay; use `workflow.now()` for timestamps and route all randomness through activity return values
- **Activities that are not idempotent** — Temporal may run an activity more than once (crash between execution and recording); an activity that charges a card or sends an email twice on retry is dangerous; use idempotency keys or check-before-act patterns
- **Missing `start_to_close_timeout`** — omitting a timeout lets a hung activity block the workflow forever; always set both `start_to_close_timeout` and a `RetryPolicy`
- **Long-running activities without heartbeats** — Temporal assumes a silent activity is dead after `heartbeat_timeout`; any activity that runs longer than a few minutes must call `activity.heartbeat()` periodically
- **Changing activity call order after workflows are in flight** — adding, removing, or reordering `execute_activity` calls in a running workflow causes `NondeterminismError` on replay; use `workflow.patched()` to safely introduce new code paths
- **Using `asyncio.create_task` inside a workflow** — spawning raw tasks in workflow code bypasses Temporal's scheduler and breaks determinism; use child workflows or signals for concurrent branching

## Checklist

- [ ] All HTTP, DB, and I/O calls are in activities — zero I/O in workflow functions
- [ ] No `random`, `time.time()`, `datetime.now()`, or I/O imports at module level in workflow files
- [ ] Every `execute_activity` call has `start_to_close_timeout` and `RetryPolicy`
- [ ] Activities are idempotent — safe to run more than once
- [ ] Long-running activities call `activity.heartbeat()` and have `heartbeat_timeout` set
- [ ] `workflow.execute_activity` wrapped in `try/except` to handle exhausted retries gracefully
- [ ] Workflow ID is unique and deterministic per business entity (e.g. `f"order-{order_id}"`)
- [ ] Code changes to running workflows use `workflow.patched()` for safe versioning
- [ ] Tests use `WorkflowEnvironment.start_time_skipping()` to run timers instantly
- [ ] Worker registers all activity functions and workflow classes on the correct task queue
