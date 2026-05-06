---
name: langgraph
description: Use when building or debugging LangGraph workflows — designing state graphs, adding conditional routing, wiring checkpointers, streaming tokens, implementing human-in-the-loop interrupts, or coordinating multi-agent subgraphs.
---

# LangGraph Patterns

LangGraph builds stateful multi-step LLM workflows as directed graphs. Each node is a Python function; edges define routing between them.

## When to Activate

- Building a multi-step LLM pipeline (research → draft → review → publish)
- Implementing human-in-the-loop interrupts or approval steps
- Designing conditional routing based on LLM output
- Adding persistence/memory to an agent across sessions
- Streaming intermediate results to the client
- Coordinating multiple agents as subgraphs
- Debugging `InvalidUpdateError`, cycle errors, or state shape issues

---

## Core Concepts

```
StateGraph
├── State        — TypedDict that flows through every node
├── Nodes        — functions: State → State update (partial dict)
├── Edges        — unconditional routing A → B
├── Conditional  — function decides which node to go to next
└── Checkpointer — persists state between invocations (memory)
```

---

## Minimal Example

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI

# 1. Define state — Annotated[list, add_messages] appends instead of replacing
class State(TypedDict):
    messages: Annotated[list, add_messages]

llm = ChatOpenAI(model="gpt-4o-mini")

# 2. Define a node — receives full state, returns partial update
def chatbot(state: State) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

# 3. Build the graph
graph = (
    StateGraph(State)
    .add_node("chatbot", chatbot)
    .add_edge(START, "chatbot")
    .add_edge("chatbot", END)
    .compile()
)

# 4. Invoke
result = graph.invoke({"messages": [{"role": "user", "content": "Hello!"}]})
print(result["messages"][-1].content)
```

---

## State Design

```python
from typing import TypedDict, Annotated
from operator import add

# Annotated reducers control how values merge on update
class ResearchState(TypedDict):
    # add_messages: appends new messages, deduplicates by ID
    messages: Annotated[list, add_messages]

    # add (operator.add): appends items from each node update
    sources: Annotated[list[str], add]

    # Last-write-wins (default — no annotation needed)
    query: str
    status: str
    final_report: str | None

    # Optional fields
    error: str | None
```

**Key rule:** Nodes return a **partial dict** — only include keys you want to update. LangGraph merges with the existing state using the reducer.

```python
# Node returns partial — only updates 'status' and 'sources'
def fetch_sources(state: ResearchState) -> dict:
    sources = search_web(state["query"])
    return {
        "sources": sources,      # add reducer: appends
        "status": "sources_ready",
    }
```

---

## Conditional Routing

```python
from langgraph.graph import StateGraph, START, END

def route_after_llm(state: State) -> str:
    """Return the name of the next node (or END)."""
    last_message = state["messages"][-1]

    # If the LLM called a tool, go to tools node
    if last_message.tool_calls:
        return "tools"

    # Otherwise finish
    return END

graph = StateGraph(State)
graph.add_node("llm", call_llm)
graph.add_node("tools", run_tools)

graph.add_edge(START, "llm")
graph.add_conditional_edges(
    "llm",              # source node
    route_after_llm,    # routing function → returns node name
    {                   # optional: map return values to node names
        "tools": "tools",
        END: END,
    },
)
graph.add_edge("tools", "llm")   # loop back after tools
```

### Multiple possible routes

```python
def classify_query(state: State) -> str:
    query = state["query"].lower()
    if "code" in query:   return "code_agent"
    if "math" in query:   return "math_agent"
    return "general_agent"

graph.add_conditional_edges(
    "classifier",
    classify_query,
    ["code_agent", "math_agent", "general_agent"],  # all possible targets
)
```

---

## Tool Calling

```python
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

@tool
def search_web(query: str) -> str:
    """Search the web for current information."""
    return web_search_api(query)

@tool
def calculator(expression: str) -> float:
    """Evaluate a mathematical expression."""
    return eval(expression)  # use safer eval in production

tools = [search_web, calculator]
tool_node = ToolNode(tools)              # pre-built node that runs tools

