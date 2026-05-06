---
name: promptbase
description: Use when writing, reviewing, or adapting a Claude Code skill for sale on PromptBase — checking scope, audience breadth, rejection risk, description quality, examples, and setup instructions.
---

# PromptBase Skill Publishing

Patterns for writing Claude Code skills that pass PromptBase review and sell well.

## When to Activate

- Writing a new skill intended for sale on PromptBase
- Reviewing an existing skill before submission
- Adapting a rejected skill after a "too specific" or "too simple" ruling
- Writing listing copy — title, description, examples, setup instructions
- Deciding whether a skill idea is worth submitting at all

---

## The Core Test: Would a Stranger Pay For This?

Before writing a single line, answer three questions:

| Question | Green light | Red light |
|---|---|---|
| Who is the buyer? | Any Python/TS/Go developer | Users of one specific internal platform |
| What problem does it solve? | A hard, non-obvious problem they hit often | Something a quick search answers |
| Could they reproduce it from the title alone? | No — the value is in the patterns | Yes — the title explains everything |

If any answer is red, fix the concept before writing the skill.

---

## Rejection Reasons and Fixes

### Too Specific (most common rejection)

**What it means:** The skill only works for users of a niche platform, private SDK, or internal framework. The audience is too small to justify listing it.

**Signs your skill is too specific:**
- It imports from a private package (`from mycompany.lib import ...`)
- It references internal tool names, ports, config files, or env vars no outsider would know
- It combines more than 3 niche ideas (e.g. "LangGraph + Agentex + custom state machine")
- The target framework has fewer than ~5k GitHub stars

**Fix: generalize the layer**

```
REJECTED:  Temporal + Agentex ADK + adk.state + adk.messages + FastACP
APPROVED:  Temporal + Python temporalio SDK — standard patterns any developer can use
```

Strip the platform-specific layer. Keep the hard, transferable patterns underneath.

---

### Too Simple / Guessable

**What it means:** A buyer could recreate the skill by reading the title and thinking for 30 seconds. The value isn't there.

**Signs your skill is too simple:**
- The entire skill is one pattern or one code snippet
- It documents official defaults (e.g. "how to create a FastAPI route")
- It has no decision tables, no red flags, no non-obvious gotchas
- Word count is low AND there are no patterns that require explanation

**Fix: add depth**
- Add a decision table (when to use X vs Y)
- Add a Red Flags section (7–10 anti-patterns with explanations)
- Add the non-obvious gotchas — things that only experience teaches
- Add a pre-ship checklist

---

### No Use Case

**What it means:** The skill has no practical application for real work — it's a demo, experiment, or overly academic topic.

**Fix:** Anchor every section to a real scenario a working developer would face. If you can't name a concrete task the skill helps complete, the concept needs rethinking.

---

## Scope Rules

| Scope | Verdict | Notes |
|---|---|---|
| Standard open-source framework (FastAPI, Redis, Temporal) | ✅ Good | Broad audience |
| Cloud provider service (AWS S3, Azure Blob) | ✅ Good | Large user base |
| Niche but popular tool (LangGraph, Pydantic v2) | ✅ OK | Active community |
| Combination of 2 standard tools | ✅ OK | Keep each section useful standalone |
| Combination of 3+ niche tools | ⚠️ Risk | May be rejected as too specific |
| Private/internal SDK or platform | ❌ Reject | Useless to outsiders |
| Single well-known function/pattern | ❌ Reject | Too simple |

**The 3-niche rule:** PromptBase rejects skills that combine more than 3 niche ideas. A "niche idea" is any tool, pattern, or concept that a developer might not already know. Standard Python, SQL, and REST are not niche. LangGraph, Temporal, and a custom state machine pattern together are three niche ideas — borderline.

---

## Writing the Listing

### Title

```
# BAD — platform-specific, tiny audience
Agentex Temporal Agent Skill

# BAD — too vague, no value signal
Python Async Skill

# GOOD — specific problem, broad audience
Crash-Proof AI Agents: Temporal Workflow Skill for Claude Code
```

Formula: `[Outcome the buyer wants]: [Technology] Skill for Claude Code`

### Description (keep it under 100 words)

Structure:
1. One sentence on the problem it solves
2. 4–6 bullet points on what Claude knows after activation
3. One line on format and installation

