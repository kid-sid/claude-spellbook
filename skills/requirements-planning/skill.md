---
name: requirements-planning
description: "Requirements planning: writing user stories with INVEST criteria, BDD acceptance criteria (Given/When/Then), PRD templates (Problem/Goals/Non-Goals/Requirements/Metrics), story pointing with Fibonacci scale, epic decomposition with vertical slicing, and Definition of Done templates."
---

# Requirements Planning

A complete reference for writing requirements that are clear, testable, and ready for development — from individual user stories to full PRDs.

## When to Activate

- Writing a PRD, one-pager, or product requirements document
- Creating user stories or acceptance criteria for a feature
- Story pointing or sprint planning
- Breaking down an epic into implementable tasks
- Defining Done criteria for a story or sprint
- Reviewing whether requirements are testable and complete

---

## User Stories

### INVEST Criteria

Every well-formed user story satisfies all six INVEST properties.

| Criteria     | Meaning                                              | Test question                                  |
|--------------|------------------------------------------------------|------------------------------------------------|
| Independent  | Can be developed without depending on another story  | "Can this be built and deployed alone?"        |
| Negotiable   | Details can be discussed, not a rigid contract       | "Is there flexibility in the how?"             |
| Valuable     | Delivers value to a user or stakeholder              | "Who benefits and how?"                        |
| Estimable    | Team can roughly size it                             | "Do we know enough to estimate?"               |
| Small        | Can be completed in one sprint                       | "Can one developer finish this in ≤5 days?"    |
| Testable     | Acceptance criteria can be verified                  | "How will we know it's done?"                  |

### Story Format

```
As a <role>,
I want to <action>,
so that <benefit>.
```

**BAD** — This is a task disguised as a story:
```
As a developer,
I want to implement the login endpoint,
so that the API exists.
```

**GOOD** — Clear role, action, and benefit:
```
As a returning user,
I want to log in with my email and password,
so that I can access my account and personal data.
```

### Common Anti-Patterns

- **Story is a task** — "Implement the login endpoint" describes technical work, not user value. Reframe around what the user can do.
- **No acceptance criteria** — Without AC, there is no shared definition of done. Write AC before any code is written.
- **Story spans multiple sprints** — If a story cannot be completed in a single sprint, split it using vertical slicing (see below).
- **Story says how instead of what** — Requirements describe the desired outcome, not the implementation. Leave the how to the team.
- **Passive voice hides the actor** — "Notifications should be sent" — by whom? to whom? Make the subject explicit.

---

## Acceptance Criteria

### BDD Format (Gherkin-style)

Use for behavioral, user-facing requirements. Each scenario maps to a test case.

```
Given <initial context>
When <action is taken>
Then <expected outcome>
And <additional outcome>  # optional
```

**Example — login story:**

```
Given a registered user with email "user@example.com"
When they submit valid credentials
Then they receive a JWT access token
And they are redirected to the dashboard

Given a registered user
When they submit an incorrect password 3 times
Then their account is locked for 30 minutes

Given a registered user whose account is locked
When they attempt to log in
Then they see the message "Account locked. Try again in 30 minutes."
```

### Checklist-Style AC

Use for non-behavioral or non-functional requirements where Given/When/Then does not fit naturally.

```
- [ ] Response time < 200ms at p95
- [ ] Works on Chrome, Firefox, Safari (last 2 versions)
- [ ] Error message shown for invalid input
- [ ] Form fields validated client-side before submission
```

### Functional vs Non-Functional AC

| Type          | Example                                          | Who writes it         |
|---------------|--------------------------------------------------|-----------------------|
| Functional    | "User can reset password via email link"         | PO / Dev together     |
| Performance   | "API responds in < 500ms"                        | Dev / SRE             |
| Security      | "Session expires after 30 min inactivity"        | Security / Dev        |
| Accessibility | "Form navigable by keyboard"                     | Designer / Dev        |

Non-functional requirements are frequently omitted. Make them explicit on every story where they apply.

---

## PRD Template

Use this template when writing a product requirements document, feature brief, or one-pager.

```markdown
# PRD: [Feature Name]

## Problem Statement
[1–2 sentences: what problem are we solving and for whom?]

## Goals
- Goal 1 (measurable)
- Goal 2

## Non-Goals
- Explicitly out of scope item 1
- Explicitly out of scope item 2

## User Personas
| Persona | Description | Primary need |
|---------|-------------|-------------|
| ...     | ...         | ...         |

## Functional Requirements
1. [REQ-001] The system shall...
2. [REQ-002] The system shall...

## Non-Functional Requirements
- Performance: [e.g., p95 latency < 300ms]
- Security: [e.g., data encrypted at rest]
- Scalability: [e.g., support 10k concurrent users]

## Out of Scope
- ...

## Open Questions
| Question | Owner | Due |
|----------|-------|-----|
| ...      | ...   | ... |

## Success Metrics
- Metric 1: [e.g., 20% increase in activation rate]
- Metric 2: [e.g., 0 P0 security incidents]

## Timeline
| Milestone | Date |
|-----------|------|
| ...       | ...  |
```

### PRD Writing Tips

- **Non-Goals are mandatory.** Explicitly stating what is out of scope prevents scope creep and misaligned expectations.
- **Every goal must be measurable.** "Improve performance" is not a goal. "Reduce p95 latency from 800ms to 300ms" is a goal.
- **Open questions block progress.** Assign every open question an owner and a deadline. Review at the next refinement session.
- **Success metrics connect to goals.** If you cannot measure whether a goal was achieved, the goal is not yet well-formed.

