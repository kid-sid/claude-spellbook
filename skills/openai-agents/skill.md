---
name: openai-agents
description: Use when building or debugging OpenAI Agents SDK workflows — defining agents with tools and handoffs, wiring typed context, streaming responses, adding guardrails, or integrating with the Agentex ADK.
---

# OpenAI Agents SDK Patterns

The OpenAI Agents SDK (`openai-agents`) orchestrates LLM agents with tools, handoffs, and tracing.

## When to Activate

- Defining agents with system prompts, tools, and handoffs
- Writing `@function_tool` decorators and tool schemas
- Running agents with `Runner.run()` or streaming with `Runner.run_streamed()`
- Implementing multi-agent handoffs (triage → specialist)
- Debugging tool call errors, context leaks, or infinite loops
- Integrating with Agentex ADK via `adk.providers.openai`
- Adding tracing spans for observability

---

## Core Concepts

```
Agent
├── name, instructions (system prompt)
├── tools     — functions the agent can call
├── handoffs  — other agents it can delegate to
├── model     — LLM to use (default: gpt-4o)
└── output_type — structured Pydantic output (optional)

Runner
├── .run()          — async, returns final output
├── .run_streamed() — async generator, streams events
└── .run_sync()     — sync wrapper (testing/scripts)
```

---

## Minimal Agent

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"It's sunny and 72°F in {city}."

agent = Agent(
    name="Weather Agent",
    instructions="You help users check weather. Always use the get_weather tool.",
    tools=[get_weather],
    model="gpt-4o-mini",
)

# Run
result = await Runner.run(agent, "What's the weather in Tokyo?")
print(result.final_output)
```

---

## Defining Tools

```python
from agents import function_tool
from pydantic import BaseModel

# Simple tool — docstring becomes the tool description
@function_tool
def search_web(query: str) -> str:
    """Search the web for current information. Returns the top results."""
    return web_search_api(query)

# Tool with multiple typed params
@function_tool
def calculate(expression: str, precision: int = 2) -> str:
    """Evaluate a mathematical expression and return the result."""
    result = eval(expression)  # use ast.literal_eval or a math parser in production
    return str(round(result, precision))

# Tool returning structured data
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str

@function_tool
def search_docs(query: str, limit: int = 5) -> list[SearchResult]:
    """Search the documentation. Returns matching articles."""
    return [SearchResult(...) for r in docs_search(query, limit)]

# Async tool
@function_tool
async def fetch_user(user_id: str) -> dict:
    """Fetch user profile from the database."""
    user = await db.get_user(user_id)
    return user.model_dump()
```

**Tool naming:** the function name becomes the tool name. Keep names short and action-oriented (`search_web`, not `search_the_web_for_information`).

---

## Context (passing data to tools without LLM)

```python
from agents import Agent, Runner, RunContextWrapper, function_tool
from dataclasses import dataclass

@dataclass
class AppContext:
    user_id: str
    db_session: AsyncSession

# Tools receive context as first param (not exposed to LLM)
@function_tool
async def get_my_orders(ctx: RunContextWrapper[AppContext]) -> list[dict]:
    """Get the current user's orders."""
    orders = await OrderCRUD(ctx.context.db_session).list_for_user(ctx.context.user_id)
    return [o.model_dump() for o in orders]

agent = Agent[AppContext](
    name="Order Agent",
    instructions="Help users check their orders.",
    tools=[get_my_orders],
)

context = AppContext(user_id="u-123", db_session=session)
result = await Runner.run(agent, "Show my recent orders", context=context)
```

---

## Structured Output

```python
from pydantic import BaseModel
from agents import Agent, Runner

class EmailDraft(BaseModel):
    subject: str
    body: str
    tone: Literal["formal", "casual", "urgent"]

agent = Agent(
    name="Email Writer",
    instructions="Draft professional emails based on user requests.",
    output_type=EmailDraft,   # forces structured JSON response
)

