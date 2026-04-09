Analyze code for smells and suggest or apply refactoring with examples.

## Instructions

1. Read the target file or directory the user specifies.
2. Detect the language and analyze the code for these smell categories:

### Code Smells to Detect

**Size & Complexity:**
- Functions longer than 30 lines
- Classes with more than 10 methods (God Class)
- Cyclomatic complexity > 10
- Deep nesting (> 3 levels)
- Long parameter lists (> 4 parameters)

**Duplication & Coupling:**
- Duplicate or near-duplicate code blocks
- Shotgun surgery (one change requires editing many files)
- Feature envy (method uses another class's data more than its own)
- Inappropriate intimacy (classes that know too much about each other)

**Naming & Clarity:**
- Unclear variable/function names
- Magic numbers without named constants
- Boolean parameters (use named options/enums instead)
- Comments explaining "what" instead of code being self-documenting

**Design:**
- Primitive obsession (using primitives instead of small value objects)
- Data clumps (groups of data that always appear together)
- Switch statements that should be polymorphism
- Refused bequest (subclass doesn't use parent's methods)
- Speculative generality (unused abstractions)

**SOLID Violations:**
- Single Responsibility: class/function doing too many things
- Open/Closed: modification required instead of extension
- Liskov Substitution: subtypes not substitutable for base types
- Interface Segregation: forced to depend on unused methods
- Dependency Inversion: high-level modules depending on low-level details

3. For each smell found, provide:
   - **Location**: file:line
   - **Smell**: name of the code smell
   - **Severity**: Low / Medium / High
   - **Current code**: the problematic snippet
   - **Refactored code**: the improved version
   - **Technique**: name of the refactoring pattern applied (e.g., Extract Method, Replace Conditional with Polymorphism, Introduce Parameter Object)

4. Output format:

```
## Refactoring Report
**File(s):** {paths}
**Language:** {language}
**Issues found:** {count}

### High Priority

#### 1. {Smell Name} — {file:line}
**Technique:** {refactoring pattern}

Before:
```{lang}
{original code}
```

After:
```{lang}
{refactored code}
```

**Why:** {explanation of the improvement}

---

### Medium Priority
{same format}

### Low Priority
{same format}

## Summary
- {count} issues found across {severity levels}
- Estimated improvement: {what gets better — readability, testability, maintainability}
- Suggested order: {which refactors to do first}
```

5. If the user asks to apply the refactoring (not just analyze):
   - Apply changes one smell at a time
   - Run tests after each change to verify nothing breaks
   - Commit each refactoring separately with descriptive messages

6. If no significant smells found, say so — don't invent problems.

## Output
- Structured refactoring report with before/after code examples
- Prioritized list of improvements
- Option to auto-apply the suggested changes
