---
name: ai-engineer
description: Production LLM application patterns covering RAG pipelines, vector search, agent orchestration, prompt engineering, multimodal AI, cost optimization, and AI safety for Python and TypeScript.
---

# AI Engineering

Patterns for building production-grade LLM applications, RAG systems, and intelligent agents.

## When to Activate

- Building or improving RAG systems, LLM features, or AI agent workflows
- Selecting models, vector databases, or embedding strategies
- Optimizing retrieval quality, latency, or inference cost
- Implementing AI safety guardrails, content moderation, or PII handling
- Integrating multimodal inputs (images, audio, documents) into AI pipelines
- Designing multi-agent coordination or agentic tool-use loops
- Setting up AI observability, evaluation, or A/B testing

## Model Selection

| Model | Best For | Relative Cost |
|-------|----------|---------------|
| `claude-opus-4-6` | Complex reasoning, architecture, research | High |
| `claude-sonnet-4-6` | Balanced coding, most development tasks | Medium |
| `claude-haiku-4-5` | Classification, extraction, high-volume tasks | Low |
| GPT-4o | OpenAI tool ecosystem, function calling | Medium-High |
| Llama 3.1 70B (local) | Air-gapped, cost-sensitive, no PII risk | None (infra cost) |

Default to Sonnet-class models for development. Use Haiku/mini variants for high-throughput steps. Reserve Opus/GPT-4o for reasoning-heavy tasks.

## RAG Architecture

### Chunking Strategy

```python
# BAD: Fixed-size splits break semantic units
text_splitter = CharacterTextSplitter(chunk_size=500)

# GOOD: Semantic chunking preserves context
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

| Strategy | Use When |
|----------|----------|
| Recursive character | General prose, code |
| Semantic (sentence-transformers) | Mixed-length documents |
| Document-structure aware | PDFs, HTML, Markdown |
| Sliding window | Dense technical content |

### Vector Database Selection

| DB | Hosted | Self-Hosted | Hybrid Search | Notes |
|----|--------|-------------|---------------|-------|
| Pinecone | Yes | No | Yes | Managed, serverless |
| Qdrant | Yes | Yes | Yes | Rust core, fast filtering |
| Weaviate | Yes | Yes | Yes | GraphQL API |
| pgvector | Via Supabase | Yes | With tsvector | Great if already on Postgres |
| Chroma | No | Yes | No | Local dev only |

### Hybrid Search (Vector + Keyword)

```python
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector, NamedSparseVector

# Dense vector (semantic) + sparse vector (BM25)
results = client.query_points(
    collection_name="docs",
    prefetch=[
        models.Prefetch(query=dense_embedding, using="dense", limit=20),
        models.Prefetch(query=SparseVector(indices=bm25_indices, values=bm25_values),
                        using="sparse", limit=20),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),  # Reciprocal Rank Fusion
    limit=10,
)
```

### Reranking

```python
# BAD: Return top-k by vector similarity alone
results = index.query(vector=embedding, top_k=5)

# GOOD: Over-fetch then rerank for precision
candidates = index.query(vector=embedding, top_k=20)

import cohere
co = cohere.Client()
reranked = co.rerank(
    model="rerank-english-v3.0",
    query=user_query,
    documents=[r.metadata["text"] for r in candidates.matches],
    top_n=5,
)
```

### RAG Pipeline Patterns

| Pattern | What It Solves |
|---------|---------------|
| HyDE (Hypothetical Document Embeddings) | Query/document embedding mismatch |
| RAG-Fusion | Single query too narrow — runs multiple query variants |
| Self-RAG | Model decides when retrieval is needed |
| GraphRAG | Multi-hop reasoning across connected entities |
| Contextual compression | Retrieved chunks too noisy; extract relevant spans only |

```python
# HyDE: generate a hypothetical answer, embed it, retrieve similar docs
hyde_prompt = f"Write a paragraph that would answer: {query}"
hypothetical_doc = llm.invoke(hyde_prompt)
hyde_embedding = embedder.embed(hypothetical_doc)
results = vector_store.similarity_search_by_vector(hyde_embedding)
```

## Agent Orchestration

### Agentic Loop (LangGraph)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    tool_calls_remaining: int

def agent_node(state: AgentState):
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def tool_node(state: AgentState):
    last_message = state["messages"][-1]
    results = execute_tools(last_message.tool_calls)
    return {"messages": results, "tool_calls_remaining": state["tool_calls_remaining"] - 1}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if not last.tool_calls or state["tool_calls_remaining"] <= 0:
        return END
    return "tools"

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.add_edge("tools", "agent")
graph.add_conditional_edges("agent", should_continue)
```