llm_with_tools = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

def call_llm(state: State) -> dict:
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

def should_continue(state: State) -> str:
    return "tools" if state["messages"][-1].tool_calls else END

graph = StateGraph(State)
graph.add_node("llm", call_llm)
graph.add_node("tools", tool_node)
graph.add_edge(START, "llm")
graph.add_conditional_edges("llm", should_continue)
graph.add_edge("tools", "llm")
```

---

## Persistence (Checkpointers)

Checkpointers save state after every node so the graph can be paused, resumed, or continued in a new session.

```python
from langgraph.checkpoint.memory import MemorySaver       # in-process (dev/test)
from langgraph.checkpoint.postgres import PostgresSaver    # production

# In-memory checkpointer
memory = MemorySaver()
graph = StateGraph(State).compile(checkpointer=memory)

# PostgreSQL checkpointer
import psycopg
conn = psycopg.connect("postgresql://user:pass@localhost/db")
checkpointer = PostgresSaver(conn)
graph = StateGraph(State).compile(checkpointer=checkpointer)

# thread_id groups messages into a "conversation" — same ID = same history
config = {"configurable": {"thread_id": "user-123-session-1"}}

# First call — creates new thread
result = graph.invoke({"messages": [HumanMessage("Hello")]}, config=config)

# Second call — continues the same thread
result = graph.invoke({"messages": [HumanMessage("Follow up")]}, config=config)

# Get current state of a thread
snapshot = graph.get_state(config)
print(snapshot.values)        # current state
print(snapshot.next)          # next node to run (empty if finished)
```

---

## Human-in-the-Loop (Interrupts)

```python
from langgraph.types import interrupt, Command

# interrupt() pauses the graph and surfaces a value to the caller
def approval_step(state: State) -> dict:
    # This raises an interrupt — graph pauses here
    human_response = interrupt({
        "question": "Should I proceed?",
        "context": state["draft"],
    })
    # Execution resumes here when resumed with a Command
    if human_response == "yes":
        return {"status": "approved"}
    return {"status": "rejected"}

graph = StateGraph(State).compile(
    checkpointer=memory,
    interrupt_before=["approval_step"],   # pause BEFORE this node
    # interrupt_after=["draft"],          # pause AFTER this node
)

# First invocation — runs until interrupt
result = graph.invoke(input, config=config)
# result contains the interrupt value

# Resume after human provides input
result = graph.invoke(
    Command(resume="yes"),   # pass human decision
    config=config,
)
```

---

## Streaming

```python
# stream_mode options:
# "values"  — full state after each node
# "updates" — partial state update from each node
# "messages"— LLM token-by-token streaming

# Stream full state values
for state in graph.stream(input, config=config, stream_mode="values"):
    print(state)

# Stream node updates only
for chunk in graph.stream(input, config=config, stream_mode="updates"):
    node_name, update = list(chunk.items())[0]
    print(f"Node '{node_name}' updated: {update}")

# Stream LLM tokens (best for chat UI)
async for chunk in graph.astream(input, config=config, stream_mode="messages"):
    if hasattr(chunk, "content"):
        print(chunk.content, end="", flush=True)

# Async streaming in FastAPI
@router.get("/chat/stream")
async def stream_chat(query: str):
    async def generate():
        async for chunk in graph.astream(
            {"messages": [HumanMessage(query)]},
            stream_mode="messages",
        ):
            if hasattr(chunk, "content") and chunk.content:
                yield f"data: {chunk.content}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Subgraphs (Multi-Agent)

```python
# Define a specialised sub-agent as its own graph
researcher = (
    StateGraph(ResearchState)
    .add_node("search", search_web)
    .add_node("summarize", summarize)
    .add_edge(START, "search")
    .add_edge("search", "summarize")
    .add_edge("summarize", END)
    .compile()
)

writer = (
    StateGraph(WriterState)
    .add_node("draft", draft_content)
    .add_node("refine", refine_draft)
    .compile()
)

# Orchestrator graph uses sub-agents as nodes
def run_researcher(state: OrchestratorState) -> dict:
    result = researcher.invoke({"query": state["topic"]})
    return {"research": result["summary"]}

orchestrator = (
    StateGraph(OrchestratorState)
    .add_node("research", run_researcher)
    .add_node("write",    run_writer)
    .add_edge(START, "research")
    .add_edge("research", "write")
    .add_edge("write", END)
    .compile(checkpointer=memory)
)
```

