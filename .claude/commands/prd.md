Generate a Product Requirements Document (PRD) pre-filled from context.

## Instructions

1. Ask the user (if not already specified):
   - **Feature/product name**: what is being built?
   - **Problem statement**: what user pain point does this solve?
   - **Target users**: who is this for?

2. Generate the PRD using this template:

```markdown
# PRD: {Feature/Product Name}

**Author:** {name}
**Date:** {YYYY-MM-DD}
**Status:** Draft | In Review | Approved
**Priority:** P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low)

## 1. Problem Statement

{What problem are we solving? Why does it matter? Include data/evidence if available.}

## 2. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| {goal 1} | {metric} | {target value} |
| {goal 2} | {metric} | {target value} |

### Non-Goals (Explicit Exclusions)
- {thing we are deliberately NOT doing and why}

## 3. User Stories

### Primary Persona: {name/role}
- As a {role}, I want to {action} so that {benefit}
- As a {role}, I want to {action} so that {benefit}

### Secondary Persona: {name/role}
- As a {role}, I want to {action} so that {benefit}

## 4. Functional Requirements

### Must Have (P0)
- [ ] {requirement}
- [ ] {requirement}

### Should Have (P1)
- [ ] {requirement}

### Nice to Have (P2)
- [ ] {requirement}

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|------------|
| Performance | {e.g., API response < 200ms at p99} |
| Scalability | {e.g., support 10K concurrent users} |
| Security | {e.g., SOC2 compliant, encrypted at rest} |
| Availability | {e.g., 99.9% uptime SLA} |
| Accessibility | {e.g., WCAG 2.1 AA compliant} |

## 6. User Flow

{Describe the primary user flow step by step, or include a diagram reference}

1. User {action}
2. System {response}
3. User {action}
4. System {response}

## 7. Technical Considerations

### Dependencies
- {external service or team dependency}

### Risks & Mitigations
| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| {risk} | High/Med/Low | High/Med/Low | {mitigation} |

### Open Questions
- [ ] {question that needs resolution}

## 8. Timeline & Milestones

| Milestone | Target Date | Description |
|-----------|------------|-------------|
| Design Complete | {date} | {description} |
| MVP / Alpha | {date} | {description} |
| Beta | {date} | {description} |
| GA | {date} | {description} |

## 9. Appendix

### Related Documents
- {link to design doc}
- {link to ADR}
- {link to competitive analysis}
```

3. Pre-fill sections by:
   - Reading the codebase to understand existing architecture
   - Checking git history for related work
   - Inferring technical constraints from the stack

4. Save the file to `docs/prd/{kebab-case-name}.md` (create directory if needed).

## Output
- The generated PRD file
- A list of sections that need human input (marked with `{placeholders}`)
- Suggested next steps (design review, technical scoping, etc.)
