Generate an Architecture Decision Record (ADR) from a discussion or decision.

## Instructions

1. Ask the user (if not already specified):
   - **Decision title**: short summary of the architectural decision
   - **Context**: what problem or requirement prompted this decision?
   - **Options considered**: what alternatives were evaluated?

2. Generate the ADR using this format:

```markdown
# ADR-{NUMBER}: {Title}

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date:** {YYYY-MM-DD}
**Deciders:** {names or roles}

## Context

{What is the issue that we're seeing that is motivating this decision or change?}

## Decision Drivers

- {driver 1: e.g., scalability requirement}
- {driver 2: e.g., team expertise}
- {driver 3: e.g., time constraint}

## Options Considered

### Option 1: {Name}

{Description}

**Pros:**
- {pro}

**Cons:**
- {con}

### Option 2: {Name}

{Description}

**Pros:**
- {pro}

**Cons:**
- {con}

### Option 3: {Name}

{Description}

**Pros:**
- {pro}

**Cons:**
- {con}

## Decision

{Which option was chosen and why. Be specific about the reasoning.}

## Consequences

### Positive
- {positive consequence}

### Negative
- {negative consequence}

### Neutral
- {neutral consequence}

## Follow-up Actions

- [ ] {action item 1}
- [ ] {action item 2}
```

3. Number the ADR:
   - Check `docs/adr/` or `docs/decisions/` for existing ADRs
   - Use the next sequential number (e.g., ADR-0005)
   - If no ADR directory exists, create `docs/adr/` and start at ADR-0001

4. Save the file as `docs/adr/{NUMBER}-{kebab-case-title}.md`

5. Update `docs/adr/README.md` (create if needed) with a table of all ADRs:
   ```
   | ADR | Title | Status | Date |
   |-----|-------|--------|------|
   ```

## Output
- The generated ADR file
- Updated ADR index
- Suggestion to share with the team for review before marking as "Accepted"