### Agent Memory Patterns

| Type | Storage | Use For |
|------|---------|---------|
| Short-term | In-memory messages list | Current conversation context |
| Long-term | Vector store + summary | Facts, preferences across sessions |
| Episodic | Structured DB | Past task outcomes |
| Procedural | Prompt / tool definitions | Skills, workflows |

```python
# Summarize + compress conversation memory
from langchain.memory import ConversationSummaryBufferMemory

memory = ConversationSummaryBufferMemory(
    llm=llm,
    max_token_limit=1000,  # summarize once buffer exceeds limit
    return_messages=True,
)
```

### Multi-Agent Pattern (CrewAI)

```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role="Senior Researcher",
    goal="Find accurate information",
    tools=[search_tool, browse_tool],
    llm=llm,
)
writer = Agent(
    role="Technical Writer",
    goal="Synthesize research into clear prose",
    llm=llm,
)

research_task = Task(description="Research {topic}", agent=researcher)
write_task = Task(description="Write a report based on research", agent=writer)

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task])
result = crew.kickoff(inputs={"topic": "vector databases"})
```

## Prompt Engineering

### Structured Output

```python
# TypeScript: Zod schema → structured output
import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import zodToJsonSchema from "zod-to-json-schema";

const ExtractedData = z.object({
  entities: z.array(z.object({ name: z.string(), type: z.string() })),
  summary: z.string(),
});

const response = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 1024,
  tools: [{
    name: "extract_data",
    description: "Extract structured data from text",
    input_schema: zodToJsonSchema(ExtractedData),
  }],
  tool_choice: { type: "tool", name: "extract_data" },
  messages: [{ role: "user", content: `Extract from: ${text}` }],
});
```

### Prompting Techniques

| Technique | When to Use |
|-----------|-------------|
| Chain-of-thought (`Think step by step`) | Multi-step reasoning, math, logic |
| Tree-of-thoughts | Exploring multiple solution paths |
| Self-consistency | Sample multiple outputs, majority vote |
| Few-shot examples | Consistent formatting, specialized tasks |
| Constitutional self-critique | Safety checks, tone alignment |

```python
# BAD: Vague instruction
"Summarize this document"

# GOOD: Structured, constrained prompt
"""Summarize the following document in exactly 3 bullet points.
Each bullet must start with a verb and be under 20 words.
Focus only on actionable findings.

Document:
{document}"""
```

## Production Patterns

### Semantic Caching

```python
from semantic_router.encoders import OpenAIEncoder
from semantic_router.layer import RouteLayer

# Cache responses for semantically similar queries
cache = RedisSemanticCache(
    redis_url="redis://localhost:6379",
    embedding=OpenAIEmbeddings(),
    score_threshold=0.95,  # cosine similarity threshold
)

@cache
def get_answer(query: str) -> str:
    return llm.invoke(query)
```

### Streaming with FastAPI

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import anthropic

app = FastAPI()
client = anthropic.Anthropic()

@app.post("/chat")
async def chat(query: str):
    async def generate():
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": query}],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Cost Controls