result = await Runner.run(agent, "Write a follow-up email for a job interview")
email: EmailDraft = result.final_output   # typed, validated by Pydantic
print(email.subject)
```

---

## Handoffs (Multi-Agent)

Handoffs let one agent delegate to another specialized agent. The triage agent decides which specialist handles the task.

```python
from agents import Agent, handoff, Runner

coding_agent = Agent(
    name="Coding Assistant",
    instructions="You solve programming problems. Write clean, working code.",
    tools=[search_docs, run_code],
)

writing_agent = Agent(
    name="Writing Assistant",
    instructions="You help with writing, editing, and proofreading.",
)

triage_agent = Agent(
    name="Triage",
    instructions="""Route the user to the right specialist:
    - For code/programming questions → coding_assistant
    - For writing/editing requests → writing_assistant
    - Handle simple questions yourself.""",
    handoffs=[coding_agent, writing_agent],
)

result = await Runner.run(triage_agent, "Fix this Python bug: ...")
# triage_agent may hand off to coding_agent, which runs to completion
print(result.final_output)
```

**Customizing handoff behavior:**
```python
from agents import handoff

def on_handoff_to_billing(ctx: RunContextWrapper[AppContext]):
    # Called when handoff happens — log, update state, etc.
    logger.info(f"Handing off to billing for user {ctx.context.user_id}")

billing_agent = Agent(name="Billing", instructions="...")

triage_agent = Agent(
    handoffs=[
        handoff(billing_agent, on_handoff=on_handoff_to_billing),
    ]
)
```

---

## Streaming

```python
from agents import Runner
from agents.stream_events import RunItemStreamEvent, AgentUpdatedStreamEvent

async def stream_agent(agent, prompt: str):
    stream = Runner.run_streamed(agent, prompt)
    async for event in stream.stream_events():
        if isinstance(event, RunItemStreamEvent):
            # Each completed item (tool call, tool result, message)
            item = event.item
            if hasattr(item, "raw_item"):
                raw = item.raw_item
                if raw.get("type") == "response.output_text.delta":
                    print(raw["delta"], end="", flush=True)

    return await stream.get_final_output()

# FastAPI SSE endpoint
@router.get("/stream")
async def stream_response(prompt: str):
    async def generate():
        stream = Runner.run_streamed(agent, prompt)
        async for event in stream.stream_events():
            if isinstance(event, RunItemStreamEvent):
                item = event.item
                if hasattr(item, "raw_item"):
                    delta = item.raw_item.get("delta", "")
                    if delta:
                        yield f"data: {delta}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Guardrails

Guardrails validate input/output before the agent processes or responds.

```python
from agents import Agent, input_guardrail, output_guardrail, GuardrailFunctionOutput

@input_guardrail
async def no_pii(ctx, agent, input) -> GuardrailFunctionOutput:
    text = input if isinstance(input, str) else str(input)
    if contains_pii(text):
        return GuardrailFunctionOutput(
            output_info="PII detected",
            tripwire_triggered=True,    # stops the agent
        )
    return GuardrailFunctionOutput(output_info="clean", tripwire_triggered=False)

@output_guardrail
async def no_harmful_content(ctx, agent, output) -> GuardrailFunctionOutput:
    if is_harmful(str(output)):
        return GuardrailFunctionOutput(
            output_info="harmful content",
            tripwire_triggered=True,
        )
    return GuardrailFunctionOutput(output_info="safe", tripwire_triggered=False)

agent = Agent(
    name="Safe Agent",
    instructions="...",
    input_guardrails=[no_pii],
    output_guardrails=[no_harmful_content],
)
```

---

## Tracing

```python
from agents import Agent, Runner
from agents.tracing import trace, custom_span

# Runner automatically creates a root trace
result = await Runner.run(agent, "Hello", run_config=RunConfig(
    trace_id="my-trace-123",        # link to your own tracing system
    trace_metadata={"user_id": "u-123"},
))

# Add custom spans inside tools
@function_tool
async def complex_search(query: str) -> str:
    """Search across multiple sources."""
    with custom_span("db_search"):
        db_results = await db.search(query)
    with custom_span("web_search"):
        web_results = await web.search(query)
    return combine(db_results, web_results)
```