---

## Agentex Integration

In Agentex Temporal agents, LangGraph runs inside a Temporal activity (not directly in the workflow). The ADK provides helpers:

```python
from agentex.lib import adk

# In an activity:
async def run_langgraph_agent(params: AgentParams) -> str:
    graph = build_my_graph()

    # stream_langgraph_events sends each token/update to the Agentex UI
    async for event in adk.stream_langgraph_events(
        graph=graph,
        inputs={"messages": [HumanMessage(params.user_message)]},
        task_id=params.task_id,
    ):
        pass

    return final_result

# Checkpointer backed by Agentex state (MongoDB) for persistence
checkpointer = adk.create_checkpointer(task_id=params.task_id)
graph = build_my_graph().compile(checkpointer=checkpointer)
```

---

## Debugging

```python
# Print the graph structure
print(graph.get_graph().draw_ascii())

# Print state at each step
for step in graph.stream(input, stream_mode="values"):
    print("---")
    for k, v in step.items():
        print(f"  {k}: {v}")

# Inspect checkpointed history
history = list(graph.get_state_history(config))
for snapshot in history:
    print(snapshot.values, snapshot.next, snapshot.created_at)

# Replay from a specific checkpoint
graph.invoke(None, config={**config, "checkpoint_id": old_checkpoint_id})
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `InvalidUpdateError` | Node returned a key not in State TypedDict | Add the key to State or remove from return |
| `GraphRecursionError` | Cycle with no termination condition | Add conditional edge → END when done |
| State not persisting | No checkpointer compiled | Add `checkpointer=memory` to `.compile()` |
| Interrupt not working | Missing checkpointer | Interrupts require a checkpointer |
| `add_messages` duplicating | Returning same message ID twice | Return new messages only; don't re-include history |

---

## Red Flags

- **Returning full state from a node** — returning the entire state dict instead of a partial update overwrites all fields and breaks reducers; nodes must return only the keys they changed
- **Cycles with no exit condition** — a loop between two nodes with no conditional edge to `END` causes `GraphRecursionError`; always add a conditional edge that can reach `END`
- **`MemorySaver` in production** — in-process memory is lost on worker restart; use `PostgresSaver` (or another persistent backend) for any deployed graph
- **Non-deterministic code in node functions** — calling `time.time()`, `random`, or direct HTTP requests inside nodes makes replay unpredictable in LangGraph Cloud and Temporal-hosted graphs; use activity patterns for side effects
- **Missing `thread_id` or reusing it across unrelated sessions** — reusing a `thread_id` continues an old conversation; always generate a unique ID per session and pass it in the config's `configurable` dict
- **Human-in-the-loop without a checkpointer** — `interrupt()` silently does nothing if the graph was compiled without a checkpointer; interrupts require `checkpointer=` in `.compile()`
- **Accessing relationship fields across incompatible subgraph state types** — parent and subgraph states must have compatible shapes; passing keys the subgraph doesn't declare in its `TypedDict` causes `InvalidUpdateError`
- **`add_messages` on a field that isn't a message list** — annotating a plain list of strings with `add_messages` deduplicates by message ID and discards entries without one; use `operator.add` for plain list fields

## Checklist

- [ ] State is a `TypedDict` with explicit reducers (`add_messages`, `add`) for list fields
- [ ] Nodes return partial dicts — only updated keys
- [ ] All cycles have a conditional edge that can route to `END`
- [ ] Tools defined with `@tool` decorator and bound to LLM with `.bind_tools()`
- [ ] Production graphs use `PostgresSaver` (not `MemorySaver`)
- [ ] `thread_id` in config is unique per conversation/session
- [ ] Human-in-the-loop graphs always compiled with a checkpointer
- [ ] Streaming uses `astream` for async contexts