---

## Story Pointing

### Fibonacci Scale

Points are assigned from the sequence: **1, 2, 3, 5, 8, 13, 21** (and **∞** for "we cannot estimate this yet").

- Points measure **complexity + uncertainty**, NOT hours worked.
- A story pointed at 8 is roughly twice as complex and uncertain as a story pointed at 3.
- Calibration anchor: pick a well-understood story the team agrees is a **3**, then size all others relative to it.
- If a story is pointed at 13 or 21, strongly consider splitting it before the sprint.
- **∞** means the team lacks enough information to estimate — do discovery work before committing to the story.

### T-Shirt Sizing (Alternative)

Use **XS / S / M / L / XL** when:
- The team is new and has no calibration anchor.
- Estimating at the epic level rather than the story level.
- Rough relative sizing is sufficient (roadmap planning, not sprint planning).

Map to Fibonacci before sprint planning: XS → 1–2, S → 3, M → 5, L → 8, XL → 13+.

### Planning Poker Norms

- Everyone reveals their estimate **simultaneously** — avoids anchoring on a loud voice.
- **High variance** (e.g., one person says 3, another says 13) means the team has different assumptions. Discuss, do not average.
- After discussion, re-estimate if the spread was greater than 2 sizes.
- Keep the round time-boxed: aim to settle an estimate in under 5 minutes.

### What Affects Points

| Increases points                          | Does NOT affect points           |
|-------------------------------------------|----------------------------------|
| Technical complexity                      | Who will work on it              |
| Uncertainty / unknowns                    | Time of day or week              |
| Integration risk (third-party APIs, etc.) | Developer seniority or speed     |
| Testing surface area                      | Calendar deadline pressure       |
| Cross-team dependencies                   | Whether the work is boring or fun |

---

## Epic and Feature Decomposition

### Horizontal vs Vertical Slicing

| Approach   | Definition                                      | Example                                                           | Problem                          |
|------------|-------------------------------------------------|-------------------------------------------------------------------|----------------------------------|
| Horizontal | Split by technical layer                        | "Build the database schema", "Build the API", "Build the UI"      | Not independently valuable       |
| Vertical   | Split by user journey / thin feature slice      | "User can register with email (no profile picture yet)"           | None — preferred approach        |

Vertical slices are shippable. Each delivers some user value. Horizontal slices only deliver value when all layers are complete — meaning nothing is releasable until all layers are done.

### Walking Skeleton

1. Build the **thinnest possible end-to-end slice** first (e.g., login → dashboard with placeholder data).
2. This proves the architecture works before building width.
3. Subsequent stories add **depth** to each slice — more data, edge cases, polish.

The walking skeleton is never the full feature. It is the minimal path through the system.

### Decomposition Patterns

| Pattern              | Description                                           | Example                                                 |
|----------------------|-------------------------------------------------------|---------------------------------------------------------|
| By user role         | Different actors get separate stories                 | Admin story vs regular user story for the same screen   |
| By data volume       | Simple case first, then scale                         | "View first 10 items" → "View paginated list"           |
| By exception flow    | Happy path first, error paths separately              | "User logs in" → "User sees error on locked account"    |
| By CRUD operation    | Each operation is a separate story                    | Create → Read → Update → Delete as four stories         |
| By configuration     | Default behaviour first, then customization           | "Email sends with default template" → "Custom template" |

---

## Definition of Done

### Org-Level DoD (applies to all stories)

Copy this into your team's working agreement and adjust as needed.

```
- [ ] Code reviewed and approved (minimum 1 reviewer)
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] No new HIGH/CRITICAL security vulnerabilities introduced
- [ ] Feature deployed to staging and smoke-tested
- [ ] Acceptance criteria verified by PO or QA
- [ ] Documentation updated (if applicable)
- [ ] No unresolved review comments left open
```

### Story-Level DoD (specific to the story)

- Written by the team **during refinement**, before sprint start.
- Lives inside the story ticket as part of the acceptance criteria.
- Example for "User profile picture upload":
  ```
  - [ ] File size validated (max 5MB, reject otherwise with error message)
  - [ ] Uploaded file stored in S3 under /users/{id}/avatar
  - [ ] S3 URL saved to the users table (avatar_url column)
  - [ ] Profile page displays new avatar within 1 page reload
  - [ ] Old avatar deleted from S3 on successful replacement
  ```

### Sprint-Level DoD (applies to the sprint as a whole)

```
- [ ] All stories meeting org-level DoD are merged to main
- [ ] Release notes drafted
- [ ] Regression suite passing on staging
- [ ] PO has signed off on the sprint goal
```

---

## Checklist

- [ ] Every story follows the "As a / I want / so that" format
- [ ] Story satisfies all INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- [ ] Acceptance criteria are written before development starts
- [ ] BDD Given/When/Then used for behavioral requirements
- [ ] Non-functional requirements captured explicitly (performance, security, accessibility)
- [ ] Epic decomposed into vertical slices, not horizontal layers
- [ ] Story is sized (points or T-shirt) and team agrees on the estimate
- [ ] Definition of Done agreed upon before sprint starts
- [ ] Open questions in the PRD have owners and deadlines assigned
- [ ] Success metrics are defined, measurable, and tied to stated goals