```python
# Estimate cost before execution
def estimate_cost(prompt: str, model: str = "claude-sonnet-4-6") -> float:
    input_tokens = len(prompt) // 4  # rough estimate
    # Sonnet 4.6: $3/M input, $15/M output
    return (input_tokens / 1_000_000) * 3.0

# Hard cap: reject if estimated cost exceeds threshold
if estimate_cost(prompt) > 0.10:
    raise ValueError("Prompt too large for single request — chunk it")
```

## AI Safety & Guardrails

### Prompt Injection Detection

```python
INJECTION_PATTERNS = [
    r"ignore (previous|above|all) instructions",
    r"you are now",
    r"disregard your",
    r"new persona",
    r"act as (if you are|a)?",
]

def detect_injection(user_input: str) -> bool:
    import re
    return any(re.search(p, user_input, re.IGNORECASE) for p in INJECTION_PATTERNS)

# Wrap all user inputs
if detect_injection(user_message):
    return {"error": "Input rejected"}
```

### PII Redaction

```python
import re

PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
    "phone": r"\b\+?1?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
}

def redact_pii(text: str) -> str:
    for label, pattern in PII_PATTERNS.items():
        text = re.sub(pattern, f"[{label.upper()}_REDACTED]", text)
    return text
```

### Content Moderation

```python
# Use OpenAI Moderation API as a pre-filter (free)
import openai

def is_safe(text: str) -> bool:
    result = openai.moderations.create(input=text)
    return not result.results[0].flagged

# Gate all user inputs
if not is_safe(user_message):
    return {"error": "Message violates content policy"}
```

## AI Observability

### LangSmith Tracing

```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "your-key"
os.environ["LANGCHAIN_PROJECT"] = "my-rag-app"

# All LangChain calls now auto-traced — no code changes needed
chain = prompt | llm | output_parser
result = chain.invoke({"query": user_query})
```

### Custom Metrics (Prometheus)

```python
from prometheus_client import Counter, Histogram

llm_requests = Counter("llm_requests_total", "Total LLM API calls", ["model", "status"])
llm_latency = Histogram("llm_latency_seconds", "LLM response latency", ["model"])
retrieval_score = Histogram("retrieval_relevance_score", "RAG retrieval scores")

with llm_latency.labels(model="claude-sonnet-4-6").time():
    response = client.messages.create(...)
llm_requests.labels(model="claude-sonnet-4-6", status="success").inc()
```

### RAG Evaluation

| Metric | Tool | Measures |
|--------|------|---------|
| Context Precision | RAGAS | Are retrieved chunks relevant? |
| Context Recall | RAGAS | Did retrieval miss needed chunks? |
| Answer Faithfulness | RAGAS | Does answer match retrieved context? |
| Answer Relevance | RAGAS | Does answer address the question? |

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

dataset = Dataset.from_dict({
    "question": questions,
    "answer": answers,
    "contexts": retrieved_contexts,
    "ground_truth": expected_answers,
})
scores = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
```

## Checklist

Before shipping an AI feature:

- [ ] Model pinned to specific version, not `latest`
- [ ] `max_tokens` set explicitly; generation budget validated against cost
- [ ] Prompt injection detection applied to all user-controlled inputs
- [ ] PII redaction runs before sending data to external models
- [ ] Content moderation gate in place for user-facing endpoints
- [ ] Retrieval quality measured (context precision/recall via RAGAS or equivalent)
- [ ] Semantic caching enabled for repeated or near-duplicate queries
- [ ] Streaming used for responses >200 tokens to avoid client timeouts
- [ ] Retry with exponential backoff on rate-limit and transient errors
- [ ] LLM calls traced (LangSmith, Phoenix, or custom spans)
- [ ] Latency and token-usage metrics emitted to monitoring stack
- [ ] Fallback model or graceful degradation path defined
- [ ] Chunking strategy validated on representative documents
- [ ] Reranker in place if retrieval corpus exceeds 10K chunks

> See also: `claude-api`, `observability`, `security`