---

## Agentex ADK Integration

In Agentex Temporal agents, use `adk.providers.openai` instead of calling `Runner` directly — it handles message streaming to the UI automatically.

```python
from agentex.lib import adk
from agents import Agent, function_tool

@function_tool
async def search_web(query: str) -> str:
    """Search the web for information."""
    return await web_search(query)

agent = Agent(
    name="Research Agent",
    instructions="Research topics thoroughly using web search.",
    tools=[search_web],
    model="gpt-4o",
)

# In a Temporal activity:
async def run_research_agent(params: AgentParams) -> str:
    result = await adk.providers.openai.run_agent_streamed_auto_send(
        agent=agent,
        task_id=params.task_id,
        input=params.user_message,
        # context=AppContext(...)  if using typed context
    )
    return result.final_output

# run_agent_streamed_auto_send:
# - streams each token to the Agentex UI via adk.messages
# - wraps Runner.run_streamed internally
# - handles tracing integration
```

---

## RunConfig Options

```python
from agents import RunConfig

result = await Runner.run(
    agent,
    "Hello",
    run_config=RunConfig(
        model="gpt-4o",                    # override agent's model
        model_settings=ModelSettings(
            temperature=0.2,
            max_tokens=2000,
        ),
        max_turns=10,                       # prevent infinite agent loops
        trace_id="req-abc-123",
        workflow_name="my-workflow",        # appears in traces
    ),
)
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `MaxTurnsExceeded` | Agent looping (tool → agent → tool) | Set `max_turns`, check for circular handoffs |
| Tool not called | Weak system prompt | Be explicit: "You MUST use X tool to answer" |
| Wrong handoff | Ambiguous triage instructions | List exact conditions for each handoff |
| `ValidationError` in tool | Pydantic type mismatch in return | Ensure return type matches annotation |
| Context `None` in tool | Forgot to pass `context=` to Runner | Pass `context=your_context` in `Runner.run()` |

---

## Red Flags

- **No `max_turns` set** — without a turn limit an agent that calls a tool whose result triggers another tool call can loop indefinitely; always pass `RunConfig(max_turns=N)` to cap runaway execution
- **Passing app state (DB session, user ID) through the LLM** — including session objects or sensitive IDs in the prompt or tool return values exposes them to the model and wastes tokens; use typed `context` (`RunContextWrapper`) so tools receive state without the LLM ever seeing it
- **Vague tool docstrings** — the docstring is the only description the LLM sees; "Does stuff with the database" gives the model no signal on when to call it; write one sentence that says exactly what the tool returns and when to use it
- **Vague handoff instructions in the triage agent** — "Route to the right agent" with no criteria leads to random or wrong handoffs; list the exact conditions for each handoff in the triage agent's instructions
- **Using `Runner.run()` directly inside an Agentex activity** — `Runner.run()` doesn't stream tokens to the Agentex UI; use `adk.providers.openai.run_agent_streamed_auto_send()` which wraps `Runner.run_streamed()` and handles token delivery automatically
- **No input/output guardrails on user-facing agents** — agents that handle user-supplied text without guardrails can be prompted to leak context, call wrong tools, or produce harmful output; add `@input_guardrail` and `@output_guardrail` for sensitive deployments
- **Tool names that are long or vague** — the model uses the tool name as a primary signal; `search_the_web_for_current_information` is worse than `search_web`; keep tool names short, lowercase, and verb-noun

## Checklist

- [ ] Tool docstrings are clear — they become the LLM-facing description
- [ ] Context used for app state (DB session, user ID) — not passed through LLM
- [ ] `output_type` set for structured outputs — avoids parsing LLM text
- [ ] `max_turns` set to prevent runaway agent loops
- [ ] Handoff instructions are specific — vague routing leads to wrong agent
- [ ] `run_agent_streamed_auto_send` used in Agentex activities (not `Runner` directly)
- [ ] Guardrails added for user-facing agents handling sensitive data
- [ ] Tool names are short verb-noun: `get_user`, `search_docs`, `send_email`