```markdown
Your Temporal workflows break in ways that are invisible until production.
This skill teaches Claude the patterns that prevent it.

- Workflow vs activity split and determinism rules
- Retry policies, timeouts, and heartbeats
- State management across replays
- Signal handling and `wait_condition`
- 7 red flags that silently break Temporal agents

One `.md` file. Drop in `~/.claude/skills/` — activates automatically.
```

### When to Use (activation description)

Write this as a single sentence starting with "Use when" that describes triggering conditions — not a summary of topics:

```
# BAD — topic summary, not a trigger
Use when working with Temporal, workflows, activities, signals, and state.

# GOOD — triggering condition
Use when building or debugging Temporal workflows in Python — structuring
activities, enforcing determinism, handling retries, or diagnosing replay failures.
```

### Examples (2 required)

Each example is a realistic user message + a sample Claude response showing the skill in action.

**Example 1 (shown as preview on store page):** Pick the sharpest, most impressive demo — the problem that would make a buyer think "I need this right now."

**Example 2:** Show a different use case from Example 1. Don't demonstrate the same pattern twice.

```
# BAD example pair — same pattern twice
Example 1: "How do I add a retry to my activity?"
Example 2: "How do I set a timeout on my activity?"

# GOOD example pair — different concerns
Example 1: "My workflow stops receiving signals after the first message."
Example 2: "Can I call httpx directly inside my workflow?"
```

### Setup Instructions

Keep it to 3 steps maximum:

```markdown
1. Download `skill.md`
2. Place it at `~/.claude/skills/<skill-name>/skill.md`
3. Restart Claude Code

No MCP servers, env vars, or dependencies required.
```

If the skill requires external tools (MCP server, API key), list them explicitly. Buyers who can't set up the skill will leave bad reviews.

### Skill Body (the SKILL.md content)

PromptBase asks for the body only — everything after the YAML frontmatter. The frontmatter is generated on their end. Paste starting from the first `#` heading.

---

## Pre-Submission Checklist

- [ ] Skill uses only publicly available, open-source tools — no private SDKs
- [ ] Topic is not reproducible from the title alone — real value is in the patterns
- [ ] Combines at most 3 niche ideas
- [ ] Has at least one decision/comparison table
- [ ] Has a `## Red Flags` section with 6–10 domain-specific anti-patterns
- [ ] Has a `## Checklist` section with 8–12 pre-ship items
- [ ] Title follows `[Outcome]: [Tech] Skill for Claude Code` formula
- [ ] Description is under 100 words and leads with the problem
- [ ] `description` frontmatter starts with "Use when" and describes trigger conditions only
- [ ] Two examples show different use cases, not the same pattern twice
- [ ] Setup instructions have 3 steps or fewer
- [ ] Skill body pasted without frontmatter (PromptBase generates it)
- [ ] No references to internal systems, private repos, or proprietary env vars

## Red Flags

- **Private SDK imports in examples** — any `from yourcompany.internal import ...` immediately signals the skill is platform-locked; reviewers reject these without reading further; replace with the standard open-source equivalent
- **Title that gives away the entire skill** — if the title is "Use `retry_policy=RetryPolicy(maximum_attempts=3)` in Temporal", a buyer can reproduce it without purchasing; titles should name the outcome, not the solution
- **Description longer than 150 words** — PromptBase listing descriptions overflow on mobile and store pages; buyers skim; if you need 200 words the concept isn't focused enough
- **Examples that demonstrate the same pattern** — two examples showing retry configuration are one example, not two; reviewers flag this as low variety; each example must address a distinct concern
- **Setup instructions that require a paid API key or private access** — buyers who hit a wall during setup leave negative reviews; if the skill requires external services, state it prominently in the listing before purchase
- **"Use when" description that summarizes topics instead of triggers** — "Use when working with Redis, caching, pub/sub, and streams" is a topic list; "Use when choosing a Redis data structure, implementing rate limiting, or debugging slow commands" is a trigger list; only triggers activate the skill correctly
- **Submitting a skill that is a thin wrapper around official docs** — if every pattern in the skill appears verbatim in the framework's own documentation, it adds no value; the skill must contain non-obvious patterns, gotchas, and decisions that experience teaches
